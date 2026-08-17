"""Support utilities and validations for task services."""

from __future__ import annotations

from collections import deque
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import Integer, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.vision import Vision
from lifeos_cli.db.services.validation_utils import (
    DomainValidationError,
    choice_validator,
    validate_choice,
)

VALID_TASK_STATUSES = {"todo", "in_progress", "done", "cancelled", "paused"}
TASK_STATUSES_ALLOWED_FOR_PARENT_COMPLETION = {"done", "cancelled", "paused"}
VALID_PLANNING_CYCLE_TYPES = ("day", "week", "month", "year", "7years")
MAX_TASK_DEPTH = 8


def planning_cycle_end_date(start_date: date, days: int) -> date:
    """Return the inclusive end date of one planning cycle window."""
    return start_date + timedelta(days=days - 1)


class TaskNotFoundError(LookupError):
    """Raised when a task cannot be found."""


class VisionReferenceNotFoundError(LookupError):
    """Raised when a referenced vision cannot be found."""


class ParentTaskReferenceNotFoundError(LookupError):
    """Raised when a referenced parent task cannot be found."""


class InvalidTaskDepthError(ValueError):
    """Raised when a task hierarchy exceeds the configured max depth."""


class InvalidPlanningCycleError(DomainValidationError):
    """Raised when planning cycle fields are incomplete or invalid."""


class TaskValidationError(DomainValidationError):
    """Raised when task input validation fails."""


class CircularTaskReferenceError(ValueError):
    """Raised when a task parent change would create a cycle."""


class TaskCannotBeCompletedError(ValueError):
    """Raised when a task status transition is not allowed."""


class InvalidTaskOperationError(ValueError):
    """Raised when a task operation is inconsistent with current state."""


validate_task_status = choice_validator(
    VALID_TASK_STATUSES,
    error_cls=TaskValidationError,
    label="task status",
    doc="Validate a task status.",
)


def validate_planning_cycle(
    *,
    planning_cycle_type: str | None,
    planning_cycle_days: int | None,
    planning_cycle_start_date: date | None,
) -> tuple[str | None, int | None, date | None]:
    """Validate planning cycle fields."""
    values = (planning_cycle_type, planning_cycle_days, planning_cycle_start_date)
    if all(value is None for value in values):
        return values
    if (
        planning_cycle_type is None
        or planning_cycle_days is None
        or planning_cycle_start_date is None
    ):
        raise InvalidPlanningCycleError(
            "Planning cycle type, days, and start date must be provided together"
        )
    normalized_type = validate_choice(
        planning_cycle_type,
        VALID_PLANNING_CYCLE_TYPES,
        error_cls=InvalidPlanningCycleError,
        label="planning cycle type",
    )
    normalized_days = planning_cycle_days
    normalized_start_date = planning_cycle_start_date
    if normalized_days <= 0:
        raise InvalidPlanningCycleError("Planning cycle days must be greater than zero")
    return normalized_type, normalized_days, normalized_start_date


async def ensure_vision_exists(session: AsyncSession, vision_id: UUID) -> None:
    """Ensure a vision reference exists."""
    result = await session.execute(
        select(Vision.id).where(Vision.id == vision_id, Vision.deleted_at.is_(None)).limit(1)
    )
    if result.scalar_one_or_none() is None:
        raise VisionReferenceNotFoundError(f"Vision {vision_id} was not found")


async def load_parent_task(session: AsyncSession, parent_task_id: UUID | None) -> Task | None:
    """Load a parent task when one is referenced."""
    if parent_task_id is None:
        return None
    return (
        await session.execute(
            select(Task).where(Task.id == parent_task_id, Task.deleted_at.is_(None)).limit(1)
        )
    ).scalar_one_or_none()


async def validate_parent_task(
    session: AsyncSession,
    *,
    vision_id: UUID,
    parent_task_id: UUID | None,
    child_task_id: UUID | None = None,
) -> Task | None:
    """Ensure a parent task exists, belongs to the same vision, and respects depth limits."""
    parent_task = await load_parent_task(session, parent_task_id)
    if parent_task_id is None:
        return None
    if parent_task is None:
        raise ParentTaskReferenceNotFoundError(f"Task {parent_task_id} was not found")
    if parent_task.vision_id != vision_id:
        raise ParentTaskReferenceNotFoundError(
            "Parent task must belong to the same vision as the child task"
        )
    ancestor_parent_by_id = await _load_ancestor_parent_ids(
        session,
        start_task_id=parent_task.id,
    )
    depth = 1
    current_id: UUID = parent_task.id
    current_parent_id: UUID | None = parent_task.parent_task_id
    while current_parent_id is not None:
        if current_id == child_task_id:
            raise CircularTaskReferenceError("This would create a circular task reference")
        depth += 1
        if depth >= MAX_TASK_DEPTH:
            raise InvalidTaskDepthError(
                f"Task hierarchy depth cannot exceed {MAX_TASK_DEPTH} levels"
            )
        if current_parent_id not in ancestor_parent_by_id:
            break
        current_id = current_parent_id
        current_parent_id = ancestor_parent_by_id[current_id]
    if current_id == child_task_id:
        raise CircularTaskReferenceError("This would create a circular task reference")
    return parent_task


