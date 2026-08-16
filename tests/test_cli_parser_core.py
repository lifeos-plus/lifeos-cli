from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from lifeos_cli.cli import build_parser


def test_cli_parser_uses_lifeos_command_name() -> None:
    parser = build_parser()

    assert parser.prog == "lifeos"


def test_cli_parser_supports_short_version_flag(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["-v"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert captured.out.startswith("lifeos ")


def test_cli_parser_supports_note_add_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["note", "add", "a new note"])

    assert args.resource == "note"
    assert args.note_command == "add"
    assert args.content == "a new note"


def test_cli_parser_supports_note_add_from_stdin() -> None:
    parser = build_parser()
    args = parser.parse_args(["note", "add", "--stdin"])

    assert args.resource == "note"
    assert args.note_command == "add"
    assert args.stdin is True
    assert args.content is None


def test_cli_parser_supports_note_show_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["note", "show", "11111111-1111-1111-1111-111111111111"])

    assert args.resource == "note"
    assert args.note_command == "show"
    assert str(args.note_id) == "11111111-1111-1111-1111-111111111111"


def test_cli_parser_supports_init_preference_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "init",
            "--database-url",
            "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos",
            "--timezone",
            "America/Toronto",
            "--language",
            "zh-Hans",
            "--day-starts-at",
            "04:00",
            "--week-starts-on",
            "sunday",
            "--vision-experience-rate-per-hour",
            "120",
        ]
    )

    assert args.database_url == "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos"
    assert args.timezone == "America/Toronto"
    assert args.language == "zh-Hans"
    assert args.day_starts_at == "04:00"
    assert args.week_starts_on == "sunday"
    assert args.vision_experience_rate_per_hour == 120


def test_cli_parser_supports_config_set_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["config", "set", "preferences.timezone", "America/Toronto"])

    assert args.resource == "config"
    assert args.config_command == "set"
    assert args.key == "preferences.timezone"
    assert args.value == "America/Toronto"


def test_cli_parser_supports_note_search_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["note", "search", "meeting notes", "--limit", "20"])

    assert args.resource == "note"
    assert args.note_command == "search"
    assert args.query == "meeting notes"
    assert args.limit == 20


def test_cli_parser_supports_note_batch_update_content_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "note",
            "batch",
            "update-content",
            "--ids",
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "--find-text",
            "draft",
            "--replace-text",
            "final",
        ]
    )

    assert args.resource == "note"
    assert args.note_command == "batch"
    assert args.note_batch_command == "update-content"
    assert args.find_text == "draft"
    assert args.replace_text == "final"
    assert len(args.note_ids) == 2


def test_cli_parser_supports_data_commands() -> None:
    parser = build_parser()

    export_args = parser.parse_args(["data", "export", "timelog", "--format", "jsonl"])
    bundle_args = parser.parse_args(["data", "import", "bundle", "--file", "backup.zip"])
    batch_update_args = parser.parse_args(
        ["data", "batch-update", "task", "--file", "task-patch.jsonl"]
    )
    batch_delete_args = parser.parse_args(
        ["data", "batch-delete", "event", "--id", "11111111-1111-1111-1111-111111111111"]
    )

    assert export_args.resource == "data"
    assert export_args.data_command == "export"
    assert export_args.target == "timelog"
    assert export_args.format == "jsonl"
    assert bundle_args.data_command == "import"
    assert bundle_args.target == "bundle"
    assert batch_update_args.data_command == "batch-update"
    assert batch_update_args.target == "task"
    assert batch_delete_args.data_command == "batch-delete"
    assert batch_delete_args.target == "event"


