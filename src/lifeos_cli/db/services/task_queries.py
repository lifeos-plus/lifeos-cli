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
from lifeos_cli.application.time_preferences import get_operational_date
from lifeos_cli.config import ConfigurationError, get_preferences_settings
from lifeos_cli.db.models.association import Association
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.models.vision import Vision
from lifeos_cli.db.services.entity_person import load_person_for_entities
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
    TaskValidationError,
    ensure_vision_exists,
    load_task_subtree,
    validate_task_status,
)
from lifeos_cli.db.services.validation_utils import validate_choice
from lifeos_cli.db.sql_expressions import AddDaysToDate


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
    person: tuple[PersonSummaryView, ...]
    subtasks: tuple[TaskWithSubtasks, ...]
    completion_percentage: float
    depth: int


@dataclass(frozen=True)
class TaskHierarchy:
    """Vision task hierarchy read model."""

    vision_id: UUID
    root_tasks: tuple[TaskWithSubtasks, ...]


@dataclass(frozen=True)
class PlanningView:
    """Cross-vision planning tree for one calendar-aware window."""

    cycle_type: str
    period_start: date
    period_end: date
    roots: tuple[TaskWithSubtasks, ...]
    context_root_ids: tuple[UUID, ...]
    total_tasks: int


MAX_PLANNING_CONTEXT_PARENT_FETCHES = 100


def _build_task_tree(
    tasks: list[Task],
    *,
    person_map: dict[UUID, list[Person]],
    max_depth: int | None = None,
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
        child_tasks = children_by_parent[task.id]
        if max_depth is not None and depth >= max_depth:
            child_tasks = []
        subtasks = tuple(convert(subtask, depth=depth + 1) for subtask in child_tasks)
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
            person=tuple(build_person_summary(person) for person in person_map.get(task.id, [])),
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
) -> tuple[date, date] | None:
    """Return the calendar-aware planning-cycle range from persisted preferences."""
    if planning_cycle_type not in {"day", "week", "month", "year", "7years"}:
        return None
    preferences = get_preferences_settings()
    try:
        return get_calendar_period_range(
            cast(CalendarGranularity, planning_cycle_type),
            planning_cycle_start_date,
            calendar_system=preferences.calendar_system,
            first_day_of_week=preferences.calendar_first_day_of_week,
            seven_year_anchor_date=date.fromisoformat(preferences.calendar_seven_year_anchor_date),
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
            Association,
            (Association.source_model == "task")
            & (Association.source_id == Task.id)
            & (Association.target_model == "person"),
        ).where(Association.target_id == person_id)
    if status is not None:
        stmt = stmt.where(Task.status == validate_task_status(status))
    included_statuses = _parse_status_csv(status_in)
    if included_statuses:
        stmt = stmt.where(Task.status.in_(included_statuses))
    excluded_statuses = _parse_status_csv(exclude_status)
    if excluded_statuses:
        stmt = stmt.where(Task.status.not_in(excluded_statuses))
    if planning_cycle_type is not None:
        normalized_cycle_type = validate_choice(
            planning_cycle_type,
            VALID_PLANNING_CYCLE_TYPES,
            error_cls=TaskValidationError,
            label="planning cycle type",
        )
        stmt = stmt.where(Task.planning_cycle_type == normalized_cycle_type)
    if planning_cycle_start_date is not None:
        if planning_cycle_type is not None:
            cycle_range = _planning_cycle_date_filter_range(
                planning_cycle_type=planning_cycle_type.strip().lower(),
                planning_cycle_start_date=planning_cycle_start_date,
            )
        else:
            cycle_range = None
        if cycle_range is None:
            stmt = stmt.where(Task.planning_cycle_start_date == planning_cycle_start_date)
        else:
            cycle_start, cycle_end = cycle_range
            stmt = stmt.where(
                Task.planning_cycle_start_date <= cycle_end,
                AddDaysToDate(Task.planning_cycle_start_date, Task.planning_cycle_days - 1)
                >= cycle_start,
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


def _apply_task_display_order(stmt: Any) -> Any:
    """Apply the shared task tree ordering used by list and view queries."""
    return stmt.order_by(Task.display_order.asc(), Task.created_at.asc(), Task.id.asc())


async def _build_task_view(session: AsyncSession, task: Task) -> TaskView:
    person_map = await load_person_for_entities(
        session,
        entity_ids=[task.id],
        entity_type="task",
    )
    return build_task_view(task, person_records=person_map.get(task.id, ()))


async def _build_task_views(session: AsyncSession, tasks: list[Task]) -> list[TaskView]:
    if not tasks:
        return []
    person_map = await load_person_for_entities(
        session,
        entity_ids=[task.id for task in tasks],
        entity_type="task",
    )
    return [build_task_view(task, person_records=person_map.get(task.id, ())) for task in tasks]


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
        content=content,
        query=query,
    )
    stmt = _apply_task_display_order(stmt).offset(offset).limit(limit)
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
        content=content,
        query=query,
    )
    return int((await session.execute(stmt)).scalar_one())


