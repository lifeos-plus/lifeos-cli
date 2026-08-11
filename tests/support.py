from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any


def make_session_scope(session: object | None = None):
    session_object = object() if session is None else session

    @asynccontextmanager
    async def _session_scope():
        yield session_object

    return _session_scope


def make_record(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def utc_datetime(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
