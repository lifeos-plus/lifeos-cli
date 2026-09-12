"""Real file-backed SQLite request transaction concurrency regressions."""

from __future__ import annotations

import asyncio
from datetime import UTC, date

import httpx2 as httpx
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lifeos_cli.db import session as db_session
from lifeos_cli.db.base import Base
from lifeos_cli.db.models import Task, Vision
from lifeos_web.app import create_app
from lifeos_web.db_errors import is_lock_contention_error
from lifeos_web.routers import tasks


def test_finance_bootstrap_is_serialized_and_formatting_is_read_only(tmp_path, monkeypatch) -> None:
    from datetime import datetime

    from lifeos_cli.db.models.finance import FinanceAsset
    from lifeos_cli.db.services import finance as finance_services
    from lifeos_web.routers.finance import _finance_asset_decimal_places

    async def scenario() -> None:
        engine = db_session.configure_async_engine(
            create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'finance.db'}")
        )
        factory = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)
        monkeypatch.setattr(db_session, "get_async_session_factory", lambda: factory)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with factory() as session:
                assert await _finance_asset_decimal_places(session) == {}
                assert not list((await session.scalars(select(FinanceAsset))).all())
            app = create_app(allowed_hosts=["testserver"])
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://testserver",
            ) as client:
                responses = await asyncio.gather(
                    *(client.get("/api/v1/finance/assets") for _ in range(3))
                )
                assert [response.status_code for response in responses] == [200, 200, 200]
                assert responses[0].json() == responses[1].json() == responses[2].json()
            async with factory() as session:
                assets = list((await session.scalars(select(FinanceAsset))).all())
                assert len(assets) == len(finance_services.DEFAULT_FINANCE_ASSETS)
                deleted = assets[0]
                deleted.deleted_at = datetime.now(UTC)
                deleted_code = deleted.code
                await session.commit()
            async with factory() as session:
                await finance_services.ensure_default_finance_assets(session)
                await session.commit()
                codes = list((await session.scalars(select(FinanceAsset.code))).all())
                assert deleted_code not in codes
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_lock_classification_uses_extended_codes_not_sql_text() -> None:
    class SnapshotBusy(Exception):
        sqlite_errorcode = 517

    assert is_lock_contention_error(OperationalError("UPDATE tasks", {}, SnapshotBusy()))
    assert not is_lock_contention_error(
        OperationalError("SELECT 'database is locked'", {}, Exception("disk I/O error"))
    )


def test_concurrent_planning_patches_and_independent_reader(tmp_path, monkeypatch) -> None:
    async def scenario() -> None:
        engine = db_session.configure_async_engine(
            create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'requests.db'}")
        )
        factory = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)
        monkeypatch.setattr(db_session, "get_async_session_factory", lambda: factory)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with factory() as session:
                vision = Vision(name="Planning")
                session.add(vision)
                await session.flush()
                records = [
                    Task(
                        vision_id=vision.id,
                        content=str(index),
                        planning_cycle_type="day",
                        planning_cycle_days=1,
                        planning_cycle_start_date=date(2026, 9, 12),
                    )
                    for index in range(3)
                ]
                session.add_all(records)
                await session.commit()
                ids = [record.id for record in records]
            entered, release = asyncio.Event(), asyncio.Event()
            original = tasks.task_services.update_task

            async def delayed_update(session, **kwargs):
                await session.scalar(select(Task.id).where(Task.id == kwargs["task_id"]))
                entered.set()
                await release.wait()
                return await original(session, **kwargs)

            monkeypatch.setattr(tasks.task_services, "update_task", delayed_update)
            app = create_app(allowed_hosts=["testserver"])
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                pending = [
                    asyncio.create_task(
                        client.patch(
                            f"/api/v1/tasks/{task_id}",
                            json={"planning_cycle_start_date": "2026-09-13"},
                        )
                    )
                    for task_id in ids
                ]
                try:
                    await asyncio.wait_for(entered.wait(), timeout=5)
                    await asyncio.sleep(0.05)
                    reader = await asyncio.wait_for(
                        client.get(f"/api/v1/tasks/{ids[0]}"), timeout=2
                    )
                    assert reader.status_code == 200
                    assert reader.json()["planning_cycle_start_date"] == "2026-09-12"
                finally:
                    release.set()
                    responses = await asyncio.wait_for(asyncio.gather(*pending), timeout=10)
                assert [response.status_code for response in responses] == [200, 200, 200]
            async with factory() as session:
                assert set(
                    (await session.scalars(select(Task.planning_cycle_start_date))).all()
                ) == {date(2026, 9, 13)}
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_exhausted_write_lock_returns_503_and_can_be_retried(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db_session, "SQLITE_BUSY_TIMEOUT_MS", 30)

    async def scenario() -> None:
        engine = db_session.configure_async_engine(
            create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'busy.db'}")
        )
        factory = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)
        monkeypatch.setattr(db_session, "get_async_session_factory", lambda: factory)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with factory() as session:
                vision = Vision(name="Busy")
                session.add(vision)
                await session.flush()
                task = Task(vision_id=vision.id, content="Original")
                session.add(task)
                await session.commit()
                task_id = task.id
            app = create_app(allowed_hosts=["testserver"])
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                async with factory() as blocker:
                    await blocker.execute(
                        update(Task).where(Task.id == task_id).values(content="Held")
                    )
                    response = await client.patch(
                        f"/api/v1/tasks/{task_id}",
                        json={"content": "Retry"},
                        headers={"Origin": "http://localhost:5173"},
                    )
                    assert response.status_code == 503
                    assert response.headers["retry-after"] == "1"
                    assert (
                        response.headers["access-control-allow-origin"] == "http://localhost:5173"
                    )
                    assert response.json() == {"detail": "The database is busy; please retry."}
                    await blocker.rollback()
                assert (await client.get(f"/api/v1/tasks/{task_id}")).json()[
                    "content"
                ] == "Original"
                assert (
                    await client.patch(f"/api/v1/tasks/{task_id}", json={"content": "Retry"})
                ).status_code == 200
        finally:
            await engine.dispose()

    asyncio.run(scenario())
