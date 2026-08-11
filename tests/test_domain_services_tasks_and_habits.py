from __future__ import annotations

import asyncio
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from sqlalchemy import select

from lifeos_cli.application import time_preferences
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.services import (
    habit_mutations,
    habit_queries,
    habit_support,
    habits,
    planning_lifecycle,
    task_mutations,
    task_queries,
    task_support,
    tasks,
)


async def _identity_task_view(_: object, task: object) -> object:
    return task


def test_validate_planning_cycle_requires_complete_fields() -> None:
    with pytest.raises(tasks.InvalidPlanningCycleError):
        tasks.validate_planning_cycle(
            planning_cycle_type="week",
            planning_cycle_days=None,
            planning_cycle_start_date=date(2026, 4, 9),
        )


def test_validate_planning_cycle_accepts_seven_year_cycle() -> None:
    assert tasks.validate_planning_cycle(
        planning_cycle_type="7years",
        planning_cycle_days=365 * 7,
        planning_cycle_start_date=date(2026, 1, 1),
    ) == ("7years", 365 * 7, date(2026, 1, 1))


def test_create_task_flushes_without_committing(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(
        add=None,
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )

    async def fake_ensure_vision_exists(_: object, vision_id: UUID) -> None:
        assert vision_id == UUID("11111111-1111-1111-1111-111111111111")

    async def fake_validate_parent_task(
        _: object,
        *,
        vision_id: UUID,
        parent_task_id: UUID | None,
        child_task_id: UUID | None = None,
    ) -> None:
        assert vision_id == UUID("11111111-1111-1111-1111-111111111111")
        assert parent_task_id is None
        assert child_task_id is None

    def fake_add(task: object) -> None:
        return None

    monkeypatch.setattr(task_mutations, "ensure_vision_exists", fake_ensure_vision_exists)
    monkeypatch.setattr(task_mutations, "validate_parent_task", fake_validate_parent_task)
    monkeypatch.setattr(task_mutations, "_build_task_view", _identity_task_view)
    session.add = fake_add

    task = asyncio.run(
        tasks.create_task(
            cast(Any, session),
            vision_id=UUID("11111111-1111-1111-1111-111111111111"),
            content="Draft release checklist",
        )
    )

    assert task.content == "Draft release checklist"
    session.flush.assert_awaited_once()
    session.commit.assert_not_called()


def test_update_task_can_clear_parent_without_committing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = SimpleNamespace(
        id=UUID("77777777-7777-7777-7777-777777777777"),
        vision_id=UUID("11111111-1111-1111-1111-111111111111"),
        parent_task_id=UUID("22222222-2222-2222-2222-222222222222"),
        content="Existing task",
        description=None,
        status="todo",
        priority=0,
        display_order=0,
        estimated_effort=None,
        planning_cycle_type=None,
        planning_cycle_days=None,
        planning_cycle_start_date=None,
    )
    session = SimpleNamespace(
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )

    async def fake_load_task(
        _: object,
        *,
        model_cls: object,
        model_id: UUID,
    ) -> object:
        assert model_cls is task_mutations.Task
        assert model_id == UUID("77777777-7777-7777-7777-777777777777")
        return task

    async def fake_validate_parent_task(
        _: object,
        *,
        vision_id: UUID,
        parent_task_id: UUID | None,
        child_task_id: UUID | None = None,
    ) -> None:
        assert vision_id == UUID("11111111-1111-1111-1111-111111111111")
        assert parent_task_id is None
        assert child_task_id == task.id

    monkeypatch.setattr(task_mutations, "load_model_by_id", fake_load_task)
    monkeypatch.setattr(task_mutations, "validate_parent_task", fake_validate_parent_task)
    monkeypatch.setattr(task_mutations, "_build_task_view", _identity_task_view)
    recompute_subtree = AsyncMock()
    recompute_upwards = AsyncMock()
    sync_experience = AsyncMock()
    monkeypatch.setattr(task_mutations, "recompute_subtree_totals", recompute_subtree)
    monkeypatch.setattr(task_mutations, "recompute_totals_upwards", recompute_upwards)
    monkeypatch.setattr(task_mutations, "sync_vision_experience_for_vision_ids", sync_experience)

    updated_task = asyncio.run(
        task_mutations.update_task(
            cast(Any, session),
            task_id=UUID("77777777-7777-7777-7777-777777777777"),
            clear_parent=True,
        )
    )

    assert updated_task.parent_task_id is None
    recompute_subtree.assert_awaited_once_with(cast(Any, session), task.id)
    recompute_upwards.assert_any_await(
        cast(Any, session),
        UUID("22222222-2222-2222-2222-222222222222"),
    )
    recompute_upwards.assert_any_await(cast(Any, session), task.id)
    sync_experience.assert_awaited_once_with(
        cast(Any, session),
        vision_ids=[UUID("11111111-1111-1111-1111-111111111111")],
    )
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(task)
    session.commit.assert_not_called()


def test_move_task_updates_parent_vision_and_descendants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = SimpleNamespace(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        vision_id=UUID("22222222-2222-2222-2222-222222222222"),
        parent_task_id=UUID("33333333-3333-3333-3333-333333333333"),
        display_order=0,
    )
    descendant = SimpleNamespace(
        id=UUID("44444444-4444-4444-4444-444444444444"),
        vision_id=UUID("55555555-5555-5555-5555-555555555555"),
    )
    session = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock(), commit=AsyncMock())

    async def fake_load_task(
        _: object,
        *,
        model_cls: object,
        model_id: UUID,
    ) -> object:
        assert model_cls is task_mutations.Task
        assert model_id == task.id
        return task

    async def fake_ensure_vision_exists(_: object, vision_id: UUID) -> None:
        assert vision_id == UUID("55555555-5555-5555-5555-555555555555")

    async def fake_validate_parent_task(_: object, **kwargs: object) -> None:
        assert kwargs["vision_id"] == UUID("55555555-5555-5555-5555-555555555555")
        assert kwargs["parent_task_id"] == UUID("66666666-6666-6666-6666-666666666666")
        assert kwargs["child_task_id"] == task.id

    async def fake_update_descendant_visions(_: object, **kwargs: object) -> tuple[object, ...]:
        assert kwargs["root_task_id"] == task.id
        assert kwargs["new_vision_id"] == UUID("55555555-5555-5555-5555-555555555555")
        return (descendant,)

    recompute_subtree = AsyncMock()
    recompute_upwards = AsyncMock()
    sync_experience = AsyncMock()
    monkeypatch.setattr(task_mutations, "load_model_by_id", fake_load_task)
    monkeypatch.setattr(task_mutations, "ensure_vision_exists", fake_ensure_vision_exists)
    monkeypatch.setattr(task_mutations, "validate_parent_task", fake_validate_parent_task)
    monkeypatch.setattr(
        task_mutations,
        "_update_descendant_visions",
        fake_update_descendant_visions,
    )
    monkeypatch.setattr(task_mutations, "recompute_subtree_totals", recompute_subtree)
    monkeypatch.setattr(task_mutations, "recompute_totals_upwards", recompute_upwards)
    monkeypatch.setattr(task_mutations, "sync_vision_experience_for_vision_ids", sync_experience)

    result = asyncio.run(
        tasks.move_task(
            cast(Any, session),
            task_id=task.id,
            old_parent_task_id=task.parent_task_id,
            new_parent_task_id=UUID("66666666-6666-6666-6666-666666666666"),
            new_vision_id=UUID("55555555-5555-5555-5555-555555555555"),
            new_display_order=7,
        )
    )

    assert result.task is task
    assert result.updated_descendants == (descendant,)
    assert task.parent_task_id == UUID("66666666-6666-6666-6666-666666666666")
    assert task.vision_id == UUID("55555555-5555-5555-5555-555555555555")
    assert task.display_order == 7
    recompute_subtree.assert_awaited_once_with(cast(Any, session), task.id)
    sync_experience.assert_awaited_once_with(
        cast(Any, session),
        vision_ids=[
            UUID("22222222-2222-2222-2222-222222222222"),
            UUID("55555555-5555-5555-5555-555555555555"),
        ],
    )
    recompute_upwards.assert_any_await(
        cast(Any, session),
        UUID("33333333-3333-3333-3333-333333333333"),
    )
    recompute_upwards.assert_any_await(
        cast(Any, session),
        UUID("66666666-6666-6666-6666-666666666666"),
    )
    recompute_upwards.assert_any_await(cast(Any, session), task.id)
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(task)
    session.commit.assert_not_called()


