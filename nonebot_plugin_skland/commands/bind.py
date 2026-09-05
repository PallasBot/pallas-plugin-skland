"""绑定相关命令"""

import asyncio
import ipaddress
from io import BytesIO
from urllib.parse import urlsplit
from datetime import datetime, timedelta

import httpx
import qrcode
from nonebot_plugin_waiter import prompt
from nonebot_plugin_user import UserSession
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_alconna import Match, Arparma, MsgTarget, UniMessage
from PIL import Image, ImageOps, ImageDraw, ImageFilter, UnidentifiedImageError

from ..model import SkUser
from ..schemas import CRED
from ..player_data import ark_card_data
from ..exception import RequestException
from ..api import SklandAPI, SklandLoginAPI
from ..utils import send_reaction, get_characters_and_bind
from ..db_handler import delete_user, delete_characters, delete_user_all_gacha_records

_AVATAR_MAX_BYTES = 2 * 1024 * 1024
_AVATAR_MAX_PIXELS = 4_000_000

_BIND_GUIDE_LINK = "https://docs.qq.com/doc/p/2f705965caafb3ef342d4a979811ff3960bb3c17"


def _is_supported_avatar_url(avatar_url: str) -> bool:
    try:
        parsed = urlsplit(avatar_url)
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return address.is_global


async def _fetch_user_avatar(avatar_url: str | None) -> Image.Image | None:
    if not avatar_url or not _is_supported_avatar_url(avatar_url):
        return None
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            async with client.stream("GET", avatar_url) as response:
                if not 200 <= response.status_code < 300:
                    return None
                content_type = response.headers.get("content-type", "").partition(";")[0].strip().lower()
                if not content_type.startswith("image/"):
                    return None
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > _AVATAR_MAX_BYTES:
                    return None
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > _AVATAR_MAX_BYTES:
                        return None
        with Image.open(BytesIO(body)) as image:
            if image.width * image.height > _AVATAR_MAX_PIXELS:
                return None
            return ImageOps.exif_transpose(image).convert("RGB")
    except (httpx.HTTPError, OSError, UnidentifiedImageError, ValueError):
        return None


def _render_qrcode_card(scan_url: str, avatar: Image.Image | None) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(scan_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    panel_padding = 24
    panel_size = qr_image.width + panel_padding * 2
    card_width = max(640, panel_size + 64)
    panel_top = 136 if avatar else 32
    card_height = panel_top + panel_size + 32

    if avatar:
        card = ImageOps.fit(avatar, (card_width, card_height), Image.Resampling.LANCZOS)
        card = card.filter(ImageFilter.GaussianBlur(24)).convert("RGBA")
    else:
        card = Image.new("RGBA", (card_width, card_height), (31, 38, 51, 255))
    card.alpha_composite(Image.new("RGBA", card.size, (5, 10, 18, 118)))

    panel_left = (card_width - panel_size) // 2
    panel_box = (
        panel_left,
        panel_top,
        panel_left + panel_size,
        panel_top + panel_size,
    )
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (panel_box[0] + 6, panel_box[1] + 10, panel_box[2] + 6, panel_box[3] + 10),
        radius=28,
        fill=(0, 0, 0, 90),
    )
    card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(12)))
    ImageDraw.Draw(card).rounded_rectangle(panel_box, radius=28, fill=(255, 255, 255, 255))
    card.paste(qr_image, (panel_left + panel_padding, panel_top + panel_padding))

    if avatar:
        badge_size = 88
        badge_left = (card_width - badge_size) // 2
        badge_top = 24
        draw = ImageDraw.Draw(card)
        draw.ellipse(
            (badge_left - 5, badge_top - 5, badge_left + badge_size + 5, badge_top + badge_size + 5),
            fill=(255, 255, 255, 255),
        )
        badge = ImageOps.fit(avatar, (badge_size, badge_size), Image.Resampling.LANCZOS)
        badge_mask = Image.new("L", (badge_size, badge_size), 0)
        ImageDraw.Draw(badge_mask).ellipse((0, 0, badge_size - 1, badge_size - 1), fill=255)
        card.paste(badge, (badge_left, badge_top), badge_mask)

    result_stream = BytesIO()
    card.convert("RGB").save(result_stream, "PNG", optimize=True)
    return result_stream.getvalue()


