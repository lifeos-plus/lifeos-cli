"""Read-side helpers for CLI schedule views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.time_preferences import (
    get_operational_date,
    get_utc_window_for_local_date,
    get_utc_window_for_local_date_range,
)
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.services.event_support import EventOccurrenceQuery
from lifeos_cli.db.services.events import EventOccurrence, list_event_occurrences
from lifeos_cli.db.services.habit_actions import list_habit_actions_in_range
from lifeos_cli.db.services.task_support import planning_cycle_end_date
from lifeos_cli.db.sql_expressions import AddDaysToDate


@dataclass(frozen=True)
class ScheduleTaskItem:
    """Task item included in a schedule day."""

    id: UUID
    content: str
    status: str
    planning_cycle_type: str
    planning_cycle_days: int
    planning_cycle_start_date: date
    planning_cycle_end_date: date


@dataclass(frozen=True)
class ScheduleHabitActionItem:
    """Habit-action item included in a schedule day."""

    id: UUID | None
    habit_id: UUID
    habit_title: str
    action_date: date
    status: str
    notes: str | None


@dataclass(frozen=True)
class ScheduleEventItem:
    """Event item included in a schedule day."""

    id: UUID
    title: str
    status: str
    event_type: str
    start_time: datetime
    end_time: datetime | None
    task_id: UUID | None


@dataclass(frozen=True)
class ScheduleDay:
    """Aggregated schedule view for one local date."""

    local_date: date
    tasks: tuple[ScheduleTaskItem, ...]
    habit_actions: tuple[ScheduleHabitActionItem, ...]
    events: tuple[ScheduleEventItem, ...]


def _iter_date_range(start_date: date, end_date: date) -> list[date]:
    day_count = (end_date - start_date).days + 1
    return [start_date + timedelta(days=offset) for offset in range(day_count)]


def _normalize_schedule_range(*, start_date: date, end_date: date) -> tuple[date, date]:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    return start_date, end_date


def _task_cycle_end_date(task: Task) -> date:
    planning_cycle_start_date = task.planning_cycle_start_date
    planning_cycle_days = task.planning_cycle_days
    if planning_cycle_start_date is None or planning_cycle_days is None:
        raise ValueError("Scheduled tasks must include planning cycle start date and days.")
    return planning_cycle_end_date(planning_cycle_start_date, planning_cycle_days)


async def _load_schedule_tasks(
    session: AsyncSession,
    *,
    start_date: date,
    end_date: date,
) -> list[Task]:
    stmt = (
        select(Task)
        .where(
            Task.deleted_at.is_(None),
            Task.planning_cycle_start_date.is_not(None),
            Task.planning_cycle_days.is_not(None),
            Task.planning_cycle_type.is_not(None),
            Task.planning_cycle_start_date <= end_date,
            AddDaysToDate(Task.planning_cycle_start_date, Task.planning_cycle_days - 1)
            >= start_date,
        )
        .order_by(Task.planning_cycle_start_date.asc(), Task.display_order.asc(), Task.id.asc())
    )
    return list((await session.execute(stmt)).scalars())


async def _load_schedule_events(
    session: AsyncSession,
    *,
    start_date: date,
    end_date: date,
) -> list[EventOccurrence]:
    range_window_start, range_window_end = get_utc_window_for_local_date_range(
        start_date,
        end_date,
    )
    return await list_event_occurrences(
        session,
        query=EventOccurrenceQuery(
            window_start=range_window_start,
            window_end=range_window_end,
        ),
    )


def _map_task_item(task: Task) -> ScheduleTaskItem:
    planning_cycle_type = task.planning_cycle_type
    planning_cycle_days = task.planning_cycle_days
    planning_cycle_start_date = task.planning_cycle_start_date
    if (
        planning_cycle_type is None
        or planning_cycle_days is None
        or planning_cycle_start_date is None
    ):
        raise ValueError("Scheduled tasks must include complete planning cycle fields.")
    return ScheduleTaskItem(
        id=task.id,
        content=task.content,
        status=task.status,
        planning_cycle_type=planning_cycle_type,
        planning_cycle_days=planning_cycle_days,
        planning_cycle_start_date=planning_cycle_start_date,
        planning_cycle_end_date=_task_cycle_end_date(task),
    )


def _is_overdue_unfinished_task(item: ScheduleTaskItem, *, local_today: date) -> bool:
    return item.status not in {"cancelled", "done"} and item.planning_cycle_end_date < local_today


def _is_overdue_unfinished_habit_action(
    item: ScheduleHabitActionItem,
    *,
    local_today: date,
) -> bool:
    return item.status == "pending" and item.action_date < local_today


async def list_schedule_in_range(
    session: AsyncSession,
    *,
    start_date: date,
    end_date: date,
    hide_overdue_unfinished: bool = False,
) -> list[ScheduleDay]:
    """Return a grouped schedule view for one local-date range."""
    start_date, end_date = _normalize_schedule_range(start_date=start_date, end_date=end_date)
    dates = _iter_date_range(start_date, end_date)
    local_today = get_operational_date()
    query_start_date = start_date if hide_overdue_unfinished else date.min
    tasks = await _load_schedule_tasks(session, start_date=query_start_date, end_date=end_date)
    habit_actions = await list_habit_actions_in_range(
        session,
        start_date=query_start_date,
        end_date=end_date,
    )
    events = await _load_schedule_events(session, start_date=start_date, end_date=end_date)

    task_items = [_map_task_item(task) for task in tasks]
    action_items = [
        ScheduleHabitActionItem(
            id=action.id,
            habit_id=action.habit_id,
            habit_title=action.habit_title,
            action_date=action.action_date,
            status=action.status,
            notes=getattr(action, "notes", None),
        )
        for action in habit_actions
    ]
    event_items = [
        ScheduleEventItem(
            id=event.id,
            title=event.title,
            status=event.status,
            event_type=event.event_type,
            start_time=event.start_time,
            end_time=event.end_time,
            task_id=event.task_id,
        )
        for event in events
    ]

    days: list[ScheduleDay] = []
    for current_date in dates:
        current_tasks = tuple(
            item
            for item in task_items
            if item.planning_cycle_start_date <= current_date <= item.planning_cycle_end_date
            or (
                current_date <= local_today
                and item.planning_cycle_end_date < current_date
                and item.status not in {"cancelled", "done"}
            )
        )
        current_actions = tuple(
            item
            for item in action_items
            if item.action_date == current_date
            or (
                current_date <= local_today
                and item.action_date < current_date
                and item.status == "pending"
            )
        )
        if hide_overdue_unfinished:
            current_tasks = tuple(
                item
                for item in current_tasks
                if not _is_overdue_unfinished_task(item, local_today=local_today)
            )
            current_actions = tuple(
                item
                for item in current_actions
                if not _is_overdue_unfinished_habit_action(item, local_today=local_today)
            )
        (
            current_window_start,
            current_window_end_exclusive,
        ) = get_utc_window_for_local_date(current_date)
        current_window_end = current_window_end_exclusive - timedelta(microseconds=1)
        current_events = tuple(
            item
            for item in event_items
            if item.status != "completed"
            and item.start_time <= current_window_end
            and (item.end_time is None or item.end_time >= current_window_start)
        )
        days.append(
            ScheduleDay(
                local_date=current_date,
                tasks=current_tasks,
                habit_actions=current_actions,
                events=current_events,
            )
        )
    return days


async def get_schedule_for_date(
    session: AsyncSession,
    *,
    target_date: date,
    hide_overdue_unfinished: bool = False,
) -> ScheduleDay:
    """Return a grouped schedule view for one local date."""
    return (
        await list_schedule_in_range(
            session,
            start_date=target_date,
            end_date=target_date,
            hide_overdue_unfinished=hide_overdue_unfinished,
        )
    )[0]