def test_move_task_preserves_parent_when_parent_change_is_not_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = SimpleNamespace(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        vision_id=UUID("22222222-2222-2222-2222-222222222222"),
        parent_task_id=UUID("33333333-3333-3333-3333-333333333333"),
        display_order=5,
    )
    session = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock(), commit=AsyncMock())

    async def fake_load_task(
        _: object,
        *,
        model_cls: object,
        model_id: UUID,
    ) -> object:
        assert model_cls is task_mutations.Task
        assert model_id == task.id
        return task

    async def fake_validate_parent_task(_: object, **kwargs: object) -> None:
        assert kwargs["vision_id"] == task.vision_id
        assert kwargs["parent_task_id"] == task.parent_task_id
        assert kwargs["child_task_id"] == task.id

    recompute_subtree = AsyncMock()
    recompute_upwards = AsyncMock()
    sync_experience = AsyncMock()
    monkeypatch.setattr(task_mutations, "load_model_by_id", fake_load_task)
    monkeypatch.setattr(task_mutations, "validate_parent_task", fake_validate_parent_task)
    monkeypatch.setattr(task_mutations, "recompute_subtree_totals", recompute_subtree)
    monkeypatch.setattr(task_mutations, "recompute_totals_upwards", recompute_upwards)
    monkeypatch.setattr(task_mutations, "sync_vision_experience_for_vision_ids", sync_experience)

    result = asyncio.run(
        tasks.move_task(
            cast(Any, session),
            task_id=task.id,
            new_display_order=7,
        )
    )

    assert result.task is task
    assert task.parent_task_id == UUID("33333333-3333-3333-3333-333333333333")
    assert task.display_order == 7
    recompute_subtree.assert_awaited_once_with(cast(Any, session), task.id)
    recompute_upwards.assert_any_await(
        cast(Any, session),
        UUID("33333333-3333-3333-3333-333333333333"),
    )
    sync_experience.assert_not_awaited()
    recompute_upwards.assert_any_await(cast(Any, session), task.id)
    assert recompute_upwards.await_count == 2
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(task)
    session.commit.assert_not_called()


def test_reorder_tasks_updates_display_order_without_committing() -> None:
    task_1 = SimpleNamespace(id=UUID("11111111-1111-1111-1111-111111111111"), display_order=3)
    task_2 = SimpleNamespace(id=UUID("22222222-2222-2222-2222-222222222222"), display_order=4)
    result = SimpleNamespace(scalars=lambda: [task_1, task_2])
    session = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock())

    asyncio.run(
        tasks.reorder_tasks(
            cast(Any, session),
            task_orders=[(task_1.id, 0), (task_2.id, 1)],
        )
    )

    assert task_1.display_order == 0
    assert task_2.display_order == 1
    session.flush.assert_awaited_once()


def test_update_task_can_clear_optional_fields_without_committing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = SimpleNamespace(
        id=UUID("88888888-8888-8888-8888-888888888888"),
        vision_id=UUID("11111111-1111-1111-1111-111111111111"),
        parent_task_id=None,
        content="Existing task",
        description="Write details",
        status="todo",
        priority=0,
        display_order=0,
        estimated_effort=45,
        planning_cycle_type="week",
        planning_cycle_days=7,
        planning_cycle_start_date=date(2026, 4, 9),
    )
    session = SimpleNamespace(
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )

    async def fake_load_task(
        _: object,
        *,
        model_cls: object,
        model_id: UUID,
    ) -> object:
        assert model_cls is task_mutations.Task
        assert model_id == UUID("88888888-8888-8888-8888-888888888888")
        return task

    async def fake_validate_parent_task(
        _: object,
        *,
        vision_id: UUID,
        parent_task_id: UUID | None,
        child_task_id: UUID | None = None,
    ) -> None:
        assert vision_id == UUID("11111111-1111-1111-1111-111111111111")
        assert parent_task_id is None
        assert child_task_id == task.id

    monkeypatch.setattr(task_mutations, "load_model_by_id", fake_load_task)
    monkeypatch.setattr(task_mutations, "validate_parent_task", fake_validate_parent_task)
    monkeypatch.setattr(task_mutations, "_build_task_view", _identity_task_view)

    updated_task = asyncio.run(
        task_mutations.update_task(
            cast(Any, session),
            task_id=UUID("88888888-8888-8888-8888-888888888888"),
            clear_description=True,
            clear_estimated_effort=True,
            clear_planning_cycle=True,
        )
    )

    assert updated_task.description is None
    assert updated_task.estimated_effort is None
    assert updated_task.planning_cycle_type is None
    assert updated_task.planning_cycle_days is None
    assert updated_task.planning_cycle_start_date is None
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(task)
    session.commit.assert_not_called()


