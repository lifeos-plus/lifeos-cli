"""Serialization helpers shared by Web API routers."""

from __future__ import annotations

from lifeos_cli.application.serialization import to_jsonable, to_jsonable_dict

__all__ = ["to_jsonable", "to_jsonable_dict", "task_summary_payload"]


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
