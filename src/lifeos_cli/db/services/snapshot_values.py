"""Shared scalar decoding for resource imports and versioned table snapshots."""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, Numeric, String

from lifeos_cli.application.datetime_utils import (
    normalize_storage_datetime,
    parse_iso_datetime_input,
)


class SnapshotValueError(ValueError):
    """Raised when a value cannot be stored losslessly on both supported backends."""


def _validate_json_value(value: Any) -> None:
    if value is None or type(value) in {bool, int}:
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("contains a non-finite JSON number")
        return
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("contains a null character unsupported by PostgreSQL JSON")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("contains a non-string JSON object key")
            _validate_json_value(key)
            _validate_json_value(item)
        return
    raise ValueError(f"contains unsupported JSON value {type(value).__name__}")


def parse_snapshot_value(column: Any, value: Any, *, allow_native: bool = False) -> Any:
    label = f"Field {column.name!r}"
    if value is None:
        if not column.nullable:
            raise SnapshotValueError(f"{label} cannot be null.")
        return None

    column_type = column.type
    try:
        python_type = column_type.python_type
        if isinstance(column_type, Boolean):
            if type(value) is not bool:
                raise ValueError("must be a boolean")
            return value
        if isinstance(column_type, Integer):
            if type(value) is not int:
                raise ValueError("must be an integer")
            if not -(2**31) <= value < 2**31:
                raise ValueError("is outside the PostgreSQL INTEGER range")
            return value
        if isinstance(column_type, Numeric):
            if isinstance(value, bool):
                raise ValueError("must be a decimal number")
            parsed = Decimal(str(value))
            if not parsed.is_finite():
                raise ValueError("must be finite")
            precision = column_type.precision
            scale = column_type.scale
            if precision is not None and scale is not None:
                quantum = Decimal(1).scaleb(-scale)
                if parsed != parsed.quantize(quantum):
                    raise ValueError(f"exceeds the numeric scale of {scale}")
                if abs(parsed) >= Decimal(10) ** (precision - scale):
                    raise ValueError(f"exceeds the numeric precision of {precision}")
            return parsed
        if isinstance(column_type, DateTime) or python_type is datetime:
            if allow_native and isinstance(value, datetime):
                return normalize_storage_datetime(value)
            if not isinstance(value, str):
                raise ValueError("must be an ISO-8601 datetime string")
            return normalize_storage_datetime(parse_iso_datetime_input(value))
        if isinstance(column_type, Date) or python_type is date:
            if allow_native and isinstance(value, date) and not isinstance(value, datetime):
                return value
            if not isinstance(value, str):
                raise ValueError("must be an ISO date string")
            return date.fromisoformat(value)
        if python_type is UUID:
            if allow_native and isinstance(value, UUID):
                return value
            if not isinstance(value, str):
                raise ValueError("must be a UUID string")
            return UUID(value)
        if isinstance(column_type, String):
            if not isinstance(value, str):
                raise ValueError("must be a string")
            if "\x00" in value:
                raise ValueError("contains a null character unsupported by PostgreSQL")
            if column_type.length is not None and len(value) > column_type.length:
                raise ValueError(f"exceeds the maximum length of {column_type.length}")
            return value
        if isinstance(column_type, JSON):
            _validate_json_value(value)
            return value
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SnapshotValueError(f"{label} {exc}.") from exc
    return value