def test_cli_parser_supports_finance_commands() -> None:
    parser = build_parser()

    tree_args = parser.parse_args(
        ["finance", "tree-add", "Personal Finance", "--primary-currency", "USD", "--default"]
    )
    node_args = parser.parse_args(
        [
            "finance",
            "node-add",
            "11111111-1111-1111-1111-111111111111",
            "Checking",
            "--parent-id",
            "22222222-2222-2222-2222-222222222222",
        ]
    )
    snapshot_args = parser.parse_args(
        [
            "finance",
            "snapshot-add",
            "11111111-1111-1111-1111-111111111111",
            "--rate-snapshot-id",
            "33333333-3333-3333-3333-333333333333",
            "--entry",
            "22222222-2222-2222-2222-222222222222:100:USD",
        ]
    )
    rate_snapshot_args = parser.parse_args(
        [
            "finance",
            "rate-snapshot-add",
            "--rate",
            "EUR:1.1:USD",
        ]
    )

    assert tree_args.resource == "finance"
    assert tree_args.finance_command == "tree-add"
    assert tree_args.primary_currency == "USD"
    assert tree_args.default is True
    assert node_args.finance_command == "node-add"
    assert str(node_args.parent_id) == "22222222-2222-2222-2222-222222222222"
    assert snapshot_args.finance_command == "snapshot-add"
    assert snapshot_args.entries[0].amount == Decimal("100")
    assert str(snapshot_args.rate_snapshot_id) == "33333333-3333-3333-3333-333333333333"
    assert rate_snapshot_args.finance_command == "rate-snapshot-add"
    assert rate_snapshot_args.rates[0].base_currency == "EUR"
    assert rate_snapshot_args.rates[0].quote_currency == "USD"
    assert rate_snapshot_args.rates[0].rate == Decimal("1.1")


def test_cli_parser_supports_timelog_stats_commands() -> None:
    parser = build_parser()

    day_args = parser.parse_args(["timelog", "stats", "day", "--date", "2026-04-10"])
    range_args = parser.parse_args(
        [
            "timelog",
            "stats",
            "range",
            "--start-date",
            "2026-04-01",
            "--end-date",
            "2026-04-30",
        ]
    )
    month_args = parser.parse_args(["timelog", "stats", "month", "--month", "2026-04"])
    rebuild_args = parser.parse_args(["timelog", "stats", "rebuild", "--all"])

    assert day_args.resource == "timelog"
    assert day_args.timelog_command == "stats"
    assert day_args.timelog_stats_command == "day"
    assert day_args.target_date == date(2026, 4, 10)
    assert range_args.timelog_stats_command == "range"
    assert range_args.start_date == date(2026, 4, 1)
    assert range_args.end_date == date(2026, 4, 30)
    assert month_args.timelog_stats_command == "month"
    assert month_args.month == date(2026, 4, 1)
    assert rebuild_args.timelog_stats_command == "rebuild"
    assert rebuild_args.rebuild_all is True


def test_cli_parser_supports_area_add_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "area",
            "add",
            "Health",
            "--display-order",
            "2",
        ]
    )

    assert args.resource == "area"
    assert args.area_command == "add"
    assert args.name == "Health"
    assert args.display_order == 2


def test_cli_parser_supports_area_update_clear_icon_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "area",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-icon",
        ]
    )

    assert args.resource == "area"
    assert args.area_command == "update"
    assert args.clear_icon is True


def test_cli_parser_supports_event_add_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "event",
            "add",
            "Doctor appointment",
            "--start-time",
            "2026-04-10T09:00:00",
            "--person-id",
            "11111111-1111-1111-1111-111111111111",
        ]
    )

    assert args.resource == "event"
    assert args.event_command == "add"
    assert args.title == "Doctor appointment"
    assert len(args.person_ids) == 1
    assert args.event_type == "appointment"


def test_cli_parser_supports_event_list_by_local_date() -> None:
    parser = build_parser()
    args = parser.parse_args(["event", "list", "--date", "2026-04-10"])

    assert args.resource == "event"
    assert args.event_command == "list"
    assert args.date_values == [date(2026, 4, 10)]


