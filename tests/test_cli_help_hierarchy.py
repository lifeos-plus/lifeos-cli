from __future__ import annotations

import pytest

from lifeos_cli import cli
from lifeos_cli.cli import build_parser


def test_main_note_without_action_prints_resource_help(capsys) -> None:
    exit_code = cli.main(["note"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Create, inspect, update, and delete note records." in captured.out
    assert "\n  lifeos note add --help\n" in captured.out
    assert "Run `lifeos init` before using note commands for the first time." in captured.out
    assert "\n  lifeos init\n" not in captured.out
    assert "tab-separated columns" not in captured.out
    assert "Use `show` to inspect the full note body" not in captured.out


@pytest.mark.parametrize(
    ("resource", "expected_help_examples"),
    [
        ("area", ("lifeos area add --help", "lifeos area list --help", "lifeos area batch --help")),
        (
            "data",
            (
                "lifeos data export --help",
                "lifeos data import --help",
                "lifeos data batch-update --help",
            ),
        ),
        (
            "event",
            ("lifeos event add --help", "lifeos event list --help", "lifeos event batch --help"),
        ),
        (
            "habit",
            ("lifeos habit add --help", "lifeos habit list --help", "lifeos habit batch --help"),
        ),
        (
            "habit-action",
            (
                "lifeos habit-action list --help",
                "lifeos habit-action show --help",
                "lifeos habit-action log --help",
            ),
        ),
        (
            "finance",
            (
                "lifeos finance tree-add --help",
                "lifeos finance node-add --help",
                "lifeos finance snapshot-add --help",
            ),
        ),
        ("note", ("lifeos note add --help", "lifeos note list --help", "lifeos note batch --help")),
        (
            "people",
            (
                "lifeos people add --help",
                "lifeos people list --help",
                "lifeos people batch --help",
            ),
        ),
        ("planning", ("lifeos planning show --help",)),
        ("schedule", ("lifeos schedule show --help", "lifeos schedule list --help")),
        ("tag", ("lifeos tag add --help", "lifeos tag list --help", "lifeos tag batch --help")),
        (
            "task",
            ("lifeos task add --help", "lifeos task list --help", "lifeos task batch --help"),
        ),
        (
            "timelog",
            (
                "lifeos timelog add --help",
                "lifeos timelog list --help",
                "lifeos timelog search --help",
                "lifeos timelog stats --help",
            ),
        ),
        (
            "vision",
            ("lifeos vision add --help", "lifeos vision list --help", "lifeos vision batch --help"),
        ),
    ],
)
def test_main_resource_help_surfaces_action_help_examples(
    resource: str,
    expected_help_examples: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main([resource])
    captured = capsys.readouterr()

    assert exit_code == 0
    for expected_help_example in expected_help_examples:
        assert f"\n  {expected_help_example}\n" in captured.out


@pytest.mark.parametrize(
    ("argv", "expected_help_examples"),
    [
        (
            ["area", "batch"],
            (
                "lifeos area batch delete --help",
                "lifeos area batch delete --ids <area-id-1> <area-id-2>",
            ),
        ),
        (
            ["event", "batch"],
            (
                "lifeos event batch delete --help",
                "lifeos event batch delete --ids <event-id-1> <event-id-2>",
            ),
        ),
        (
            ["habit", "batch"],
            (
                "lifeos habit batch delete --help",
                "lifeos habit batch delete --ids <habit-id-1> <habit-id-2>",
            ),
        ),
        (
            ["note", "batch"],
            ("lifeos note batch update-content --help", "lifeos note batch delete --help"),
        ),
        (
            ["people", "batch"],
            (
                "lifeos people batch delete --help",
                "lifeos people batch delete --ids <person-id-1> <person-id-2>",
            ),
        ),
        (
            ["tag", "batch"],
            (
                "lifeos tag batch delete --help",
                "lifeos tag batch delete --ids <tag-id-1> <tag-id-2>",
            ),
        ),
        (
            ["task", "batch"],
            (
                "lifeos task batch delete --help",
                "lifeos task batch delete --ids <task-id-1> <task-id-2>",
            ),
        ),
        (
            ["timelog", "batch"],
            (
                "lifeos timelog batch update --help",
                "lifeos timelog batch delete --help",
            ),
        ),
        (
            ["timelog", "stats"],
            (
                "lifeos timelog stats day --help",
                "lifeos timelog stats range --help",
                "lifeos timelog stats rebuild --help",
            ),
        ),
        (
            ["vision", "batch"],
            (
                "lifeos vision batch delete --help",
                "lifeos vision batch delete --ids <vision-id-1> <vision-id-2>",
            ),
        ),
    ],
)
def test_namespace_help_surfaces_nested_help_examples(
    argv: list[str],
    expected_help_examples: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(argv)
    captured = capsys.readouterr()

    assert exit_code == 0
    for expected_help_example in expected_help_examples:
        assert f"\n  {expected_help_example}\n" in captured.out


@pytest.mark.parametrize(
    ("argv", "expected_text"),
    [
        (["area", "batch"], "Delete multiple areas in one command."),
        (["event", "batch"], "Delete multiple events in one command."),
        (["habit", "batch"], "Delete multiple habits in one command."),
        (["people", "batch"], "Delete multiple people records in one command."),
        (["tag", "batch"], "Delete multiple tags in one command."),
        (["task", "batch"], "Delete multiple tasks in one command."),
        (["vision", "batch"], "Delete multiple visions in one command."),
        (
            ["note", "batch"],
            "Use `update-content` for bulk find/replace across active note content.",
        ),
        (
            ["timelog", "batch"],
            "Run bulk update and delete operations for timelogs.",
        ),
        (
            ["timelog", "stats"],
            "Use `range` for arbitrary windows and `rebuild` to refresh persisted stats.",
        ),
    ],
)
def test_namespace_help_surfaces_user_facing_scope_guidance(
    argv: list[str],
    expected_text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(argv)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert expected_text in captured.out


@pytest.mark.parametrize(
    ("argv", "unexpected_text"),
    [
        (["area", "batch"], "Run bulk delete operations for areas."),
        (["area", "batch"], "stable CLI shape"),
        (["event", "batch"], "Grouped namespace for multi-record event writes."),
        (["habit", "batch"], "Grouped namespace for multi-record habit writes."),
        (["note", "batch"], "Future note batch operations should be added under this namespace."),
        (["people", "batch"], "bulk maintenance operations"),
        (["tag", "batch"], "adding many top-level verbs"),
        (["task", "batch"], "adding many top-level verbs"),
        (["timelog", "batch"], "Grouped namespace for multi-record timelog writes."),
        (["timelog", "stats"], "Range stats aggregate directly from source timelogs"),
        (["vision", "batch"], "adding many top-level verbs"),
    ],
)
def test_namespace_help_avoids_internal_structure_rationale(
    argv: list[str],
    unexpected_text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(argv)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert unexpected_text not in captured.out


@pytest.mark.parametrize(
    ("argv", "expected_note"),
    [
        (["area", "batch"], "This namespace currently exposes only the `delete` workflow."),
        (["event", "batch"], "This namespace currently exposes only the `delete` workflow."),
        (["habit", "batch"], "This namespace currently exposes only the `delete` workflow."),
        (["people", "batch"], "This namespace currently exposes only the `delete` workflow."),
        (["tag", "batch"], "This namespace currently exposes only the `delete` workflow."),
        (["task", "batch"], "This namespace currently exposes only the `delete` workflow."),
        (["vision", "batch"], "This namespace currently exposes only the `delete` workflow."),
    ],
)
def test_single_action_batch_help_explains_current_scope(
    argv: list[str],
    expected_note: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(argv)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert expected_note in captured.out


@pytest.mark.parametrize(
    ("resource", "unexpected"),
    [
        ("task", "A task appears in `lifeos schedule show`"),
        ("schedule", "segmented into appointment, timeblock, and deadline sections"),
        ("timelog", "linked_notes_count"),
    ],
)
def test_resource_help_avoids_action_level_contract_details(
    resource: str,
    unexpected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main([resource])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert unexpected not in captured.out


@pytest.mark.parametrize(
    ("resource", "expected_note"),
    [
        ("area", "See `lifeos area batch --help` for bulk delete operations."),
        ("event", "See `lifeos event batch --help` for bulk delete operations."),
        ("habit", "See `lifeos habit batch --help` for bulk delete operations."),
        (
            "note",
            "See `lifeos note batch --help` for bulk `update-content` and `delete` workflows.",
        ),
        ("people", "See `lifeos people batch --help` for bulk delete operations."),
        ("tag", "See `lifeos tag batch --help` for bulk delete operations."),
        ("task", "See `lifeos task batch --help` for bulk delete operations."),
        (
            "timelog",
            "See `lifeos timelog batch --help` for bulk `update` and `delete` workflows.",
        ),
        ("vision", "See `lifeos vision batch --help` for bulk delete operations."),
    ],
)
def test_resource_help_surfaces_concrete_batch_guidance(
    resource: str,
    expected_note: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main([resource])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert expected_note in captured.out


@pytest.mark.parametrize(
    "resource",
    ("area", "event", "habit", "note", "people", "tag", "task", "timelog", "vision"),
)
def test_resource_help_avoids_delete_behavior_contract_details(
    resource: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main([resource])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "soft deletion" not in captured.out


@pytest.mark.parametrize(
    ("resource", "unexpected_examples"),
    [
        (
            "note",
            ('lifeos note add "Capture an idea"', 'lifeos note search "sprint retrospective"'),
        ),
        (
            "area",
            (
                'lifeos area add "Health" --color "#16A34A"',
                "lifeos area show 11111111-1111-1111-1111-111111111111",
            ),
        ),
        (
            "timelog",
            (
                'lifeos timelog add "Deep work" --start-time 2026-04-10T13:00:00 '
                "--end-time 2026-04-10T14:30:00",
            ),
        ),
    ],
)
def test_resource_help_examples_stay_navigation_focused(
    resource: str,
    unexpected_examples: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main([resource])
    captured = capsys.readouterr()

    assert exit_code == 0
    for unexpected_example in unexpected_examples:
        assert unexpected_example not in captured.out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["note", "-h", "add"], "Create a new note from inline text, stdin, or a file."),
        (["task", "-h", "add"], "Create a new task for a vision."),
        (
            ["note", "-h", "batch", "update-content"],
            "Apply a find/replace operation across multiple active notes.",
        ),
        (
            ["note", "batch", "-h", "update-content"],
            "Apply a find/replace operation across multiple active notes.",
        ),
        (["-h", "note", "add"], "Create a new note from inline text, stdin, or a file."),
    ],
)
def test_main_rewrites_misplaced_help_flags_to_target_subcommand(
    argv: list[str],
    expected: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(argv)

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert expected in captured.out


def test_cli_note_batch_help_explains_namespace_intent(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["note", "batch", "--help"])

    captured = capsys.readouterr()

    assert "Run note operations that target multiple records in one command." in captured.out
    assert "Use `update-content` for bulk find/replace across active note content." in captured.out
    assert "update-content" in captured.out
    assert "delete" in captured.out
