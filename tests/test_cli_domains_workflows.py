from __future__ import annotations

import io
from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID

import pytest

from lifeos_cli import cli
from lifeos_cli.cli_support.resources.timelog import handlers as timelog_handlers
from lifeos_cli.config import clear_config_cache
from lifeos_cli.db import session as db_session
from lifeos_cli.db.models.habit import Habit
from lifeos_cli.db.services import (
    habit_actions,
    habits,
    tasks,
    timelogs,
)
from tests.support import make_record, make_session_scope, utc_datetime


class _PromptInput(io.StringIO):
    def isatty(self) -> bool:
        return True


def _isoformat_datetime(value: object) -> str:
    assert isinstance(value, datetime)
    return value.isoformat()


def test_main_timelog_add_creates_timelog(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_timelog(_session: object, **kwargs: object) -> object:
        payload = cast(timelogs.TimelogCreateInput, kwargs["payload"])
        assert payload.title == "Deep work"
        assert payload.tracking_method == "manual"
        return make_record(id=UUID("13131313-1313-1313-1313-131313131313"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "create_timelog", fake_create_timelog)

    exit_code = cli.main(
        [
            "timelog",
            "add",
            "Deep work",
            "--start-time",
            "2026-04-10T13:00:00",
            "--end-time",
            "2026-04-10T14:30:00",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created timelog 13131313-1313-1313-1313-131313131313" in captured.out


def test_main_timelog_add_quick_batch_creates_timelogs_after_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_calls: list[dict[str, object]] = []

    async def fake_create_timelog(_session: object, **kwargs: object) -> object:
        captured_calls.append(kwargs)
        return make_record(id=UUID(f"13131313-1313-1313-1313-13131313131{len(captured_calls)}"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "create_timelog", fake_create_timelog)
    monkeypatch.setattr(timelog_handlers.sys, "stdin", _PromptInput("yes\n"))
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "America/Toronto")

    exit_code = cli.main(
        [
            "timelog",
            "add",
            "--entry",
            "0700 Breakfast",
            "--entry",
            "0830 Deep work",
            "--first-start-time",
            "2026-04-10T06:30:00",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert len(captured_calls) == 2
    first_payload = cast(timelogs.TimelogCreateInput, captured_calls[0]["payload"])
    second_payload = cast(timelogs.TimelogCreateInput, captured_calls[1]["payload"])
    assert first_payload.title == "Breakfast"
    assert _isoformat_datetime(first_payload.start_time) == "2026-04-10T06:30:00-04:00"
    assert _isoformat_datetime(first_payload.end_time) == "2026-04-10T07:00:00-04:00"
    assert second_payload.title == "Deep work"
    assert _isoformat_datetime(second_payload.start_time) == "2026-04-10T07:00:00-04:00"
    assert _isoformat_datetime(second_payload.end_time) == "2026-04-10T08:30:00-04:00"
    assert "Quick batch timelog preview:" in captured.out
    assert "Created timelogs: 2" in captured.out
    clear_config_cache()


def test_main_timelog_add_quick_batch_reads_entries_from_stdin_without_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_calls: list[dict[str, object]] = []

    async def fake_create_timelog(_session: object, **kwargs: object) -> object:
        captured_calls.append(kwargs)
        return make_record(id=UUID(f"15151515-1515-1515-1515-15151515151{len(captured_calls)}"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "create_timelog", fake_create_timelog)
    monkeypatch.setattr(
        timelog_handlers.sys,
        "stdin",
        io.StringIO("0700 Breakfast\n0830 Deep work\n"),
    )
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "America/Toronto")

    exit_code = cli.main(
        [
            "timelog",
            "add",
            "--stdin",
            "--first-start-time",
            "2026-04-10T06:30:00",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert len(captured_calls) == 2
    first_payload = cast(timelogs.TimelogCreateInput, captured_calls[0]["payload"])
    second_payload = cast(timelogs.TimelogCreateInput, captured_calls[1]["payload"])
    assert first_payload.title == "Breakfast"
    assert _isoformat_datetime(first_payload.start_time) == "2026-04-10T06:30:00-04:00"
    assert _isoformat_datetime(first_payload.end_time) == "2026-04-10T07:00:00-04:00"
    assert second_payload.title == "Deep work"
    assert _isoformat_datetime(second_payload.start_time) == "2026-04-10T07:00:00-04:00"
    assert _isoformat_datetime(second_payload.end_time) == "2026-04-10T08:30:00-04:00"
    assert "Quick batch timelog preview:" in captured.out
    assert "Created timelogs: 2" in captured.out
    clear_config_cache()


def test_main_timelog_add_quick_batch_skips_confirmation_prompt_for_stdin(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_calls: list[dict[str, object]] = []

    async def fake_create_timelog(_session: object, **kwargs: object) -> object:
        captured_calls.append(kwargs)
        return make_record(id=UUID("16161616-1616-1616-1616-161616161616"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "create_timelog", fake_create_timelog)
    monkeypatch.setattr(timelog_handlers.sys, "stdin", io.StringIO("0700 Breakfast\n"))
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "America/Toronto")

    exit_code = cli.main(
        [
            "timelog",
            "add",
            "--stdin",
            "--first-start-time",
            "2026-04-10T06:30:00",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert len(captured_calls) == 1
    assert "Type `yes` to create these timelogs:" not in captured.out
    clear_config_cache()


def test_main_timelog_add_quick_batch_inherits_latest_end_time(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_calls: list[dict[str, object]] = []

    async def fake_get_latest_timelog_end_time(_session: object) -> object:
        return utc_datetime(2026, 4, 10, 10, 30)

    async def fake_create_timelog(_session: object, **kwargs: object) -> object:
        captured_calls.append(kwargs)
        return make_record(id=UUID("14141414-1414-1414-1414-141414141414"))

    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "America/Toronto")
    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "get_latest_timelog_end_time", fake_get_latest_timelog_end_time)
    monkeypatch.setattr(timelogs, "create_timelog", fake_create_timelog)
    monkeypatch.setattr(timelog_handlers.sys, "stdin", _PromptInput("yes\n"))

    exit_code = cli.main(["timelog", "add", "--entry", "0700 Breakfast"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = cast(timelogs.TimelogCreateInput, captured_calls[0]["payload"])
    assert _isoformat_datetime(payload.start_time) == "2026-04-10T06:30:00-04:00"
    assert _isoformat_datetime(payload.end_time) == "2026-04-10T07:00:00-04:00"
    assert "Quick batch timelog preview:" in captured.out
    clear_config_cache()


def test_main_timelog_list_passes_search_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "UTC")

    async def fake_list_timelogs(_session: object, **kwargs: object) -> list[object]:
        query = cast(timelogs.TimelogListInput, kwargs["query"])
        assert query.filters.query == "deep work"
        assert query.filters.notes_contains == "focused"
        assert query.filters.area_name == "Work"
        assert query.filters.without_area is False
        assert query.filters.without_task is True
        return [
            make_record(
                id=UUID("13131313-1313-1313-1313-131313131313"),
                deleted_at=None,
                tracking_method="manual",
                start_time=utc_datetime(2026, 4, 10, 13, 0),
                end_time=utc_datetime(2026, 4, 10, 14, 0),
                task_id=None,
                linked_notes_count=0,
                title="Deep work",
            )
        ]

    async def fake_count_timelogs(_session: object, **kwargs: object) -> int:
        filters = cast(timelogs.TimelogQueryFilters, kwargs["filters"])
        assert filters.query == "deep work"
        assert filters.notes_contains == "focused"
        assert filters.area_name == "Work"
        assert filters.without_area is False
        assert filters.without_task is True
        return 1

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "list_timelogs", fake_list_timelogs)
    monkeypatch.setattr(timelogs, "count_timelogs", fake_count_timelogs)

    exit_code = cli.main(
        [
            "timelog",
            "list",
            "--query",
            "deep work",
            "--notes-contains",
            "focused",
            "--area-name",
            "Work",
            "--without-task",
            "--count",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "timelog_id\tstatus\tstart_time\tend_time\ttask_id\ttitle",
        (
            "13131313-1313-1313-1313-131313131313\tmanual\t2026-04-10T13:00:00+00:00\t"
            "2026-04-10T14:00:00+00:00\t-\tDeep work"
        ),
        "Total timelogs: 1",
    ]
    clear_config_cache()


def test_main_timelog_search_reuses_list_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "UTC")

    expected_start = utc_datetime(2026, 6, 16, 16, 0)
    expected_end = datetime(2026, 6, 17, 15, 59, 59, 999000, tzinfo=UTC)

    async def fake_list_timelogs(_session: object, **kwargs: object) -> list[object]:
        query = cast(timelogs.TimelogListInput, kwargs["query"])
        assert query.filters.query == "洗"
        assert query.filters.window_start == expected_start
        assert query.filters.window_end == expected_end
        assert query.limit == 500
        assert query.offset == 0
        return [
            make_record(
                id=UUID("13131313-1313-1313-1313-131313131313"),
                deleted_at=None,
                tracking_method="manual",
                start_time=expected_start,
                end_time=expected_end,
                task_id=None,
                linked_notes_count=0,
                title="洗衣",
            )
        ]

    async def fake_count_timelogs(_session: object, **kwargs: object) -> int:
        filters = cast(timelogs.TimelogQueryFilters, kwargs["filters"])
        assert filters.query == "洗"
        assert filters.window_start == expected_start
        assert filters.window_end == expected_end
        return 1

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "list_timelogs", fake_list_timelogs)
    monkeypatch.setattr(timelogs, "count_timelogs", fake_count_timelogs)

    exit_code = cli.main(
        [
            "timelog",
            "search",
            "--query",
            "洗",
            "--start-time",
            "2026-06-16T16:00:00.000Z",
            "--end-time",
            "2026-06-17T15:59:59.999Z",
            "--limit",
            "500",
            "--count",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "timelog_id\tstatus\tstart_time\tend_time\ttask_id\ttitle",
        (
            "13131313-1313-1313-1313-131313131313\tmanual\t2026-06-16T16:00:00+00:00\t"
            "2026-06-17T15:59:59.999000+00:00\t-\t洗衣"
        ),
        "Total timelogs: 1",
    ]
    clear_config_cache()


def test_main_timelog_list_can_include_relationship_counts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "UTC")

    async def fake_list_timelogs(_session: object, **kwargs: object) -> list[object]:
        query = cast(timelogs.TimelogListInput, kwargs["query"])
        assert query.filters.query is None
        return [
            make_record(
                id=UUID("13131313-1313-1313-1313-131313131313"),
                deleted_at=None,
                tracking_method="manual",
                start_time=utc_datetime(2026, 4, 10, 13, 0),
                end_time=utc_datetime(2026, 4, 10, 14, 0),
                task_id=None,
                linked_notes_count=2,
                title="Deep work",
            )
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "list_timelogs", fake_list_timelogs)

    exit_code = cli.main(["timelog", "list", "--with-counts"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "timelog_id\tstatus\tstart_time\tend_time\ttask_id\tlinked_notes_count\ttitle",
        (
            "13131313-1313-1313-1313-131313131313\tmanual\t2026-04-10T13:00:00+00:00\t"
            "2026-04-10T14:00:00+00:00\t-\t2\tDeep work"
        ),
    ]
    clear_config_cache()


def test_main_timelog_list_passes_discrete_date_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_timelogs(_session: object, **kwargs: object) -> list[object]:
        query = cast(timelogs.TimelogListInput, kwargs["query"])
        assert query.filters.date_values == (date(2026, 4, 10), date(2026, 4, 11))
        assert query.filters.start_date is None
        assert query.filters.end_date is None
        return []

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "list_timelogs", fake_list_timelogs)

    exit_code = cli.main(["timelog", "list", "--date", "2026-04-10", "--date", "2026-04-11"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "No timelogs found."


def test_main_timelog_batch_update_passes_relation_and_title_updates(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_batch_update_timelogs(_session: object, **kwargs: object) -> object:
        changes = cast(timelogs.TimelogBatchUpdateInput, kwargs["changes"])
        assert kwargs["timelog_ids"] == [
            UUID("13131313-1313-1313-1313-131313131313"),
            UUID("14141414-1414-1414-1414-141414141414"),
        ]
        assert changes.find_title_text == "deep"
        assert changes.replace_title_text == "focused"
        assert changes.changes.clear_task is True
        assert changes.changes.person_ids == [UUID("33333333-3333-3333-3333-333333333333")]
        return timelogs.TimelogBatchUpdateResult(
            updated_count=2,
            unchanged_ids=(),
            failed_ids=(),
            errors=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "batch_update_timelogs", fake_batch_update_timelogs)

    exit_code = cli.main(
        [
            "timelog",
            "batch",
            "update",
            "--ids",
            "13131313-1313-1313-1313-131313131313",
            "14141414-1414-1414-1414-141414141414",
            "--find-title-text",
            "deep",
            "--replace-title-text",
            "focused",
            "--clear-task",
            "--person-id",
            "33333333-3333-3333-3333-333333333333",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated timelogs: 2" in captured.out


def test_main_task_add_creates_task(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_task(_session: object, **kwargs: object) -> object:
        assert kwargs["content"] == "Draft release checklist"
        assert kwargs["priority"] == 2
        assert kwargs["person_ids"] == [UUID("11111111-1111-1111-1111-111111111111")]
        return make_record(id=UUID("55555555-5555-5555-5555-555555555555"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tasks, "create_task", fake_create_task)

    exit_code = cli.main(
        [
            "task",
            "add",
            "Draft release checklist",
            "--vision-id",
            "66666666-6666-6666-6666-666666666666",
            "--priority",
            "2",
            "--person-id",
            "11111111-1111-1111-1111-111111111111",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created task 55555555-5555-5555-5555-555555555555" in captured.out


def test_main_task_read_model_commands_print_results(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root_task = make_record(
        id=UUID("55555555-5555-5555-5555-555555555555"),
        status="todo",
        content="Root task",
        completion_percentage=0.5,
        depth=0,
        subtasks=(
            make_record(
                id=UUID("66666666-6666-6666-6666-666666666666"),
                status="done",
                content="Child task",
                completion_percentage=1.0,
                depth=1,
                subtasks=(),
            ),
        ),
    )

    async def fake_get_task_with_subtasks(_session: object, **kwargs: object) -> object:
        assert kwargs["task_id"] == UUID("55555555-5555-5555-5555-555555555555")
        return root_task

    async def fake_get_hierarchy(_session: object, **kwargs: object) -> object:
        assert kwargs["vision_id"] == UUID("44444444-4444-4444-4444-444444444444")
        return make_record(
            vision_id=UUID("44444444-4444-4444-4444-444444444444"),
            root_tasks=(root_task,),
        )

    async def fake_get_stats(_session: object, **kwargs: object) -> object:
        assert kwargs["task_id"] == UUID("55555555-5555-5555-5555-555555555555")
        return tasks.TaskStats(
            total_subtasks=1,
            completed_subtasks=1,
            completion_percentage=0.5,
            total_estimated_effort=90,
            total_actual_effort=60,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tasks, "get_task_with_subtasks", fake_get_task_with_subtasks)
    monkeypatch.setattr(tasks, "get_vision_task_hierarchy", fake_get_hierarchy)
    monkeypatch.setattr(tasks, "get_task_stats", fake_get_stats)

    with_subtasks_exit_code = cli.main(
        ["task", "with-subtasks", "55555555-5555-5555-5555-555555555555"]
    )
    hierarchy_exit_code = cli.main(["task", "hierarchy", "44444444-4444-4444-4444-444444444444"])
    stats_exit_code = cli.main(["task", "stats", "55555555-5555-5555-5555-555555555555"])
    captured = capsys.readouterr()

    assert with_subtasks_exit_code == 0
    assert hierarchy_exit_code == 0
    assert stats_exit_code == 0
    assert "Root task" in captured.out
    assert "Child task" in captured.out
    assert "root_tasks:" in captured.out
    assert "total_subtasks: 1" in captured.out
    assert "completion_percentage: 0.50" in captured.out


def test_main_task_list_prints_header_and_rows(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_tasks(_session: object, **kwargs: object) -> list[object]:
        assert kwargs["vision_id"] is None
        return [
            make_record(
                id=UUID("55555555-5555-5555-5555-555555555555"),
                status="todo",
                vision_id=UUID("66666666-6666-6666-6666-666666666666"),
                parent_task_id=None,
                content="Draft release checklist",
                deleted_at=None,
            )
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tasks, "list_tasks", fake_list_tasks)

    exit_code = cli.main(["task", "list"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "task_id\tstatus\tvision_id\tparent_task_id\tcontent",
        (
            "55555555-5555-5555-5555-555555555555\t"
            "todo\t"
            "66666666-6666-6666-6666-666666666666\t"
            "-\t"
            "Draft release checklist"
        ),
    ]


def test_main_task_list_passes_extended_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_tasks(_session: object, **kwargs: object) -> list[object]:
        assert kwargs["vision_in"] == "44444444-4444-4444-4444-444444444444"
        assert kwargs["status_in"] == "todo,in_progress"
        assert kwargs["exclude_status"] == "cancelled"
        assert kwargs["planning_cycle_type"] == "week"
        assert kwargs["planning_cycle_start_date"] == date(2026, 4, 10)
        assert kwargs["content"] == "Draft release checklist"
        return []

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tasks, "list_tasks", fake_list_tasks)

    exit_code = cli.main(
        [
            "task",
            "list",
            "--vision-in",
            "44444444-4444-4444-4444-444444444444",
            "--status-in",
            "todo,in_progress",
            "--exclude-status",
            "cancelled",
            "--planning-cycle-type",
            "week",
            "--planning-cycle-start-date",
            "2026-04-10",
            "--content",
            "Draft release checklist",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "No tasks found." in captured.out


def test_main_task_move_and_reorder_call_services(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_move_task(_session: object, **kwargs: object) -> object:
        assert kwargs["task_id"] == UUID("55555555-5555-5555-5555-555555555555")
        assert kwargs["old_parent_task_id"] == UUID("66666666-6666-6666-6666-666666666666")
        assert kwargs["new_parent_task_id"] == UUID("77777777-7777-7777-7777-777777777777")
        assert kwargs["new_vision_id"] == UUID("88888888-8888-8888-8888-888888888888")
        assert kwargs["new_display_order"] == 3
        return make_record(
            task=make_record(id=UUID("55555555-5555-5555-5555-555555555555")),
            updated_descendants=(),
        )

    async def fake_reorder_tasks(_session: object, **kwargs: object) -> None:
        assert kwargs["task_orders"] == [
            (UUID("55555555-5555-5555-5555-555555555555"), 0),
            (UUID("66666666-6666-6666-6666-666666666666"), 1),
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tasks, "move_task", fake_move_task)
    monkeypatch.setattr(tasks, "reorder_tasks", fake_reorder_tasks)

    move_exit_code = cli.main(
        [
            "task",
            "move",
            "55555555-5555-5555-5555-555555555555",
            "--old-parent-task-id",
            "66666666-6666-6666-6666-666666666666",
            "--new-parent-task-id",
            "77777777-7777-7777-7777-777777777777",
            "--new-vision-id",
            "88888888-8888-8888-8888-888888888888",
            "--new-display-order",
            "3",
        ]
    )
    reorder_exit_code = cli.main(
        [
            "task",
            "reorder",
            "--order",
            "55555555-5555-5555-5555-555555555555:0",
            "--order",
            "66666666-6666-6666-6666-666666666666:1",
        ]
    )
    captured = capsys.readouterr()

    assert move_exit_code == 0
    assert reorder_exit_code == 0
    assert "Moved task 55555555-5555-5555-5555-555555555555" in captured.out
    assert "Reordered tasks: 2" in captured.out


def test_main_task_move_preserves_parent_when_parent_flag_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_move_task(_session: object, **kwargs: object) -> object:
        assert kwargs["task_id"] == UUID("55555555-5555-5555-5555-555555555555")
        assert "new_parent_task_id" not in kwargs
        assert kwargs["new_display_order"] == 4
        return make_record(
            task=make_record(id=UUID("55555555-5555-5555-5555-555555555555")),
            updated_descendants=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tasks, "move_task", fake_move_task)

    exit_code = cli.main(
        [
            "task",
            "move",
            "55555555-5555-5555-5555-555555555555",
            "--new-display-order",
            "4",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Moved task 55555555-5555-5555-5555-555555555555" in captured.out


def test_main_task_batch_delete_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_batch_delete_tasks(
        _session: object,
        *,
        task_ids: list[UUID],
    ) -> object:
        assert task_ids == [
            UUID("11111111-1111-1111-1111-111111111111"),
            UUID("22222222-2222-2222-2222-222222222222"),
        ]
        return make_record(
            deleted_count=2,
            failed_ids=(),
            errors=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tasks, "batch_delete_tasks", fake_batch_delete_tasks)

    exit_code = cli.main(
        [
            "task",
            "batch",
            "delete",
            "--ids",
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Deleted tasks: 2" in captured.out


def test_main_task_update_can_clear_parent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_update_task(_session: object, **kwargs: object) -> object:
        assert kwargs["clear_parent"] is True
        assert kwargs["parent_task_id"] is None
        return make_record(id=UUID("55555555-5555-5555-5555-555555555555"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tasks, "update_task", fake_update_task)

    exit_code = cli.main(
        [
            "task",
            "update",
            "55555555-5555-5555-5555-555555555555",
            "--clear-parent",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated task 55555555-5555-5555-5555-555555555555" in captured.out


def test_main_task_update_can_clear_people(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_update_task(_session: object, **kwargs: object) -> object:
        assert kwargs["clear_people"] is True
        assert kwargs["person_ids"] is None
        return make_record(id=UUID("55555555-5555-5555-5555-555555555555"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tasks, "update_task", fake_update_task)

    exit_code = cli.main(
        [
            "task",
            "update",
            "55555555-5555-5555-5555-555555555555",
            "--clear-people",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated task 55555555-5555-5555-5555-555555555555" in captured.out


def test_main_task_update_rejects_conflicting_clear_planning_cycle_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "task",
            "update",
            "55555555-5555-5555-5555-555555555555",
            "--planning-cycle-type",
            "week",
            "--clear-planning-cycle",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use either planning cycle fields or --clear-planning-cycle, not both." in captured.err


def test_main_task_update_rejects_conflicting_parent_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "task",
            "update",
            "55555555-5555-5555-5555-555555555555",
            "--parent-task-id",
            "66666666-6666-6666-6666-666666666666",
            "--clear-parent",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use either --parent-task-id or --clear-parent, not both." in captured.err


def test_main_timelog_update_rejects_conflicting_clear_notes_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "timelog",
            "update",
            "13131313-1313-1313-1313-131313131313",
            "--notes",
            "done",
            "--clear-notes",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use either --notes or --clear-notes, not both." in captured.err


def test_main_habit_add_creates_habit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_habit(_session: object, **kwargs: object) -> object:
        assert kwargs["title"] == "Daily Exercise"
        assert str(kwargs["start_date"]) == "2026-04-09"
        assert kwargs["duration_days"] == 21
        assert kwargs["cadence_frequency"] == "daily"
        assert kwargs["cadence_weekdays"] is None
        assert kwargs["cadence_monthdays"] is None
        assert kwargs["target_per_cycle"] is None
        return make_record(id=UUID("77777777-7777-7777-7777-777777777777"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habits, "create_habit", fake_create_habit)

    exit_code = cli.main(
        [
            "habit",
            "add",
            "Daily Exercise",
            "--start-date",
            "2026-04-09",
            "--duration-days",
            "21",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created habit 77777777-7777-7777-7777-777777777777" in captured.out


def test_main_habit_add_passes_weekly_cadence_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_habit(_session: object, **kwargs: object) -> object:
        assert kwargs["cadence_frequency"] == "weekly"
        assert kwargs["cadence_weekdays"] == ["saturday", "sunday"]
        assert kwargs["cadence_monthdays"] is None
        assert kwargs["target_per_cycle"] == 1
        return make_record(id=UUID("78787878-7878-7878-7878-787878787878"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habits, "create_habit", fake_create_habit)

    exit_code = cli.main(
        [
            "habit",
            "add",
            "Call Parents",
            "--start-date",
            "2026-04-09",
            "--duration-days",
            "100",
            "--cadence-frequency",
            "weekly",
            "--weekends-only",
            "--target-per-week",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created habit 78787878-7878-7878-7878-787878787878" in captured.out


def test_main_habit_add_passes_monthly_cadence_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_habit(_session: object, **kwargs: object) -> object:
        assert kwargs["cadence_frequency"] == "monthly"
        assert kwargs["cadence_weekdays"] is None
        assert kwargs["cadence_monthdays"] == [1, 15]
        assert kwargs["target_per_cycle"] == 2
        return make_record(id=UUID("79797979-7979-7979-7979-797979797979"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habits, "create_habit", fake_create_habit)

    exit_code = cli.main(
        [
            "habit",
            "add",
            "Monthly cleanup",
            "--start-date",
            "2026-04-09",
            "--duration-days",
            "365",
            "--cadence-frequency",
            "monthly",
            "--monthdays",
            "1,15",
            "--target-per-cycle",
            "2",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created habit 79797979-7979-7979-7979-797979797979" in captured.out


def test_main_habit_list_prints_count(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_habits(_session: object, **kwargs: object) -> list[object]:
        assert kwargs["status"] == "active"
        return [
            make_record(
                id=UUID("77777777-7777-7777-7777-777777777777"),
                deleted_at=None,
                status="active",
                start_date=date(2026, 4, 9),
                duration_days=21,
                cadence_frequency="daily",
                target_per_cycle=1,
                cadence_weekdays=None,
                task_id=None,
                title="Daily Exercise",
            )
        ]

    async def fake_count_habits(_session: object, **kwargs: object) -> int:
        assert kwargs["status"] == "active"
        return 1

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habits, "list_habits", fake_list_habits)
    monkeypatch.setattr(habits, "count_habits", fake_count_habits)

    exit_code = cli.main(["habit", "list", "--status", "active", "--count"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "habit_id\tstatus\tstart_date\tduration_days\tcadence\ttask_id\ttitle",
        (
            "77777777-7777-7777-7777-777777777777\tactive\t2026-04-09\t21\t"
            "daily:1:-\t-\tDaily Exercise"
        ),
        "Total habits: 1",
    ]


def test_main_habit_list_with_stats_prints_header(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_habit_overviews(_session: object, **kwargs: object) -> list[object]:
        assert kwargs["status"] == "active"
        habit = Habit(
            title="Strength training",
            start_date=date(2026, 4, 9),
            duration_days=30,
            cadence_frequency="weekly",
            cadence_weekdays=["monday", "wednesday", "friday"],
            target_per_cycle=3,
            status="active",
        )
        habit.id = UUID("78787878-7878-7878-7878-787878787878")
        return [
            {
                "habit": habit,
                "stats": {
                    "progress_percentage": 66.7,
                    "current_streak": 4,
                    "longest_streak": 6,
                },
            }
        ]

    async def fake_count_habits(_session: object, **kwargs: object) -> int:
        assert kwargs["status"] == "active"
        return 1

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habits, "list_habit_overviews", fake_list_habit_overviews)
    monkeypatch.setattr(habits, "count_habits", fake_count_habits)

    exit_code = cli.main(["habit", "list", "--status", "active", "--with-stats", "--count"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "habit_id\tstatus\tstart_date\tduration_days\tcadence\tprogress_percentage\tcurrent_streak\tlongest_streak\ttitle",
        (
            "78787878-7878-7878-7878-787878787878\tactive\t2026-04-09\t30\t"
            "weekly:3:monday,wednesday,friday\t66.7\t4\t6\tStrength training"
        ),
        "Total habits: 1",
    ]


def test_main_habit_task_associations_prints_header(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    habit = Habit(
        title="Daily Exercise",
        start_date=date(2026, 4, 9),
        duration_days=21,
        cadence_frequency="daily",
        target_per_cycle=1,
        status="active",
        task_id=UUID("66666666-6666-6666-6666-666666666666"),
    )
    habit.id = UUID("77777777-7777-7777-7777-777777777777")

    async def fake_get_habit_task_associations(_session: object) -> dict[UUID, list[Habit]]:
        return {UUID("66666666-6666-6666-6666-666666666666"): [habit]}

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habits, "get_habit_task_associations", fake_get_habit_task_associations)

    exit_code = cli.main(["habit", "task-associations"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "task_id\thabit_id\thabit_status\thabit_start_date\thabit_title",
        (
            "66666666-6666-6666-6666-666666666666\t"
            "77777777-7777-7777-7777-777777777777\tactive\t2026-04-09\t"
            "Daily Exercise"
        ),
    ]


def test_main_habit_update_rejects_conflicting_clear_task_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "habit",
            "update",
            "77777777-7777-7777-7777-777777777777",
            "--task-id",
            "11111111-1111-1111-1111-111111111111",
            "--clear-task",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use either --task-id or --clear-task, not both." in captured.err


def test_main_habit_update_rejects_conflicting_clear_weekdays_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "habit",
            "update",
            "77777777-7777-7777-7777-777777777777",
            "--weekdays",
            "monday,wednesday,friday",
            "--clear-weekdays",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use either --weekdays / --weekends-only or --clear-weekdays, not both." in captured.err


def test_main_habit_action_list_prints_count(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_habit_actions(_session: object, **kwargs: object) -> list[object]:
        assert kwargs["date_values"] == (date(2026, 4, 9),)
        assert kwargs["start_date"] is None
        assert kwargs["end_date"] is None
        return [
            make_record(
                id=UUID("88888888-8888-8888-8888-888888888888"),
                deleted_at=None,
                status="pending",
                action_date=date(2026, 4, 9),
                habit_id=UUID("77777777-7777-7777-7777-777777777777"),
                habit_title="Daily Exercise",
            )
        ]

    async def fake_count_habit_actions(_session: object, **kwargs: object) -> int:
        assert kwargs["date_values"] == (date(2026, 4, 9),)
        assert kwargs["start_date"] is None
        assert kwargs["end_date"] is None
        return 1

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habit_actions, "list_habit_actions", fake_list_habit_actions)
    monkeypatch.setattr(habit_actions, "count_habit_actions", fake_count_habit_actions)

    exit_code = cli.main(["habit-action", "list", "--date", "2026-04-09", "--count"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "habit_action_id\tstatus\taction_date\thabit_id\thabit_title",
        (
            "88888888-8888-8888-8888-888888888888\tpending\t2026-04-09\t"
            "77777777-7777-7777-7777-777777777777\tDaily Exercise"
        ),
        "Total habit actions: 1",
    ]


def test_main_habit_action_log_updates_by_habit_and_date(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_update_habit_action_by_date(_session: object, **kwargs: object) -> object:
        assert kwargs["habit_id"] == UUID("77777777-7777-7777-7777-777777777777")
        assert kwargs["action_date"] == date(2026, 4, 9)
        assert kwargs["status"] == "done"
        assert kwargs["notes"] == "Completed"
        assert kwargs["clear_notes"] is False
        return make_record(id=UUID("88888888-8888-8888-8888-888888888888"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(
        habit_actions,
        "update_habit_action_by_date",
        fake_update_habit_action_by_date,
    )

    exit_code = cli.main(
        [
            "habit-action",
            "log",
            "--habit-id",
            "77777777-7777-7777-7777-777777777777",
            "--date",
            "2026-04-09",
            "--status",
            "done",
            "--notes",
            "Completed",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated habit action 88888888-8888-8888-8888-888888888888" in captured.out


def test_main_habit_action_list_passes_discrete_date_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_habit_actions(_session: object, **kwargs: object) -> list[object]:
        assert kwargs["date_values"] == (date(2026, 4, 9), date(2026, 4, 11))
        assert kwargs["start_date"] is None
        assert kwargs["end_date"] is None
        return []

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habit_actions, "list_habit_actions", fake_list_habit_actions)

    exit_code = cli.main(["habit-action", "list", "--date", "2026-04-09", "--date", "2026-04-11"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "No habit actions found."


def test_main_habit_action_update_can_clear_notes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_update_habit_action(_session: object, **kwargs: object) -> object:
        assert kwargs["clear_notes"] is True
        assert kwargs["notes"] is None
        return make_record(id=UUID("88888888-8888-8888-8888-888888888888"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habit_actions, "update_habit_action", fake_update_habit_action)

    exit_code = cli.main(
        [
            "habit-action",
            "update",
            "88888888-8888-8888-8888-888888888888",
            "--clear-notes",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated habit action 88888888-8888-8888-8888-888888888888" in captured.out