def test_update_task_can_clear_people_without_committing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = SimpleNamespace(
        id=UUID("99999999-9999-9999-9999-999999999999"),
        vision_id=UUID("11111111-1111-1111-1111-111111111111"),
        parent_task_id=None,
        content="Existing task",
        description=None,
        status="todo",
        priority=0,
        display_order=0,
        estimated_effort=None,
        planning_cycle_type=None,
        planning_cycle_days=None,
        planning_cycle_start_date=None,
    )
    session = SimpleNamespace(
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )

    async def fake_load_task(
        _: object,
        *,
        model_cls: object,
        model_id: UUID,
    ) -> object:
        assert model_cls is task_mutations.Task
        assert model_id == UUID("99999999-9999-9999-9999-999999999999")
        return task

    async def fake_validate_parent_task(
        _: object,
        *,
        vision_id: UUID,
        parent_task_id: UUID | None,
        child_task_id: UUID | None = None,
    ) -> None:
        assert vision_id == UUID("11111111-1111-1111-1111-111111111111")
        assert parent_task_id is None
        assert child_task_id == task.id

    async def fake_sync_people(_: object, **kwargs: object) -> None:
        assert kwargs["entity_type"] == "task"
        assert kwargs["desired_person_ids"] == []

    monkeypatch.setattr(task_mutations, "load_model_by_id", fake_load_task)
    monkeypatch.setattr(task_mutations, "validate_parent_task", fake_validate_parent_task)
    monkeypatch.setattr(task_mutations, "sync_entity_people", fake_sync_people)
    monkeypatch.setattr(
        task_mutations,
        "_build_task_view",
        AsyncMock(return_value=SimpleNamespace(**task.__dict__, people=())),
    )

    updated_task = asyncio.run(
        task_mutations.update_task(
            cast(Any, session),
            task_id=UUID("99999999-9999-9999-9999-999999999999"),
            clear_people=True,
        )
    )

    assert updated_task.people == ()
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(task)
    session.commit.assert_not_called()


def test_validate_parent_task_rejects_circular_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_id = UUID("11111111-1111-1111-1111-111111111111")
    child_id = UUID("22222222-2222-2222-2222-222222222222")
    vision_id = UUID("33333333-3333-3333-3333-333333333333")
    root_task = SimpleNamespace(id=root_id, vision_id=vision_id, parent_task_id=None)
    child_task = SimpleNamespace(id=child_id, vision_id=vision_id, parent_task_id=root_id)

    async def fake_load_parent_task(_: object, parent_task_id: UUID | None) -> object | None:
        if parent_task_id is None:
            return None
        return {
            root_id: root_task,
            child_id: child_task,
        }.get(parent_task_id)

    monkeypatch.setattr(task_support, "load_parent_task", fake_load_parent_task)

    with pytest.raises(tasks.CircularTaskReferenceError):
        asyncio.run(
            task_support.validate_parent_task(
                cast(Any, object()),
                vision_id=vision_id,
                parent_task_id=child_id,
                child_task_id=root_id,
            )
        )


def test_validate_task_status_change_rejects_done_with_incomplete_children() -> None:
    task = SimpleNamespace(id=UUID("11111111-1111-1111-1111-111111111111"), status="todo")
    result = SimpleNamespace(scalars=lambda: ["done", "todo"])
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(tasks.TaskCannotBeCompletedError):
        asyncio.run(
            tasks.validate_task_status_change(
                cast(Any, session),
                task=cast(Any, task),
                new_status="done",
            )
        )


def test_validate_task_status_change_accepts_closed_children() -> None:
    task = SimpleNamespace(id=UUID("11111111-1111-1111-1111-111111111111"), status="todo")
    result = SimpleNamespace(scalars=lambda: ["done", "cancelled", "paused"])
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    status = asyncio.run(
        tasks.validate_task_status_change(
            cast(Any, session),
            task=cast(Any, task),
            new_status="done",
        )
    )

    assert status == "done"


def test_delete_task_soft_deletes_subtree_without_committing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_task = SimpleNamespace(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        vision_id=UUID("44444444-4444-4444-4444-444444444444"),
        parent_task_id=UUID("22222222-2222-2222-2222-222222222222"),
        soft_delete=Mock(),
    )
    child_task = SimpleNamespace(
        id=UUID("33333333-3333-3333-3333-333333333333"),
        parent_task_id=root_task.id,
        soft_delete=Mock(),
    )
    session = SimpleNamespace(flush=AsyncMock(), commit=AsyncMock())

    async def fake_load_task(
        _: object,
        *,
        model_cls: object,
        model_id: UUID,
    ) -> object:
        assert model_cls is task_mutations.Task
        assert model_id == root_task.id
        return root_task

    monkeypatch.setattr(task_mutations, "load_model_by_id", fake_load_task)
    monkeypatch.setattr(
        task_mutations,
        "load_task_subtree",
        AsyncMock(return_value=[root_task, child_task]),
    )
    recompute_upwards = AsyncMock()
    sync_experience = AsyncMock()
    monkeypatch.setattr(task_mutations, "recompute_totals_upwards", recompute_upwards)
    monkeypatch.setattr(task_mutations, "sync_vision_experience_for_vision_ids", sync_experience)

    asyncio.run(task_mutations.delete_task(cast(Any, session), task_id=root_task.id))

    root_task.soft_delete.assert_called_once_with()
    child_task.soft_delete.assert_called_once_with()
    recompute_upwards.assert_awaited_once_with(cast(Any, session), root_task.parent_task_id)
    sync_experience.assert_awaited_once_with(
        cast(Any, session),
        vision_ids=[UUID("44444444-4444-4444-4444-444444444444")],
    )
    session.flush.assert_awaited_once()
    session.commit.assert_not_called()


def test_get_task_with_subtasks_builds_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    root_task = SimpleNamespace(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        vision_id=UUID("22222222-2222-2222-2222-222222222222"),
        parent_task_id=None,
        content="Root task",
        description=None,
        status="todo",
        priority=0,
        display_order=0,
        estimated_effort=60,
        planning_cycle_type=None,
        planning_cycle_days=None,
        planning_cycle_start_date=None,
        actual_effort_self=30,
        actual_effort_total=60,
        created_at=None,
        updated_at=None,
        deleted_at=None,
    )
    child_task = SimpleNamespace(
        id=UUID("33333333-3333-3333-3333-333333333333"),
        vision_id=root_task.vision_id,
        parent_task_id=root_task.id,
        content="Child task",
        description=None,
        status="done",
        priority=0,
        display_order=0,
        estimated_effort=30,
        planning_cycle_type=None,
        planning_cycle_days=None,
        planning_cycle_start_date=None,
        actual_effort_self=30,
        actual_effort_total=30,
        created_at=None,
        updated_at=None,
        deleted_at=None,
    )

    monkeypatch.setattr(
        task_queries,
        "load_task_subtree",
        AsyncMock(return_value=[root_task, child_task]),
    )
    monkeypatch.setattr(
        task_queries,
        "load_people_for_entities",
        AsyncMock(return_value={root_task.id: [], child_task.id: []}),
    )

    result = asyncio.run(tasks.get_task_with_subtasks(cast(Any, object()), task_id=root_task.id))

    assert result is not None
    assert result.id == root_task.id
    assert result.depth == 0
    assert result.completion_percentage == 1.0
    assert len(result.subtasks) == 1
    assert result.subtasks[0].id == child_task.id
    assert result.subtasks[0].depth == 1


