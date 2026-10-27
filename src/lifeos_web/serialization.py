"""Serialization helpers shared by Web API routers."""

from __future__ import annotations

from lifeos_cli.application.serialization import to_jsonable, to_jsonable_dict

__all__ = [
    "to_jsonable",
    "to_jsonable_dict",
    "task_summary_payload",
    "note_payload",
]


def task_summary_payload(task: dict[str, object]) -> dict[str, object]:
    """Reshape a serialized task summary into the Web API response shape.

    Internal ``vision_name`` / ``parent_content`` enrichment fields are mapped
    to the tooltip-consumed ``vision_summary`` / ``parent_summary`` objects and
    omitted entirely when the related record is unavailable.
    """
    payload = {
        key: value for key, value in task.items() if key not in {"vision_name", "parent_content"}
    }
    for field in (
        "priority",
        "planning_cycle_type",
        "planning_cycle_start_date",
        "actual_effort_self",
        "actual_effort_total",
        "created_at",
        "updated_at",
    ):
        if field in payload and payload[field] is None:
            del payload[field]
    vision_id = task.get("vision_id")
    vision_name = task.get("vision_name")
    parent_task_id = task.get("parent_task_id")
    parent_content = task.get("parent_content")
    if vision_id and vision_name:
        payload["vision_summary"] = {"id": vision_id, "name": vision_name}
    if parent_task_id and parent_content:
        payload["parent_summary"] = {
            "id": parent_task_id,
            "content": parent_content,
        }
    return payload


def _note_tag_payload(tag: object) -> dict[str, object]:
    """Return a frontend-compatible tag summary for note associations."""
    if not isinstance(tag, dict):
        return {}
    return {
        "id": tag.get("id"),
        "name": tag.get("name"),
        "entity_type": tag.get("entity_type") or "note",
        "category": tag.get("category") or "general",
        "description": tag.get("description"),
        "color": tag.get("color"),
        "created_at": tag.get("created_at") or "",
        "updated_at": tag.get("updated_at") or "",
    }


def _note_person_payload(person: object) -> dict[str, object]:
    """Return a frontend-compatible person summary for note associations."""
    if not isinstance(person, dict):
        return {}
    name = str(person.get("name") or "")
    display_name = str(person.get("display_name") or name)
    return {
        "id": person.get("id"),
        "name": person.get("name"),
        "display_name": display_name,
        "primary_nickname": person.get("primary_nickname") or display_name,
        "birth_date": person.get("birth_date"),
        "location": person.get("location"),
        "tags": person.get("tags") if isinstance(person.get("tags"), list) else [],
    }


def note_payload(note: object) -> dict[str, object]:
    """Return a Web UI-compatible note payload."""
    payload = to_jsonable_dict(note)
    tags = payload.get("tags")
    if isinstance(tags, list):
        payload["tags"] = [_note_tag_payload(tag) for tag in tags]
    person = payload.get("person")
    payload["person"] = (
        [_note_person_payload(person_item) for person_item in person]
        if isinstance(person, list)
        else []
    )
    tasks = payload.get("tasks")
    if isinstance(tasks, list):
        reshaped_tasks = [task_summary_payload(task) for task in tasks if isinstance(task, dict)]
        payload["tasks"] = reshaped_tasks
        payload["task"] = reshaped_tasks[0] if reshaped_tasks else None
    else:
        payload["task"] = None
    return payload