async def _load_planning_context_parents(
    session: AsyncSession,
    tasks: list[Task],
    *,
    vision_in: str | None,
) -> list[Task]:
    """Load direct parents that fall outside the queried planning window."""
    task_ids = {task.id for task in tasks}
    missing_ids = tuple(
        dict.fromkeys(
            task.parent_task_id
            for task in tasks
            if task.parent_task_id is not None and task.parent_task_id not in task_ids
        )
    )[:MAX_PLANNING_CONTEXT_PARENT_FETCHES]
    if not missing_ids:
        return []
    result = await session.execute(
        select(Task).where(
            Task.id.in_(missing_ids),
            Task.deleted_at.is_(None),
        )
    )
    allowed_visions: set[UUID] | None = None
    if vision_in is not None:
        allowed_visions = {UUID(value.strip()) for value in vision_in.split(",") if value.strip()}
    parents = [
        parent
        for parent in result.scalars()
        if allowed_visions is None or parent.vision_id in allowed_visions
    ]
    return sorted(parents, key=lambda task: (task.display_order, task.created_at, task.id))


async def get_planning_view(
    session: AsyncSession,
    *,
    cycle_type: str,
    at_date: date | None = None,
    start_date: date | None = None,
    vision_in: str | None = None,
    status_in: str | None = None,
    max_depth: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PlanningView:
    """Return the calendar-aware cross-vision planning tree for one window.

    The window query reuses the shared task filter contract and the tree is
    assembled with the shared ``_build_task_tree`` helper; ancestors outside
    the window are loaded as collapsed context roots.
    """
    if at_date is not None and start_date is not None:
        raise ValueError("Use either --at or --start, not both.")
    preferences = get_preferences_settings()
    anchor = start_date
    if anchor is None:
        reference_date = at_date or get_operational_date()
        anchor = get_calendar_period_range(
            cast(CalendarGranularity, cycle_type),
            reference_date,
            calendar_system=preferences.calendar_system,
            first_day_of_week=preferences.calendar_first_day_of_week,
            seven_year_anchor_date=date.fromisoformat(preferences.calendar_seven_year_anchor_date),
        )[0]
    period_start, period_end = get_calendar_period_range(
        cast(CalendarGranularity, cycle_type),
        anchor,
        calendar_system=preferences.calendar_system,
        first_day_of_week=preferences.calendar_first_day_of_week,
        seven_year_anchor_date=date.fromisoformat(preferences.calendar_seven_year_anchor_date),
    )
    stmt = _apply_task_filters(
        select(Task),
        planning_cycle_type=cycle_type,
        planning_cycle_start_date=anchor,
        vision_in=vision_in,
        status_in=status_in,
    )
    stmt = _apply_task_display_order(stmt).offset(offset).limit(limit)
    tasks = list((await session.execute(stmt)).scalars())
    context_parents = await _load_planning_context_parents(session, tasks, vision_in=vision_in)
    roots = _build_task_tree(
        [*tasks, *context_parents],
        person_map={},
        max_depth=max_depth,
    )
    return PlanningView(
        cycle_type=cycle_type,
        period_start=period_start,
        period_end=period_end,
        roots=roots,
        context_root_ids=tuple(parent.id for parent in context_parents),
        total_tasks=len(tasks),
    )


async def get_vision_task_hierarchy(
    session: AsyncSession,
    *,
    vision_id: UUID,
) -> TaskHierarchy:
    """Load active tasks for a vision as a hierarchy."""
    await ensure_vision_exists(session, vision_id)
    stmt = _apply_task_display_order(
        select(Task).where(Task.vision_id == vision_id, Task.deleted_at.is_(None))
    )
    tasks = list((await session.execute(stmt)).scalars())
    person_map = await load_person_for_entities(
        session,
        entity_ids=[task.id for task in tasks],
        entity_type="task",
    )
    return TaskHierarchy(
        vision_id=vision_id, root_tasks=_build_task_tree(tasks, person_map=person_map)
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
    person_map = await load_person_for_entities(
        session,
        entity_ids=[task.id for task in tasks],
        entity_type="task",
    )
    task_tree = _build_task_tree(tasks, person_map=person_map)
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
