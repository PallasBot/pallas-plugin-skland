import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _metadata_extra() -> dict:
    tree = ast.parse((ROOT / "nonebot_plugin_skland" / "__init__.py").read_text())
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "PluginMetadata"
    )
    value = next(keyword.value for keyword in call.keywords if keyword.arg == "extra")
    return ast.literal_eval(value)


def _menu_data() -> list[dict]:
    tree = ast.parse((ROOT / "nonebot_plugin_skland" / "extras.py").read_text())
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign))
    return ast.literal_eval(assignment.value)["menu_data"]


def test_plugin_defaults_to_tool_help_group() -> None:
    assert _metadata_extra()["help_tag"] == "tool"


def test_command_menu_groups_are_preserved() -> None:
    assert [item["group"] for item in _menu_data()] == [
        "账号与绑定",
        "账号与绑定",
        "账号与绑定",
        "明日方舟",
        "明日方舟",
        "明日方舟",
        "管理",
        "管理",
        "终末地",
        "终末地",
        "管理",
        "管理",
        "终末地",
        "明日方舟",
        "明日方舟",
        "明日方舟",
        "明日方舟",
        "终末地",
        "终末地",
        "明日方舟",
        "账号与绑定",
        "管理",
        "管理",
        "其他",
        "管理",
    ]


def test_command_permissions_cover_help_menu() -> None:
    permissions = {row["id"]: row for row in _metadata_extra()["command_permissions"]}
    menu = _menu_data()
    command_ids = {item["command_permission"] for item in menu if "command_permission" in item}

    assert command_ids <= permissions.keys()
    assert all(item.get("command_permission") for item in menu if item["func"] != "暗语")
    assert {row["default"] for row in permissions.values()} == {"everyone"}
