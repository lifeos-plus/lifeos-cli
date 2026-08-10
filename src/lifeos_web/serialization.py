"""Serialization helpers shared by Web API routers."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, cast
from uuid import UUID

from lifeos_cli.application.datetime_utils import format_utc_iso


def to_jsonable(value: Any) -> Any:
    """Convert LifeOS dataclasses and scalar values into JSON-compatible values."""
    if is_dataclass(value) and not isinstance(value, type):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {
            key: to_jsonable(item) for key, item in vars(value).items() if not key.startswith("_")
        }
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return format_utc_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple | list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value


def to_jsonable_dict(value: Any) -> dict[str, object]:
    """Convert a dataclass-like object into a JSON-compatible object payload."""
    payload = to_jsonable(value)
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object payload, got {type(payload).__name__}")
    return cast(dict[str, object], payload)


def task_summary_payload(task: dict[str, object]) -> dict[str, object]:
    """Reshape a serialized task summary into the Web API response shape.

    Internal ``vision_name`` / ``parent_content`` enrichment fields are mapped
    to the tooltip-consumed ``vision_summary`` / ``parent_summary`` objects and
    omitted entirely when the related record is unavailable.
    """
    payload = {
        key: value
        for key, value in task.items()
        if key not in {"vision_name", "parent_content"}
    }
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
