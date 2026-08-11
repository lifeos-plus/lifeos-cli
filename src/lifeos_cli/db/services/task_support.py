"""Support utilities and validations for task services."""

from __future__ import annotations

from collections import deque
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.vision import Vision

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


class InvalidPlanningCycleError(ValueError):
    """Raised when planning cycle fields are incomplete or invalid."""


class CircularTaskReferenceError(ValueError):
    """Raised when a task parent change would create a cycle."""


class TaskCannotBeCompletedError(ValueError):
    """Raised when a task status transition is not allowed."""


class InvalidTaskOperationError(ValueError):
    """Raised when a task operation is inconsistent with current state."""


def validate_task_status(status: str) -> str:
    """Validate a task status."""
    normalized = status.strip().lower()
    if normalized not in VALID_TASK_STATUSES:
        allowed = ", ".join(sorted(VALID_TASK_STATUSES))
        raise ValueError(f"Invalid task status {normalized!r}. Expected one of: {allowed}")
    return normalized


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
    normalized_type = planning_cycle_type.strip().lower()
    normalized_days = planning_cycle_days
    normalized_start_date = planning_cycle_start_date
    if normalized_type not in VALID_PLANNING_CYCLE_TYPES:
        allowed = ", ".join(sorted(VALID_PLANNING_CYCLE_TYPES))
        raise InvalidPlanningCycleError(
            f"Invalid planning cycle type {normalized_type!r}. Expected one of: {allowed}"
        )
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
    depth = 1
    current = parent_task
    while current.parent_task_id is not None:
        if current.id == child_task_id:
            raise CircularTaskReferenceError("This would create a circular task reference")
        depth += 1
        if depth >= MAX_TASK_DEPTH:
            raise InvalidTaskDepthError(
                f"Task hierarchy depth cannot exceed {MAX_TASK_DEPTH} levels"
            )
        next_parent = await load_parent_task(session, current.parent_task_id)
        if next_parent is None:
            break
        current = next_parent
    if current.id == child_task_id:
        raise CircularTaskReferenceError("This would create a circular task reference")
    return parent_task


async def validate_task_status_change(
    session: AsyncSession,
    *,
    task: Task,
    new_status: str,
) -> str:
    """Validate status transitions that depend on task hierarchy state."""
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
        raise TaskCannotBeCompletedError(
            "Task cannot be completed until all direct subtasks are done, cancelled, or paused"
        )
    return normalized_status


async def load_task_subtree(session: AsyncSession, *, root_task_id: UUID) -> list[Task]:
    """Load an active task subtree in breadth-first order."""
    root_task = await load_parent_task(session, root_task_id)
    if root_task is None:
        return []

    subtree: list[Task] = []
    queue = deque([root_task])
    while queue:
        task = queue.popleft()
        subtree.append(task)
        children = (
            await session.execute(
                select(Task)
                .where(
                    Task.parent_task_id == task.id,
                    Task.deleted_at.is_(None),
                )
                .order_by(Task.display_order.asc(), Task.created_at.asc(), Task.id.asc())
            )
        ).scalars()
        queue.extend(children)
    return subtree
