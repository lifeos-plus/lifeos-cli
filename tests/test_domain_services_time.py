from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lifeos_cli.config import clear_config_cache
from lifeos_cli.db.base import Base
from lifeos_cli.db.models.event import Event
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.models.vision import Vision
from lifeos_cli.db.services import events, task_effort, task_mutations, timelogs, visions
from lifeos_cli.db.session import configure_async_engine
from tests.support import utc_datetime


async def _identity_event_view(_: object, event: object) -> object:
    return event


async def _identity_timelog_view(_: object, timelog: object) -> object:
    return timelog


def _set_timezone(monkeypatch: pytest.MonkeyPatch, timezone_name: str = "America/Toronto") -> None:
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", timezone_name)


async def _create_sqlite_session_factory() -> tuple[
    AsyncEngine,
    async_sessionmaker[AsyncSession],
]:
    from lifeos_cli.db import models as db_models

    assert db_models.Event is Event
    engine = configure_async_engine(
        create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, future=True)


def test_create_event_flushes_without_committing(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(
        add=None,
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )

    def fake_add(_: object) -> None:
        pass

    async def fake_ensure_area_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    session.add = fake_add
    monkeypatch.setattr(events, "ensure_event_area_exists", fake_ensure_area_exists)
    monkeypatch.setattr(events, "ensure_event_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(events, "_build_event_view", _identity_event_view)

    event = asyncio.run(
        events.create_event(
            cast(Any, session),
            payload=events.EventCreateInput(
                title="Doctor appointment",
                start_time=utc_datetime(2026, 4, 10, 13, 0),
            ),
        )
    )

    assert event.title == "Doctor appointment"
    assert event.event_type == "appointment"
    assert event.start_time == utc_datetime(2026, 4, 10, 13, 0)
    session.flush.assert_awaited_once()
    session.commit.assert_not_called()


def test_create_timelog_flushes_without_committing(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(
        add=None,
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )

    def fake_add(_: object) -> None:
        pass

    async def fake_ensure_area_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_flush_and_recompute(_: object, **__: object) -> None:
        await session.flush()

    async def fake_sync_tags(_: object, **kwargs: object) -> None:
        assert kwargs["entity_id"] == UUID("11111111-1111-1111-1111-111111111111")

    def record_add(timelog: object) -> None:
        session.added_timelog = timelog
        fake_add(timelog)

    async def fake_flush() -> None:
        added_timelog = getattr(session, "added_timelog", None)
        if added_timelog is not None and getattr(added_timelog, "id", None) is None:
            added_timelog.id = UUID("11111111-1111-1111-1111-111111111111")

    session.add = record_add
    session.flush = AsyncMock(side_effect=fake_flush)
    monkeypatch.setattr(timelogs, "ensure_timelog_area_exists", fake_ensure_area_exists)
    monkeypatch.setattr(timelogs, "ensure_timelog_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(timelogs, "sync_entity_tags", fake_sync_tags)
    monkeypatch.setattr(
        timelogs,
        "_flush_and_recompute_timelog_dependents",
        fake_flush_and_recompute,
    )
    monkeypatch.setattr(timelogs, "_build_timelog_view", _identity_timelog_view)

    timelog = asyncio.run(
        timelogs.create_timelog(
            cast(Any, session),
            payload=timelogs.TimelogCreateInput(
                title="Deep work",
                start_time=utc_datetime(2026, 4, 10, 13, 0),
                end_time=utc_datetime(2026, 4, 10, 14, 0),
                tag_ids=[UUID("22222222-2222-2222-2222-222222222222")],
            ),
        )
    )

    assert timelog.title == "Deep work"
    assert timelog.start_time == utc_datetime(2026, 4, 10, 13, 0)
    assert timelog.end_time == utc_datetime(2026, 4, 10, 14, 0)
    assert session.flush.await_count == 2
    session.commit.assert_not_called()


def test_timelog_mutations_sync_vision_experience() -> None:
    async def scenario() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                vision = Vision(name="Build fitness", status="active")
                session.add(vision)
                await session.flush()
                task = Task(
                    vision_id=vision.id,
                    content="Run",
                    status="todo",
                    priority=0,
                    display_order=0,
                )
                session.add(task)
                await session.flush()

                created = await timelogs.create_timelog(
                    session,
                    payload=timelogs.TimelogCreateInput(
                        title="Morning run",
                        start_time=utc_datetime(2026, 4, 10, 11, 0),
                        end_time=utc_datetime(2026, 4, 10, 11, 30),
                        task_id=task.id,
                    ),
                )
                await session.refresh(task)
                await session.refresh(vision)

                assert task.actual_effort_self == 30
                assert task.actual_effort_total == 30
                assert vision.experience_points == 30
                assert vision.stage == 0

                await timelogs.update_timelog(
                    session,
                    timelog_id=created.id,
                    changes=timelogs.TimelogUpdateInput(
                        end_time=utc_datetime(2026, 4, 10, 12, 0),
                    ),
                )
                await session.refresh(task)
                await session.refresh(vision)

                assert task.actual_effort_self == 60
                assert task.actual_effort_total == 60
                assert vision.experience_points == 60

                await timelogs.delete_timelog(session, timelog_id=created.id)
                await session.refresh(task)
                await session.refresh(vision)

                assert task.actual_effort_self == 0
                assert task.actual_effort_total == 0
                assert vision.experience_points == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_task_delete_syncs_vision_experience() -> None:
    async def scenario() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                vision = Vision(name="Build focus", status="active")
                session.add(vision)
                await session.flush()
                task = Task(
                    vision_id=vision.id,
                    content="Deep work",
                    status="todo",
                    priority=0,
                    display_order=0,
                    actual_effort_self=120,
                    actual_effort_total=120,
                )
                session.add(task)
                await session.flush()

                await visions.sync_vision_experience_for_vision_ids(
                    session,
                    vision_ids=[vision.id],
                )
                await session.refresh(vision)
                assert vision.experience_points == 120
                assert vision.stage == 1

                await task_mutations.delete_task(session, task_id=task.id)
                await session.refresh(vision)

                assert vision.experience_points == 0
                assert vision.stage == 0
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_create_event_normalizes_offset_datetimes_to_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(add=None, flush=AsyncMock(), refresh=AsyncMock())

    def fake_add(_: object) -> None:
        pass

    async def fake_ensure_area_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    session.add = fake_add
    monkeypatch.setattr(events, "ensure_event_area_exists", fake_ensure_area_exists)
    monkeypatch.setattr(events, "ensure_event_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(events, "_build_event_view", _identity_event_view)

    created = asyncio.run(
        events.create_event(
            cast(Any, session),
            payload=events.EventCreateInput(
                title="Offset event",
                start_time=datetime(2026, 4, 10, 9, 0, tzinfo=timezone(timedelta(hours=-4))),
                end_time=datetime(2026, 4, 10, 10, 0, tzinfo=timezone(timedelta(hours=-4))),
            ),
        )
    )

    assert created.start_time == utc_datetime(2026, 4, 10, 13, 0)
    assert created.end_time == utc_datetime(2026, 4, 10, 14, 0)


def test_create_event_interprets_naive_datetimes_using_preferred_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_timezone(monkeypatch)
    session = SimpleNamespace(add=None, flush=AsyncMock(), refresh=AsyncMock())

    def fake_add(_: object) -> None:
        pass

    async def fake_ensure_area_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    session.add = fake_add
    monkeypatch.setattr(events, "ensure_event_area_exists", fake_ensure_area_exists)
    monkeypatch.setattr(events, "ensure_event_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(events, "_build_event_view", _identity_event_view)

    created = asyncio.run(
        events.create_event(
            cast(Any, session),
            payload=events.EventCreateInput(
                title="Local event",
                start_time=datetime(2026, 4, 10, 9, 0),
                end_time=datetime(2026, 4, 10, 10, 0),
            ),
        )
    )

    assert created.start_time == utc_datetime(2026, 4, 10, 13, 0)
    assert created.end_time == utc_datetime(2026, 4, 10, 14, 0)
    clear_config_cache()


def test_create_timelog_interprets_naive_datetimes_using_preferred_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_timezone(monkeypatch)
    session = SimpleNamespace(add=None, flush=AsyncMock(), refresh=AsyncMock())

    def fake_add(_: object) -> None:
        pass

    async def fake_ensure_area_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_flush_and_recompute(_: object, **__: object) -> None:
        await session.flush()

    session.add = fake_add
    monkeypatch.setattr(timelogs, "ensure_timelog_area_exists", fake_ensure_area_exists)
    monkeypatch.setattr(timelogs, "ensure_timelog_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(
        timelogs,
        "_flush_and_recompute_timelog_dependents",
        fake_flush_and_recompute,
    )
    monkeypatch.setattr(timelogs, "_build_timelog_view", _identity_timelog_view)

    created = asyncio.run(
        timelogs.create_timelog(
            cast(Any, session),
            payload=timelogs.TimelogCreateInput(
                title="Local timelog",
                start_time=datetime(2026, 4, 10, 9, 0),
                end_time=datetime(2026, 4, 10, 10, 0),
            ),
        )
    )

    assert created.start_time == utc_datetime(2026, 4, 10, 13, 0)
    assert created.end_time == utc_datetime(2026, 4, 10, 14, 0)
    clear_config_cache()


def test_create_event_accepts_recurrence_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(add=None, flush=AsyncMock(), refresh=AsyncMock())

    def fake_add(_: object) -> None:
        pass

    async def fake_ensure_area_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    session.add = fake_add
    monkeypatch.setattr(events, "ensure_event_area_exists", fake_ensure_area_exists)
    monkeypatch.setattr(events, "ensure_event_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(events, "_build_event_view", _identity_event_view)

    created = asyncio.run(
        events.create_event(
            cast(Any, session),
            payload=events.EventCreateInput(
                title="Daily review",
                start_time=utc_datetime(2026, 4, 10, 13, 0),
                recurrence_frequency="daily",
                recurrence_interval=2,
                recurrence_count=5,
            ),
        )
    )

    assert created.recurrence_frequency == "daily"
    assert created.recurrence_interval == 2
    assert created.recurrence_count == 5


def test_create_event_accepts_monthly_recurrence(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(add=None, flush=AsyncMock(), refresh=AsyncMock())

    def fake_add(_: object) -> None:
        pass

    async def fake_ensure_area_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    session.add = fake_add
    monkeypatch.setattr(events, "ensure_event_area_exists", fake_ensure_area_exists)
    monkeypatch.setattr(events, "ensure_event_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(events, "_build_event_view", _identity_event_view)

    created = asyncio.run(
        events.create_event(
            cast(Any, session),
            payload=events.EventCreateInput(
                title="Monthly review",
                start_time=utc_datetime(2026, 4, 30, 20, 0),
                recurrence_frequency="monthly",
            ),
        )
    )

    assert created.recurrence_frequency == "monthly"
    assert created.recurrence_interval == 1
    assert created.recurrence_count is None


def test_create_event_accepts_advanced_recurrence_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(add=None, flush=AsyncMock(), refresh=AsyncMock())

    def fake_add(_: object) -> None:
        pass

    async def fake_ensure_area_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    session.add = fake_add
    monkeypatch.setattr(events, "ensure_event_area_exists", fake_ensure_area_exists)
    monkeypatch.setattr(events, "ensure_event_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(events, "_build_event_view", _identity_event_view)

    created = asyncio.run(
        events.create_event(
            cast(Any, session),
            payload=events.EventCreateInput(
                title="Monthly review",
                start_time=utc_datetime(2026, 4, 13, 13, 0),
                recurrence_frequency="monthly",
                recurrence_rule={
                    "byweekday_ordinals": [{"weekday": "monday", "ordinal": 2}],
                },
            ),
        )
    )

    assert created.recurrence_rule == {"byweekday_ordinals": [{"weekday": "monday", "ordinal": 2}]}


def test_create_event_accepts_event_type(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(add=None, flush=AsyncMock(), refresh=AsyncMock())

    def fake_add(_: object) -> None:
        pass

    async def fake_ensure_area_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    session.add = fake_add
    monkeypatch.setattr(events, "ensure_event_area_exists", fake_ensure_area_exists)
    monkeypatch.setattr(events, "ensure_event_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(events, "_build_event_view", _identity_event_view)

    created = asyncio.run(
        events.create_event(
            cast(Any, session),
            payload=events.EventCreateInput(
                title="Focus block",
                start_time=utc_datetime(2026, 4, 10, 13, 0),
                event_type="timeblock",
            ),
        )
    )

    assert created.event_type == "timeblock"


def test_create_timelog_interprets_naive_datetimes_using_utc_preference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_timezone(monkeypatch, "UTC")
    session = SimpleNamespace(add=None, flush=AsyncMock(), refresh=AsyncMock())

    def fake_add(_: object) -> None:
        pass

    async def fake_ensure_area_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_flush_and_recompute(_: object, **__: object) -> None:
        await session.flush()

    session.add = fake_add
    monkeypatch.setattr(timelogs, "ensure_timelog_area_exists", fake_ensure_area_exists)
    monkeypatch.setattr(timelogs, "ensure_timelog_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(
        timelogs,
        "_flush_and_recompute_timelog_dependents",
        fake_flush_and_recompute,
    )
    monkeypatch.setattr(timelogs, "_build_timelog_view", _identity_timelog_view)

    created = asyncio.run(
        timelogs.create_timelog(
            cast(Any, session),
            payload=timelogs.TimelogCreateInput(
                title="Naive record",
                start_time=datetime(2026, 4, 10, 13, 0),
                end_time=datetime(2026, 4, 10, 14, 0),
            ),
        )
    )

    assert created.start_time == utc_datetime(2026, 4, 10, 13, 0)
    assert created.end_time == utc_datetime(2026, 4, 10, 14, 0)
    clear_config_cache()


def test_timelog_minutes_uses_whole_positive_minutes() -> None:
    timelog = SimpleNamespace(
        start_time=utc_datetime(2026, 4, 10, 13, 0),
        end_time=utc_datetime(2026, 4, 10, 13, 59, 59),
    )
    invalid_timelog = SimpleNamespace(
        start_time=utc_datetime(2026, 4, 10, 13, 0),
        end_time=utc_datetime(2026, 4, 10, 12, 59),
    )

    assert task_effort._timelog_minutes(cast(Any, timelog)) == 59
    assert task_effort._timelog_minutes(cast(Any, invalid_timelog)) == 0


def test_recompute_vision_task_efforts_clears_old_parent_rollup() -> None:
    async def scenario() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                vision = Vision(name="Work")
                session.add(vision)
                await session.flush()
                old_parent = Task(vision_id=vision.id, content="Old parent")
                new_parent = Task(vision_id=vision.id, content="New parent", display_order=1)
                session.add_all([old_parent, new_parent])
                await session.flush()
                child = Task(
                    vision_id=vision.id,
                    parent_task_id=old_parent.id,
                    content="Moved child",
                    display_order=2,
                )
                session.add(child)
                await session.flush()
                session.add(
                    Timelog(
                        title="Deep work",
                        start_time=utc_datetime(2026, 4, 10, 13, 0),
                        end_time=utc_datetime(2026, 4, 10, 14, 30),
                        task_id=child.id,
                    )
                )
                await session.flush()

                await visions.recompute_vision_task_efforts(session, vision_id=vision.id)
                await session.refresh(old_parent)
                assert old_parent.actual_effort_total == 90

                child.parent_task_id = new_parent.id
                await session.flush()

                result = await visions.recompute_vision_task_efforts(session, vision_id=vision.id)
                await session.refresh(old_parent)
                await session.refresh(new_parent)
                await session.refresh(child)

                assert set(result.recomputed_roots) == {old_parent.id, new_parent.id}
                assert old_parent.actual_effort_total == 0
                assert new_parent.actual_effort_total == 90
                assert child.actual_effort_total == 90
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_update_event_can_clear_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    event = SimpleNamespace(
        id=UUID("abababab-abab-abab-abab-abababababab"),
        title="Doctor appointment",
        description="Checkup",
        start_time=utc_datetime(2026, 4, 10, 9, 0),
        end_time=utc_datetime(2026, 4, 10, 10, 0),
        priority=3,
        status="planned",
        event_type="appointment",
        is_all_day=False,
        recurrence_frequency=None,
        recurrence_interval=None,
        recurrence_count=None,
        recurrence_until=None,
        area_id=UUID("11111111-1111-1111-1111-111111111111"),
        task_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    session = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock(), commit=AsyncMock())

    async def fake_get_event(_: object, *, event_id: UUID) -> object:
        assert event_id == UUID("abababab-abab-abab-abab-abababababab")
        return event

    async def fake_sync_tags(_: object, **__: object) -> None:
        return None

    async def fake_sync_people(_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(events, "_get_event_model", fake_get_event)
    monkeypatch.setattr(events, "_build_event_view", _identity_event_view)
    monkeypatch.setattr(events, "sync_entity_tags", fake_sync_tags)
    monkeypatch.setattr(events, "sync_entity_people", fake_sync_people)

    updated_event = asyncio.run(
        events.update_event(
            cast(Any, session),
            event_id=UUID("abababab-abab-abab-abab-abababababab"),
            changes=events.EventUpdateInput(
                clear_description=True,
                clear_end_time=True,
                clear_area=True,
                clear_task=True,
                clear_tags=True,
                clear_people=True,
            ),
        )
    )

    assert updated_event.description is None
    assert updated_event.end_time is None
    assert updated_event.area_id is None
    assert updated_event.task_id is None
    session.flush.assert_awaited_once()
    session.commit.assert_not_called()


def test_sqlite_roundtrip_returns_utc_aware_datetimes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(events, "_build_event_view", _identity_event_view)

    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                event = Event(
                    title="SQLite appointment",
                    start_time=datetime(
                        2026,
                        6,
                        15,
                        6,
                        30,
                        tzinfo=timezone(timedelta(hours=-4)),
                    ),
                    end_time=datetime(2026, 6, 15, 7, 30, tzinfo=timezone(timedelta(hours=-4))),
                )
                timelog = Timelog(
                    title="SQLite work",
                    start_time=utc_datetime(2026, 6, 15, 10, 30),
                    end_time=utc_datetime(2026, 6, 15, 11, 0),
                )
                session.add_all([event, timelog])
                await session.commit()
                event_id = event.id
                timelog_id = timelog.id

            async with session_factory() as session:
                loaded_event = await session.get(Event, event_id)
                loaded_timelog = await session.get(Timelog, timelog_id)

                assert loaded_event is not None
                assert loaded_timelog is not None
                assert loaded_event.start_time == utc_datetime(2026, 6, 15, 10, 30)
                assert loaded_event.end_time == utc_datetime(2026, 6, 15, 11, 30)
                assert loaded_event.created_at.utcoffset() == timedelta(0)
                assert loaded_timelog.start_time == utc_datetime(2026, 6, 15, 10, 30)
                assert loaded_timelog.end_time.utcoffset() == timedelta(0)

            async with session_factory() as session:
                updated_event = await events.update_event(
                    session,
                    event_id=event_id,
                    changes=events.EventUpdateInput(
                        end_time=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
                    ),
                )

                assert updated_event.start_time == utc_datetime(2026, 6, 15, 10, 30)
                assert updated_event.end_time == utc_datetime(2026, 6, 15, 12, 0)
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_timelog_view_does_not_hydrate_soft_deleted_task() -> None:
    async def scenario() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                vision = Vision(name="Work")
                session.add(vision)
                await session.flush()
                task = Task(vision_id=vision.id, content="Deleted task")
                session.add(task)
                await session.flush()
                timelog = Timelog(
                    title="Deep work",
                    start_time=utc_datetime(2026, 6, 30, 13, 0),
                    end_time=utc_datetime(2026, 6, 30, 14, 0),
                    task_id=task.id,
                )
                session.add(timelog)
                await session.flush()
                task.soft_delete()
                await session.commit()
                timelog_id = timelog.id

            async with session_factory() as session:
                loaded = await timelogs.get_timelog(session, timelog_id=timelog_id)

                assert loaded is not None
                assert loaded.task_id == task.id
                assert loaded.task is None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_delete_event_single_records_skip_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    event = SimpleNamespace(
        id=UUID("abababab-abab-abab-abab-abababababab"),
        start_time=utc_datetime(2026, 4, 10, 13, 0),
        end_time=utc_datetime(2026, 4, 10, 14, 0),
        recurrence_frequency="daily",
        recurrence_interval=1,
        recurrence_count=3,
        recurrence_until=None,
        recurrence_parent_event_id=None,
    )
    session = SimpleNamespace(flush=AsyncMock())
    record_skip = AsyncMock()

    async def fake_get_event(_: object, *, event_id: UUID) -> object:
        assert event_id == UUID("abababab-abab-abab-abab-abababababab")
        return event

    async def fake_get_override_event(
        _: object,
        *,
        master_event_id: UUID,
        instance_start: datetime,
    ) -> object | None:
        assert master_event_id == event.id
        assert instance_start == utc_datetime(2026, 4, 11, 13, 0)
        return None

    monkeypatch.setattr(events, "_get_event_model", fake_get_event)
    monkeypatch.setattr(events, "_get_override_event_for_instance", fake_get_override_event)
    monkeypatch.setattr(events, "_record_skip_exception", record_skip)

    asyncio.run(
        events.delete_event(
            cast(Any, session),
            event_id=UUID("abababab-abab-abab-abab-abababababab"),
            scope="single",
            instance_start=utc_datetime(2026, 4, 11, 13, 0),
        )
    )

    record_skip.assert_awaited_once()
    session.flush.assert_awaited_once()


def test_delete_event_single_interprets_naive_instance_start_using_preferred_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_timezone(monkeypatch)
    event = SimpleNamespace(
        id=UUID("abababab-abab-abab-abab-abababababab"),
        start_time=utc_datetime(2026, 4, 10, 13, 0),
        end_time=utc_datetime(2026, 4, 10, 14, 0),
        recurrence_frequency="daily",
        recurrence_interval=1,
        recurrence_count=3,
        recurrence_until=None,
        recurrence_parent_event_id=None,
    )
    session = SimpleNamespace(flush=AsyncMock())
    record_skip = AsyncMock()

    async def fake_get_event(_: object, *, event_id: UUID) -> object:
        assert event_id == UUID("abababab-abab-abab-abab-abababababab")
        return event

    async def fake_get_override_event(
        _: object,
        *,
        master_event_id: UUID,
        instance_start: datetime,
    ) -> object | None:
        assert master_event_id == event.id
        assert instance_start == utc_datetime(2026, 4, 11, 13, 0)
        return None

    monkeypatch.setattr(events, "_get_event_model", fake_get_event)
    monkeypatch.setattr(events, "_get_override_event_for_instance", fake_get_override_event)
    monkeypatch.setattr(events, "_record_skip_exception", record_skip)

    asyncio.run(
        events.delete_event(
            cast(Any, session),
            event_id=UUID("abababab-abab-abab-abab-abababababab"),
            scope="single",
            instance_start=datetime(2026, 4, 11, 9, 0),
        )
    )

    record_skip.assert_awaited_once()
    session.flush.assert_awaited_once()
    clear_config_cache()


def test_list_event_occurrences_expands_recurring_series_and_skips_exceptions() -> None:
    class _Result:
        def __init__(self, values: list[object]) -> None:
            self._values = values

        def scalars(self) -> list[object]:
            return self._values

    class _Session:
        def __init__(self) -> None:
            self._results = [
                _Result(
                    [
                        SimpleNamespace(
                            id=UUID("abababab-abab-abab-abab-abababababab"),
                            title="Daily review",
                            status="planned",
                            event_type="appointment",
                            start_time=utc_datetime(2026, 4, 10, 13, 0),
                            end_time=utc_datetime(2026, 4, 10, 14, 0),
                            task_id=None,
                            deleted_at=None,
                            recurrence_frequency="daily",
                            recurrence_interval=1,
                            recurrence_count=3,
                            recurrence_until=None,
                            recurrence_parent_event_id=None,
                        )
                    ]
                ),
                _Result(
                    [
                        SimpleNamespace(
                            master_event_id=UUID("abababab-abab-abab-abab-abababababab"),
                            instance_start=utc_datetime(2026, 4, 11, 13, 0),
                        )
                    ]
                ),
                _Result([]),
            ]

        async def execute(self, statement: object) -> _Result:
            return self._results.pop(0)

    occurrences = asyncio.run(
        events.list_event_occurrences(
            cast(Any, _Session()),
            query=events.EventOccurrenceQuery(
                window_start=utc_datetime(2026, 4, 10, 0, 0),
                window_end=utc_datetime(2026, 4, 12, 23, 59),
            ),
        )
    )

    assert [item.start_time for item in occurrences] == [
        utc_datetime(2026, 4, 10, 13, 0),
        utc_datetime(2026, 4, 12, 13, 0),
    ]


def test_list_event_occurrences_treats_naive_sqlite_datetimes_as_utc() -> None:
    class _Result:
        def __init__(self, values: list[object]) -> None:
            self._values = values

        def scalars(self) -> list[object]:
            return self._values

    class _Session:
        def __init__(self) -> None:
            self._results = [
                _Result(
                    [
                        SimpleNamespace(
                            id=UUID("abababab-abab-abab-abab-abababababab"),
                            title="Daily review",
                            status="planned",
                            event_type="appointment",
                            start_time=datetime(2026, 4, 10, 13, 0),
                            end_time=datetime(2026, 4, 10, 14, 0),
                            task_id=None,
                            deleted_at=None,
                            recurrence_frequency="daily",
                            recurrence_interval=1,
                            recurrence_count=3,
                            recurrence_until=None,
                            recurrence_parent_event_id=None,
                        )
                    ]
                ),
                _Result(
                    [
                        SimpleNamespace(
                            master_event_id=UUID("abababab-abab-abab-abab-abababababab"),
                            instance_start=datetime(2026, 4, 11, 13, 0),
                        )
                    ]
                ),
                _Result([]),
            ]

        async def execute(self, statement: object) -> _Result:
            return self._results.pop(0)

    occurrences = asyncio.run(
        events.list_event_occurrences(
            cast(Any, _Session()),
            query=events.EventOccurrenceQuery(
                window_start=utc_datetime(2026, 4, 10, 0, 0),
                window_end=utc_datetime(2026, 4, 12, 23, 59),
            ),
        )
    )

    assert [item.start_time for item in occurrences] == [
        utc_datetime(2026, 4, 10, 13, 0),
        utc_datetime(2026, 4, 12, 13, 0),
    ]


def test_list_event_occurrences_expands_monthly_series() -> None:
    class _Result:
        def __init__(self, values: list[object]) -> None:
            self._values = values

        def scalars(self) -> list[object]:
            return self._values

    class _Session:
        def __init__(self) -> None:
            self._results = [
                _Result(
                    [
                        SimpleNamespace(
                            id=UUID("acacacac-acac-acac-acac-acacacacacac"),
                            title="Monthly review",
                            status="planned",
                            event_type="appointment",
                            start_time=utc_datetime(2026, 4, 30, 20, 0),
                            end_time=utc_datetime(2026, 4, 30, 21, 0),
                            task_id=None,
                            deleted_at=None,
                            recurrence_frequency="monthly",
                            recurrence_interval=1,
                            recurrence_count=3,
                            recurrence_until=None,
                            recurrence_parent_event_id=None,
                        )
                    ]
                ),
                _Result([]),
                _Result([]),
            ]

        async def execute(self, statement: object) -> _Result:
            return self._results.pop(0)

    occurrences = asyncio.run(
        events.list_event_occurrences(
            cast(Any, _Session()),
            query=events.EventOccurrenceQuery(
                window_start=utc_datetime(2026, 4, 1, 0, 0),
                window_end=utc_datetime(2026, 6, 30, 23, 59),
            ),
        )
    )

    assert [item.start_time for item in occurrences] == [
        utc_datetime(2026, 4, 30, 20, 0),
        utc_datetime(2026, 5, 30, 20, 0),
        utc_datetime(2026, 6, 30, 20, 0),
    ]


def test_list_event_occurrences_expands_advanced_recurrence_rule() -> None:
    class _Result:
        def __init__(self, values: list[object]) -> None:
            self._values = values

        def scalars(self) -> list[object]:
            return self._values

    class _Session:
        def __init__(self) -> None:
            self._results = [
                _Result(
                    [
                        SimpleNamespace(
                            id=UUID("adadadad-adad-adad-adad-adadadadadad"),
                            title="Monthly review",
                            status="planned",
                            event_type="appointment",
                            start_time=utc_datetime(2026, 4, 13, 20, 0),
                            end_time=utc_datetime(2026, 4, 13, 21, 0),
                            task_id=None,
                            deleted_at=None,
                            recurrence_frequency="monthly",
                            recurrence_interval=1,
                            recurrence_count=3,
                            recurrence_until=None,
                            recurrence_rule={
                                "byweekday_ordinals": [{"weekday": "monday", "ordinal": 2}],
                            },
                            recurrence_parent_event_id=None,
                        )
                    ]
                ),
                _Result([]),
                _Result([]),
            ]

        async def execute(self, statement: object) -> _Result:
            return self._results.pop(0)

    occurrences = asyncio.run(
        events.list_event_occurrences(
            cast(Any, _Session()),
            query=events.EventOccurrenceQuery(
                window_start=utc_datetime(2026, 4, 1, 0, 0),
                window_end=utc_datetime(2026, 6, 30, 23, 59),
            ),
        )
    )

    assert [item.start_time for item in occurrences] == [
        utc_datetime(2026, 4, 13, 20, 0),
        utc_datetime(2026, 5, 11, 20, 0),
        utc_datetime(2026, 6, 8, 20, 0),
    ]


def test_list_event_occurrences_applies_all_supported_filters() -> None:
    class _Result:
        def __init__(self, values: list[object]) -> None:
            self._values = values

        def scalars(self) -> list[object]:
            return self._values

    class _Session:
        def __init__(self) -> None:
            self.statements: list[object] = []
            self._results = [_Result([]), _Result([])]

        async def execute(self, statement: object) -> _Result:
            self.statements.append(statement)
            return self._results.pop(0)

    area_id = UUID("11111111-1111-1111-1111-111111111111")
    task_id = UUID("22222222-2222-2222-2222-222222222222")
    person_id = UUID("33333333-3333-3333-3333-333333333333")
    tag_id = UUID("44444444-4444-4444-4444-444444444444")
    session = _Session()

    occurrences = asyncio.run(
        events.list_event_occurrences(
            cast(Any, session),
            query=events.EventOccurrenceQuery(
                window_start=utc_datetime(2026, 4, 10, 0, 0),
                window_end=utc_datetime(2026, 4, 12, 23, 59),
                filters=events.EventQueryFilters(
                    title_contains="review",
                    status="planned",
                    event_type="deadline",
                    area_id=area_id,
                    task_id=task_id,
                    person_id=person_id,
                    tag_id=tag_id,
                ),
            ),
        )
    )

    assert occurrences == []
    assert len(session.statements) == 2
    master_sql = str(session.statements[0])
    override_sql = str(session.statements[1])

    for statement_sql in (master_sql, override_sql):
        assert "person_associations" in statement_sql
        assert "tag_associations" in statement_sql
        assert "events.area_id" in statement_sql
        assert "events.task_id" in statement_sql
        assert "events.status" in statement_sql
        assert "events.event_type" in statement_sql
        assert "title" in statement_sql


def test_list_events_with_one_sided_window_uses_overlap_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Result:
        def scalars(self) -> list[object]:
            return []

    class _Session:
        def __init__(self) -> None:
            self.statements: list[object] = []

        async def execute(self, statement: object) -> _Result:
            self.statements.append(statement)
            return _Result()

    list_occurrences = AsyncMock(return_value=[])

    monkeypatch.setattr(events, "list_event_occurrences", list_occurrences)

    session = _Session()
    listed = asyncio.run(
        events.list_events(
            cast(Any, session),
            query=events.EventListInput(
                filters=events.EventQueryFilters(
                    window_start=utc_datetime(2026, 4, 10, 12, 0),
                )
            ),
        )
    )

    assert listed == []
    list_occurrences.assert_not_awaited()
    assert len(session.statements) == 1
    statement_sql = str(session.statements[0])
    assert "end_time IS NULL OR" in statement_sql
    assert "end_time >=" in statement_sql


def test_normalize_event_filters_deduplicates_discrete_dates() -> None:
    filters = events._normalize_event_filters(
        events.EventQueryFilters(
            date_values=(date(2026, 4, 10), date(2026, 4, 10), date(2026, 4, 12))
        )
    )

    assert filters.date_values == (date(2026, 4, 10), date(2026, 4, 12))


def test_resolve_timelog_filters_deduplicates_discrete_dates() -> None:
    filters = timelogs._resolve_timelog_filters(
        timelogs.TimelogQueryFilters(
            date_values=(date(2026, 4, 10), date(2026, 4, 10), date(2026, 4, 12))
        )
    )

    assert filters.date_values == (date(2026, 4, 10), date(2026, 4, 12))


def test_timelog_with_task_filter_requires_linked_task() -> None:
    statement = timelogs._apply_timelog_area_task_filters(
        select(Timelog),
        filters=timelogs.TimelogQueryFilters(with_task=True),
    )

    assert "timelogs.task_id IS NOT NULL" in str(statement)


def test_update_timelog_can_clear_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    timelog = SimpleNamespace(
        id=UUID("cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdcd"),
        title="Deep work",
        start_time=utc_datetime(2026, 4, 10, 13, 0),
        end_time=utc_datetime(2026, 4, 10, 14, 0),
        tracking_method="manual",
        location="Desk",
        energy_level=4,
        notes="Focused",
        area_id=UUID("11111111-1111-1111-1111-111111111111"),
        task_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    session = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock(), commit=AsyncMock())

    async def fake_get_timelog(
        _: object,
        *,
        timelog_id: UUID,
    ) -> object:
        assert timelog_id == UUID("cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdcd")
        return timelog

    async def fake_sync_tags(_: object, **__: object) -> None:
        return None

    async def fake_sync_people(_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(timelogs, "_get_timelog_model", fake_get_timelog)
    monkeypatch.setattr(timelogs, "_build_timelog_view", _identity_timelog_view)
    monkeypatch.setattr(timelogs, "sync_entity_tags", fake_sync_tags)
    monkeypatch.setattr(timelogs, "sync_entity_people", fake_sync_people)
    recompute_task_effort = AsyncMock()
    monkeypatch.setattr(
        timelogs,
        "recompute_task_effort_after_timelog_change",
        recompute_task_effort,
    )
    recompute_timelog_stats = AsyncMock()
    monkeypatch.setattr(
        timelogs,
        "recompute_timelog_stats_groupby_area_after_change",
        recompute_timelog_stats,
    )
    sync_vision_experience = AsyncMock()
    monkeypatch.setattr(
        timelogs,
        "sync_vision_experience_for_task_ids",
        sync_vision_experience,
    )

    updated_timelog = asyncio.run(
        timelogs.update_timelog(
            cast(Any, session),
            timelog_id=UUID("cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdcd"),
            changes=timelogs.TimelogUpdateInput(
                clear_location=True,
                clear_energy_level=True,
                clear_notes=True,
                clear_area=True,
                clear_task=True,
                clear_tags=True,
                clear_people=True,
            ),
        )
    )

    assert updated_timelog.location is None
    assert updated_timelog.energy_level is None
    assert updated_timelog.notes is None
    assert updated_timelog.area_id is None
    assert updated_timelog.task_id is None
    sync_vision_experience.assert_awaited_once_with(
        cast(Any, session),
        task_ids=[UUID("22222222-2222-2222-2222-222222222222")],
    )
    recompute_task_effort.assert_awaited_once_with(
        cast(Any, session),
        old_task_id=UUID("22222222-2222-2222-2222-222222222222"),
        new_task_id=None,
    )
    recompute_timelog_stats.assert_awaited_once()
    assert session.flush.await_count == 2
    session.commit.assert_not_called()


def test_batch_update_timelogs_applies_title_replace_and_relation_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timelog_id = UUID("cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdcd")
    missing_id = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    task_id = UUID("22222222-2222-2222-2222-222222222222")
    timelog = SimpleNamespace(
        id=timelog_id,
        title="Deep work",
        task_id=None,
        start_time=None,
        end_time=None,
        area_id=None,
    )
    session = SimpleNamespace()

    async def fake_load_batch_timelog_models(
        _: object,
        *,
        timelog_ids: list[UUID],
    ) -> dict[UUID, object]:
        assert timelog_ids == [timelog_id, missing_id]
        return {timelog_id: timelog}

    ensure_task = AsyncMock()
    replace_people = AsyncMock()
    flush_recompute = AsyncMock()
    monkeypatch.setattr(timelogs, "_load_batch_timelog_models", fake_load_batch_timelog_models)
    monkeypatch.setattr(timelogs, "ensure_timelog_task_exists", ensure_task)
    monkeypatch.setattr(timelogs, "_replace_batch_timelog_people", replace_people)
    monkeypatch.setattr(
        timelogs,
        "_flush_and_recompute_batch_timelog_dependents",
        flush_recompute,
    )

    result = asyncio.run(
        timelogs.batch_update_timelogs(
            cast(Any, session),
            timelog_ids=[timelog_id, timelog_id, missing_id],
            changes=timelogs.TimelogBatchUpdateInput(
                find_title_text="Deep",
                replace_title_text="Focused",
                changes=timelogs.TimelogUpdateInput(
                    task_id=task_id,
                    clear_people=True,
                ),
            ),
        )
    )

    assert result.updated_count == 1
    assert result.failed_ids == (missing_id,)
    assert timelog.title == "Focused work"
    assert timelog.task_id == task_id
    ensure_task.assert_awaited_once_with(cast(Any, session), task_id)
    replace_people.assert_awaited_once_with(
        cast(Any, session),
        timelog_ids=[timelog_id],
        desired_person_ids=[],
        validated_person_ids=[],
    )
    flush_recompute.assert_awaited_once()


def test_batch_update_timelogs_reports_unchanged_title_replace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timelog_id = UUID("cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdcd")
    session = SimpleNamespace()
    timelog = SimpleNamespace(
        id=timelog_id,
        title="Deep work",
        task_id=None,
        start_time=None,
        end_time=None,
        area_id=None,
    )

    async def fake_load_batch_timelog_models(
        _: object,
        *,
        timelog_ids: list[UUID],
    ) -> dict[UUID, object]:
        assert timelog_ids == [timelog_id]
        return {timelog_id: timelog}

    flush_recompute = AsyncMock()
    monkeypatch.setattr(timelogs, "_load_batch_timelog_models", fake_load_batch_timelog_models)
    monkeypatch.setattr(
        timelogs,
        "_flush_and_recompute_batch_timelog_dependents",
        flush_recompute,
    )

    result = asyncio.run(
        timelogs.batch_update_timelogs(
            cast(Any, session),
            timelog_ids=[timelog_id],
            changes=timelogs.TimelogBatchUpdateInput(
                find_title_text="Planning",
                replace_title_text="Review",
            ),
        )
    )

    assert result.updated_count == 0
    assert result.unchanged_ids == (timelog_id,)
    flush_recompute.assert_not_awaited()


def test_batch_timelog_dependent_recompute_skips_metadata_only_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id = UUID("22222222-2222-2222-2222-222222222222")
    area_id = UUID("33333333-3333-3333-3333-333333333333")
    timestamp = utc_datetime(2026, 4, 9, 12, 0)
    session = SimpleNamespace(flush=AsyncMock())
    recompute_task = AsyncMock()
    recompute_daily = AsyncMock()
    recompute_aggregated = AsyncMock()
    monkeypatch.setattr(timelogs, "recompute_totals_upwards", recompute_task)
    monkeypatch.setattr(
        timelogs,
        "recompute_daily_timelog_stats_groupby_area_for_dates",
        recompute_daily,
    )
    monkeypatch.setattr(
        timelogs,
        "recompute_aggregated_timelog_stats_groupby_area_for_dates",
        recompute_aggregated,
    )

    snapshot = timelogs._TimelogDependencySnapshot(
        task_id=task_id,
        start_time=timestamp,
        end_time=timestamp + timedelta(hours=1),
        area_id=area_id,
    )

    asyncio.run(
        timelogs._flush_and_recompute_batch_timelog_dependents(
            cast(Any, session),
            changes=[
                timelogs._TimelogDependencyChange(
                    previous=snapshot,
                    current=snapshot,
                )
            ],
        )
    )

    assert session.flush.await_count == 2
    recompute_task.assert_not_awaited()
    recompute_daily.assert_not_awaited()
    recompute_aggregated.assert_not_awaited()


def test_batch_timelog_dependent_recompute_deduplicates_affected_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id = UUID("22222222-2222-2222-2222-222222222222")
    timestamp = utc_datetime(2026, 4, 9, 12, 0)
    session = SimpleNamespace(flush=AsyncMock())
    recompute_task = AsyncMock()
    sync_vision_experience = AsyncMock()
    monkeypatch.setattr(timelogs, "recompute_totals_upwards", recompute_task)
    monkeypatch.setattr(
        timelogs,
        "sync_vision_experience_for_task_ids",
        sync_vision_experience,
    )

    previous = timelogs._TimelogDependencySnapshot(
        task_id=None,
        start_time=timestamp,
        end_time=timestamp + timedelta(hours=1),
        area_id=None,
    )
    current = timelogs._TimelogDependencySnapshot(
        task_id=task_id,
        start_time=timestamp,
        end_time=timestamp + timedelta(hours=1),
        area_id=None,
    )

    asyncio.run(
        timelogs._flush_and_recompute_batch_timelog_dependents(
            cast(Any, session),
            changes=[
                timelogs._TimelogDependencyChange(previous=previous, current=current),
                timelogs._TimelogDependencyChange(previous=previous, current=current),
            ],
        )
    )

    recompute_task.assert_awaited_once_with(cast(Any, session), task_id)
    sync_vision_experience.assert_awaited_once_with(cast(Any, session), task_ids=[task_id])
