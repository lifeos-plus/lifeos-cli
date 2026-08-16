"""Write-side task service helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.task import Task
from lifeos_cli.db.services.batching import BatchDeleteResult, batch_delete_records
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.entity_person import sync_entity_person
from lifeos_cli.db.services.model_utils import load_model_by_id
from lifeos_cli.db.services.read_models import TaskView
from lifeos_cli.db.services.task_effort import recompute_subtree_totals, recompute_totals_upwards
from lifeos_cli.db.services.task_queries import _build_task_view
from lifeos_cli.db.services.task_support import (
    InvalidTaskOperationError,
    ParentTaskReferenceNotFoundError,
    TaskNotFoundError,
    ensure_vision_exists,
    load_task_subtree,
    validate_parent_task,
    validate_planning_cycle,
    validate_task_status,
    validate_task_status_change,
)
from lifeos_cli.db.services.visions import sync_vision_experience_for_vision_ids


@dataclass(frozen=True)
class TaskMoveResult:
    """Result payload for moving a task."""

    task: Task
    updated_descendants: tuple[Task, ...]


class _UnsetParentTaskId:
    """Sentinel for omitted parent task changes."""


_UNSET_PARENT_TASK_ID: Final = _UnsetParentTaskId()


async def create_task(
    session: AsyncSession,
    *,
    vision_id: UUID,
    content: str,
    description: str | None = None,
    parent_task_id: UUID | None = None,
    status: str = "todo",
    priority: int = 0,
    display_order: int = 0,
    estimated_effort: int | None = None,
    planning_cycle_type: str | None = None,
    planning_cycle_days: int | None = None,
    planning_cycle_start_date: date | None = None,
    person_ids: list[UUID] | None = None,
) -> TaskView:
    """Create a task."""
    await ensure_vision_exists(session, vision_id)
    await validate_parent_task(session, vision_id=vision_id, parent_task_id=parent_task_id)
    planning_cycle_type, planning_cycle_days, planning_cycle_start_date = validate_planning_cycle(
        planning_cycle_type=planning_cycle_type,
        planning_cycle_days=planning_cycle_days,
        planning_cycle_start_date=planning_cycle_start_date,
    )
    task = Task(
        vision_id=vision_id,
        parent_task_id=parent_task_id,
        content=content.strip(),
        description=description,
        status=validate_task_status(status),
        priority=priority,
        display_order=display_order,
        estimated_effort=estimated_effort,
        planning_cycle_type=planning_cycle_type,
        planning_cycle_days=planning_cycle_days,
        planning_cycle_start_date=planning_cycle_start_date,
    )
    session.add(task)
    await session.flush()
    if person_ids is not None:
        await sync_entity_person(
            session, entity_id=task.id, entity_type="task", desired_person_ids=person_ids
        )
    await session.refresh(task)
    return await _build_task_view(session, task)


async def reorder_tasks(
    session: AsyncSession,
    *,
    task_orders: list[tuple[UUID, int]],
) -> None:
    """Update display order for multiple active tasks."""
    if not task_orders:
        return

    task_ids = [task_id for task_id, _ in task_orders]
    result = await session.execute(
        select(Task).where(Task.id.in_(task_ids), Task.deleted_at.is_(None))
    )
    tasks = list(result.scalars())
    if len(tasks) != len(set(task_ids)):
        raise TaskNotFoundError("One or more tasks were not found")

    tasks_by_id = {task.id: task for task in tasks}
    for task_id, display_order in task_orders:
        tasks_by_id[task_id].display_order = display_order
    await session.flush()


async def _update_descendant_visions(
    session: AsyncSession,
    *,
    root_task_id: UUID,
    new_vision_id: UUID,
) -> tuple[Task, ...]:
    """Update descendant vision ownership after moving a task subtree."""
    subtree = await load_task_subtree(session, root_task_id=root_task_id)
    updated_descendants: list[Task] = []
    for descendant in subtree[1:]:
        if descendant.vision_id == new_vision_id:
            continue
        descendant.vision_id = new_vision_id
        updated_descendants.append(descendant)
    return tuple(updated_descendants)


async def move_task(
    session: AsyncSession,
    *,
    task_id: UUID,
    old_parent_task_id: UUID | None = None,
    new_parent_task_id: UUID | None | _UnsetParentTaskId = _UNSET_PARENT_TASK_ID,
    new_vision_id: UUID | None = None,
    new_display_order: int | None = None,
) -> TaskMoveResult:
    """Move a task to a new parent and optionally a new vision."""
    task = await load_model_by_id(
        session,
        model_cls=Task,
        model_id=task_id,
    )
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} was not found")

    if old_parent_task_id is not None and old_parent_task_id != task.parent_task_id:
        raise InvalidTaskOperationError("Old parent task ID does not match current parent task ID")

    old_parent_task_id = task.parent_task_id
    old_vision_id = task.vision_id
    target_vision_id = new_vision_id or old_vision_id
    parent_change_requested = new_parent_task_id is not _UNSET_PARENT_TASK_ID
    target_parent_task_id = (
        cast(UUID | None, new_parent_task_id) if parent_change_requested else task.parent_task_id
    )
    parent_changed = parent_change_requested and target_parent_task_id != old_parent_task_id
    vision_changed = target_vision_id != old_vision_id
    if new_vision_id is not None and vision_changed:
        await ensure_vision_exists(session, new_vision_id)

    if target_parent_task_id == task.id:
        raise ParentTaskReferenceNotFoundError("Task cannot be its own parent")
    await validate_parent_task(
        session,
        vision_id=target_vision_id,
        parent_task_id=target_parent_task_id,
        child_task_id=task.id,
    )

    if parent_change_requested:
        task.parent_task_id = target_parent_task_id
    if new_display_order is not None:
        task.display_order = new_display_order
    updated_descendants: tuple[Task, ...] = ()
    if vision_changed:
        task.vision_id = target_vision_id
        updated_descendants = await _update_descendant_visions(
            session,
            root_task_id=task.id,
            new_vision_id=target_vision_id,
        )

    await recompute_subtree_totals(session, task.id)
    recompute_roots = [
        task_id
        for task_id in (
            old_parent_task_id,
            target_parent_task_id if parent_change_requested else None,
            task.id,
        )
        if task_id is not None
    ]
    for recompute_root_id in deduplicate_preserving_order(recompute_roots):
        await recompute_totals_upwards(session, recompute_root_id)
    if parent_changed or vision_changed:
        await sync_vision_experience_for_vision_ids(
            session,
            vision_ids=deduplicate_preserving_order([old_vision_id, target_vision_id]),
        )
    await session.flush()
    await session.refresh(task)
    return TaskMoveResult(task=task, updated_descendants=updated_descendants)


async def update_task(
    session: AsyncSession,
    *,
    task_id: UUID,
    content: str | None = None,
    description: str | None = None,
    clear_description: bool = False,
    parent_task_id: UUID | None = None,
    clear_parent: bool = False,
    status: str | None = None,
    priority: int | None = None,
    display_order: int | None = None,
    estimated_effort: int | None = None,
    clear_estimated_effort: bool = False,
    planning_cycle_type: str | None = None,
    planning_cycle_days: int | None = None,
    planning_cycle_start_date: date | None = None,
    clear_planning_cycle: bool = False,
    person_ids: list[UUID] | None = None,
    clear_person: bool = False,
) -> TaskView:
    """Update a task."""
    task = await load_model_by_id(
        session,
        model_cls=Task,
        model_id=task_id,
    )
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} was not found")
    if parent_task_id == task_id:
        raise ParentTaskReferenceNotFoundError("Task cannot be its own parent")
    old_parent_task_id = task.parent_task_id
    next_parent_task_id = (
        None
        if clear_parent
        else parent_task_id
        if parent_task_id is not None
        else task.parent_task_id
    )
    next_cycle_type = (
        None
        if clear_planning_cycle
        else planning_cycle_type
        if planning_cycle_type is not None
        else task.planning_cycle_type
    )
    next_cycle_days = (
        None
        if clear_planning_cycle
        else planning_cycle_days
        if planning_cycle_days is not None
        else task.planning_cycle_days
    )
    next_cycle_start_date = (
        None
        if clear_planning_cycle
        else planning_cycle_start_date
        if planning_cycle_start_date is not None
        else task.planning_cycle_start_date
    )
    await validate_parent_task(
        session,
        vision_id=task.vision_id,
        parent_task_id=next_parent_task_id,
        child_task_id=task.id,
    )
    (
        normalized_cycle_type,
        normalized_cycle_days,
        normalized_cycle_start_date,
    ) = validate_planning_cycle(
        planning_cycle_type=next_cycle_type,
        planning_cycle_days=next_cycle_days,
        planning_cycle_start_date=next_cycle_start_date,
    )
    if content is not None:
        task.content = content.strip()
    if clear_description:
        task.description = None
    elif description is not None:
        task.description = description
    if clear_parent:
        task.parent_task_id = None
    elif parent_task_id is not None:
        task.parent_task_id = parent_task_id
    if status is not None:
        task.status = await validate_task_status_change(session, task=task, new_status=status)
    if priority is not None:
        task.priority = priority
    if display_order is not None:
        task.display_order = display_order
    if clear_estimated_effort:
        task.estimated_effort = None
    elif estimated_effort is not None:
        task.estimated_effort = estimated_effort
    if clear_person:
        await sync_entity_person(
            session, entity_id=task.id, entity_type="task", desired_person_ids=[]
        )
    elif person_ids is not None:
        await sync_entity_person(
            session, entity_id=task.id, entity_type="task", desired_person_ids=person_ids
        )
    task.planning_cycle_type = normalized_cycle_type
    task.planning_cycle_days = normalized_cycle_days
    task.planning_cycle_start_date = normalized_cycle_start_date
    if task.parent_task_id != old_parent_task_id:
        await recompute_subtree_totals(session, task.id)
        if old_parent_task_id is not None:
            await recompute_totals_upwards(session, old_parent_task_id)
        await recompute_totals_upwards(session, task.id)
        await sync_vision_experience_for_vision_ids(session, vision_ids=[task.vision_id])
    await session.flush()
    await session.refresh(task)
    return await _build_task_view(session, task)


async def delete_task(session: AsyncSession, *, task_id: UUID) -> None:
    """Soft-delete a task."""
    task = await load_model_by_id(
        session,
        model_cls=Task,
        model_id=task_id,
    )
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} was not found")
    old_parent_task_id = task.parent_task_id
    old_vision_id = task.vision_id
    subtree = await load_task_subtree(session, root_task_id=task_id)
    for subtree_task in subtree:
        subtree_task.soft_delete()
    if old_parent_task_id is not None:
        await recompute_totals_upwards(session, old_parent_task_id)
    await sync_vision_experience_for_vision_ids(session, vision_ids=[old_vision_id])
    await session.flush()


async def batch_delete_tasks(
    session: AsyncSession,
    *,
    task_ids: list[UUID],
) -> BatchDeleteResult:
    """Soft-delete multiple tasks while preserving per-task error reporting."""
    return await batch_delete_records(
        identifiers=deduplicate_preserving_order(task_ids),
        delete_record=lambda task_id: delete_task(session, task_id=task_id),
        handled_exceptions=(TaskNotFoundError,),
    )
