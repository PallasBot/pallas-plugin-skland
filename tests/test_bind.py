"""Behavior tests for the skland bind handler."""

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_bind_handler_shows_guide_when_token_missing(app, mocker):
    """无 token 时发送绑定引导（含获取链接）。"""
    import nonebot_plugin_skland.commands.bind as bind

    send_reaction = mocker.patch.object(bind, "send_reaction")
    finish = mocker.AsyncMock()
    uni_message = SimpleNamespace(finish=finish)
    uni_cls = mocker.patch.object(bind, "UniMessage", return_value=uni_message)
    session = SimpleNamespace(get=mocker.AsyncMock())

    token = SimpleNamespace(available=False)
    result = SimpleNamespace(find=lambda _: False)
    user_session = SimpleNamespace(user_id=1)
    msg_target = SimpleNamespace(private=True)

    await bind.bind_handler(token, result, user_session, msg_target, session)

    # 首次反应提示为 processing
    assert send_reaction.call_args_list[0].args == (user_session, "processing")
    # 首条构造的引导消息含绑定说明、获取链接与扫码绑定提示
    text = uni_cls.call_args_list[0].args[0]
    assert "绑定森空岛账号" in str(text)
    assert "docs.qq.com" in str(text)
    assert "扫码绑定" in str(text)
