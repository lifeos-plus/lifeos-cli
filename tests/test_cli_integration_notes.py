from __future__ import annotations

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


def test_real_cli_note_workflow(integration_context: IntegrationContext) -> None:
    init_context(integration_context)

    first_add_result = run_lifeos(integration_context, "note", "add", "integration note")
    assert_ok(first_add_result)
    first_note_id = extract_created_id(first_add_result.stdout)

    second_add_result = run_lifeos(
        integration_context,
        "note",
        "add",
        "--stdin",
        input_text="first line\nsecond line\n",
    )
    assert_ok(second_add_result)
    second_note_id = extract_created_id(second_add_result.stdout)

    list_result = run_lifeos(integration_context, "note", "list")
    assert_ok(list_result)
    assert first_note_id in list_result.stdout
    assert second_note_id in list_result.stdout

    show_result = run_lifeos(integration_context, "note", "show", second_note_id)
    assert_ok(show_result)
    assert f"id: {second_note_id}" in show_result.stdout
    assert "content:\nfirst line\nsecond line" in show_result.stdout

    update_result = run_lifeos(
        integration_context,
        "note",
        "update",
        first_note_id,
        "integration note updated",
    )
    assert_ok(update_result)
    assert f"Updated note {first_note_id}" in update_result.stdout

    search_result = run_lifeos(integration_context, "note", "search", "integration")
    assert_ok(search_result)
    assert first_note_id in search_result.stdout

    batch_update_result = run_lifeos(
        integration_context,
        "note",
        "batch",
        "update-content",
        "--ids",
        first_note_id,
        second_note_id,
        "--find-text",
        "line",
        "--replace-text",
        "entry",
    )
    assert_ok(batch_update_result)
    assert "Updated notes: 1" in batch_update_result.stdout

    updated_multiline_result = run_lifeos(integration_context, "note", "show", second_note_id)
    assert_ok(updated_multiline_result)
    assert "content:\nfirst entry\nsecond entry" in updated_multiline_result.stdout

    delete_result = run_lifeos(integration_context, "note", "delete", first_note_id)
    assert_ok(delete_result)
    assert f"Soft-deleted note {first_note_id}" in delete_result.stdout

    delete_second_result = run_lifeos(
        integration_context,
        "note",
        "delete",
        second_note_id,
    )
    assert_ok(delete_second_result)
    assert f"Soft-deleted note {second_note_id}" in delete_second_result.stdout

    deleted_list_result = run_lifeos(integration_context, "note", "list")
    assert_ok(deleted_list_result)
    assert first_note_id not in deleted_list_result.stdout
    assert second_note_id not in deleted_list_result.stdout

    rejected_deleted_list_result = run_lifeos(
        integration_context,
        "note",
        "list",
        "--include-deleted",
    )
    assert rejected_deleted_list_result.returncode == 2
    assert "--include-deleted" in rejected_deleted_list_result.stderr

    missing_show_result = run_lifeos(
        integration_context,
        "note",
        "show",
        "00000000-0000-0000-0000-000000000000",
    )
    assert_missing(missing_show_result, "00000000-0000-0000-0000-000000000000")


def test_real_cli_note_associations_and_timelog_counts(
    integration_context: IntegrationContext,
) -> None:
    init_context(integration_context)

    person_result = run_lifeos(integration_context, "person", "add", "Alice")
    assert_ok(person_result)
    person_id = extract_created_id(person_result.stdout)

    vision_result = run_lifeos(integration_context, "vision", "add", "Link notes to work")
    assert_ok(vision_result)
    vision_id = extract_created_id(vision_result.stdout)

    task_result = run_lifeos(
        integration_context,
        "task",
        "add",
        "Investigate note associations",
        "--vision-id",
        vision_id,
    )
    assert_ok(task_result)
    task_id = extract_created_id(task_result.stdout)

    timelog_result = run_lifeos(
        integration_context,
        "timelog",
        "add",
        "Implementation session",
        "--start-time",
        "2026-04-10T10:00:00-04:00",
        "--end-time",
        "2026-04-10T11:00:00-04:00",
        "--task-id",
        task_id,
    )
    assert_ok(timelog_result)
    timelog_id = extract_created_id(timelog_result.stdout)

    note_result = run_lifeos(
        integration_context,
        "note",
        "add",
        "Association note",
        "--person-id",
        person_id,
        "--task-id",
        task_id,
        "--timelog-id",
        timelog_id,
    )
    assert_ok(note_result)
    note_id = extract_created_id(note_result.stdout)

    note_show_result = run_lifeos(integration_context, "note", "show", note_id)
    assert_ok(note_show_result)
    assert "person: Alice" in note_show_result.stdout
    assert f"tasks: {task_id} | Investigate note associations" in note_show_result.stdout
    assert f"timelogs: {timelog_id} | Implementation session" in note_show_result.stdout

    note_list_result = run_lifeos(
        integration_context,
        "note",
        "list",
        "--person-id",
        person_id,
        "--with-counts",
    )
    assert_ok(note_list_result)
    assert note_id in note_list_result.stdout
    assert "\t1\t0\t0\t1\t1\t0\t0\tAssociation note" in note_list_result.stdout

    note_search_result = run_lifeos(
        integration_context,
        "note",
        "search",
        "Association",
        "--task-id",
        task_id,
    )
    assert_ok(note_search_result)
    assert note_id in note_search_result.stdout

    timelog_show_result = run_lifeos(integration_context, "timelog", "show", timelog_id)
    assert_ok(timelog_show_result)
    assert "linked_notes_count: 1" in timelog_show_result.stdout

    clear_timelog_result = run_lifeos(
        integration_context,
        "note",
        "update",
        note_id,
        "--clear-timelogs",
    )
    assert_ok(clear_timelog_result)

    updated_note_result = run_lifeos(integration_context, "note", "show", note_id)
    assert_ok(updated_note_result)
    assert "timelogs: -" in updated_note_result.stdout

    updated_timelog_result = run_lifeos(integration_context, "timelog", "show", timelog_id)
    assert_ok(updated_timelog_result)
    assert "linked_notes_count: 0" in updated_timelog_result.stdout
