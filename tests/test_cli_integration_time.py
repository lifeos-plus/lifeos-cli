from __future__ import annotations

from tests.cli_integration_support import (
    INTEGRATION_PYTESTMARK,
    IntegrationContext,
    assert_ok,
    extract_created_id,
    init_context,
    run_lifeos,
)

pytestmark = INTEGRATION_PYTESTMARK


def test_real_cli_event_and_timelog_workflow(integration_context: IntegrationContext) -> None:
    init_context(integration_context)

    area_result = run_lifeos(integration_context, "area", "add", "Health")
    assert_ok(area_result)
    area_id = extract_created_id(area_result.stdout)

    vision_result = run_lifeos(integration_context, "vision", "add", "Improve fitness")
    assert_ok(vision_result)
    vision_id = extract_created_id(vision_result.stdout)

    task_result = run_lifeos(
        integration_context,
        "task",
        "add",
        "Morning run",
        "--vision-id",
        vision_id,
    )
    assert_ok(task_result)
    task_id = extract_created_id(task_result.stdout)

    person_result = run_lifeos(integration_context, "person", "add", "Coach")
    assert_ok(person_result)
    person_id = extract_created_id(person_result.stdout)

    event_tag_result = run_lifeos(
        integration_context,
        "tag",
        "add",
        "calendar",
        "--entity-type",
        "event",
        "--category",
        "context",
    )
    assert_ok(event_tag_result)
    event_tag_id = extract_created_id(event_tag_result.stdout)

    timelog_tag_result = run_lifeos(
        integration_context,
        "tag",
        "add",
        "tracked",
        "--entity-type",
        "timelog",
        "--category",
        "context",
    )
    assert_ok(timelog_tag_result)
    timelog_tag_id = extract_created_id(timelog_tag_result.stdout)

    first_event_result = run_lifeos(
        integration_context,
        "event",
        "add",
        "Morning run block",
        "--start-time",
        "2026-04-10T07:00:00-04:00",
        "--end-time",
        "2026-04-10T07:45:00-04:00",
        "--area-id",
        area_id,
        "--task-id",
        task_id,
        "--person-id",
        person_id,
        "--tag-id",
        event_tag_id,
    )
    assert_ok(first_event_result)
    first_event_id = extract_created_id(first_event_result.stdout)

    second_event_result = run_lifeos(
        integration_context,
        "event",
        "add",
        "Recovery block",
        "--start-time",
        "2026-04-10T18:00:00-04:00",
        "--end-time",
        "2026-04-10T19:00:00-04:00",
    )
    assert_ok(second_event_result)
    second_event_id = extract_created_id(second_event_result.stdout)

    event_list_result = run_lifeos(
        integration_context,
        "event",
        "list",
        "--task-id",
        task_id,
    )
    assert_ok(event_list_result)
    assert first_event_id in event_list_result.stdout

    event_show_result = run_lifeos(integration_context, "event", "show", first_event_id)
    assert_ok(event_show_result)
    assert "person: Coach" in event_show_result.stdout
    assert "tags: calendar" in event_show_result.stdout

    event_update_result = run_lifeos(
        integration_context,
        "event",
        "update",
        first_event_id,
        "--status",
        "completed",
        "--clear-task",
        "--clear-area",
        "--clear-tags",
        "--clear-person",
        "--clear-end-time",
    )
    assert_ok(event_update_result)

    updated_event_result = run_lifeos(integration_context, "event", "show", first_event_id)
    assert_ok(updated_event_result)
    assert "task_id: -" in updated_event_result.stdout
    assert "area_id: -" in updated_event_result.stdout
    assert "tags: -" in updated_event_result.stdout
    assert "person: -" in updated_event_result.stdout

    first_timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "Morning run",
        "--start-time",
        "2026-04-10T07:02:00-04:00",
        "--end-time",
        "2026-04-10T07:41:00-04:00",
        "--area-id",
        area_id,
        "--task-id",
        task_id,
        "--person-id",
        person_id,
        "--tag-id",
        timelog_tag_id,
        "--energy-level",
        "4",
    )
    assert_ok(first_timelog_result)
    first_timelog_id = extract_created_id(first_timelog_result.stdout)

    task_with_timelog_result = run_lifeos(integration_context, "task", "show", task_id)
    assert_ok(task_with_timelog_result)
    assert "actual_effort_self: 39" in task_with_timelog_result.stdout
    assert "actual_effort_total: 39" in task_with_timelog_result.stdout

    vision_sync_result = run_lifeos(integration_context, "vision", "sync-experience", vision_id)
    assert_ok(vision_sync_result)
    synced_vision_result = run_lifeos(integration_context, "vision", "show", vision_id)
    assert_ok(synced_vision_result)
    assert "experience_points: 39" in synced_vision_result.stdout
    assert "experience_rate_per_hour: -" in synced_vision_result.stdout
    vision_with_tasks_result = run_lifeos(integration_context, "vision", "with-tasks", vision_id)
    assert_ok(vision_with_tasks_result)
    assert "  task_id\tstatus\tparent_task_id\tcontent" in vision_with_tasks_result.stdout
    assert task_id in vision_with_tasks_result.stdout
    vision_stats_result = run_lifeos(integration_context, "vision", "stats", vision_id)
    assert_ok(vision_stats_result)
    assert "total_tasks: 1" in vision_stats_result.stdout
    assert "total_actual_effort: 39" in vision_stats_result.stdout

    second_timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "Stretching",
        "--start-time",
        "2026-04-10T19:10:00-04:00",
        "--end-time",
        "2026-04-10T19:25:00-04:00",
    )
    assert_ok(second_timelog_result)
    second_timelog_id = extract_created_id(second_timelog_result.stdout)

    timelog_list_result = run_lifeos(
        integration_context,
        "timelog",
        "list",
        "--start-time",
        "2026-04-10T00:00:00-04:00",
        "--end-time",
        "2026-04-10T23:59:59-04:00",
    )
    assert_ok(timelog_list_result)
    assert first_timelog_id in timelog_list_result.stdout
    assert second_timelog_id in timelog_list_result.stdout

    timelog_show_result = run_lifeos(integration_context, "timelog", "show", first_timelog_id)
    assert_ok(timelog_show_result)
    assert "person: Coach" in timelog_show_result.stdout
    assert "tags: tracked" in timelog_show_result.stdout

    timelog_update_result = run_lifeos(
        integration_context,
        "timelog",
        "update",
        first_timelog_id,
        "--notes",
        "Felt strong",
        "--clear-task",
        "--clear-area",
        "--clear-tags",
        "--clear-person",
        "--clear-energy-level",
    )
    assert_ok(timelog_update_result)

    updated_timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "show",
        first_timelog_id,
    )
    assert_ok(updated_timelog_result)
    assert "task_id: -" in updated_timelog_result.stdout
    assert "area_id: -" in updated_timelog_result.stdout
    assert "tags: -" in updated_timelog_result.stdout
    assert "person: -" in updated_timelog_result.stdout

    task_after_clear_timelog_result = run_lifeos(integration_context, "task", "show", task_id)
    assert_ok(task_after_clear_timelog_result)
    assert "actual_effort_self: 0" in task_after_clear_timelog_result.stdout
    assert "actual_effort_total: 0" in task_after_clear_timelog_result.stdout

    event_delete_result = run_lifeos(
        integration_context,
        "event",
        "delete",
        first_event_id,
    )
    assert_ok(event_delete_result)
    assert f"Soft-deleted event {first_event_id}" in event_delete_result.stdout

    event_delete_second_result = run_lifeos(
        integration_context,
        "event",
        "delete",
        second_event_id,
    )
    assert_ok(event_delete_second_result)
    assert f"Soft-deleted event {second_event_id}" in event_delete_second_result.stdout

    timelog_delete_result = run_lifeos(
        integration_context,
        "timelog",
        "delete",
        first_timelog_id,
    )
    assert_ok(timelog_delete_result)
    assert f"Soft-deleted timelog {first_timelog_id}" in timelog_delete_result.stdout

    timelog_batch_delete_result = run_lifeos(
        integration_context,
        "timelog",
        "batch",
        "delete",
        "--ids",
        second_timelog_id,
    )
    assert_ok(timelog_batch_delete_result)
    assert "Deleted timelogs: 1" in timelog_batch_delete_result.stdout

    deleted_event_result = run_lifeos(
        integration_context,
        "event",
        "list",
    )
    assert_ok(deleted_event_result)
    assert first_event_id not in deleted_event_result.stdout
    assert second_event_id not in deleted_event_result.stdout

    deleted_timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "list",
        "--start-time",
        "2026-04-10T00:00:00-04:00",
        "--end-time",
        "2026-04-10T23:59:59-04:00",
    )
    assert_ok(deleted_timelog_result)
    assert first_timelog_id not in deleted_timelog_result.stdout
    assert second_timelog_id not in deleted_timelog_result.stdout

    rejected_deleted_timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "list",
        "--include-deleted",
    )
    assert rejected_deleted_timelog_result.returncode == 2
    assert "--include-deleted" in rejected_deleted_timelog_result.stderr


