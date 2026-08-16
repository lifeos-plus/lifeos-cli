"""Shared JSON-safe serialization for LifeOS records.

Both the CLI ``--json`` read output and the Web API serialize the same domain
read models and ORM records, so the conversion rules live in one place. The
conventions are: UUIDs become strings, datetimes become explicit UTC ISO
strings, enum values become their scalar values, and dataclass or object
records become plain dictionaries.

Decimal values are intentionally left untouched here: the Web API keeps its
existing payload contract, and the CLI output layer converts them to
precision-preserving strings at render time.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, cast
from uuid import UUID

from lifeos_cli.application.datetime_utils import format_utc_iso


def to_jsonable(value: Any) -> Any:
    """Convert LifeOS records and scalar values into JSON-compatible values."""
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