def test_cli_parser_supports_event_recurrence_add_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "event",
            "add",
            "Daily review",
            "--start-time",
            "2026-04-10T09:00:00",
            "--recurrence-frequency",
            "daily",
            "--recurrence-interval",
            "2",
            "--recurrence-count",
            "5",
            "--recurrence-weekdays",
            "monday,wednesday,friday",
            "--recurrence-month-days",
            "1,15,-1",
            "--recurrence-months",
            "1,6,12",
            "--recurrence-weekday-ordinal",
            "2:monday",
        ]
    )

    assert args.resource == "event"
    assert args.event_command == "add"
    assert args.recurrence_frequency == "daily"
    assert args.recurrence_interval == 2
    assert args.recurrence_count == 5
    assert args.recurrence_weekdays == ["monday", "wednesday", "friday"]
    assert args.recurrence_month_days == [1, 15, -1]
    assert args.recurrence_months == [1, 6, 12]
    assert args.recurrence_weekday_ordinals == [{"ordinal": 2, "weekday": "monday"}]


def test_cli_parser_supports_event_monthly_recurrence_add_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "event",
            "add",
            "Monthly review",
            "--start-time",
            "2026-04-30T16:00:00",
            "--recurrence-frequency",
            "monthly",
        ]
    )

    assert args.resource == "event"
    assert args.event_command == "add"
    assert args.recurrence_frequency == "monthly"


def test_cli_parser_supports_event_type_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "event",
            "list",
            "--type",
            "deadline",
            "--date",
            "2026-04-10",
        ]
    )

    assert args.resource == "event"
    assert args.event_command == "list"
    assert args.event_type == "deadline"


def test_cli_parser_supports_event_update_scope_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "event",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--scope",
            "single",
            "--instance-start",
            "2026-04-10T09:00:00",
        ]
    )

    assert args.resource == "event"
    assert args.event_command == "update"
    assert args.scope == "single"
    assert args.instance_start.isoformat() == "2026-04-10T09:00:00"


def test_cli_parser_supports_people_add_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["people", "add", "Alice", "--nickname", "ally"])

    assert args.resource == "people"
    assert args.people_command == "add"
    assert args.name == "Alice"
    assert args.nickname == ["ally"]


def test_cli_parser_supports_note_add_association_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "note",
            "add",
            "Association note",
            "--person-id",
            "11111111-1111-1111-1111-111111111111",
            "--task-id",
            "22222222-2222-2222-2222-222222222222",
            "--timelog-id",
            "33333333-3333-3333-3333-333333333333",
        ]
    )

    assert args.resource == "note"
    assert args.note_command == "add"
    assert args.person_ids == [UUID("11111111-1111-1111-1111-111111111111")]
    assert args.task_ids == [UUID("22222222-2222-2222-2222-222222222222")]
    assert args.timelog_ids == [UUID("33333333-3333-3333-3333-333333333333")]


def test_cli_parser_supports_note_add_extended_association_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "note",
            "add",
            "Graph note",
            "--tag-id",
            "11111111-1111-1111-1111-111111111111",
            "--task-id",
            "22222222-2222-2222-2222-222222222222",
            "--task-id",
            "33333333-3333-3333-3333-333333333333",
            "--vision-id",
            "44444444-4444-4444-4444-444444444444",
            "--event-id",
            "55555555-5555-5555-5555-555555555555",
        ]
    )

    assert args.resource == "note"
    assert args.note_command == "add"
    assert args.tag_ids == [UUID("11111111-1111-1111-1111-111111111111")]
    assert args.task_ids == [
        UUID("22222222-2222-2222-2222-222222222222"),
        UUID("33333333-3333-3333-3333-333333333333"),
    ]
    assert args.vision_ids == [UUID("44444444-4444-4444-4444-444444444444")]
    assert args.event_ids == [UUID("55555555-5555-5555-5555-555555555555")]


def test_cli_parser_supports_note_update_relation_only_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "note",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-timelogs",
        ]
    )

    assert args.resource == "note"
    assert args.note_command == "update"
    assert args.content is None
    assert args.clear_timelogs is True