def test_get_task_stats_summarizes_subtree(monkeypatch: pytest.MonkeyPatch) -> None:
    root_task = SimpleNamespace(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        parent_task_id=None,
        status="todo",
        estimated_effort=60,
        actual_effort_self=30,
    )
    child_task_1 = SimpleNamespace(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        parent_task_id=root_task.id,
        status="done",
        estimated_effort=30,
        actual_effort_self=20,
    )
    child_task_2 = SimpleNamespace(
        id=UUID("33333333-3333-3333-3333-333333333333"),
        parent_task_id=root_task.id,
        status="todo",
        estimated_effort=45,
        actual_effort_self=10,
    )
    monkeypatch.setattr(
        task_queries,
        "load_task_subtree",
        AsyncMock(return_value=[root_task, child_task_1, child_task_2]),
    )

    stats = asyncio.run(tasks.get_task_stats(cast(Any, object()), task_id=root_task.id))

    assert stats.total_subtasks == 2
    assert stats.completed_subtasks == 1
    assert stats.completion_percentage == 0.5
    assert stats.total_estimated_effort == 135
    assert stats.total_actual_effort == 60


def test_create_habit_does_not_pre_generate_actions_without_committing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        def scalars(self) -> list[object]:
            return []

    session = SimpleNamespace(
        add=None,
        execute=AsyncMock(return_value=Result()),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )
    added_records: list[object] = []

    def fake_add(record: object) -> None:
        if getattr(record, "id", None) is None:
            cast(Any, record).id = UUID("99999999-9999-9999-9999-999999999999")
        added_records.append(record)

    async def fake_ensure_active_capacity(_: object, **__: object) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_refresh_habit_expiration(_: object, *, habit_id: UUID | None = None) -> int:
        assert habit_id == UUID("99999999-9999-9999-9999-999999999999")
        return 0

    session.add = fake_add
    monkeypatch.setattr(habit_mutations, "ensure_active_capacity", fake_ensure_active_capacity)
    monkeypatch.setattr(habit_mutations, "ensure_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(habit_mutations, "refresh_habit_expiration", fake_refresh_habit_expiration)

    habit = asyncio.run(
        habits.create_habit(
            cast(Any, session),
            title="Daily Exercise",
            start_date=date(2026, 4, 9),
            duration_days=7,
        )
    )

    assert habit.title == "Daily Exercise"
    assert len(added_records) == 1
    assert not any(hasattr(record, "action_date") for record in added_records)
    session.flush.assert_awaited()
    session.commit.assert_not_called()


def test_create_habit_keeps_weekly_cadence_without_pre_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        def scalars(self) -> list[object]:
            return []

    session = SimpleNamespace(
        add=None,
        execute=AsyncMock(return_value=Result()),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )
    added_records: list[object] = []

    def fake_add(record: object) -> None:
        if getattr(record, "id", None) is None:
            cast(Any, record).id = UUID("99999999-9999-9999-9999-999999999999")
        added_records.append(record)

    async def fake_ensure_active_capacity(_: object, **__: object) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_refresh_habit_expiration(_: object, *, habit_id: UUID | None = None) -> int:
        assert habit_id == UUID("99999999-9999-9999-9999-999999999999")
        return 0

    session.add = fake_add
    monkeypatch.setattr(habit_mutations, "ensure_active_capacity", fake_ensure_active_capacity)
    monkeypatch.setattr(habit_mutations, "ensure_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(habit_mutations, "refresh_habit_expiration", fake_refresh_habit_expiration)

    habit = asyncio.run(
        habits.create_habit(
            cast(Any, session),
            title="Call Parents",
            start_date=date(2026, 4, 9),
            duration_days=7,
            cadence_frequency="weekly",
            cadence_weekdays=["saturday", "sunday"],
            target_per_cycle=1,
        )
    )

    assert habit.cadence_frequency == "weekly"
    assert habit.cadence_weekdays == ["saturday", "sunday"]
    assert habit.target_per_cycle == 1
    assert not any(hasattr(record, "action_date") for record in added_records)
    session.flush.assert_awaited()
    session.commit.assert_not_called()


def test_create_habit_keeps_monthly_cadence_without_pre_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        def scalars(self) -> list[object]:
            return []

    session = SimpleNamespace(
        add=None,
        execute=AsyncMock(return_value=Result()),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )
    added_records: list[object] = []

    def fake_add(record: object) -> None:
        if getattr(record, "id", None) is None:
            cast(Any, record).id = UUID("99999999-9999-9999-9999-999999999999")
        added_records.append(record)

    async def fake_ensure_active_capacity(_: object, **__: object) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_refresh_habit_expiration(_: object, *, habit_id: UUID | None = None) -> int:
        assert habit_id == UUID("99999999-9999-9999-9999-999999999999")
        return 0

    session.add = fake_add
    monkeypatch.setattr(habit_mutations, "ensure_active_capacity", fake_ensure_active_capacity)
    monkeypatch.setattr(habit_mutations, "ensure_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(habit_mutations, "refresh_habit_expiration", fake_refresh_habit_expiration)

    habit = asyncio.run(
        habits.create_habit(
            cast(Any, session),
            title="Monthly cleanup",
            start_date=date(2026, 4, 9),
            duration_days=100,
            cadence_frequency="monthly",
            target_per_cycle=2,
        )
    )

    assert habit.cadence_frequency == "monthly"
    assert habit.target_per_cycle == 2
    assert not any(hasattr(record, "action_date") for record in added_records)
    session.flush.assert_awaited()
    session.commit.assert_not_called()


def test_create_habit_keeps_monthly_monthday_cadence_without_pre_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        def scalars(self) -> list[object]:
            return []

    session = SimpleNamespace(
        add=None,
        execute=AsyncMock(return_value=Result()),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )
    added_records: list[object] = []

    def fake_add(record: object) -> None:
        if getattr(record, "id", None) is None:
            cast(Any, record).id = UUID("99999999-9999-9999-9999-999999999999")
        added_records.append(record)

    async def fake_ensure_active_capacity(_: object, **__: object) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_refresh_habit_expiration(_: object, *, habit_id: UUID | None = None) -> int:
        assert habit_id == UUID("99999999-9999-9999-9999-999999999999")
        return 0

    session.add = fake_add
    monkeypatch.setattr(habit_mutations, "ensure_active_capacity", fake_ensure_active_capacity)
    monkeypatch.setattr(habit_mutations, "ensure_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(habit_mutations, "refresh_habit_expiration", fake_refresh_habit_expiration)

    habit = asyncio.run(
        habits.create_habit(
            cast(Any, session),
            title="Monthly cleanup",
            start_date=date(2026, 4, 1),
            duration_days=100,
            cadence_frequency="monthly",
            cadence_monthdays=[1, 15],
            target_per_cycle=2,
        )
    )

    assert habit.cadence_frequency == "monthly"
    assert habit.cadence_monthdays == [1, 15]
    assert habit.target_per_cycle == 2
    assert not any(hasattr(record, "action_date") for record in added_records)
    session.flush.assert_awaited()
    session.commit.assert_not_called()


def test_create_habit_repeat_count_resolves_duration_from_scheduled_occurrences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        def scalars(self) -> list[object]:
            return []

    session = SimpleNamespace(
        add=None,
        execute=AsyncMock(return_value=Result()),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )

    def fake_add(record: object) -> None:
        if getattr(record, "id", None) is None:
            cast(Any, record).id = UUID("99999999-9999-9999-9999-999999999999")

    async def fake_ensure_active_capacity(_: object, **__: object) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_refresh_habit_expiration(_: object, *, habit_id: UUID | None = None) -> int:
        assert habit_id == UUID("99999999-9999-9999-9999-999999999999")
        return 0

    session.add = fake_add
    monkeypatch.setattr(habit_mutations, "ensure_active_capacity", fake_ensure_active_capacity)
    monkeypatch.setattr(habit_mutations, "ensure_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(habit_mutations, "refresh_habit_expiration", fake_refresh_habit_expiration)

    habit = asyncio.run(
        habits.create_habit(
            cast(Any, session),
            title="Weekend calls",
            start_date=date(2026, 4, 9),
            repeat_count=3,
            cadence_frequency="weekly",
            cadence_weekdays=["saturday", "sunday"],
            target_per_cycle=1,
        )
    )

    assert habit.duration_days == 10
    assert habit.end_date == date(2026, 4, 18)
    session.flush.assert_awaited()
    session.commit.assert_not_called()


def test_create_habit_end_date_resolves_inclusive_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        def scalars(self) -> list[object]:
            return []

    session = SimpleNamespace(
        add=None,
        execute=AsyncMock(return_value=Result()),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )

    def fake_add(record: object) -> None:
        if getattr(record, "id", None) is None:
            cast(Any, record).id = UUID("99999999-9999-9999-9999-999999999999")

    async def fake_ensure_active_capacity(_: object, **__: object) -> None:
        return None

    async def fake_ensure_task_exists(_: object, __: UUID | None) -> None:
        return None

    async def fake_refresh_habit_expiration(_: object, *, habit_id: UUID | None = None) -> int:
        assert habit_id == UUID("99999999-9999-9999-9999-999999999999")
        return 0

    session.add = fake_add
    monkeypatch.setattr(habit_mutations, "ensure_active_capacity", fake_ensure_active_capacity)
    monkeypatch.setattr(habit_mutations, "ensure_task_exists", fake_ensure_task_exists)
    monkeypatch.setattr(habit_mutations, "refresh_habit_expiration", fake_refresh_habit_expiration)

    habit = asyncio.run(
        habits.create_habit(
            cast(Any, session),
            title="Daily review",
            start_date=date(2026, 4, 9),
            end_date=date(2026, 4, 15),
        )
    )

    assert habit.duration_days == 7
    assert habit.end_date == date(2026, 4, 15)
    session.flush.assert_awaited()
    session.commit.assert_not_called()


def test_create_habit_rejects_daily_quota_targets() -> None:
    with pytest.raises(habits.HabitValidationError):
        asyncio.run(
            habits.create_habit(
                cast(
                    Any,
                    SimpleNamespace(
                        add=lambda _: None,
                        flush=AsyncMock(),
                        refresh=AsyncMock(),
                    ),
                ),
                title="Daily Exercise",
                start_date=date(2026, 4, 9),
                duration_days=7,
                target_per_cycle=2,
            )
        )


def test_iter_habit_scheduled_dates_uses_user_calendar_monthdays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        habit_support,
        "get_preferences_settings",
        lambda: SimpleNamespace(
            day_starts_at="00:00",
            timezone="UTC",
            week_starts_on="monday",
            calendar_system="mayan_13_moon",
            calendar_first_day_of_week=1,
        ),
    )
    monkeypatch.setattr(
        time_preferences,
        "get_preferences_settings",
        lambda: SimpleNamespace(
            day_starts_at="00:00",
            timezone="UTC",
            week_starts_on="monday",
            calendar_system="mayan_13_moon",
            calendar_first_day_of_week=1,
        ),
    )
    scheduled_dates = habit_support.iter_habit_scheduled_dates(
        start_date=date(2026, 7, 26),
        end_date=date(2026, 8, 25),
        cadence_frequency="monthly",
        cadence_weekdays=None,
        cadence_monthdays=[1, 15],
    )

    assert scheduled_dates == [
        date(2026, 7, 26),
        date(2026, 8, 9),
        date(2026, 8, 23),
    ]


def test_iter_habit_scheduled_dates_matches_day_scan_for_weekly_cadence() -> None:
    start_date = date(2026, 4, 1)
    end_date = date(2026, 5, 31)
    cadence_weekdays = ["monday", "wednesday", "friday"]

    scheduled_dates = habit_support.iter_habit_scheduled_dates(
        start_date=start_date,
        end_date=end_date,
        cadence_frequency="weekly",
        cadence_weekdays=cadence_weekdays,
    )

    reference_dates = [
        current_date
        for current_date in (
            start_date + timedelta(days=offset)
            for offset in range((end_date - start_date).days + 1)
        )
        if habit_support.habit_occurs_on_date(
            start_date=start_date,
            end_date=end_date,
            cadence_frequency="weekly",
            cadence_weekdays=cadence_weekdays,
            target_date=current_date,
        )
    ]

    assert scheduled_dates == reference_dates


def test_iter_habit_scheduled_dates_matches_day_scan_for_monthly_monthdays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        habit_support,
        "get_preferences_settings",
        lambda: SimpleNamespace(
            day_starts_at="00:00",
            timezone="UTC",
            week_starts_on="monday",
            calendar_system="gregorian",
            calendar_first_day_of_week=1,
        ),
    )
    start_date = date(2026, 1, 1)
    end_date = date(2026, 4, 30)
    cadence_monthdays = [1, 15, 31]

    scheduled_dates = habit_support.iter_habit_scheduled_dates(
        start_date=start_date,
        end_date=end_date,
        cadence_frequency="monthly",
        cadence_weekdays=None,
        cadence_monthdays=cadence_monthdays,
    )

    reference_dates = [
        current_date
        for current_date in (
            start_date + timedelta(days=offset)
            for offset in range((end_date - start_date).days + 1)
        )
        if habit_support.habit_occurs_on_date(
            start_date=start_date,
            end_date=end_date,
            cadence_frequency="monthly",
            cadence_weekdays=None,
            cadence_monthdays=cadence_monthdays,
            target_date=current_date,
        )
    ]

    assert scheduled_dates == reference_dates
    assert date(2026, 3, 31) in scheduled_dates
    assert all(
        current_date.day <= 28 for current_date in scheduled_dates if current_date.month == 2
    )


def test_update_habit_can_clear_task_without_committing(monkeypatch: pytest.MonkeyPatch) -> None:
    habit = SimpleNamespace(
        id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        title="Daily Exercise",
        description="Move every day",
        start_date=date(2026, 4, 9),
        duration_days=21,
        cadence_frequency="daily",
        cadence_weekdays=None,
        target_per_cycle=1,
        status="active",
        task_id=UUID("11111111-1111-1111-1111-111111111111"),
    )
    session = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock(), commit=AsyncMock())

    async def fake_get_habit(_: object, *, habit_id: UUID) -> object:
        assert habit_id == UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        return habit

    async def fake_refresh_habit_expiration(_: object, *, habit_id: UUID | None = None) -> int:
        assert habit_id == UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        return 0

    monkeypatch.setattr(habit_mutations, "get_habit", fake_get_habit)
    monkeypatch.setattr(habit_mutations, "refresh_habit_expiration", fake_refresh_habit_expiration)

    updated_habit = asyncio.run(
        habits.update_habit(
            cast(Any, session),
            habit_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            clear_task=True,
        )
    )

    assert updated_habit.task_id is None
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(habit)
    session.commit.assert_not_called()


def test_update_habit_records_status_changed_date(monkeypatch: pytest.MonkeyPatch) -> None:
    habit = SimpleNamespace(
        id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        title="Daily Exercise",
        description="Move every day",
        start_date=date(2026, 4, 9),
        duration_days=90,
        cadence_frequency="daily",
        cadence_weekdays=None,
        cadence_monthdays=None,
        target_per_cycle=1,
        status="active",
        status_changed_date=date(2026, 4, 9),
        task_id=None,
    )
    session = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock())

    async def fake_get_habit(_: object, *, habit_id: UUID) -> object:
        assert habit_id == UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        return habit

    async def fake_refresh_habit_expiration(_: object, *, habit_id: UUID | None = None) -> int:
        assert habit_id == UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        return 0

    monkeypatch.setattr(habit_mutations, "get_habit", fake_get_habit)
    monkeypatch.setattr(habit_mutations, "refresh_habit_expiration", fake_refresh_habit_expiration)
    monkeypatch.setattr(habit_mutations, "get_operational_date", lambda: date(2026, 7, 1))

    updated_habit = asyncio.run(
        habits.update_habit(
            cast(Any, session),
            habit_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            status="paused",
        )
    )

    assert updated_habit.status == "paused"
    assert updated_habit.status_changed_date == date(2026, 7, 1)


def test_update_habit_rejects_zero_target_per_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    habit = SimpleNamespace(
        id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        title="Weekly Exercise",
        description=None,
        start_date=date(2026, 4, 9),
        duration_days=21,
        cadence_frequency="weekly",
        cadence_weekdays=["monday"],
        cadence_monthdays=None,
        target_per_cycle=1,
        status="active",
        task_id=None,
    )
    session = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock(), commit=AsyncMock())

    async def fake_get_habit(_: object, *, habit_id: UUID) -> object:
        assert habit_id == UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        return habit

    monkeypatch.setattr(habit_mutations, "get_habit", fake_get_habit)

    with pytest.raises(habits.HabitValidationError):
        asyncio.run(
            habits.update_habit(
                cast(Any, session),
                habit_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                target_per_cycle=0,
            )
        )

    session.flush.assert_not_awaited()
    session.refresh.assert_not_awaited()
    session.commit.assert_not_called()