def test_real_cli_timelog_add_quick_batch_inherits_latest_end_time(
    integration_context: IntegrationContext,
) -> None:
    init_context(integration_context)

    seed_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "Seed session",
        "--start-time",
        "2026-04-10T06:00:00-04:00",
        "--end-time",
        "2026-04-10T06:30:00-04:00",
    )
    assert_ok(seed_result)

    quick_file = integration_context.config_path.parent / "quick-timelog.txt"
    quick_file.write_text("0700 Breakfast\n0830 Deep work\n", encoding="utf-8")

    batch_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "--file",
        str(quick_file),
        input_text="yes\n",
    )
    assert_ok(batch_result)
    assert "Quick batch timelog preview:" in batch_result.stdout
    assert "Created timelogs: 2" in batch_result.stdout

    timelog_list_result = run_lifeos(
        integration_context,
        "timelog",
        "list",
        "--start-time",
        "2026-04-10T00:00:00-04:00",
        "--end-time",
        "2026-04-10T23:59:59-04:00",
    )
    assert_ok(timelog_list_result)
    assert "Seed session" in timelog_list_result.stdout
    assert "Breakfast" in timelog_list_result.stdout
    assert "Deep work" in timelog_list_result.stdout


def test_real_cli_timelog_add_quick_batch_accepts_multiline_stdin(
    integration_context: IntegrationContext,
) -> None:
    init_context(integration_context)

    batch_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "--stdin",
        "--first-start-time",
        "2026-04-10T06:30:00-04:00",
        input_text="0700 Breakfast\n0830 Deep work\n",
    )
    assert_ok(batch_result)
    assert "Quick batch timelog preview:" in batch_result.stdout
    assert "Created timelogs: 2" in batch_result.stdout

    timelog_list_result = run_lifeos(
        integration_context,
        "timelog",
        "list",
        "--start-time",
        "2026-04-10T00:00:00-04:00",
        "--end-time",
        "2026-04-10T23:59:59-04:00",
    )
    assert_ok(timelog_list_result)
    assert "Breakfast" in timelog_list_result.stdout
    assert "Deep work" in timelog_list_result.stdout


