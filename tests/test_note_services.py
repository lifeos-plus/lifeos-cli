from __future__ import annotations

import asyncio
import warnings
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy.exc import SAWarning
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lifeos_cli.db.base import Base
from lifeos_cli.db.models.habit import Habit
from lifeos_cli.db.models.habit_action import HabitAction
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.models.vision import Vision
from lifeos_cli.db.services import habit_actions, notes, people, tags


async def _create_sqlite_session_factory() -> tuple[
    AsyncEngine,
    async_sessionmaker[AsyncSession],
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, future=True)


def test_create_note_flushes_without_committing(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(
        add=AsyncMock(),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )

    def fake_add(_: object) -> None:
        pass

    async def fake_build_note_view(_: object, note: object) -> object:
        return note

    session.add = fake_add
    monkeypatch.setattr(notes, "_build_note_view", fake_build_note_view)

    note = asyncio.run(notes.create_note(cast(Any, session), content="hello"))

    assert note.content == "hello"
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(note)
    session.commit.assert_not_called()


def test_list_notes_by_tag_does_not_emit_cartesian_product_warning() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tag = await tags.create_tag(
                    session,
                    name="Project",
                    entity_type="note",
                    category="general",
                )
                created_note = await notes.create_note(
                    session,
                    content="Tagged note",
                    tag_ids=[tag.id],
                )

                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always", SAWarning)
                    rows = await notes.list_notes(session, tag_id=tag.id)

                assert [row.id for row in rows] == [created_note.id]
                assert not any(
                    issubclass(item.category, SAWarning)
                    and "cartesian product" in str(item.message)
                    for item in caught
                )
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_list_notes_by_task_does_not_emit_cartesian_product_warning() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                vision = Vision(name="Planning")
                session.add(vision)
                await session.flush()
                task = Task(vision_id=vision.id, content="Review notes")
                session.add(task)
                await session.flush()
                created_note = await notes.create_note(
                    session,
                    content="Task note",
                    task_ids=[task.id],
                )

                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always", SAWarning)
                    rows = await notes.list_notes(session, task_id=task.id)

                assert [row.id for row in rows] == [created_note.id]
                assert not any(
                    issubclass(item.category, SAWarning)
                    and "cartesian product" in str(item.message)
                    for item in caught
                )
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_note_can_link_to_habit_action() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                habit = Habit(
                    title="Walk",
                    start_date=date(2026, 7, 4),
                    duration_days=1,
                    status="active",
                    status_changed_date=date(2026, 7, 4),
                )
                session.add(habit)
                await session.flush()
                action = HabitAction(habit_id=habit.id, action_date=date(2026, 7, 4))
                session.add(action)
                await session.flush()

                created_note = await notes.create_note(
                    session,
                    content="Completed after lunch",
                    habit_action_ids=[action.id],
                )
                rows = await notes.list_notes(session, habit_action_id=action.id)

                assert [row.id for row in rows] == [created_note.id]
                assert rows[0].habit_actions[0].id == action.id
                assert rows[0].habit_actions[0].habit_title == "Walk"
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_habit_action_notes_are_stored_as_linked_notes() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                habit = Habit(
                    title="Walk",
                    start_date=date(2026, 7, 4),
                    duration_days=1,
                    status="active",
                    status_changed_date=date(2026, 7, 4),
                )
                session.add(habit)
                await session.flush()
                action = HabitAction(habit_id=habit.id, action_date=date(2026, 7, 4))
                session.add(action)
                await session.flush()

                updated = await habit_actions.update_habit_action(
                    session,
                    action_id=action.id,
                    notes="Completed after lunch",
                )
                linked_notes = await notes.list_notes(session, habit_action_id=action.id)
                action_views = await habit_actions.list_habit_actions(
                    session,
                    habit_id=habit.id,
                    date_values=(date(2026, 7, 4),),
                )

                assert updated.__dict__["notes"] == "Completed after lunch"
                assert [note.content for note in linked_notes] == ["Completed after lunch"]
                assert action_views[0].notes == "Completed after lunch"
                assert action_views[0].linked_notes_count == 1

                await habit_actions.update_habit_action(
                    session,
                    action_id=action.id,
                    clear_notes=True,
                )

                assert await notes.list_notes(session, habit_action_id=action.id) == []
                cleared_action_views = await habit_actions.list_habit_actions(
                    session,
                    habit_id=habit.id,
                    date_values=(date(2026, 7, 4),),
                )
                assert cleared_action_views[0].linked_notes_count == 0
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_task_relation_counts_exclude_soft_deleted_records() -> None:
    pytest.importorskip("fastapi")

    from lifeos_cli.db.services.task_queries import load_task_relation_counts

    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                vision = Vision(name="Planning")
                session.add(vision)
                await session.flush()
                task = Task(vision_id=vision.id, content="Review notes")
                session.add(task)
                await session.flush()
                await notes.create_note(
                    session,
                    content="Active task note",
                    task_ids=[task.id],
                )
                deleted_note = await notes.create_note(
                    session,
                    content="Deleted task note",
                    task_ids=[task.id],
                )
                await notes.delete_note(session, note_id=deleted_note.id)

                timestamp = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
                deleted_timelog = Timelog(
                    title="Deleted task timelog",
                    start_time=timestamp,
                    end_time=timestamp.replace(minute=30),
                    task_id=task.id,
                )
                session.add_all(
                    [
                        Timelog(
                            title="Active task timelog",
                            start_time=timestamp,
                            end_time=timestamp.replace(minute=30),
                            task_id=task.id,
                        ),
                        deleted_timelog,
                    ]
                )
                await session.flush()
                deleted_timelog.soft_delete()
                await session.flush()

                note_counts, timelog_counts = await load_task_relation_counts(
                    session,
                    task_ids=[task.id],
                )

                assert note_counts == {task.id: 1}
                assert timelog_counts == {task.id: 1}
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_count_note_usage_by_person_counts_active_notes() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                person = await people.create_person(session, name="Alice")
                active_note = await notes.create_note(
                    session,
                    content="Active note",
                    person_ids=[person.id],
                )
                deleted_note = await notes.create_note(
                    session,
                    content="Deleted note",
                    person_ids=[person.id],
                )
                await notes.delete_note(session, note_id=deleted_note.id)

                stats = await notes.count_note_usage_by_person(session)

                assert active_note.people[0].id == person.id
                assert [(row.id, row.name, row.display_name, row.usage_count) for row in stats] == [
                    (person.id, "Alice", "Alice", 1),
                ]
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_batch_update_note_content_does_not_rollback_missing_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_id = UUID("11111111-1111-1111-1111-111111111111")
    missing_id = UUID("22222222-2222-2222-2222-222222222222")
    session = SimpleNamespace(
        flush=AsyncMock(),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
    )
    existing_note = SimpleNamespace(id=target_id, content="draft value")

    async def fake_get_note_model(*_: object, note_id: UUID, **__: object) -> object | None:
        if note_id == target_id:
            return existing_note
        return None

    monkeypatch.setattr(notes, "_get_note_model", fake_get_note_model)

    result = asyncio.run(
        notes.batch_update_note_content(
            cast(Any, session),
            note_ids=[target_id, missing_id],
            find_text="draft",
            replace_text="final",
        )
    )

    assert result.updated_count == 1
    assert result.failed_ids == (missing_id,)
    assert existing_note.content == "final value"
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(existing_note)
    session.rollback.assert_not_called()