def test_cli_parser_supports_note_update_clear_tasks_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "note",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-tasks",
        ]
    )

    assert args.resource == "note"
    assert args.note_command == "update"
    assert args.clear_tasks is True


def test_cli_parser_supports_note_list_relation_filters() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "note",
            "list",
            "--person-id",
            "11111111-1111-1111-1111-111111111111",
            "--timelog-id",
            "22222222-2222-2222-2222-222222222222",
            "--with-counts",
        ]
    )

    assert args.resource == "note"
    assert args.note_command == "list"
    assert args.person_id == UUID("11111111-1111-1111-1111-111111111111")
    assert args.timelog_id == UUID("22222222-2222-2222-2222-222222222222")
    assert args.with_counts is True


def test_cli_parser_supports_schedule_show_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["schedule", "show", "--hide-overdue-unfinished"])

    assert args.resource == "schedule"
    assert args.schedule_command == "show"
    assert args.target_date is None
    assert args.hide_overdue_unfinished is True


def test_cli_parser_supports_schedule_list_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["schedule", "list", "--date", "2026-04-10", "--date", "2026-04-16"])

    assert args.resource == "schedule"
    assert args.schedule_command == "list"
    assert args.date_values == [date(2026, 4, 10), date(2026, 4, 16)]
    assert args.hide_overdue_unfinished is False


def test_cli_parser_supports_schedule_list_explicit_date_range_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "schedule",
            "list",
            "--start-date",
            "2026-04-10",
            "--end-date",
            "2026-04-16",
        ]
    )

    assert args.resource == "schedule"
    assert args.schedule_command == "list"
    assert args.start_date == date(2026, 4, 10)
    assert args.end_date == date(2026, 4, 16)
    assert args.date_values is None
    assert args.hide_overdue_unfinished is False


def test_cli_parser_supports_people_update_clear_location_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "people",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-location",
        ]
    )

    assert args.resource == "people"
    assert args.people_command == "update"
    assert args.clear_location is True


def test_cli_parser_supports_task_add_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "task",
            "add",
            "Draft release checklist",
            "--vision-id",
            "11111111-1111-1111-1111-111111111111",
            "--priority",
            "3",
        ]
    )

    assert args.resource == "task"
    assert args.task_command == "add"
    assert args.content == "Draft release checklist"
    assert str(args.vision_id) == "11111111-1111-1111-1111-111111111111"
    assert args.priority == 3


def test_cli_parser_supports_planning_show_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "planning",
            "show",
            "--cycle-type",
            "7years",
            "--at",
            "2026-08-11",
            "--depth",
            "2",
            "--status",
            "todo,in_progress",
            "--vision",
            "11111111-1111-1111-1111-111111111111",
            "--limit",
            "50",
        ]
    )

    assert args.resource == "planning"
    assert args.planning_command == "show"
    assert args.cycle_type == "7years"
    assert args.at == date(2026, 8, 11)
    assert args.start is None
    assert args.depth == 2
    assert args.status == "todo,in_progress"
    assert args.vision == "11111111-1111-1111-1111-111111111111"
    assert args.limit == 50


def test_cli_parser_supports_timelog_list_by_local_date() -> None:
    parser = build_parser()
    args = parser.parse_args(["timelog", "list", "--date", "2026-04-10"])

    assert args.resource == "timelog"
    assert args.timelog_command == "list"
    assert args.date_values == [date(2026, 4, 10)]


def test_cli_parser_supports_timelog_list_search_filters() -> None:
    parser = build_parser()
    args = parser.parse_args(
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
            "--with-counts",
            "--count",
        ]
    )

    assert args.resource == "timelog"
    assert args.timelog_command == "list"
    assert args.query == "deep work"
    assert args.notes_contains == "focused"
    assert args.area_name == "Work"
    assert args.without_task is True
    assert args.with_counts is True
    assert args.count is True