def test_real_cli_event_and_timelog_accept_naive_write_datetimes(
    integration_context: IntegrationContext,
) -> None:
    init_context(integration_context)

    event_result = run_lifeos(
        integration_context,
        "event",
        "add",
        "Naive event",
        "--start-time",
        "2026-04-10T09:00:00",
        "--end-time",
        "2026-04-10T10:00:00",
    )
    assert_ok(event_result)
    event_id = extract_created_id(event_result.stdout)

    timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "Naive timelog",
        "--start-time",
        "2026-04-10T10:15:00",
        "--end-time",
        "2026-04-10T11:45:00",
    )
    assert_ok(timelog_result)
    timelog_id = extract_created_id(timelog_result.stdout)

    event_show_result = run_lifeos(integration_context, "event", "show", event_id)
    assert_ok(event_show_result)
    assert "start_time: 2026-04-10T09:00:00-04:00" in event_show_result.stdout
    assert "end_time: 2026-04-10T10:00:00-04:00" in event_show_result.stdout

    timelog_show_result = run_lifeos(integration_context, "timelog", "show", timelog_id)
    assert_ok(timelog_show_result)
    assert "start_time: 2026-04-10T10:15:00-04:00" in timelog_show_result.stdout
    assert "end_time: 2026-04-10T11:45:00-04:00" in timelog_show_result.stdout


