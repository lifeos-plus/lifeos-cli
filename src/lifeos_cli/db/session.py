"""Async engine and session helpers for configured database storage."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from lifeos_cli.config import (
    ensure_database_driver_available,
    ensure_database_url_storage_ready,
    get_database_settings,
)
from lifeos_cli.db.backend_policy import backend_policy_for_drivername
from lifeos_cli.db.base import SoftDeleteMixin

_CACHED_ENGINE: AsyncEngine | None = None
INCLUDE_SOFT_DELETED_EXECUTION_OPTION = "include_soft_deleted"
SQLITE_BUSY_TIMEOUT_MS = 5000


@event.listens_for(Session, "do_orm_execute")
def _exclude_soft_deleted_rows_by_default(execute_state: ORMExecuteState) -> None:
    """Apply the default user-facing soft-delete scope to ORM SELECT statements."""
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get(INCLUDE_SOFT_DELETED_EXECUTION_OPTION):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda model_cls: model_cls.deleted_at.is_(None),
            include_aliases=True,
        )
    )


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Apply SQLite connection pragmas for reliability and concurrent access."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def configure_async_engine(engine: AsyncEngine) -> AsyncEngine:
    """Apply backend-specific engine configuration."""
    policy = backend_policy_for_drivername(engine.sync_engine.url.drivername)
    if not policy.enable_foreign_keys_on_connect:
        return engine

    event.listen(engine.sync_engine, "connect", _configure_sqlite_connection)
    return engine


def _remember_async_engine(engine: AsyncEngine) -> AsyncEngine:
    """Track the cached engine so it can be disposed during cache resets."""
    global _CACHED_ENGINE
    _CACHED_ENGINE = engine
    return engine


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """Return the process-wide SQLAlchemy async engine."""
    settings = get_database_settings()
    database_url = settings.require_database_url()
    ensure_database_driver_available(database_url)
    ensure_database_url_storage_ready(database_url)
    engine = create_async_engine(
        database_url,
        echo=settings.database_echo,
        future=True,
        pool_pre_ping=True,
    )
    if settings.database_schema is not None:
        engine = engine.execution_options(schema_translate_map={None: settings.database_schema})
    return _remember_async_engine(configure_async_engine(engine))


@lru_cache(maxsize=1)
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the configured SQLAlchemy async session factory."""
    return async_sessionmaker(
        bind=get_async_engine(),
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Open an async session and roll back automatically on failure."""
    session = get_async_session_factory()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def clear_session_cache() -> None:
    """Clear cached engine and session factories for the current process."""
    global _CACHED_ENGINE
    engine = _CACHED_ENGINE
    _CACHED_ENGINE = None
    get_async_engine.cache_clear()
    get_async_session_factory.cache_clear()
    if engine is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(engine.dispose())
        return
    loop.create_task(engine.dispose())