def test_cli_parser_supports_timelog_search_advanced_filters() -> None:
    parser = build_parser()
    args = parser.parse_args(
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

    assert args.resource == "timelog"
    assert args.timelog_command == "search"
    assert args.query == "洗"
    assert args.window_start.isoformat() == "2026-06-16T16:00:00+00:00"
    assert args.window_end.isoformat() == "2026-06-17T15:59:59.999000+00:00"
    assert args.limit == 500
    assert args.count is True


def test_cli_parser_requires_query_for_timelog_search() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["timelog", "search", "--date", "2026-04-10"])

    assert exc_info.value.code == 2

    args = parser.parse_args(["timelog", "search", "--query", "deep work"])
    assert args.timelog_command == "search"
    assert args.query == "deep work"


def test_cli_parser_keeps_query_optional_for_timelog_list() -> None:
    parser = build_parser()

    args = parser.parse_args(["timelog", "list", "--date", "2026-04-10"])

    assert args.timelog_command == "list"
    assert args.query is None


def test_cli_parser_supports_clear_advanced_recurrence_alias() -> None:
    parser = build_parser()
    event_uuid = "11111111-1111-1111-1111-111111111111"

    args = parser.parse_args(["event", "update", event_uuid, "--clear-advanced-recurrence"])
    assert args.clear_recurrence_rule is True

    legacy_args = parser.parse_args(["event", "update", event_uuid, "--clear-recurrence-rule"])
    assert legacy_args.clear_recurrence_rule is True


def test_cli_parser_supports_task_list_person_filter() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "task",
            "list",
            "--person-id",
            "11111111-1111-1111-1111-111111111111",
        ]
    )

    assert args.resource == "task"
    assert args.task_command == "list"
    assert str(args.person_id) == "11111111-1111-1111-1111-111111111111"


def test_cli_parser_supports_task_list_extended_filters() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "task",
            "list",
            "--vision-in",
            "11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222",
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

    assert args.resource == "task"
    assert args.task_command == "list"
    assert args.status_in == "todo,in_progress"
    assert args.exclude_status == "cancelled"
    assert args.planning_cycle_type == "week"
    assert args.planning_cycle_start_date == "2026-04-10"
    assert args.content == "Draft release checklist"


def test_cli_parser_supports_task_read_model_commands() -> None:
    parser = build_parser()

    with_subtasks_args = parser.parse_args(
        ["task", "with-subtasks", "11111111-1111-1111-1111-111111111111"]
    )
    hierarchy_args = parser.parse_args(
        ["task", "hierarchy", "22222222-2222-2222-2222-222222222222"]
    )
    stats_args = parser.parse_args(["task", "stats", "33333333-3333-3333-3333-333333333333"])

    assert with_subtasks_args.resource == "task"
    assert with_subtasks_args.task_command == "with-subtasks"
    assert str(with_subtasks_args.task_id) == "11111111-1111-1111-1111-111111111111"
    assert hierarchy_args.resource == "task"
    assert hierarchy_args.task_command == "hierarchy"
    assert str(hierarchy_args.vision_id) == "22222222-2222-2222-2222-222222222222"
    assert stats_args.resource == "task"
    assert stats_args.task_command == "stats"
    assert str(stats_args.task_id) == "33333333-3333-3333-3333-333333333333"


def test_cli_parser_supports_task_move_and_reorder_commands() -> None:
    parser = build_parser()

    move_args = parser.parse_args(
        [
            "task",
            "move",
            "11111111-1111-1111-1111-111111111111",
            "--old-parent-task-id",
            "22222222-2222-2222-2222-222222222222",
            "--new-parent-task-id",
            "33333333-3333-3333-3333-333333333333",
            "--new-vision-id",
            "44444444-4444-4444-4444-444444444444",
            "--new-display-order",
            "2",
        ]
    )
    reorder_args = parser.parse_args(
        [
            "task",
            "reorder",
            "--order",
            "11111111-1111-1111-1111-111111111111:0",
            "--order",
            "22222222-2222-2222-2222-222222222222:1",
        ]
    )

    assert move_args.resource == "task"
    assert move_args.task_command == "move"
    assert str(move_args.old_parent_task_id) == "22222222-2222-2222-2222-222222222222"
    assert str(move_args.new_parent_task_id) == "33333333-3333-3333-3333-333333333333"
    assert str(move_args.new_vision_id) == "44444444-4444-4444-4444-444444444444"
    assert move_args.new_display_order == 2
    assert reorder_args.resource == "task"
    assert reorder_args.task_command == "reorder"
    assert reorder_args.order == [
        "11111111-1111-1111-1111-111111111111:0",
        "22222222-2222-2222-2222-222222222222:1",
    ]