def test_build_habit_stats_payload_uses_weekly_cycle_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(habit_support, "get_operational_date", lambda value=None: date(2026, 4, 13))
    monkeypatch.setattr(
        habit_support,
        "get_week_bounds",
        lambda reference_date: (date(2026, 4, 13), date(2026, 4, 19)),
    )

    habit = SimpleNamespace(
        id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        start_date=date(2026, 4, 9),
        cadence_frequency="weekly",
        cadence_weekdays=["saturday", "sunday"],
        target_per_cycle=1,
    )
    actions = [
        SimpleNamespace(action_date=date(2026, 4, 11), status="done"),
        SimpleNamespace(action_date=date(2026, 4, 12), status="pending"),
    ]

    stats = habit_support.build_habit_stats_payload(cast(Any, habit), cast(Any, actions))

    assert stats["completed_cycles"] == 1
    assert stats["eligible_cycles"] == 1
    assert stats["progress_percentage"] == 100.0
    assert stats["current_streak"] == 1
    assert stats["longest_streak"] == 1


def test_build_habit_stats_payload_uses_monthly_cycle_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(habit_support, "get_operational_date", lambda value=None: date(2026, 4, 20))
    monkeypatch.setattr(
        habit_support,
        "get_week_bounds",
        lambda reference_date: (date(2026, 4, 20), date(2026, 4, 26)),
    )

    habit = SimpleNamespace(
        id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        start_date=date(2026, 4, 1),
        cadence_frequency="monthly",
        cadence_weekdays=None,
        target_per_cycle=2,
    )
    actions = [
        SimpleNamespace(action_date=date(2026, 4, 2), status="done"),
        SimpleNamespace(action_date=date(2026, 4, 16), status="done"),
        SimpleNamespace(action_date=date(2026, 4, 20), status="pending"),
    ]

    stats = habit_support.build_habit_stats_payload(cast(Any, habit), cast(Any, actions))

    assert stats["cadence_frequency"] == "monthly"
    assert stats["completed_cycles"] == 1
    assert stats["eligible_cycles"] == 1
    assert stats["progress_percentage"] == 100.0
    assert stats["current_cycle_start"] == date(2026, 4, 1)
    assert stats["current_cycle_end"] == date(2026, 4, 30)


