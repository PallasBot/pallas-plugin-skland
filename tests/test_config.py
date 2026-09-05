"""森空岛插件配置结构与中文说明测试。"""


def test_config_keeps_nonebot_nested_structure():
    """Config 保持 NoneBot 官方嵌套结构（skland: ScopedConfig）。"""
    from nonebot_plugin_skland.config import Config, ScopedConfig

    cfg = Config()
    assert isinstance(cfg.skland, ScopedConfig)
    assert cfg.skland.github_proxy_url == ""
    assert cfg.skland.check_res_update is False
    assert cfg.skland.argot_expire == 300


def test_config_fields_have_chinese_descriptions():
    """嵌套字段带中文描述（供 WebUI 展示）。"""
    from nonebot_plugin_skland.config import ScopedConfig

    fields = ScopedConfig.model_fields
    for name, f in fields.items():
        assert f.description, f"字段 {name} 缺少 description"
        assert any("\u4e00" <= c <= "\u9fff" for c in f.description), f"字段 {name} description 非中文"


def test_config_has_local_background_path_fields():
    """有独立的本地背景路径配置项，默认空。"""
    from nonebot_plugin_skland.config import Config, ScopedConfig

    cfg = Config()
    assert cfg.skland.background_source_local_path == ""
    assert cfg.skland.rogue_background_source_local_path == ""
    names = set(ScopedConfig.model_fields.keys())
    assert "background_source_local_path" in names
    assert "rogue_background_source_local_path" in names