def test_cli_parser_supports_timelog_add_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "timelog",
            "add",
            "Deep work",
            "--start-time",
            "2026-04-10T13:00:00",
            "--end-time",
            "2026-04-10T14:30:00",
            "--tracking-method",
            "manual",
        ]
    )

    assert args.resource == "timelog"
    assert args.timelog_command == "add"
    assert args.title == "Deep work"
    assert args.tracking_method == "manual"


def test_cli_parser_supports_timelog_add_quick_batch_mode() -> None:
    parser = build_parser()
    args = parser.parse_args(
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

    assert args.resource == "timelog"
    assert args.timelog_command == "add"
    assert args.entry_lines == ["0700 Breakfast", "0830 Deep work"]
    assert args.first_start_time.isoformat() == "2026-04-10T06:30:00"
    assert args.title is None


def test_cli_parser_supports_timelog_add_quick_batch_from_stdin() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "timelog",
            "add",
            "--stdin",
            "--first-start-time",
            "2026-04-10T06:30:00",
        ]
    )

    assert args.resource == "timelog"
    assert args.timelog_command == "add"
    assert args.stdin is True
    assert args.yes is False
    assert args.entry_lines is None
    assert args.file is None
    assert args.first_start_time.isoformat() == "2026-04-10T06:30:00"
    assert args.title is None


def test_cli_parser_supports_vision_update_clear_area_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "vision",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-area",
        ]
    )

    assert args.resource == "vision"
    assert args.vision_command == "update"
    assert args.clear_area is True


def test_cli_parser_supports_vision_update_clear_people_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "vision",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-people",
        ]
    )

    assert args.resource == "vision"
    assert args.vision_command == "update"
    assert args.clear_people is True


def test_cli_parser_supports_vision_experience_commands() -> None:
    parser = build_parser()

    add_args = parser.parse_args(
        [
            "vision",
            "add-experience",
            "11111111-1111-1111-1111-111111111111",
            "--points",
            "120",
        ]
    )
    sync_args = parser.parse_args(
        ["vision", "sync-experience", "11111111-1111-1111-1111-111111111111"]
    )
    harvest_args = parser.parse_args(["vision", "harvest", "11111111-1111-1111-1111-111111111111"])

    assert add_args.resource == "vision"
    assert add_args.vision_command == "add-experience"
    assert add_args.experience_points == 120
    assert sync_args.vision_command == "sync-experience"
    assert harvest_args.vision_command == "harvest"


def test_cli_parser_supports_vision_read_model_commands() -> None:
    parser = build_parser()

    with_tasks_args = parser.parse_args(
        ["vision", "with-tasks", "11111111-1111-1111-1111-111111111111"]
    )
    stats_args = parser.parse_args(["vision", "stats", "11111111-1111-1111-1111-111111111111"])

    assert with_tasks_args.resource == "vision"
    assert with_tasks_args.vision_command == "with-tasks"
    assert stats_args.resource == "vision"
    assert stats_args.vision_command == "stats"


def test_cli_parser_supports_tag_update_clear_color_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "tag",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-color",
        ]
    )

    assert args.resource == "tag"
    assert args.tag_command == "update"
    assert args.clear_color is True


