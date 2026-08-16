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


def test_real_cli_habit_workflow(integration_context: IntegrationContext) -> None:
    init_context(integration_context)

    vision_result = run_lifeos(integration_context, "vision", "add", "Improve fitness")
    assert_ok(vision_result)
    vision_id = extract_created_id(vision_result.stdout)

    task_result = run_lifeos(
        integration_context,
        "task",
        "add",
        "Exercise consistently",
        "--vision-id",
        vision_id,
    )
    assert_ok(task_result)
    task_id = extract_created_id(task_result.stdout)

    first_habit_result = run_lifeos(
        integration_context,
        "habit",
        "add",
        "Daily Exercise",
        "--start-date",
        "2026-04-09",
        "--duration-days",
        "21",
        "--task-id",
        task_id,
    )
    assert_ok(first_habit_result)
    first_habit_id = extract_created_id(first_habit_result.stdout)

    second_habit_result = run_lifeos(
        integration_context,
        "habit",
        "add",
        "Morning Review",
        "--start-date",
        "2026-04-09",
        "--duration-days",
        "100",
    )
    assert_ok(second_habit_result)
    second_habit_id = extract_created_id(second_habit_result.stdout)

    weekly_habit_result = run_lifeos(
        integration_context,
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
    )
    assert_ok(weekly_habit_result)
    weekly_habit_id = extract_created_id(weekly_habit_result.stdout)

    habit_list_result = run_lifeos(integration_context, "habit", "list", "--with-stats")
    assert_ok(habit_list_result)
    assert first_habit_id in habit_list_result.stdout
    assert second_habit_id in habit_list_result.stdout

    habit_show_result = run_lifeos(integration_context, "habit", "show", first_habit_id)
    assert_ok(habit_show_result)
    assert f"id: {first_habit_id}" in habit_show_result.stdout
    assert "total_actions: 21" in habit_show_result.stdout

    weekly_habit_show_result = run_lifeos(integration_context, "habit", "show", weekly_habit_id)
    assert_ok(weekly_habit_show_result)
    assert f"id: {weekly_habit_id}" in weekly_habit_show_result.stdout
    assert "cadence_frequency: weekly" in weekly_habit_show_result.stdout
    assert "cadence_weekdays: saturday,sunday" in weekly_habit_show_result.stdout
    assert "target_per_cycle: 1" in weekly_habit_show_result.stdout

    task_association_result = run_lifeos(
        integration_context,
        "habit",
        "task-associations",
    )
    assert_ok(task_association_result)
    assert (
        "task_id\thabit_id\thabit_status\thabit_start_date\thabit_title"
        in task_association_result.stdout
    )
    assert first_habit_id in task_association_result.stdout
    assert task_id in task_association_result.stdout

    habit_update_result = run_lifeos(
        integration_context,
        "habit",
        "update",
        first_habit_id,
        "--description",
        "Move every day",
        "--status",
        "paused",
    )
    assert_ok(habit_update_result)
    assert f"Updated habit {first_habit_id}" in habit_update_result.stdout

    habit_clear_result = run_lifeos(
        integration_context,
        "habit",
        "update",
        first_habit_id,
        "--clear-description",
        "--clear-task",
        "--status",
        "active",
    )
    assert_ok(habit_clear_result)

    habit_stats_result = run_lifeos(integration_context, "habit", "stats", first_habit_id)
    assert_ok(habit_stats_result)
    assert f"habit_id: {first_habit_id}" in habit_stats_result.stdout

    action_list_result = run_lifeos(
        integration_context,
        "habit-action",
        "list",
        "--habit-id",
        first_habit_id,
    )
    assert_ok(action_list_result)
    action_id = extract_created_id(action_list_result.stdout)

    action_show_result = run_lifeos(integration_context, "habit-action", "show", action_id)
    assert_ok(action_show_result)
    assert f"id: {action_id}" in action_show_result.stdout

    action_update_result = run_lifeos(
        integration_context,
        "habit-action",
        "update",
        action_id,
        "--status",
        "done",
        "--notes",
        "Completed before work",
    )
    assert_ok(action_update_result)
    assert f"Updated habit action {action_id}" in action_update_result.stdout

    action_clear_result = run_lifeos(
        integration_context,
        "habit-action",
        "update",
        action_id,
        "--status",
        "skip",
        "--clear-notes",
    )
    assert_ok(action_clear_result)

    action_date_result = run_lifeos(
        integration_context,
        "habit-action",
        "list",
        "--date",
        "2026-04-09",
    )
    assert_ok(action_date_result)
    assert action_id in action_date_result.stdout

    weekly_action_list_result = run_lifeos(
        integration_context,
        "habit-action",
        "list",
        "--habit-id",
        weekly_habit_id,
    )
    assert_ok(weekly_action_list_result)
    assert "2026-04-11" in weekly_action_list_result.stdout
    assert "2026-04-12" in weekly_action_list_result.stdout
    assert "2026-04-10" not in weekly_action_list_result.stdout

    habit_delete_result = run_lifeos(integration_context, "habit", "delete", first_habit_id)
    assert_ok(habit_delete_result)
    assert f"Soft-deleted habit {first_habit_id}" in habit_delete_result.stdout

    habit_delete_multiple_result = run_lifeos(
        integration_context,
        "habit",
        "delete",
        second_habit_id,
        weekly_habit_id,
    )
    assert_ok(habit_delete_multiple_result)
    assert "Deleted habits: 2" in habit_delete_multiple_result.stdout

    deleted_habit_result = run_lifeos(integration_context, "habit", "list")
    assert_ok(deleted_habit_result)
    assert first_habit_id not in deleted_habit_result.stdout
    assert second_habit_id not in deleted_habit_result.stdout
    assert weekly_habit_id not in deleted_habit_result.stdout

    rejected_deleted_habit_result = run_lifeos(
        integration_context,
        "habit",
        "list",
        "--include-deleted",
    )
    assert rejected_deleted_habit_result.returncode == 2
    assert "--include-deleted" in rejected_deleted_habit_result.stderr
