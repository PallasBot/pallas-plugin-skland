import ast
from pathlib import Path


def test_help_menu_items_have_stable_groups() -> None:
    expected = [
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

    module = ast.parse((Path(__file__).parents[1] / "nonebot_plugin_skland" / "extras.py").read_text())
    assignment = next(node for node in module.body if isinstance(node, ast.Assign))
    extra_data = ast.literal_eval(assignment.value)

    assert [item["group"] for item in extra_data["menu_data"]] == expected