def test_cli_parser_supports_tag_list_person_filter() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "tag",
            "list",
            "--person-id",
            "11111111-1111-1111-1111-111111111111",
        ]
    )

    assert args.resource == "tag"
    assert args.tag_command == "list"
    assert str(args.person_id) == "11111111-1111-1111-1111-111111111111"


def test_cli_parser_supports_task_batch_delete_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "task",
            "batch",
            "delete",
            "--ids",
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ]
    )

    assert args.resource == "task"
    assert args.task_command == "batch"
    assert args.task_batch_command == "delete"
    assert len(args.task_ids) == 2


def test_cli_parser_supports_task_update_clear_parent_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "task",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-parent",
        ]
    )

    assert args.resource == "task"
    assert args.task_command == "update"
    assert str(args.task_id) == "11111111-1111-1111-1111-111111111111"
    assert args.clear_parent is True


def test_cli_parser_supports_task_update_clear_people_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "task",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-people",
        ]
    )

    assert args.resource == "task"
    assert args.task_command == "update"
    assert args.clear_people is True


def test_cli_parser_supports_habit_add_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
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

    assert args.resource == "habit"
    assert args.habit_command == "add"
    assert args.title == "Daily Exercise"
    assert args.duration_days == 21


def test_cli_parser_supports_habit_add_weekly_cadence_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
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

    assert args.resource == "habit"
    assert args.habit_command == "add"
    assert args.cadence_frequency == "weekly"
    assert args.weekends_only is True
    assert args.target_per_cycle == 1


def test_cli_parser_supports_habit_add_monthly_cadence_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
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

    assert args.resource == "habit"
    assert args.habit_command == "add"
    assert args.cadence_frequency == "monthly"
    assert args.monthdays == [1, 15]
    assert args.target_per_cycle == 2


def test_cli_parser_supports_habit_list_count_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["habit", "list", "--status", "active", "--count"])

    assert args.resource == "habit"
    assert args.habit_command == "list"
    assert args.status == "active"
    assert args.count is True


def test_cli_parser_supports_habit_update_clear_task_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "habit",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-task",
        ]
    )

    assert args.resource == "habit"
    assert args.habit_command == "update"
    assert str(args.habit_id) == "11111111-1111-1111-1111-111111111111"
    assert args.clear_task is True


def test_cli_parser_supports_habit_update_clear_weekdays_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "habit",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-weekdays",
        ]
    )

    assert args.resource == "habit"
    assert args.habit_command == "update"
    assert str(args.habit_id) == "11111111-1111-1111-1111-111111111111"
    assert args.clear_weekdays is True


def test_cli_parser_supports_habit_update_clear_monthdays_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "habit",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-monthdays",
        ]
    )

    assert args.resource == "habit"
    assert args.habit_command == "update"
    assert str(args.habit_id) == "11111111-1111-1111-1111-111111111111"
    assert args.clear_monthdays is True


def test_cli_parser_supports_habit_action_list_by_date_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "habit-action",
            "list",
            "--date",
            "2026-04-09",
        ]
    )

    assert args.resource == "habit-action"
    assert args.habit_action_command == "list"
    assert args.date_values == [date(2026, 4, 9)]


def test_cli_parser_supports_habit_action_list_count_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["habit-action", "list", "--date", "2026-04-09", "--count"])

    assert args.resource == "habit-action"
    assert args.habit_action_command == "list"
    assert args.count is True


def test_cli_parser_supports_habit_action_log_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "habit-action",
            "log",
            "--habit-id",
            "77777777-7777-7777-7777-777777777777",
            "--date",
            "2026-04-09",
            "--status",
            "done",
        ]
    )

    assert args.resource == "habit-action"
    assert args.habit_action_command == "log"
    assert args.habit_id == UUID("77777777-7777-7777-7777-777777777777")
    assert str(args.action_date) == "2026-04-09"
    assert args.status == "done"


def test_cli_parser_supports_event_update_clear_people_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "event",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-people",
        ]
    )

    assert args.resource == "event"
    assert args.event_command == "update"
    assert args.clear_people is True