async def _load_ancestor_parent_ids(
    session: AsyncSession,
    *,
    start_task_id: UUID,
) -> dict[UUID, UUID | None]:
    """Load one task's active ancestor chain in a single recursive CTE query."""
    ancestors_cte = (
        select(
            Task.id,
            Task.parent_task_id,
            literal(0, Integer).label("depth"),
        )
        .where(Task.id == start_task_id, Task.deleted_at.is_(None))
        .cte(name="task_ancestors", recursive=True)
    )
    ancestor_step = (
        select(
            Task.id,
            Task.parent_task_id,
            (ancestors_cte.c.depth + 1).label("depth"),
        )
        .join(ancestors_cte, Task.id == ancestors_cte.c.parent_task_id)
        .where(Task.deleted_at.is_(None), ancestors_cte.c.depth < MAX_TASK_DEPTH)
    )
    ancestors_cte = ancestors_cte.union_all(ancestor_step)
    stmt = select(ancestors_cte.c.id, ancestors_cte.c.parent_task_id).order_by(
        ancestors_cte.c.depth.asc()
    )
    return {
        task_id: parent_task_id for task_id, parent_task_id in (await session.execute(stmt)).all()
    }


async def _apply_status_to_open_subtasks(
    session: AsyncSession,
    *,
    parent_task_id: UUID,
    status: str,
) -> None:
    """Recursively apply a terminal status to open descendants within one session.

    Children already in a closed state (``done``, ``cancelled``, or ``paused``)
    are left untouched, matching ``TASK_STATUSES_ALLOWED_FOR_PARENT_COMPLETION``.
    The change is intentionally not committed here; the caller owns the
    transaction boundary so the whole cascade stays atomic.
    """
    children = list(
        (
            await session.execute(
                select(Task).where(
                    Task.parent_task_id == parent_task_id,
                    Task.deleted_at.is_(None),
                )
            )
        ).scalars()
    )
    for child in children:
        if child.status in TASK_STATUSES_ALLOWED_FOR_PARENT_COMPLETION:
            continue
        await _apply_status_to_open_subtasks(
            session,
            parent_task_id=child.id,
            status=status,
        )
        child.status = status


async def validate_task_status_change(
    session: AsyncSession,
    *,
    task: Task,
    new_status: str,
    apply_to_subtasks: bool = False,
) -> str:
    """Validate status transitions that depend on task hierarchy state.

    Marking a task done is rejected while any direct subtask is still open
    (``todo`` / ``in_progress``). When ``apply_to_subtasks`` is set, the
    open descendants are updated to the target status recursively in the same
    transaction first, leaving ``done`` / ``cancelled`` / ``paused`` children
    untouched.
    """
    normalized_status = validate_task_status(new_status)
    if normalized_status == task.status:
        return normalized_status
    if normalized_status != "done":
        return normalized_status

    result = await session.execute(
        select(Task.status).where(
            Task.parent_task_id == task.id,
            Task.deleted_at.is_(None),
        )
    )
    child_statuses = list(result.scalars())
    if child_statuses and any(
        status not in TASK_STATUSES_ALLOWED_FOR_PARENT_COMPLETION for status in child_statuses
    ):
        if not apply_to_subtasks:
            raise TaskCannotBeCompletedError(
                "Task cannot be completed until all direct subtasks are done, cancelled, or paused"
            )
        await _apply_status_to_open_subtasks(
            session,
            parent_task_id=task.id,
            status=normalized_status,
        )
    return normalized_status


async def load_task_subtree(session: AsyncSession, *, root_task_id: UUID) -> list[Task]:
    """Load an active task subtree in breadth-first order."""
    root_task = await load_parent_task(session, root_task_id)
    if root_task is None:
        return []

    descendants_cte = (
        select(Task.id, literal(0, Integer).label("depth"))
        .where(Task.id == root_task_id, Task.deleted_at.is_(None))
        .cte(name="task_descendants", recursive=True)
    )
    child_step = (
        select(Task.id, (descendants_cte.c.depth + 1).label("depth"))
        .join(descendants_cte, Task.parent_task_id == descendants_cte.c.id)
        .where(Task.deleted_at.is_(None), descendants_cte.c.depth < MAX_TASK_DEPTH)
    )
    descendants_cte = descendants_cte.union_all(child_step)
    stmt = select(Task).join(descendants_cte, Task.id == descendants_cte.c.id)
    descendant_tasks = list((await session.execute(stmt)).scalars())

    children_by_parent: dict[UUID | None, list[Task]] = {}
    for task in descendant_tasks:
        children_by_parent.setdefault(task.parent_task_id, []).append(task)
    for children in children_by_parent.values():
        children.sort(key=lambda task: (task.display_order, task.created_at, task.id))

    subtree: list[Task] = []
    queue = deque([root_task])
    while queue:
        task = queue.popleft()
        subtree.append(task)
        queue.extend(children_by_parent.get(task.id, []))
    return subtree
