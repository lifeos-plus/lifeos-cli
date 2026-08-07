from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from lifeos_cli.cli import build_parser

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_cli_task_help_supports_zh_hans_locale(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["task", "--help"])

    captured = capsys.readouterr()

    assert "创建并维护属于某个 `vision` 的 `task` 树。" in captured.out
    assert "创建 `task`" in captured.out
    assert "说明:" in captured.out


def test_cli_task_list_help_supports_zh_hans_locale_and_documents_header_row(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["task", "list", "--help"])

    captured = capsys.readouterr()

    assert "列出 `task` 以及可选的 `vision`、父级或状态过滤器。" in captured.out
    assert (
        "当存在结果时，`list` 命令会先输出一行表头，随后按制表符分隔输出列："
        "task_id、status、vision_id、parent_task_id、content。"
    ) in captured.out


def test_cli_top_level_help_supports_zh_hans_argparse_scaffolding(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])

    captured = capsys.readouterr()

    assert "██╗     ██╗███████╗███████╗ ██████╗ ███████╗" in captured.out
    assert "╚══════╝╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚══════╝" in captured.out
    assert "usage:" not in captured.out and "用法：" not in captured.out
    assert "显示此帮助信息并退出" in captured.out or "-h, --help" in captured.out
    assert "资源:\n  资源" not in captured.out
    assert "在终端中运行 LifeOS 资源命令。" not in captured.out
    assert "repo: https://github.com/lifeos-plus/lifeos-cli" in captured.out
    assert "uv tool install --upgrade lifeos-cli" in captured.out
    assert "area" in captured.out and "管理 `area`" in captured.out
    assert "people" in captured.out and "管理 `people` 和关系" in captured.out
    assert "timelog" in captured.out and "管理 `timelog`" in captured.out
    assert "欢迎通过 https://github.com/lifeos-plus/lifeos-cli 提交问题报告和建议。" in captured.out


def test_cli_top_level_help_keeps_long_resource_summaries_on_one_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])

    captured = capsys.readouterr()

    assert any(
        "habit-action" in line and "管理按日期生成的 `habit-action`" in line
        for line in captured.out.splitlines()
    )


def test_cli_resource_help_keeps_long_action_summaries_on_one_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["habit", "--help"])

    captured = capsys.readouterr()

    assert any(
        "task-associations" in line and "列出 `task` 与 `habit` 的关联" in line
        for line in captured.out.splitlines()
    )


def test_cli_task_add_help_keeps_long_option_invocation_with_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["task", "add", "--help"])

    captured = capsys.readouterr()

    assert any(
        "--planning-cycle-type PLANNING_CYCLE_TYPE" in line
        and "planning-cycle 类型：7years、year、month、week 或 day" in line
        for line in captured.out.splitlines()
    )


def test_cli_event_add_help_keeps_long_option_invocation_with_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["event", "add", "--help"])

    captured = capsys.readouterr()

    assert any(
        "--recurrence-frequency RECURRENCE_FREQUENCY" in line
        and "可选的重复频率：daily、weekly、monthly 或" in line
        for line in captured.out.splitlines()
    )


def test_cli_schedule_show_help_supports_zh_hans_locale(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["schedule", "show", "--help"])

    captured = capsys.readouterr()

    assert "显示某一个本地日期的聚合 `schedule`。" in captured.out
    assert "`task` 行来自 planning-cycle 的时间重叠" in captured.out
    assert "示例:" in captured.out


def test_cli_timelog_add_help_supports_zh_hans_locale_for_stdin_batch_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["timelog", "add", "--help"])

    captured = capsys.readouterr()

    assert "从标准输入读取快捷批量行，使用与 `--entry` 相同的时间规则" in captured.out
    assert "`HHMM Title` 表示 `HHMM` 是片段结束时间，不是开始时间" in captured.out
    assert "`--entry`、`--stdin` 和 `--file` 使用同一套解析规则" in captured.out
    assert "预览后直接写入快捷批量 `timelog`，无需交互确认" in captured.out
    assert "并在输入来自 `--stdin` 或提供 `--yes` 时跳过确认" in captured.out
    assert "当日期时间省略时区信息时" in captured.out
    assert "Create one actual time record" not in captured.out
    assert "Repeat to add one quick batch-entry line" not in captured.out


@pytest.mark.parametrize(
    "catalog_path",
    [
        PROJECT_ROOT / "src/lifeos_cli/locales/zh_Hans/cli_messages.json",
        PROJECT_ROOT / "src/lifeos_cli/locales/zh_Hans/cli_help.json",
    ],
)
def test_zh_hans_catalogs_do_not_contain_untranslated_english_prose(
    catalog_path: Path,
) -> None:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    untranslated: list[tuple[str, str]] = []

    def walk(value: object, path: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else key)
            return
        if not isinstance(value, str):
            return
        without_literals = re.sub(r"`[^`]+`", " ", value)
        without_literals = re.sub(r"https?://\S+", " ", without_literals)
        without_literals = re.sub(r"\{[^}]+\}", " ", without_literals)
        has_chinese = re.search(r"[\u4e00-\u9fff]", value) is not None
        has_english = re.search(r"[A-Za-z]{4,}", without_literals) is not None
        has_english_phrase = (
            re.search(r"\b[A-Za-z]{4,}\s+[A-Za-z]{4,}\b", without_literals) is not None
        )
        if (has_english and not has_chinese) or has_english_phrase:
            untranslated.append((path, value))

    walk(catalog)

    assert untranslated == []