def test_build_habit_stats_payload_uses_selected_calendar_month_cycles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        habit_support,
        "get_operational_date",
        lambda value=None: date(2026, 8, 10),
    )
    monkeypatch.setattr(
        habit_support,
        "get_week_bounds",
        lambda reference_date: (date(2026, 8, 9), date(2026, 8, 15)),
    )
    monkeypatch.setattr(
        habit_support,
        "get_preferences_settings",
        lambda: SimpleNamespace(
            day_starts_at="00:00",
            timezone="UTC",
            week_starts_on="monday",
            calendar_system="mayan_13_moon",
            calendar_first_day_of_week=1,
        ),
    )
    monkeypatch.setattr(
        time_preferences,
        "get_preferences_settings",
        lambda: SimpleNamespace(
            day_starts_at="00:00",
            timezone="UTC",
            week_starts_on="monday",
            calendar_system="mayan_13_moon",
            calendar_first_day_of_week=1,
        ),
    )
    habit = SimpleNamespace(
        id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        start_date=date(2026, 7, 26),
        cadence_frequency="monthly",
        cadence_weekdays=None,
        cadence_monthdays=[1, 15],
        target_per_cycle=2,
    )
    actions = [
        SimpleNamespace(action_date=date(2026, 7, 26), status="done"),
        SimpleNamespace(action_date=date(2026, 8, 9), status="done"),
    ]

    stats = habit_support.build_habit_stats_payload(cast(Any, habit), cast(Any, actions))

    assert stats["cadence_monthdays"] == (1, 15)
    assert stats["completed_cycles"] == 1
    assert stats["current_cycle_start"] == date(2026, 7, 26)
    assert stats["current_cycle_end"] == date(2026, 8, 22)


