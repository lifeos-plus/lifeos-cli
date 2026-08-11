"""Read-side planning view service.

The planning view mirrors the Web planning page: a calendar-aware planning
window selects a flat set of tasks across all visions, and the tree shape is
assembled in the view layer from ``parent_task_id`` links.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.calendar_adapter import (
    CalendarGranularity,
    get_calendar_period_range,
)
from lifeos_cli.application.time_preferences import (
    get_calendar_preferences,
    get_operational_date,
)
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.services import task_queries
from lifeos_cli.db.services.read_models import TaskView

MAX_CONTEXT_PARENT_FETCHES = 100


@dataclass(frozen=True)
class PlanningTaskFlat:
    """One flat task row used to assemble a planning tree."""

    id: UUID
    vision_id: UUID
    parent_task_id: UUID | None
    content: str
    status: str
    estimated_effort: int | None
    planning_cycle_start_date: date | None
    planning_cycle_days: int | None
    display_order: int
    created_at: datetime


@dataclass(frozen=True)
class PlanningTaskNode:
    """One node in the assembled planning tree."""

    id: UUID
    vision_id: UUID
    parent_task_id: UUID | None
    content: str
    status: str
    estimated_effort: int | None
    planning_cycle_start_date: date | None
    planning_cycle_days: int | None
    depth: int
    is_context: bool
    children: tuple[PlanningTaskNode, ...] = ()


@dataclass(frozen=True)
class PlanningView:
    """A cross-vision planning tree for one calendar-aware window."""

    cycle_type: str
    period_start: date
    period_end: date
    roots: tuple[PlanningTaskNode, ...]
    total_tasks: int


def _flatten_task(task: Task | TaskView) -> PlanningTaskFlat:
    """Copy the planning-relevant task fields into one plain row."""
    return PlanningTaskFlat(
        id=task.id,
        vision_id=task.vision_id,
        parent_task_id=task.parent_task_id,
        content=task.content,
        status=task.status,
        estimated_effort=task.estimated_effort,
        planning_cycle_start_date=task.planning_cycle_start_date,
        planning_cycle_days=task.planning_cycle_days,
        display_order=task.display_order,
        created_at=task.created_at,
    )


def _task_sort_key(task: PlanningTaskFlat) -> tuple[int, datetime, UUID]:
    """Order tasks like ``task list``: display order, then creation order."""
    return (task.display_order, task.created_at, task.id)


def build_planning_forest(
    tasks: tuple[PlanningTaskFlat, ...],
    *,
    context_parents: tuple[PlanningTaskFlat, ...] = (),
    max_depth: int | None = None,
) -> tuple[PlanningTaskNode, ...]:
    """Assemble a cross-vision forest from flat planning-window tasks.

    Tasks whose parent is inside the window are nested below it. Tasks whose
    parent is outside the window are attached below the matching collapsed
    context parent when one is supplied; otherwise they surface as roots.
    """
    task_ids = {task.id for task in tasks}
    children_by_parent: dict[UUID | None, list[PlanningTaskFlat]] = {}
    for task in sorted(tasks, key=_task_sort_key):
        children_by_parent.setdefault(task.parent_task_id, []).append(task)

    def convert(task: PlanningTaskFlat, *, depth: int) -> PlanningTaskNode:
        child_tasks = children_by_parent.get(task.id, ())
        if max_depth is not None and depth >= max_depth:
            child_tasks = ()
        return PlanningTaskNode(
            id=task.id,
            vision_id=task.vision_id,
            parent_task_id=task.parent_task_id,
            content=task.content,
            status=task.status,
            estimated_effort=task.estimated_effort,
            planning_cycle_start_date=task.planning_cycle_start_date,
            planning_cycle_days=task.planning_cycle_days,
            depth=depth,
            is_context=False,
            children=tuple(convert(child, depth=depth + 1) for child in child_tasks),
        )

    context_parent_ids = {parent.id for parent in context_parents}
    roots: list[PlanningTaskNode] = []
    for task in sorted(tasks, key=_task_sort_key):
        if task.parent_task_id is not None and task.parent_task_id in context_parent_ids:
            continue
        if task.parent_task_id is None or task.parent_task_id not in task_ids:
            roots.append(convert(task, depth=0))

    for parent in sorted(context_parents, key=_task_sort_key):
        child_tasks = children_by_parent.get(parent.id, ())
        if max_depth is not None and max_depth < 1:
            child_tasks = ()
        children = tuple(convert(child, depth=1) for child in child_tasks)
        roots.append(
            PlanningTaskNode(
                id=parent.id,
                vision_id=parent.vision_id,
                parent_task_id=parent.parent_task_id,
                content=parent.content,
                status=parent.status,
                estimated_effort=parent.estimated_effort,
                planning_cycle_start_date=parent.planning_cycle_start_date,
                planning_cycle_days=parent.planning_cycle_days,
                depth=0,
                is_context=True,
                children=children,
            )
        )

    return tuple(roots)


async def _load_context_parents(
    session: AsyncSession,
    tasks: tuple[PlanningTaskFlat, ...],
    *,
    vision_in: str | None,
) -> tuple[PlanningTaskFlat, ...]:
    """Load direct parents that fall outside the queried planning window."""
    task_ids = {task.id for task in tasks}
    missing_ids = tuple(
        dict.fromkeys(
            task.parent_task_id
            for task in tasks
            if task.parent_task_id is not None and task.parent_task_id not in task_ids
        )
    )[:MAX_CONTEXT_PARENT_FETCHES]
    if not missing_ids:
        return ()
    result = await session.execute(
        select(Task).where(
            Task.id.in_(missing_ids),
            Task.deleted_at.is_(None),
        )
    )
    allowed_visions: set[UUID] | None = None
    if vision_in is not None:
        allowed_visions = {UUID(value.strip()) for value in vision_in.split(",") if value.strip()}
    parents = tuple(
        parent
        for parent in result.scalars()
        if allowed_visions is None or parent.vision_id in allowed_visions
    )
    return tuple(sorted((_flatten_task(parent) for parent in parents), key=_task_sort_key))


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

    Calendar preferences are read from the persisted user configuration by the
    backend instead of being passed in by the caller. ``at_date`` selects the
    period containing the date; ``start_date`` anchors the period directly.
    """
    if at_date is not None and start_date is not None:
        raise ValueError("Use either --at or --start, not both.")
    calendar_preferences = get_calendar_preferences()
    anchor = start_date
    if anchor is None:
        reference_date = at_date or get_operational_date()
        anchor = get_calendar_period_range(
            cast(CalendarGranularity, cycle_type),
            reference_date,
            calendar_system=calendar_preferences.system,
            first_day_of_week=calendar_preferences.first_day_of_week,
            seven_year_anchor_date=calendar_preferences.seven_year_anchor_date,
        )[0]
    period_start, period_end = get_calendar_period_range(
        cast(CalendarGranularity, cycle_type),
        anchor,
        calendar_system=calendar_preferences.system,
        first_day_of_week=calendar_preferences.first_day_of_week,
        seven_year_anchor_date=calendar_preferences.seven_year_anchor_date,
    )
    tasks = await task_queries.list_tasks(
        session,
        planning_cycle_type=cycle_type,
        planning_cycle_start_date=anchor,
        vision_in=vision_in,
        status_in=status_in,
        limit=limit,
        offset=offset,
    )
    flat_tasks = tuple(_flatten_task(task) for task in tasks)
    context_parents = await _load_context_parents(session, flat_tasks, vision_in=vision_in)
    roots = build_planning_forest(
        flat_tasks,
        context_parents=context_parents,
        max_depth=max_depth,
    )
    return PlanningView(
        cycle_type=cycle_type,
        period_start=period_start,
        period_end=period_end,
        roots=roots,
        total_tasks=len(tasks),
    )
