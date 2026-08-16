from __future__ import annotations

import json

from tests.cli_integration_support import (
    INTEGRATION_PYTESTMARK,
    IntegrationContext,
    assert_missing,
    assert_ok,
    extract_created_id,
    init_context,
    run_lifeos,
)

pytestmark = INTEGRATION_PYTESTMARK


def test_real_cli_data_round_trip_and_batch_workflow(
    integration_context: IntegrationContext,
) -> None:
    init_context(integration_context)

    area_result = run_lifeos(integration_context, "area", "add", "Work")
    assert_ok(area_result)
    area_id = extract_created_id(area_result.stdout)

    vision_result = run_lifeos(integration_context, "vision", "add", "Ship unified data CLI")
    assert_ok(vision_result)
    vision_id = extract_created_id(vision_result.stdout)

    person_result = run_lifeos(integration_context, "person", "add", "Alice")
    assert_ok(person_result)
    person_id = extract_created_id(person_result.stdout)

    task_result = run_lifeos(
        integration_context,
        "task",
        "add",
        "Implement data operations",
        "--vision-id",
        vision_id,
        "--person-id",
        person_id,
    )
    assert_ok(task_result)
    task_id = extract_created_id(task_result.stdout)

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

    habit_result = run_lifeos(
        integration_context,
        "habit",
        "add",
        "Daily review",
        "--start-date",
        "2026-04-10",
        "--duration-days",
        "7",
        "--task-id",
        task_id,
    )
    assert_ok(habit_result)
    habit_id = extract_created_id(habit_result.stdout)

    habit_action_list_result = run_lifeos(
        integration_context,
        "habit-action",
        "list",
        "--habit-id",
        habit_id,
    )
    assert_ok(habit_action_list_result)
    habit_action_id = extract_created_id(habit_action_list_result.stdout)

    event_result = run_lifeos(
        integration_context,
        "event",
        "add",
        "Planning block",
        "--start-time",
        "2026-04-10T09:00:00-04:00",
        "--end-time",
        "2026-04-10T10:00:00-04:00",
        "--area-id",
        area_id,
        "--task-id",
        task_id,
        "--person-id",
        person_id,
        "--tag-id",
        event_tag_id,
    )
    assert_ok(event_result)
    event_id = extract_created_id(event_result.stdout)

    timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "Implementation session",
        "--start-time",
        "2026-04-10T10:15:00-04:00",
        "--end-time",
        "2026-04-10T11:45:00-04:00",
        "--area-id",
        area_id,
        "--task-id",
        task_id,
        "--person-id",
        person_id,
        "--tag-id",
        timelog_tag_id,
        "--notes",
        "Initial draft",
    )
    assert_ok(timelog_result)
    timelog_id = extract_created_id(timelog_result.stdout)

    note_result = run_lifeos(
        integration_context,
        "note",
        "add",
        "Bundle restore checklist",
        "--person-id",
        person_id,
        "--task-id",
        task_id,
        "--timelog-id",
        timelog_id,
    )
    assert_ok(note_result)
    note_id = extract_created_id(note_result.stdout)

    bundle_path = integration_context.config_path.parent / "lifeos-bundle.zip"
    export_bundle_result = run_lifeos(
        integration_context,
        "data",
        "export",
        "all",
        "--output",
        str(bundle_path),
    )
    assert_ok(export_bundle_result)
    assert bundle_path.is_file()

    timelog_export_path = integration_context.config_path.parent / "timelog.jsonl"
    export_timelog_result = run_lifeos(
        integration_context,
        "data",
        "export",
        "timelog",
        "--format",
        "jsonl",
        "--output",
        str(timelog_export_path),
    )
    assert_ok(export_timelog_result)

    patch_path = integration_context.config_path.parent / "timelog-patch.jsonl"
    patch_path.write_text(
        json.dumps(
            {
                "id": timelog_id,
                "title": "Updated implementation session",
                "notes": "Patched through data batch update",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    batch_update_result = run_lifeos(
        integration_context,
        "data",
        "batch-update",
        "timelog",
        "--file",
        str(patch_path),
        "--format",
        "jsonl",
    )
    assert_ok(batch_update_result)
    assert "Updated rows: 1" in batch_update_result.stdout

    updated_timelog_result = run_lifeos(integration_context, "timelog", "show", timelog_id)
    assert_ok(updated_timelog_result)
    assert "title: Updated implementation session" in updated_timelog_result.stdout
    assert "notes: Patched through data batch update" in updated_timelog_result.stdout

    batch_delete_result = run_lifeos(
        integration_context,
        "data",
        "batch-delete",
        "timelog",
        "--file",
        str(timelog_export_path),
        "--format",
        "jsonl",
    )
    assert_ok(batch_delete_result)
    assert "Deleted rows: 1" in batch_delete_result.stdout

    deleted_timelog_result = run_lifeos(integration_context, "timelog", "show", timelog_id)
    assert_missing(deleted_timelog_result, "Timelog")

    import_bundle_result = run_lifeos(
        integration_context,
        "data",
        "import",
        "bundle",
        "--file",
        str(bundle_path),
        "--replace-existing",
    )
    assert_ok(import_bundle_result)
    assert "Bundle resources:" in import_bundle_result.stdout

    restored_timelog_result = run_lifeos(integration_context, "timelog", "show", timelog_id)
    assert_ok(restored_timelog_result)
    assert "title: Implementation session" in restored_timelog_result.stdout
    assert "notes: Initial draft" in restored_timelog_result.stdout
    assert "linked_notes_count: 1" in restored_timelog_result.stdout
    assert "person: Alice" in restored_timelog_result.stdout
    assert "tags: tracked" in restored_timelog_result.stdout

    restored_event_result = run_lifeos(integration_context, "event", "show", event_id)
    assert_ok(restored_event_result)
    assert "person: Alice" in restored_event_result.stdout
    assert "tags: calendar" in restored_event_result.stdout

    restored_habit_action_result = run_lifeos(
        integration_context,
        "habit-action",
        "show",
        habit_action_id,
    )
    assert_ok(restored_habit_action_result)
    assert f"id: {habit_action_id}" in restored_habit_action_result.stdout

    restored_note_result = run_lifeos(integration_context, "note", "show", note_id)
    assert_ok(restored_note_result)
    assert "Bundle restore checklist" in restored_note_result.stdout
    assert "person: Alice" in restored_note_result.stdout
    assert f"tasks: {task_id} | Implement data operations" in restored_note_result.stdout
    assert f"timelogs: {timelog_id} | Implementation session" in restored_note_result.stdout

    restored_task_result = run_lifeos(integration_context, "task", "show", task_id)
    assert_ok(restored_task_result)
    assert f"id: {task_id}" in restored_task_result.stdout