def test_cli_timelog_search_help_supports_zh_hans_locale(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["timelog", "search", "--help"])

    captured = capsys.readouterr()

    assert "搜索 `timelog`，可选使用关键词、时间窗口、关系和方法过滤器。" in captured.out
    assert 'lifeos timelog search --query "洗"' in captured.out
    assert "复用 `timelog list` 的过滤器和制表符分隔摘要输出" in captured.out
    assert "`--query` 不搜索 task 或 area 名称" in captured.out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["task", "list", "--help"],
            "当存在结果时，`list` 命令会先输出一行表头，随后按制表符分隔输出列："
            "task_id、status、vision_id、parent_task_id、content。",
        ),
        (
            ["habit", "list", "--help"],
            "默认 `list` 输出会先输出一行表头，随后按制表符分隔输出列："
            "habit_id、status、start_date、duration_days、cadence、task_id、title。",
        ),
        (
            ["note", "list", "--help"],
            "当存在结果时，`list` 命令会先输出一行表头，随后按制表符分隔输出列："
            "note_id、status、created_at、content。",
        ),
        (
            ["vision", "with-tasks", "--help"],
            "当该 `vision` 存在 task 时，`tasks` 分段会先输出一行表头，随后按制表符分隔输出列："
            "task_id、status、parent_task_id、content。",
        ),
        (
            ["schedule", "show", "--help"],
            "`task` 分段的列为：task_id、status、planning_cycle_type、planning_cycle_start_date、"
            "planning_cycle_end_date、content。",
        ),
    ],
)
def test_cli_zh_hans_help_documents_entity_specific_header_names(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    assert expected in captured.out


def test_cli_zh_hans_help_keeps_internal_entity_terms_in_english(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    cases = [
        (["people", "--help"], ["`people`", "`person`"]),
        (["timelog", "--help"], ["`timelog`", "`area`", "`task`"]),
        (["schedule", "--help"], ["`schedule`", "`task`", "`habit-action`", "`event`"]),
    ]

    for argv, expected_terms in cases:
        with pytest.raises(SystemExit):
            parser.parse_args([*argv[:-1], argv[-1]])
        captured = capsys.readouterr()
        for term in expected_terms:
            assert term in captured.out


@pytest.mark.parametrize(
    ("argv", "expected_terms", "forbidden_terms"),
    [
        (
            ["event", "add", "--help"],
            [
                "创建一个计划中的 `event`。",
                "`event` 类型：appointment、timeblock 或 deadline",
                "重复附加一个或多个 `tag`",
                "共享的时间块",
            ],
            [
                "浙江活动",
                "`event``tag`",
                "路线块",
            ],
        ),
        (
            ["event", "update", "--help"],
            [
                "清除描述",
                "清除结束时间",
                "清除关联的 `task`",
                "移除所有 `people`",
            ],
            [
                "清晰的描述",
                "明确结束时间",
                "明确链接 `task`",
                "撤走所有 `people`",
            ],
        ),
        (
            ["task", "--help"],
            [
                "显示 `vision` 的 `task` 层级",
                "使用 planning-cycle 字段表示更大的时间范围。"
                "当 `task` 还需要具体的时间块时，请使用 `event`。",
                "批量删除操作请查看 `lifeos task batch --help`。",
            ],
            [
                "`vision``task`",
                "Use planning-cycle fields for the broader timebox",
                "See `lifeos task batch --help` for bulk delete operations.",
            ],
        ),
        (
            ["task", "hierarchy", "--help"],
            [
                "输出会先打印 `vision` 标识符，然后使用与 `with-subtasks` 相同的"
                "缩进树形结构打印每个根 `task` 及其后代。",
                "当你只想查看树中的一个分支时，请使用 `with-subtasks`。",
            ],
            [
                "The output starts with the vision identifier",
                "Use `with-subtasks` when you want to inspect only one branch of the tree.",
            ],
        ),
        (
            ["timelog", "add", "--help"],
            [
                "可选备注",
                "重复附加一个或多个 `tag`",
                "重复使用同一个 `--tag-id` 或 `--person-id` 参数，即可在一条命令中"
                "附加多个 `tag` 或 `people`。",
            ],
            [
                "可选 `note`",
                "`timelog``tag`",
                "Repeat the same `--tag-id` or `--person-id` flag to attach "
                "multiple tags or people in one command.",
            ],
        ),
        (
            ["timelog", "update", "--help"],
            [
                "更新备注",
                "清除位置",
                "清除能量等级",
                "清除备注",
            ],
            [
                "更新 `note`",
                "清晰的位置",
                "清晰的能量水平",
                "清除 `note`",
            ],
        ),
        (
            ["vision", "update", "--help"],
            [
                "更新可变的 `vision` 字段。",
                "清除可选的 `vision` 描述",
            ],
            [
                "更新可变的 `vision``area`。",
                "明确可选的 `vision` 描述",
            ],
        ),
    ],
)
def test_cli_zh_hans_help_avoids_misleading_translations(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    expected_terms: list[str],
    forbidden_terms: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIFEOS_LANGUAGE", "zh-Hans")
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)

    captured = capsys.readouterr()

    for expected_term in expected_terms:
        assert expected_term in captured.out
    for forbidden_term in forbidden_terms:
        assert forbidden_term not in captured.out
