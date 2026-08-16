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


def test_real_cli_core_resource_workflow(integration_context: IntegrationContext) -> None:
    init_context(integration_context)

    area_one_result = run_lifeos(integration_context, "area", "add", "Health")
    assert_ok(area_one_result)
    area_one_id = extract_created_id(area_one_result.stdout)

    area_two_result = run_lifeos(
        integration_context,
        "area",
        "add",
        "Work",
        "--inactive",
    )
    assert_ok(area_two_result)
    area_two_id = extract_created_id(area_two_result.stdout)

    area_show_result = run_lifeos(integration_context, "area", "show", area_one_id)
    assert_ok(area_show_result)
    assert f"id: {area_one_id}" in area_show_result.stdout

    area_update_result = run_lifeos(
        integration_context,
        "area",
        "update",
        area_one_id,
        "--description",
        "Physical wellbeing",
        "--icon",
        "heart",
    )
    assert_ok(area_update_result)
    assert f"Updated area {area_one_id}" in area_update_result.stdout

    area_clear_result = run_lifeos(
        integration_context,
        "area",
        "update",
        area_one_id,
        "--clear-description",
        "--clear-icon",
    )
    assert_ok(area_clear_result)

    vision_one_result = run_lifeos(
        integration_context,
        "vision",
        "add",
        "Launch lifeos-cli",
        "--area-id",
        area_one_id,
        "--status",
        "active",
    )
    assert_ok(vision_one_result)
    vision_one_id = extract_created_id(vision_one_result.stdout)

    vision_two_result = run_lifeos(
        integration_context,
        "vision",
        "add",
        "Improve sleep quality",
        "--area-id",
        area_two_id,
    )
    assert_ok(vision_two_result)
    vision_two_id = extract_created_id(vision_two_result.stdout)

    vision_show_result = run_lifeos(integration_context, "vision", "show", vision_one_id)
    assert_ok(vision_show_result)
    assert f"area_id: {area_one_id}" in vision_show_result.stdout

    vision_update_result = run_lifeos(
        integration_context,
        "vision",
        "update",
        vision_one_id,
        "--description",
        "Deliver the first production-ready release",
        "--status",
        "fruit",
    )
    assert_ok(vision_update_result)

    vision_clear_result = run_lifeos(
        integration_context,
        "vision",
        "update",
        vision_one_id,
        "--clear-description",
        "--clear-area",
    )
    assert_ok(vision_clear_result)

    task_one_result = run_lifeos(
        integration_context,
        "task",
        "add",
        "Draft release checklist",
        "--vision-id",
        vision_one_id,
        "--status",
        "todo",
    )
    assert_ok(task_one_result)
    task_one_id = extract_created_id(task_one_result.stdout)

    task_two_result = run_lifeos(
        integration_context,
        "task",
        "add",
        "Write changelog",
        "--vision-id",
        vision_one_id,
        "--parent-task-id",
        task_one_id,
        "--estimated-effort",
        "45",
    )
    assert_ok(task_two_result)
    task_two_id = extract_created_id(task_two_result.stdout)

    task_show_result = run_lifeos(integration_context, "task", "show", task_two_id)
    assert_ok(task_show_result)
    assert f"parent_task_id: {task_one_id}" in task_show_result.stdout

    task_update_result = run_lifeos(
        integration_context,
        "task",
        "update",
        task_two_id,
        "--status",
        "in_progress",
        "--clear-parent",
        "--clear-estimated-effort",
    )
    assert_ok(task_update_result)

    person_one_result = run_lifeos(
        integration_context,
        "person",
        "add",
        "Alice",
        "--location",
        "Toronto",
    )
    assert_ok(person_one_result)
    person_one_id = extract_created_id(person_one_result.stdout)

    person_two_result = run_lifeos(
        integration_context,
        "person",
        "add",
        "Bob",
        "--location",
        "Montreal",
    )
    assert_ok(person_two_result)
    person_two_id = extract_created_id(person_two_result.stdout)

    person_show_result = run_lifeos(integration_context, "person", "show", person_one_id)
    assert_ok(person_show_result)
    assert "location: Toronto" in person_show_result.stdout

    person_update_result = run_lifeos(
        integration_context,
        "person",
        "update",
        person_one_id,
        "--nickname",
        "ally",
        "--clear-location",
    )
    assert_ok(person_update_result)

    tag_one_result = run_lifeos(
        integration_context,
        "tag",
        "add",
        "family",
        "--entity-type",
        "person",
        "--category",
        "relation",
    )
    assert_ok(tag_one_result)
    tag_one_id = extract_created_id(tag_one_result.stdout)

    tag_two_result = run_lifeos(
        integration_context,
        "tag",
        "add",
        "friend",
        "--entity-type",
        "person",
        "--category",
        "relation",
    )
    assert_ok(tag_two_result)
    tag_two_id = extract_created_id(tag_two_result.stdout)

    tag_show_result = run_lifeos(integration_context, "tag", "show", tag_one_id)
    assert_ok(tag_show_result)
    assert "entity_type: person" in tag_show_result.stdout

    tag_update_result = run_lifeos(
        integration_context,
        "tag",
        "update",
        tag_one_id,
        "--description",
        "Relationship marker",
        "--color",
        "#22C55E",
    )
    assert_ok(tag_update_result)

    tag_person_result = run_lifeos(
        integration_context,
        "tag",
        "update",
        tag_one_id,
        "--person-id",
        person_one_id,
    )
    assert_ok(tag_person_result)

    tag_clear_result = run_lifeos(
        integration_context,
        "tag",
        "update",
        tag_one_id,
        "--clear-description",
        "--clear-color",
    )
    assert_ok(tag_clear_result)

    vision_person_result = run_lifeos(
        integration_context,
        "vision",
        "update",
        vision_one_id,
        "--person-id",
        person_one_id,
        "--person-id",
        person_two_id,
    )
    assert_ok(vision_person_result)

    task_person_result = run_lifeos(
        integration_context,
        "task",
        "update",
        task_one_id,
        "--person-id",
        person_one_id,
    )
    assert_ok(task_person_result)

    assert area_one_id in run_lifeos(integration_context, "area", "list").stdout
    assert vision_one_id in run_lifeos(integration_context, "vision", "list").stdout
    assert (
        vision_one_id
        in run_lifeos(
            integration_context,
            "vision",
            "list",
            "--person-id",
            person_two_id,
        ).stdout
    )
    assert (
        task_one_id
        in run_lifeos(
            integration_context,
            "task",
            "list",
            "--vision-id",
            vision_one_id,
        ).stdout
    )
    assert (
        task_one_id
        in run_lifeos(
            integration_context,
            "task",
            "list",
            "--person-id",
            person_one_id,
        ).stdout
    )
    assert (
        person_one_id
        in run_lifeos(
            integration_context,
            "person",
            "list",
            "--search",
            "Ali",
        ).stdout
    )
    assert (
        tag_one_id
        in run_lifeos(
            integration_context,
            "tag",
            "list",
            "--entity-type",
            "person",
        ).stdout
    )
    assert (
        tag_one_id
        in run_lifeos(
            integration_context,
            "tag",
            "list",
            "--person-id",
            person_one_id,
        ).stdout
    )

    area_show_result = run_lifeos(integration_context, "area", "show", area_one_id)
    assert_ok(area_show_result)
    assert "person:" not in area_show_result.stdout

    vision_show_with_person_result = run_lifeos(
        integration_context,
        "vision",
        "show",
        vision_one_id,
    )
    assert_ok(vision_show_with_person_result)
    assert "person: Alice, Bob" in vision_show_with_person_result.stdout

    task_show_with_person_result = run_lifeos(integration_context, "task", "show", task_one_id)
    assert_ok(task_show_with_person_result)
    assert "person: Alice" in task_show_with_person_result.stdout

    tag_show_with_person_result = run_lifeos(integration_context, "tag", "show", tag_one_id)
    assert_ok(tag_show_with_person_result)
    assert "person: Alice" in tag_show_with_person_result.stdout

    person_delete_result = run_lifeos(
        integration_context,
        "person",
        "delete",
        person_one_id,
    )
    assert_ok(person_delete_result)
    assert f"Soft-deleted person {person_one_id}" in person_delete_result.stdout

    person_batch_delete_result = run_lifeos(
        integration_context,
        "person",
        "batch",
        "delete",
        "--ids",
        person_two_id,
    )
    assert_ok(person_batch_delete_result)
    assert "Deleted people: 1" in person_batch_delete_result.stdout

    tag_delete_result = run_lifeos(integration_context, "tag", "delete", tag_one_id)
    assert_ok(tag_delete_result)
    assert f"Soft-deleted tag {tag_one_id}" in tag_delete_result.stdout

    tag_batch_delete_result = run_lifeos(
        integration_context,
        "tag",
        "batch",
        "delete",
        "--ids",
        tag_two_id,
    )
    assert_ok(tag_batch_delete_result)
    assert "Deleted tags: 1" in tag_batch_delete_result.stdout

    task_delete_result = run_lifeos(integration_context, "task", "delete", task_two_id)
    assert_ok(task_delete_result)
    assert f"Soft-deleted task {task_two_id}" in task_delete_result.stdout

    task_batch_delete_result = run_lifeos(
        integration_context,
        "task",
        "batch",
        "delete",
        "--ids",
        task_one_id,
    )
    assert_ok(task_batch_delete_result)
    assert "Deleted tasks: 1" in task_batch_delete_result.stdout

    vision_delete_result = run_lifeos(integration_context, "vision", "delete", vision_one_id)
    assert_ok(vision_delete_result)
    assert f"Soft-deleted vision {vision_one_id}" in vision_delete_result.stdout

    vision_batch_delete_result = run_lifeos(
        integration_context,
        "vision",
        "batch",
        "delete",
        "--ids",
        vision_two_id,
    )
    assert_ok(vision_batch_delete_result)
    assert "Deleted visions: 1" in vision_batch_delete_result.stdout

    area_delete_result = run_lifeos(integration_context, "area", "delete", area_one_id)
    assert_ok(area_delete_result)
    assert f"Soft-deleted area {area_one_id}" in area_delete_result.stdout

    area_batch_delete_result = run_lifeos(
        integration_context,
        "area",
        "batch",
        "delete",
        "--ids",
        area_two_id,
    )
    assert_ok(area_batch_delete_result)
    assert "Deleted areas: 1" in area_batch_delete_result.stdout

    deleted_area_result = run_lifeos(
        integration_context,
        "area",
        "list",
        "--include-inactive",
    )
    assert_ok(deleted_area_result)
    assert area_one_id not in deleted_area_result.stdout
    assert area_two_id not in deleted_area_result.stdout

    rejected_deleted_area_result = run_lifeos(
        integration_context,
        "area",
        "list",
        "--include-deleted",
    )
    assert rejected_deleted_area_result.returncode == 2
    assert "--include-deleted" in rejected_deleted_area_result.stderr