def test_habit_task_associations_require_active_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statements: list[object] = []

    class Result:
        def scalars(self) -> list[object]:
            return []

    session = SimpleNamespace(flush=AsyncMock())

    async def fake_execute(statement: object) -> Result:
        statements.append(statement)
        return Result()

    async def fake_refresh_habit_expiration(_: object) -> int:
        return 0

    session.execute = fake_execute
    monkeypatch.setattr(habit_queries, "refresh_habit_expiration", fake_refresh_habit_expiration)

    associations = asyncio.run(habits.get_habit_task_associations(cast(Any, session)))

    assert associations == {}
    assert statements
    compiled = str(statements[-1])
    assert "tasks.deleted_at IS NULL" in compiled
    assert "habits.status =" not in compiled


def test_task_list_filters_require_active_parent_visions() -> None:
    stmt = task_queries._apply_task_filters(select(Task))

    compiled = str(stmt)
    assert "tasks.deleted_at IS NULL" in compiled
    assert "visions.deleted_at IS NULL" in compiled
    assert "tasks.vision_id IS NULL" not in compiled


def test_update_habit_action_by_date_uses_existing_update_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    habit_id = UUID("77777777-7777-7777-7777-777777777777")
    action_id = UUID("88888888-8888-8888-8888-888888888888")
    action_date = date(2026, 4, 9)
    action = SimpleNamespace(id=action_id, action_date=action_date)
    session = SimpleNamespace(flush=AsyncMock())

    class Result:
        def scalar_one_or_none(self) -> object:
            return action

    async def fake_get_habit(_: object, *, habit_id: UUID) -> object:
        return SimpleNamespace(
            id=habit_id,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            cadence_frequency="daily",
            cadence_weekdays=None,
            cadence_monthdays=None,
            status="active",
            status_changed_date=date(2026, 4, 1),
        )

    async def fake_execute(statement: object) -> Result:
        return Result()

    async def fake_update_habit_action(_: object, **kwargs: object) -> object:
        assert kwargs == {
            "action_id": action_id,
            "status": "done",
            "notes": "Completed",
            "clear_notes": False,
        }
        return action

    session.execute = fake_execute
    monkeypatch.setattr(habit_mutations, "get_habit", fake_get_habit)
    monkeypatch.setattr(habit_mutations, "update_habit_action", fake_update_habit_action)

    updated_action = asyncio.run(
        habits.update_habit_action_by_date(
            cast(Any, session),
            habit_id=habit_id,
            action_date=action_date,
            status="done",
            notes="Completed",
        )
    )

    assert updated_action is action


def test_update_habit_action_by_date_materializes_missing_occurrence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    habit_id = UUID("77777777-7777-7777-7777-777777777777")
    action_id = UUID("88888888-8888-8888-8888-888888888888")
    action_date = date(2026, 4, 9)
    session = SimpleNamespace(add=None, flush=AsyncMock(), refresh=AsyncMock())
    added_records: list[object] = []

    class Result:
        def scalar_one_or_none(self) -> object:
            return None

    def fake_add(record: object) -> None:
        cast(Any, record).id = action_id
        added_records.append(record)

    async def fake_get_habit(_: object, *, habit_id: UUID) -> object:
        return SimpleNamespace(
            id=habit_id,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            cadence_frequency="daily",
            cadence_weekdays=None,
            cadence_monthdays=None,
            status="active",
            status_changed_date=date(2026, 4, 1),
        )

    async def fake_execute(statement: object) -> Result:
        return Result()

    async def fake_update_habit_action(_: object, **kwargs: object) -> object:
        assert kwargs == {
            "action_id": action_id,
            "status": "done",
            "notes": "Completed",
            "clear_notes": False,
        }
        return SimpleNamespace(id=action_id, action_date=action_date)

    session.add = fake_add
    session.execute = fake_execute
    monkeypatch.setattr(habit_mutations, "get_habit", fake_get_habit)
    monkeypatch.setattr(habit_mutations, "update_habit_action", fake_update_habit_action)

    updated_action = asyncio.run(
        habits.update_habit_action_by_date(
            cast(Any, session),
            habit_id=habit_id,
            action_date=action_date,
            status="done",
            notes="Completed",
        )
    )

    assert updated_action.id == action_id
    assert len(added_records) == 1
    assert cast(Any, added_records[0]).action_date == action_date


def test_list_habit_actions_materializes_listed_occurrences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    habit_id = UUID("77777777-7777-7777-7777-777777777777")
    action_id = UUID("88888888-8888-8888-8888-888888888888")
    action_date = date(2026, 4, 9)

    class Result:
        def scalars(self) -> list[object]:
            return [SimpleNamespace(id=habit_id, title="Daily Exercise", deleted_at=None)]

    session = SimpleNamespace(flush=AsyncMock())

    async def fake_execute(statement: object) -> Result:
        return Result()

    async def fake_build_views(*args: object, **kwargs: object) -> list[object]:
        return [
            SimpleNamespace(
                id=None,
                habit_id=habit_id,
                habit_title="Daily Exercise",
                action_date=action_date,
                status="pending",
                notes=None,
                created_at=None,
                updated_at=None,
                deleted_at=None,
            )
        ]

    async def fake_materialize(*args: object, **kwargs: object) -> object:
        return SimpleNamespace(
            id=action_id,
            habit_id=habit_id,
            action_date=action_date,
            status="pending",
            notes=None,
            created_at=None,
            updated_at=None,
            deleted_at=None,
        )

    session.execute = fake_execute
    monkeypatch.setattr(habit_queries, "build_habit_action_views", fake_build_views)
    monkeypatch.setattr(habit_queries, "_materialize_habit_action_for_date", fake_materialize)

    views = asyncio.run(habits.list_habit_actions(cast(Any, session), habit_id=habit_id))

    assert len(views) == 1
    assert views[0].id == action_id
    assert views[0].habit_title == "Daily Exercise"


def test_build_habit_action_views_uses_discrete_target_dates_without_gap_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    habit_id = UUID("77777777-7777-7777-7777-777777777777")
    selected_dates = (date(2026, 4, 1), date(2026, 4, 30))
    habit = SimpleNamespace(
        id=habit_id,
        title="Daily Exercise",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
        cadence_weekdays=None,
    )

    async def fake_load_candidate_habits(*args: object, **kwargs: object) -> list[object]:
        assert kwargs["action_window"] is None
        assert kwargs["target_dates"] == selected_dates
        return [habit]

    async def fake_load_materialized_actions(*args: object, **kwargs: object) -> list[object]:
        assert kwargs["start_date"] is None
        assert kwargs["end_date"] is None
        assert kwargs["target_dates"] == selected_dates
        return []

    monkeypatch.setattr(habit_queries, "_load_candidate_habits", fake_load_candidate_habits)
    monkeypatch.setattr(
        habit_queries,
        "_load_materialized_actions_for_habits",
        fake_load_materialized_actions,
    )

    views = asyncio.run(
        habit_queries.build_habit_action_views(
            cast(Any, object()),
            habit_id=None,
            status=None,
            action_window=None,
            target_dates=selected_dates,
        )
    )

    assert [view.action_date for view in views] == [date(2026, 4, 1), date(2026, 4, 30)]