async def bind_handler(
    token: Match[str],
    result: Arparma,
    user_session: UserSession,
    msg_target: MsgTarget,
    session: async_scoped_session,
):
    """绑定森空岛账号"""

    if not msg_target.private:
        send_reaction(user_session, "unmatch")
        await UniMessage("绑定指令只允许在私聊中使用").finish(at_sender=True)

    if not token.available:
        send_reaction(user_session, "processing")
        await UniMessage(
            "**绑定森空岛账号**\n\n"
            "- 获取 token 或 cred 的教程：\n"
            f"{_BIND_GUIDE_LINK}\n\n"
            "- 或发送 **`扫码绑定`**，用森空岛 App 扫码即可直接绑定，无需手动填写 token。"
        ).finish(at_sender=True)

    if user := await session.get(SkUser, user_session.user_id):
        if result.find("bind.update"):
            if len(token.result) == 24:
                grant_code = await SklandLoginAPI.get_grant_code(token.result, 0)
                cred = await SklandLoginAPI.get_cred(grant_code)
                user.access_token = token.result
                user.cred = cred.cred
                user.cred_token = cred.token
            elif len(token.result) == 32:
                cred_token = await SklandLoginAPI.refresh_token(token.result)
                user.cred = token.result
                user.cred_token = cred_token
            else:
                send_reaction(user_session, "unmatch")
                await UniMessage("token 或 cred 错误,请检查格式").finish(at_sender=True)
            await get_characters_and_bind(user, session)
            send_reaction(user_session, "done")
            await UniMessage("更新成功").finish(at_sender=True)
        send_reaction(user_session, "unmatch")
        await UniMessage("已绑定过 skland 账号").finish(at_sender=True)

    if token.available:
        try:
            if len(token.result) == 24:
                grant_code = await SklandLoginAPI.get_grant_code(token.result, 0)
                cred = await SklandLoginAPI.get_cred(grant_code)
                user = SkUser(
                    access_token=token.result,
                    cred=cred.cred,
                    cred_token=cred.token,
                    id=user_session.user_id,
                    user_id=cred.userId,
                )
            elif len(token.result) == 32:
                cred_token = await SklandLoginAPI.refresh_token(token.result)
                user_id = await SklandAPI.get_user_ID(CRED(cred=token.result, token=cred_token))
                user = SkUser(
                    cred=token.result,
                    cred_token=cred_token,
                    id=user_session.user_id,
                    user_id=user_id,
                )
            else:
                send_reaction(user_session, "unmatch")
                await UniMessage("token 或 cred 错误,请检查格式").finish(at_sender=True)
            session.add(user)
            await get_characters_and_bind(user, session)
            send_reaction(user_session, "done")
            await UniMessage("绑定成功").finish(at_sender=True)
        except RequestException as e:
            send_reaction(user_session, "fail")
            await UniMessage(f"绑定失败,错误信息:{e}").finish(at_sender=True)


async def qrcode_handler(
    user_session: UserSession,
    session: async_scoped_session,
):
    """二维码绑定森空岛账号"""
    send_reaction(user_session, "processing")
    avatar = await _fetch_user_avatar(user_session.platform_user.avatar)
    scan_id = await SklandLoginAPI.get_scan()
    scan_url = f"hypergryph://scan_login?scanId={scan_id}"
    qr_image = _render_qrcode_card(scan_url, avatar)
    msg = UniMessage("请使用森空岛 App 扫描二维码绑定账号\n二维码仅限本次命令发起者本人扫描，有效时间约两分钟")
    msg += UniMessage.image(raw=qr_image)
    qr_msg = await msg.send(reply_to=True, at_sender=not user_session.session.scene.is_private)
    end_time = datetime.now() + timedelta(seconds=100)
    scan_code = None
    while datetime.now() < end_time:
        try:
            scan_code = await SklandLoginAPI.get_scan_status(scan_id)
            break
        except RequestException:
            pass
        await asyncio.sleep(2)
    if qr_msg.recallable:
        await qr_msg.recall(index=0)
    if scan_code:
        send_reaction(user_session, "received")
        token = await SklandLoginAPI.get_token_by_scan_code(scan_code)
        grant_code = await SklandLoginAPI.get_grant_code(token, 0)
        cred = await SklandLoginAPI.get_cred(grant_code)
        if user := await session.get(SkUser, user_session.user_id):
            user.access_token = token
            user.cred = cred.cred
            user.cred_token = cred.token
        else:
            user = SkUser(
                access_token=token,
                cred=cred.cred,
                cred_token=cred.token,
                id=user_session.user_id,
                user_id=cred.userId,
            )
            session.add(user)
        await get_characters_and_bind(user, session)
        send_reaction(user_session, "done")
        await UniMessage("绑定成功").finish(at_sender=True)
    else:
        send_reaction(user_session, "fail")
        await UniMessage("二维码超时,请重新获取并扫码").finish(at_sender=True)


async def unbind_handler(
    user_session: UserSession,
    session: async_scoped_session,
):
    """解绑森空岛账号"""

    user = await session.get(SkUser, user_session.user_id)
    if not user:
        send_reaction(user_session, "unmatch")
        await UniMessage("你还没有绑定森空岛账号").finish(at_sender=True)

    resp = await prompt("确认解绑将删除所有绑定数据（包括角色和抽卡记录），回复「确认」继续", timeout=30)
    if resp is None or resp.extract_plain_text().strip() != "确认":
        await UniMessage("已取消解绑操作").finish(at_sender=True)

    await delete_user_all_gacha_records(user, session)
    await delete_characters(user, session)
    await delete_user(user, session)
    await session.commit()
    await ark_card_data.invalidate_user(user.id)

    send_reaction(user_session, "done")
    await UniMessage("解绑成功，已清除所有绑定数据").finish(at_sender=True)
