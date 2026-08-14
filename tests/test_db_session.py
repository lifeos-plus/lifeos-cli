from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from lifeos_cli.db import session as db_session


def test_clear_session_cache_disposes_cached_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispose = AsyncMock()
    fake_engine = SimpleNamespace(dispose=dispose)

    monkeypatch.setattr(db_session, "_CACHED_ENGINE", fake_engine)

    db_session.clear_session_cache()

    dispose.assert_awaited_once()
    assert db_session._CACHED_ENGINE is None


def test_clear_session_cache_disposes_cached_engine_inside_active_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispose = AsyncMock()
    fake_engine = SimpleNamespace(dispose=dispose)

    async def run_clear() -> None:
        monkeypatch.setattr(db_session, "_CACHED_ENGINE", fake_engine)

        db_session.clear_session_cache()
        await asyncio.sleep(0)

    asyncio.run(run_clear())

    dispose.assert_awaited_once()
    assert db_session._CACHED_ENGINE is None


def test_configure_async_engine_enables_sqlite_foreign_keys_only_for_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listened: list[tuple[object, str, object]] = []

    def fake_listen(target: object, event_name: str, listener: object) -> None:
        listened.append((target, event_name, listener))

    monkeypatch.setattr(db_session.event, "listen", fake_listen)

    sqlite_engine = cast(
        AsyncEngine,
        SimpleNamespace(
            sync_engine=SimpleNamespace(
                url=SimpleNamespace(drivername="sqlite+aiosqlite"),
            )
        ),
    )
    postgres_engine = cast(
        AsyncEngine,
        SimpleNamespace(
            sync_engine=SimpleNamespace(
                url=SimpleNamespace(drivername="postgresql+psycopg"),
            )
        ),
    )

    assert db_session.configure_async_engine(sqlite_engine) is sqlite_engine
    assert listened == [
        (sqlite_engine.sync_engine, "connect", db_session._configure_sqlite_connection)
    ]

    listened.clear()
    assert db_session.configure_async_engine(postgres_engine) is postgres_engine
    assert listened == []


def test_configure_sqlite_connection_sets_concurrency_pragmas() -> None:
    executed: list[str] = []

    class FakeCursor:
        def execute(self, statement: str) -> None:
            executed.append(statement)

        def close(self) -> None:
            return None

    class FakeConnection:
        def cursor(self) -> FakeCursor:
            return FakeCursor()

    db_session._configure_sqlite_connection(FakeConnection(), None)

    assert executed == [
        "PRAGMA foreign_keys=ON",
        "PRAGMA journal_mode=WAL",
        f"PRAGMA busy_timeout={db_session.SQLITE_BUSY_TIMEOUT_MS}",
    ]


def _patch_session_factory(
    monkeypatch: pytest.MonkeyPatch,
    session: object,
) -> None:
    monkeypatch.setattr(
        db_session,
        "get_async_session_factory",
        lambda: lambda: session,
    )


def test_session_scope_commits_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        close=AsyncMock(),
    )
    _patch_session_factory(monkeypatch, session)

    async def run_scope() -> None:
        async with db_session.session_scope():
            pass

    asyncio.run(run_scope())

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()


def test_session_scope_skips_commit_when_commit_on_exit_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        close=AsyncMock(),
    )
    _patch_session_factory(monkeypatch, session)

    async def run_scope() -> None:
        async with db_session.session_scope(commit_on_exit=False):
            pass

    asyncio.run(run_scope())

    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()


def test_session_scope_rolls_back_on_error_when_commit_on_exit_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        close=AsyncMock(),
    )
    _patch_session_factory(monkeypatch, session)

    async def run_scope() -> None:
        async with db_session.session_scope(commit_on_exit=False):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(run_scope())

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()