def test_reconcile_planning_habit_action_lifecycle_expires_overdue_pending_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    habit_id = UUID("77777777-7777-7777-7777-777777777777")
    overdue = SimpleNamespace(
        id=UUID("88888888-8888-8888-8888-888888888888"),
        habit_id=habit_id,
        action_date=date(2026, 4, 1),
        status="pending",
    )
    materialized_synthetic = SimpleNamespace(
        id=UUID("99999999-9999-9999-9999-999999999999"),
        habit_id=habit_id,
        action_date=date(2026, 4, 1),
        status="pending",
    )
    habit = SimpleNamespace(id=habit_id)

    class Result:
        def scalars(self) -> list[object]:
            return [overdue]

    async def fake_execute(statement: object) -> Result:
        return Result()

    session = SimpleNamespace(execute=fake_execute, flush=AsyncMock())

    async def fake_build_views(*args: object, **kwargs: object) -> list[object]:
        assert kwargs["status"] == "pending"
        assert kwargs["action_window"] == (date(2026, 4, 1), date(2026, 4, 1))
        return [
            SimpleNamespace(
                id=None,
                habit_id=habit_id,
                habit_title="Daily Exercise",
                action_date=date(2026, 4, 1),
                status="pending",
                notes=None,
                created_at=None,
                updated_at=None,
                deleted_at=None,
            )
        ]

    async def fake_get_habit(*args: object, **kwargs: object) -> object:
        assert kwargs["habit_id"] == habit_id
        return habit

    async def fake_materialize(*args: object, **kwargs: object) -> object:
        assert kwargs["habit"] is habit
        assert kwargs["action_date"] == date(2026, 4, 1)
        return materialized_synthetic

    monkeypatch.setattr(planning_lifecycle, "build_habit_action_views", fake_build_views)
    monkeypatch.setattr(planning_lifecycle, "get_habit", fake_get_habit)
    monkeypatch.setattr(
        planning_lifecycle,
        "_materialize_habit_action_for_date",
        fake_materialize,
    )

    expired_count = asyncio.run(
        planning_lifecycle.reconcile_planning_habit_action_lifecycle(
            cast(Any, session),
            reference_date=date(2026, 4, 5),
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 8),
        )
    )

    assert expired_count == 2
    assert overdue.status == "miss"
    assert materialized_synthetic.status == "miss"
    session.flush.assert_awaited_once()


def test_build_habit_action_views_stops_after_status_change_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    habit_id = UUID("77777777-7777-7777-7777-777777777777")
    selected_dates = (date(2026, 6, 30), date(2026, 7, 1))
    habit = SimpleNamespace(
        id=habit_id,
        title="Daily Exercise",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 7, 31),
        cadence_frequency="daily",
        cadence_weekdays=None,
        cadence_monthdays=None,
        status="paused",
        status_changed_date=date(2026, 7, 1),
    )

    async def fake_load_candidate_habits(*args: object, **kwargs: object) -> list[object]:
        assert kwargs["target_dates"] == selected_dates
        return [habit]

    async def fake_load_materialized_actions(*args: object, **kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(habit_queries, "_load_candidate_habits", fake_load_candidate_habits)
    monkeypatch.setattr(
        habit_queries,
        "_load_materialized_actions_for_habits",
        fake_load_materialized_actions,
    )

    views = asyncio.run(
        habit_queries.build_habit_action_views(
            cast(Any, object()),
            habit_id=None,
            status=None,
            action_window=None,
            target_dates=selected_dates,
        )
    )

    assert [view.action_date for view in views] == [date(2026, 6, 30)]


def test_build_habit_action_views_with_window_stops_after_status_change_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    habit_id = UUID("77777777-7777-7777-7777-777777777777")
    habit = SimpleNamespace(
        id=habit_id,
        title="Weekend Review",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 7, 31),
        cadence_frequency="weekly",
        cadence_weekdays=["saturday", "sunday"],
        cadence_monthdays=None,
        status="paused",
        status_changed_date=date(2026, 7, 1),
    )

    async def fake_load_candidate_habits(*args: object, **kwargs: object) -> list[object]:
        assert kwargs["action_window"] == (date(2026, 6, 1), date(2026, 7, 31))
        return [habit]

    async def fake_load_materialized_actions(*args: object, **kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(habit_queries, "_load_candidate_habits", fake_load_candidate_habits)
    monkeypatch.setattr(
        habit_queries,
        "_load_materialized_actions_for_habits",
        fake_load_materialized_actions,
    )

    views = asyncio.run(
        habit_queries.build_habit_action_views(
            cast(Any, object()),
            habit_id=None,
            status=None,
            action_window=(date(2026, 6, 1), date(2026, 7, 31)),
        )
    )

    assert [view.action_date for view in views] == [
        date(2026, 6, 6),
        date(2026, 6, 7),
        date(2026, 6, 13),
        date(2026, 6, 14),
        date(2026, 6, 20),
        date(2026, 6, 21),
        date(2026, 6, 27),
        date(2026, 6, 28),
    ]


def test_list_and_count_habit_actions_pass_discrete_dates_to_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_calls: list[dict[str, object]] = []
    action_dates = (date(2026, 4, 3), date(2026, 4, 1))

    async def fake_build_views(*args: object, **kwargs: object) -> list[object]:
        captured_calls.append(kwargs)
        return [
            SimpleNamespace(
                id=UUID("88888888-8888-8888-8888-888888888888"),
                habit_id=UUID("77777777-7777-7777-7777-777777777777"),
                habit_title="Daily Exercise",
                action_date=action_dates[0],
                status="pending",
                notes=None,
                created_at=None,
                updated_at=None,
                deleted_at=None,
            ),
            SimpleNamespace(
                id=UUID("99999999-9999-9999-9999-999999999999"),
                habit_id=UUID("77777777-7777-7777-7777-777777777777"),
                habit_title="Daily Exercise",
                action_date=action_dates[1],
                status="pending",
                notes=None,
                created_at=None,
                updated_at=None,
                deleted_at=None,
            ),
        ]

    monkeypatch.setattr(habit_queries, "build_habit_action_views", fake_build_views)
    monkeypatch.setattr(habit_queries, "refresh_habit_expiration", AsyncMock(return_value=0))

    views = asyncio.run(
        habits.list_habit_actions(
            cast(Any, object()),
            date_values=(date(2026, 4, 3), date(2026, 4, 1), date(2026, 4, 3)),
        )
    )
    count = asyncio.run(
        habits.count_habit_actions(
            cast(Any, object()),
            date_values=(date(2026, 4, 3), date(2026, 4, 1), date(2026, 4, 3)),
        )
    )

    assert [view.action_date for view in views] == [date(2026, 4, 3), date(2026, 4, 1)]
    assert count == 2
    assert captured_calls[0]["target_dates"] == (date(2026, 4, 3), date(2026, 4, 1))
    assert captured_calls[0]["action_window"] is None
    assert captured_calls[1]["target_dates"] == (date(2026, 4, 3), date(2026, 4, 1))
    assert captured_calls[1]["action_window"] is None