def test_cli_parser_supports_timelog_update_clear_notes_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "timelog",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--clear-notes",
        ]
    )

    assert args.resource == "timelog"
    assert args.timelog_command == "update"
    assert args.clear_notes is True


def test_cli_parser_supports_timelog_batch_update_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "timelog",
            "batch",
            "update",
            "--ids",
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "--find-title-text",
            "deep",
            "--replace-title-text",
            "focused",
            "--clear-task",
            "--person-id",
            "33333333-3333-3333-3333-333333333333",
        ]
    )

    assert args.resource == "timelog"
    assert args.timelog_command == "batch"
    assert args.timelog_batch_command == "update"
    assert args.find_title_text == "deep"
    assert args.replace_title_text == "focused"
    assert args.clear_task is True
    assert args.person_ids == [UUID("33333333-3333-3333-3333-333333333333")]
    assert len(args.timelog_ids) == 2


@pytest.mark.parametrize(
    ("argv",),
    [
        (["note", "delete", "11111111-1111-1111-1111-111111111111", "--hard"],),
        (
            [
                "note",
                "batch",
                "delete",
                "--ids",
                "11111111-1111-1111-1111-111111111111",
                "--hard",
            ],
        ),
        (["area", "delete", "11111111-1111-1111-1111-111111111111", "--hard"],),
        (
            [
                "area",
                "batch",
                "delete",
                "--ids",
                "11111111-1111-1111-1111-111111111111",
                "--hard",
            ],
        ),
        (["tag", "delete", "11111111-1111-1111-1111-111111111111", "--hard"],),
        (
            [
                "tag",
                "batch",
                "delete",
                "--ids",
                "11111111-1111-1111-1111-111111111111",
                "--hard",
            ],
        ),
        (["people", "delete", "11111111-1111-1111-1111-111111111111", "--hard"],),
        (
            [
                "people",
                "batch",
                "delete",
                "--ids",
                "11111111-1111-1111-1111-111111111111",
                "--hard",
            ],
        ),
        (["vision", "delete", "11111111-1111-1111-1111-111111111111", "--hard"],),
        (
            [
                "vision",
                "batch",
                "delete",
                "--ids",
                "11111111-1111-1111-1111-111111111111",
                "--hard",
            ],
        ),
        (["task", "delete", "11111111-1111-1111-1111-111111111111", "--hard"],),
        (
            [
                "task",
                "batch",
                "delete",
                "--ids",
                "11111111-1111-1111-1111-111111111111",
                "--hard",
            ],
        ),
        (["habit", "delete", "11111111-1111-1111-1111-111111111111", "--hard"],),
        (
            [
                "habit",
                "batch",
                "delete",
                "--ids",
                "11111111-1111-1111-1111-111111111111",
                "--hard",
            ],
        ),
        (["habit-action", "delete", "11111111-1111-1111-1111-111111111111", "--hard"],),
        (["event", "delete", "11111111-1111-1111-1111-111111111111", "--hard"],),
        (
            [
                "event",
                "batch",
                "delete",
                "--ids",
                "11111111-1111-1111-1111-111111111111",
                "--hard",
            ],
        ),
        (["timelog", "delete", "11111111-1111-1111-1111-111111111111", "--hard"],),
        (
            [
                "timelog",
                "batch",
                "delete",
                "--ids",
                "11111111-1111-1111-1111-111111111111",
                "--hard",
            ],
        ),
    ],
)
def test_cli_parser_rejects_hard_delete_flags(argv: list[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)


@pytest.mark.parametrize(
    ("argv",),
    [
        (["timelog", "restore", "11111111-1111-1111-1111-111111111111"],),
        (
            [
                "timelog",
                "batch",
                "restore",
                "--ids",
                "11111111-1111-1111-1111-111111111111",
            ],
        ),
    ],
)
def test_cli_parser_rejects_removed_timelog_restore_commands(argv: list[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)
