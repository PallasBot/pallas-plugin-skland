import random
from pathlib import Path
from typing import Any, Literal

from nonebot import logger
from pydantic import Field
from pydantic import BaseModel
from pydantic import AnyUrl as Url
from nonebot.compat import PYDANTIC_V2
import nonebot_plugin_localstore as store
from nonebot.plugin import get_plugin_config

RES_DIR: Path = Path(__file__).parent / "resources"
TEMPLATES_DIR: Path = RES_DIR / "templates"
CACHE_DIR = store.get_plugin_cache_dir()
DATA_DIR = store.get_plugin_data_dir()
RESOURCE_ROUTES = ["portrait", "skill", "avatar"]
DATA_ROUTES = [
    "gamedata/excel/gacha_table.json",
    "gamedata/excel/character_table.json",
    "gamedata/excel/char_patch_table.json",
    "gamedata/excel/uniequip_table.json",
    "gamedata/excel/handbook_info_table.json",
    "gamedata/excel/handbook_team_table.json",
]
GACHA_DATA_PATH = DATA_DIR / "gamedata" / "excel"
OPERATOR_METADATA_PATH = DATA_DIR / "operator_metadata.json"


class CustomSource(BaseModel):
    uri: Url | Path

    def to_uri(self) -> Any:
        if isinstance(self.uri, Path):
            uri = self.uri
            if not uri.is_absolute():
                uri = Path(store.get_plugin_data_dir() / uri)

            if uri.is_dir():
                # random pick a file
                files = [f for f in uri.iterdir() if f.is_file()]
                logger.debug(f"CustomSource: {uri} is a directory, random pick a file: {files}")
                if PYDANTIC_V2:
                    return Url((uri / random.choice(files)).as_posix())
                else:
                    return Url((uri / random.choice(files)).as_posix(), scheme="file")  # type: ignore

            if not uri.exists():
                raise FileNotFoundError(f"CustomSource: {uri} not exists")
            if PYDANTIC_V2:
                return Url(uri.as_posix())
            else:
                return Url(uri.as_posix(), scheme="file")  # type: ignore

        return self.uri


def _ui(group: str, order: int, **extra: object) -> dict[str, object]:
    return {"ui_group": group, "ui_order": order, **extra}


class ScopedConfig(BaseModel):
    github_proxy_url: str = Field(
        default="",
        description="GitHub 代理 URL，用于加速拉取游戏资源；留空则直连官方仓库。国内网络下载资源慢时可填镜像地址。",
        json_schema_extra=_ui("GitHub", 10),
    )
    github_token: str = Field(
        default="",
        description="GitHub Token，用于缓解 fetch_file_list 接口的免费调用上限；一般无需填写。",
        json_schema_extra={**_ui("GitHub", 20), "secret": True},
    )
    check_res_update: bool = Field(
        default=False,
        description="启动时是否检查并下载最新游戏资源；开启后每次启动会联网检查更新，会拖慢启动时间。",
        json_schema_extra=_ui("资源", 10),
    )
    ark_portrait_cache_enabled: bool = Field(
        default=False,
        description="首次渲染后按需缓存方舟干员半身图到本地；开启后后续渲染更快但对磁盘有占用。",
        json_schema_extra=_ui("渲染", 10),
    )
    background_source: Literal["default", "Lolicon", "random"] | CustomSource = Field(
        default="default",
        description="背景图片来源：default 内置 / Lolicon 网络随机 / random 本地随机；也支持 {uri: 图片地址} 自定义。",
        json_schema_extra=_ui("渲染", 15),
    )
    background_source_local_path: str = Field(
        default="",
        description="本地背景图片路径（单张图或目录，目录则随机选一张）。填此值后优先使用，背景来源不再生效；相对路径以插件数据目录为根，可用绝对路径。",
        json_schema_extra=_ui("渲染", 16),
    )
    endfield_background_simple: bool = Field(
        default=False,
        description="终末地角色卡片是否使用简化背景（纯色），减少图片体积与加载时间。",
        json_schema_extra=_ui("渲染", 20),
    )
    rogue_background_source: Literal["default", "rogue", "Lolicon"] | CustomSource = Field(
        default="rogue",
        description=(
            "肉鸽战绩背景来源：rogue 主题套图 / default 默认 / Lolicon 网络随机；也支持 {uri: 图片地址} 自定义。"
        ),
        json_schema_extra=_ui("渲染", 25),
    )
    rogue_background_source_local_path: str = Field(
        default="",
        description="本地肉鸽战绩背景图片路径（单张图或目录，目录则随机选一张）。填此值后优先使用，肉鸽来源不再生效；相对路径以插件数据目录为根，可用绝对路径。",
        json_schema_extra=_ui("渲染", 26),
    )
    argot_expire: int = Field(
        default=300,
        description="暗语消息（查看背景图、线索板）的过期时间，单位秒。",
        json_schema_extra=_ui("渲染", 30),
    )
    ark_card_cache_ttl: int = Field(default=120, gt=0, description="玩家角色卡内存缓存时间（秒），减少重复请求接口。")
    ark_card_cache_max_entries: int = Field(default=64, gt=0, description="玩家角色卡缓存数量上限，防止占用过多内存。")
    gacha_render_max: int = Field(
        default=30,
        description="明日方舟抽卡记录单张图片最多渲染的卡池数，超过会自动分页。",
        json_schema_extra=_ui("渲染", 40),
    )
    ef_gacha_render_max: int = Field(
        default=5,
        description="终末地抽卡记录单张图片最多渲染的卡池数（各类别分别计数）。",
        json_schema_extra=_ui("渲染", 50),
    )
    roster_render_max: int = Field(
        default=16, gt=0, description="方舟干员每次查询单张图片最多渲染的干员数，超过自动分页。"
    )
    render_timeout: int = Field(default=180_000, gt=0, description="模板截图超时时间（毫秒），网络慢时适当调大。")
    roster_render_format: Literal["png", "jpeg"] = Field(
        default="jpeg",
        description="方舟干员卡片图片格式：png 更清晰但更大，jpeg 体积小加载快。",
        json_schema_extra=_ui("渲染", 60),
    )
    roster_jpeg_quality: int = Field(
        default=90,
        ge=1,
        le=100,
        description="方舟干员卡片 JPEG 图片质量（1-100），越高越清晰但文件越大。",
        json_schema_extra=_ui("渲染", 70),
    )


class Config(BaseModel):
    skland: ScopedConfig = Field(default_factory=ScopedConfig)


config = get_plugin_config(Config).skland
