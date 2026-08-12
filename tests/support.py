from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lifeos_cli.db.base import Base
from lifeos_cli.db.session import configure_async_engine


async def create_sqlite_session_factory() -> tuple[
    AsyncEngine,
    async_sessionmaker[AsyncSession],
]:
    """Create an isolated in-memory SQLite engine with the project schema."""
    engine = configure_async_engine(
        create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, future=True)


@asynccontextmanager
async def sqlite_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Yield a session factory backed by an isolated in-memory SQLite engine.

    The engine is created with the project schema and disposed when the
    context exits, so tests do not need to manage engine lifecycle.
    """
    engine, factory = await create_sqlite_session_factory()
    try:
        yield factory
    finally:
        await engine.dispose()


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
