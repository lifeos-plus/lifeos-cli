"""Datetime helpers for storage and API boundaries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import overload


@overload
def normalize_storage_datetime(value: None) -> None: ...


@overload
def normalize_storage_datetime(value: datetime) -> datetime: ...


def normalize_storage_datetime(value: datetime | None) -> datetime | None:
    """Return stored datetimes as UTC-aware values, treating naive storage values as UTC."""
    if value is None:
        return None
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value.astimezone(UTC)
    return value.replace(tzinfo=UTC)


def normalize_iso_datetime_input(value: str) -> str:
    """Normalize accepted ISO datetime input variants before parsing."""
    return f"{value[:-1]}+00:00" if value.endswith("Z") else value


def parse_iso_datetime_input(value: str) -> datetime:
    """Parse one accepted ISO datetime input string."""
    return datetime.fromisoformat(normalize_iso_datetime_input(value))


def format_utc_iso(value: datetime) -> str:
    """Render one stored datetime as an explicit UTC ISO string."""
    return normalize_storage_datetime(value).isoformat().replace("+00:00", "Z")
