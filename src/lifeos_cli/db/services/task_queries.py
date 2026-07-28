"""Read-side task service helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.calendar_adapter import (
    CalendarGranularity,
    get_calendar_period_range,
)
from lifeos_cli.config import ConfigurationError
from lifeos_cli.db.models.association import Association
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.person_association import person_associations
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.models.vision import Vision
from lifeos_cli.db.services.entity_people import load_people_for_entities
from lifeos_cli.db.services.model_utils import load_view_by_id
from lifeos_cli.db.services.read_models import (
    PersonSummaryView,
    TaskView,
    build_person_summary,
    build_task_view,
)
from lifeos_cli.db.services.task_support import (
    VALID_PLANNING_CYCLE_TYPES,
    TaskNotFoundError,
    ensure_vision_exists,
    load_task_subtree,
    validate_task_status,
)


@dataclass(frozen=True)
class TaskStats:
    """Aggregated statistics for a task subtree."""

    total_subtasks: int
    completed_subtasks: int
    completion_percentage: float
    total_estimated_effort: int | None
    total_actual_effort: int | None


@dataclass(frozen=True)
class TaskWithSubtasks:
    """Task read model with nested subtasks."""

    task: Task
    id: UUID
    vision_id: UUID
    parent_task_id: UUID | None
    content: str
    description: str | None
    status: str
    priority: int
    display_order: int
    estimated_effort: int | None
    planning_cycle_type: str | None
    planning_cycle_days: int | None
    planning_cycle_start_date: date | None
    actual_effort_self: int
    actual_effort_total: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    people: tuple[PersonSummaryView, ...]
    subtasks: tuple[TaskWithSubtasks, ...]
    completion_percentage: float
    depth: int


@dataclass(frozen=True)
class TaskHierarchy:
    """Vision task hierarchy read model."""

    vision_id: UUID
    root_tasks: tuple[TaskWithSubtasks, ...]


def _build_task_tree(
    tasks: list[Task],
    *,
    people_map: dict[UUID, list[Person]],
) -> tuple[TaskWithSubtasks, ...]:
    """Build a task tree from a flat task list."""
    task_ids = {task.id for task in tasks}
    children_by_parent: dict[UUID, list[Task]] = {task.id: [] for task in tasks}
    root_tasks: list[Task] = []
    for task in tasks:
        if task.parent_task_id is None or task.parent_task_id not in task_ids:
            root_tasks.append(task)
            continue
        children_by_parent.setdefault(task.parent_task_id, []).append(task)

    def completion_ratio(task: Task, subtasks: tuple[TaskWithSubtasks, ...]) -> float:
        if not subtasks:
            return 1.0 if task.status == "done" else 0.0
        completed_count = sum(1 for subtask in subtasks if subtask.status == "done")
        return completed_count / len(subtasks)

    def convert(task: Task, *, depth: int) -> TaskWithSubtasks:
        subtasks = tuple(
            convert(subtask, depth=depth + 1) for subtask in children_by_parent[task.id]
        )
        return TaskWithSubtasks(
            task=task,
            id=task.id,
            vision_id=task.vision_id,
            parent_task_id=task.parent_task_id,
            content=task.content,
            description=task.description,
            status=task.status,
            priority=task.priority,
            display_order=task.display_order,
            estimated_effort=task.estimated_effort,
            planning_cycle_type=task.planning_cycle_type,
            planning_cycle_days=task.planning_cycle_days,
            planning_cycle_start_date=task.planning_cycle_start_date,
            actual_effort_self=task.actual_effort_self,
            actual_effort_total=task.actual_effort_total,
            created_at=task.created_at,
            updated_at=task.updated_at,
            deleted_at=task.deleted_at,
            people=tuple(build_person_summary(person) for person in people_map.get(task.id, [])),
            subtasks=subtasks,
            completion_percentage=completion_ratio(task, subtasks),
            depth=depth,
        )

    return tuple(convert(task, depth=0) for task in root_tasks)


def _split_csv(value: str | None) -> list[str]:
    """Return non-empty comma-separated values."""
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_uuid_csv(value: str | None) -> list[UUID]:
    """Parse comma-separated UUID values."""
    return [UUID(item) for item in _split_csv(value)]


def _parse_status_csv(value: str | None) -> list[str]:
    """Parse comma-separated task statuses."""
    return [validate_task_status(item) for item in _split_csv(value)]


def _planning_cycle_date_filter_range(
    *,
    planning_cycle_type: str,
    planning_cycle_start_date: date,
    calendar_system: str | None,
    first_day_of_week: int | None,
) -> tuple[date, date] | None:
    """Return a calendar-aware planning-cycle filter range when requested."""
    if calendar_system is None and first_day_of_week is None:
        return None
    if planning_cycle_type not in {"day", "week", "month", "year", "7years"}:
        return None
    try:
        return get_calendar_period_range(
            cast(CalendarGranularity, planning_cycle_type),
            planning_cycle_start_date,
            calendar_system=calendar_system,
            first_day_of_week=first_day_of_week,
        )
    except (ConfigurationError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


def _apply_task_filters(
    stmt: Any,
    *,
    vision_id: UUID | None = None,
    vision_in: str | None = None,
    parent_task_id: UUID | None = None,
    person_id: UUID | None = None,
    status: str | None = None,
    status_in: str | None = None,
    exclude_status: str | None = None,
    planning_cycle_type: str | None = None,
    planning_cycle_start_date: date | None = None,
    calendar_system: str | None = None,
    first_day_of_week: int | None = None,
    content: str | None = None,
    query: str | None = None,
) -> Any:
    """Apply the shared task list/count filter contract."""
    stmt = stmt.where(
        Task.deleted_at.is_(None),
        Task.vision.has(Vision.deleted_at.is_(None)),
    )
    if vision_id is not None:
        stmt = stmt.where(Task.vision_id == vision_id)
    vision_ids = _parse_uuid_csv(vision_in)
    if vision_ids:
        stmt = stmt.where(Task.vision_id.in_(vision_ids))
    if parent_task_id is None and vision_id is not None:
        stmt = stmt.where(Task.parent_task_id.is_(None))
    elif parent_task_id is not None:
        stmt = stmt.where(Task.parent_task_id == parent_task_id)
    if person_id is not None:
        stmt = stmt.join(
            person_associations,
            (person_associations.c.entity_id == Task.id)
            & (person_associations.c.entity_type == "task"),
        ).where(person_associations.c.person_id == person_id)
    if status is not None:
        stmt = stmt.where(Task.status == validate_task_status(status))
    included_statuses = _parse_status_csv(status_in)
    if included_statuses:
        stmt = stmt.where(Task.status.in_(included_statuses))
    excluded_statuses = _parse_status_csv(exclude_status)
    if excluded_statuses:
        stmt = stmt.where(Task.status.not_in(excluded_statuses))
    if planning_cycle_type is not None:
        normalized_cycle_type = planning_cycle_type.strip().lower()
        if normalized_cycle_type not in VALID_PLANNING_CYCLE_TYPES:
            allowed = ", ".join(sorted(VALID_PLANNING_CYCLE_TYPES))
            raise ValueError(
                f"Invalid planning cycle type {normalized_cycle_type!r}. Expected one of: {allowed}"
            )
        stmt = stmt.where(Task.planning_cycle_type == normalized_cycle_type)
    if planning_cycle_start_date is not None:
        if planning_cycle_type is not None:
            cycle_range = _planning_cycle_date_filter_range(
                planning_cycle_type=planning_cycle_type.strip().lower(),
                planning_cycle_start_date=planning_cycle_start_date,
                calendar_system=calendar_system,
                first_day_of_week=first_day_of_week,
            )
        else:
            cycle_range = None
        if cycle_range is None:
            stmt = stmt.where(Task.planning_cycle_start_date == planning_cycle_start_date)
        else:
            cycle_start, cycle_end = cycle_range
            stmt = stmt.where(
                Task.planning_cycle_start_date >= cycle_start,
                Task.planning_cycle_start_date <= cycle_end,
            )
    if content is not None:
        normalized_content = content.strip()
        if normalized_content:
            stmt = stmt.where(Task.content == normalized_content)
    if query is not None:
        normalized_query = query.strip()
        if normalized_query:
            stmt = stmt.where(Task.content.ilike(f"%{normalized_query}%"))
    return stmt


async def _build_task_view(session: AsyncSession, task: Task) -> TaskView:
    people_map = await load_people_for_entities(
        session,
        entity_ids=[task.id],
        entity_type="task",
    )
    return build_task_view(task, people=people_map.get(task.id, ()))


async def _build_task_views(session: AsyncSession, tasks: list[Task]) -> list[TaskView]:
    if not tasks:
        return []
    people_map = await load_people_for_entities(
        session,
        entity_ids=[task.id for task in tasks],
        entity_type="task",
    )
    return [build_task_view(task, people=people_map.get(task.id, ())) for task in tasks]


async def load_task_relation_counts(
    session: AsyncSession,
    *,
    task_ids: list[UUID],
) -> tuple[dict[UUID, int], dict[UUID, int]]:
    """Load active note and timelog counts for a set of tasks."""
    unique_task_ids = list(dict.fromkeys(task_ids))
    if not unique_task_ids:
        return {}, {}

    note_rows = await session.execute(
        select(Association.target_id, func.count(Association.id))
        .join(Note, Note.id == Association.source_id)
        .where(
            Association.source_model == "note",
            Association.target_model == "task",
            Association.link_type == "relates_to",
            Association.target_id.in_(unique_task_ids),
            Note.deleted_at.is_(None),
        )
        .group_by(Association.target_id)
    )
    timelog_rows = await session.execute(
        select(Timelog.task_id, func.count(Timelog.id))
        .where(
            Timelog.task_id.in_(unique_task_ids),
            Timelog.deleted_at.is_(None),
        )
        .group_by(Timelog.task_id)
    )
    return (
        {task_id: int(count) for task_id, count in note_rows.all()},
        {task_id: int(count) for task_id, count in timelog_rows.all()},
    )


async def get_task(
    session: AsyncSession,
    *,
    task_id: UUID,
) -> TaskView | None:
    """Load a task by identifier."""
    return await load_view_by_id(
        session,
        model_cls=Task,
        model_id=task_id,
        view_builder=_build_task_view,
    )


async def list_tasks(
    session: AsyncSession,
    *,
    vision_id: UUID | None = None,
    vision_in: str | None = None,
    parent_task_id: UUID | None = None,
    person_id: UUID | None = None,
    status: str | None = None,
    status_in: str | None = None,
    exclude_status: str | None = None,
    planning_cycle_type: str | None = None,
    planning_cycle_start_date: date | None = None,
    calendar_system: str | None = None,
    first_day_of_week: int | None = None,
    content: str | None = None,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TaskView]:
    """List tasks with basic filters."""
    stmt = _apply_task_filters(
        select(Task),
        vision_id=vision_id,
        vision_in=vision_in,
        parent_task_id=parent_task_id,
        person_id=person_id,
        status=status,
        status_in=status_in,
        exclude_status=exclude_status,
        planning_cycle_type=planning_cycle_type,
        planning_cycle_start_date=planning_cycle_start_date,
        calendar_system=calendar_system,
        first_day_of_week=first_day_of_week,
        content=content,
        query=query,
    )
    stmt = (
        stmt.order_by(Task.display_order.asc(), Task.created_at.asc(), Task.id.asc())
        .offset(offset)
        .limit(limit)
    )
    tasks = list((await session.execute(stmt)).scalars())
    return await _build_task_views(session, tasks)


async def count_tasks(
    session: AsyncSession,
    *,
    vision_id: UUID | None = None,
    vision_in: str | None = None,
    parent_task_id: UUID | None = None,
    person_id: UUID | None = None,
    status: str | None = None,
    status_in: str | None = None,
    exclude_status: str | None = None,
    planning_cycle_type: str | None = None,
    planning_cycle_start_date: date | None = None,
    calendar_system: str | None = None,
    first_day_of_week: int | None = None,
    content: str | None = None,
    query: str | None = None,
) -> int:
    """Count tasks with the same filters as ``list_tasks``."""
    stmt = _apply_task_filters(
        select(func.count()).select_from(Task),
        vision_id=vision_id,
        vision_in=vision_in,
        parent_task_id=parent_task_id,
        person_id=person_id,
        status=status,
        status_in=status_in,
        exclude_status=exclude_status,
        planning_cycle_type=planning_cycle_type,
        planning_cycle_start_date=planning_cycle_start_date,
        calendar_system=calendar_system,
        first_day_of_week=first_day_of_week,
        content=content,
        query=query,
    )
    return int((await session.execute(stmt)).scalar_one())


async def get_vision_task_hierarchy(
    session: AsyncSession,
    *,
    vision_id: UUID,
) -> TaskHierarchy:
    """Load active tasks for a vision as a hierarchy."""
    await ensure_vision_exists(session, vision_id)
    stmt = (
        select(Task)
        .where(Task.vision_id == vision_id, Task.deleted_at.is_(None))
        .order_by(Task.display_order.asc(), Task.created_at.asc(), Task.id.asc())
    )
    tasks = list((await session.execute(stmt)).scalars())
    people_map = await load_people_for_entities(
        session,
        entity_ids=[task.id for task in tasks],
        entity_type="task",
    )
    return TaskHierarchy(
        vision_id=vision_id, root_tasks=_build_task_tree(tasks, people_map=people_map)
    )


async def get_task_with_subtasks(
    session: AsyncSession,
    *,
    task_id: UUID,
) -> TaskWithSubtasks | None:
    """Load a task with all active subtasks."""
    tasks = await load_task_subtree(session, root_task_id=task_id)
    if not tasks:
        return None
    people_map = await load_people_for_entities(
        session,
        entity_ids=[task.id for task in tasks],
        entity_type="task",
    )
    task_tree = _build_task_tree(tasks, people_map=people_map)
    return task_tree[0] if task_tree else None


async def get_task_stats(
    session: AsyncSession,
    *,
    task_id: UUID,
) -> TaskStats:
    """Return task subtree statistics."""
    tasks = await load_task_subtree(session, root_task_id=task_id)
    if not tasks:
        raise TaskNotFoundError(f"Task {task_id} was not found")

    root = next((task for task in tasks if task.id == task_id), None)
    if root is None:
        raise TaskNotFoundError(f"Task {task_id} was not found")

    subtasks = [task for task in tasks if task.id != task_id]
    total_subtasks = len(subtasks)
    completed_subtasks = len([task for task in subtasks if task.status == "done"])

    direct_children = [task for task in subtasks if task.parent_task_id == task_id]
    if not direct_children:
        completion_percentage = 1.0 if root.status == "done" else 0.0
    else:
        done_children = len([task for task in direct_children if task.status == "done"])
        completion_percentage = done_children / len(direct_children)

    total_estimated_effort = sum(task.estimated_effort or 0 for task in tasks)
    total_actual_effort = sum(task.actual_effort_self or 0 for task in tasks)

    return TaskStats(
        total_subtasks=total_subtasks,
        completed_subtasks=completed_subtasks,
        completion_percentage=completion_percentage,
        total_estimated_effort=total_estimated_effort or None,
        total_actual_effort=total_actual_effort or None,
    )