def test_real_cli_timelog_stats_groupby_area_updates_after_writes(
    integration_context: IntegrationContext,
) -> None:
    init_context(integration_context, "--timezone", "America/Toronto")

    area_result = run_lifeos(integration_context, "area", "add", "Health")
    assert_ok(area_result)
    health_area_id = extract_created_id(area_result.stdout)

    second_area_result = run_lifeos(integration_context, "area", "add", "Work")
    assert_ok(second_area_result)
    work_area_id = extract_created_id(second_area_result.stdout)

    first_timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "Late workout",
        "--start-time",
        "2026-04-10T22:30:00-04:00",
        "--end-time",
        "2026-04-11T00:30:00-04:00",
        "--area-id",
        health_area_id,
    )
    assert_ok(first_timelog_result)
    first_timelog_id = extract_created_id(first_timelog_result.stdout)

    second_timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "Morning planning",
        "--start-time",
        "2026-04-11T09:00:00-04:00",
        "--end-time",
        "2026-04-11T10:00:00-04:00",
        "--area-id",
        work_area_id,
    )
    assert_ok(second_timelog_result)

    first_day_stats = run_lifeos(
        integration_context,
        "timelog",
        "stats",
        "day",
        "--date",
        "2026-04-10",
    )
    assert_ok(first_day_stats)
    assert "granularity: day" in first_day_stats.stdout
    assert "Health" in first_day_stats.stdout
    assert "90" in first_day_stats.stdout

    second_day_stats = run_lifeos(
        integration_context,
        "timelog",
        "stats",
        "day",
        "--date",
        "2026-04-11",
    )
    assert_ok(second_day_stats)
    assert "Health" in second_day_stats.stdout
    assert "30" in second_day_stats.stdout
    assert "Work" in second_day_stats.stdout
    assert "60" in second_day_stats.stdout

    update_timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "update",
        first_timelog_id,
        "--area-id",
        work_area_id,
    )
    assert_ok(update_timelog_result)

    updated_first_day_stats = run_lifeos(
        integration_context,
        "timelog",
        "stats",
        "day",
        "--date",
        "2026-04-10",
    )
    assert_ok(updated_first_day_stats)
    assert "Health" not in updated_first_day_stats.stdout
    assert "Work" in updated_first_day_stats.stdout
    assert "90" in updated_first_day_stats.stdout


def test_real_cli_time_preferences_affect_display_and_local_date_filters(
    integration_context: IntegrationContext,
) -> None:
    init_context(
        integration_context,
        "--timezone",
        "America/Toronto",
        "--day-starts-at",
        "04:00",
        "--week-starts-on",
        "sunday",
        "--language",
        "zh-Hans",
    )

    event_result = run_lifeos(
        integration_context,
        "event",
        "add",
        "Late night planning",
        "--start-time",
        "2026-04-10T03:30:00+00:00",
        "--end-time",
        "2026-04-10T05:00:00+00:00",
    )
    assert_ok(event_result)
    event_id = extract_created_id(event_result.stdout)

    timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "Late night work",
        "--start-time",
        "2026-04-10T03:30:00+00:00",
        "--end-time",
        "2026-04-10T05:00:00+00:00",
    )
    assert_ok(timelog_result)
    timelog_id = extract_created_id(timelog_result.stdout)

    event_show_result = run_lifeos(integration_context, "event", "show", event_id)
    assert_ok(event_show_result)
    assert "start_time: 2026-04-09T23:30:00-04:00" in event_show_result.stdout
    assert "end_time: 2026-04-10T01:00:00-04:00" in event_show_result.stdout

    timelog_show_result = run_lifeos(integration_context, "timelog", "show", timelog_id)
    assert_ok(timelog_show_result)
    assert "start_time: 2026-04-09T23:30:00-04:00" in timelog_show_result.stdout
    assert "end_time: 2026-04-10T01:00:00-04:00" in timelog_show_result.stdout

    event_date_result = run_lifeos(
        integration_context,
        "event",
        "list",
        "--date",
        "2026-04-09",
    )
    assert_ok(event_date_result)
    assert event_id in event_date_result.stdout

    timelog_date_result = run_lifeos(
        integration_context,
        "timelog",
        "list",
        "--date",
        "2026-04-09",
    )
    assert_ok(timelog_date_result)
    assert timelog_id in timelog_date_result.stdout

    missing_event_date_result = run_lifeos(
        integration_context,
        "event",
        "list",
        "--date",
        "2026-04-10",
    )
    assert_ok(missing_event_date_result)
    assert event_id not in missing_event_date_result.stdout

    missing_timelog_date_result = run_lifeos(
        integration_context,
        "timelog",
        "list",
        "--date",
        "2026-04-10",
    )
    assert_ok(missing_timelog_date_result)
    assert timelog_id not in missing_timelog_date_result.stdout
