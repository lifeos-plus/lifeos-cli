"""Async engine and session helpers for configured database storage."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache, partial

from sqlalchemy import event
from sqlalchemy.engine import Connection
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


def _configure_sqlite_connection(
    dbapi_connection, _connection_record, *, foreign_keys: bool = True
) -> None:
    """Apply SQLite connection pragmas for reliability and concurrent access."""
    # Own BEGIN explicitly: legacy sqlite3 transactions otherwise exclude SELECT,
    # DDL and an initial SAVEPOINT from the surrounding transaction.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(f"PRAGMA foreign_keys={'ON' if foreign_keys else 'OFF'}")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def _begin_sqlite_transaction(connection: Connection) -> None:
    statement = (
        "BEGIN IMMEDIATE" if connection.get_execution_options().get("sqlite_write") else "BEGIN"
    )
    connection.exec_driver_sql(statement)


def configure_async_engine(engine: AsyncEngine, *, sqlite_foreign_keys: bool = True) -> AsyncEngine:
    """Apply backend-specific engine configuration."""
    policy = backend_policy_for_drivername(engine.sync_engine.url.drivername)
    if not policy.enable_foreign_keys_on_connect:
        return engine

    listener = (
        _configure_sqlite_connection
        if sqlite_foreign_keys
        else partial(_configure_sqlite_connection, foreign_keys=False)
    )
    event.listen(engine.sync_engine, "connect", listener)
    event.listen(engine.sync_engine, "begin", _begin_sqlite_transaction)
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
async def session_scope(
    *,
    commit_on_exit: bool = True,
    sqlite_write: bool = False,
) -> AsyncIterator[AsyncSession]:
    """Open an async session and roll back automatically on failure.

    By default the session is committed when the block exits normally. Callers
    that finalize the transaction elsewhere (for example the Web response
    middleware committing before the response is sent) pass
    ``commit_on_exit=False`` so there is exactly one commit point.
    Web mutations pass ``sqlite_write=True`` to reserve SQLite's writer before
    the first read, retaining bounded busy waiting instead of snapshot upgrades.
    """
    factory = get_async_session_factory()
    if sqlite_write and factory.kw["bind"].dialect.name == "sqlite":
        # Preserve write intent after rollback without changing the shared engine.
        session = factory(bind=factory.kw["bind"].execution_options(sqlite_write=True))
    else:
        session = factory()
    try:
        yield session
        if commit_on_exit:
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
