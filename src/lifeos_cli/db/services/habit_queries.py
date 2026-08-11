"""Query helpers for habits and sparse habit-action occurrences."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lifeos_cli.application.time_preferences import get_operational_date
from lifeos_cli.db.models.association import Association
from lifeos_cli.db.models.habit import Habit
from lifeos_cli.db.models.habit_action import HabitAction
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.habit_support import (
    HabitActionLike,
    HabitActionNotFoundError,
    HabitNotFoundError,
    HabitValidationError,
    build_habit_stats_payload,
    get_habit_occurrence_end_date,
    habit_occurs_on_date,
    iter_habit_scheduled_dates,
    refresh_habit_expiration,
    validate_habit_action_status,
    validate_habit_status,
)
from lifeos_cli.db.services.read_models import HabitActionView
from lifeos_cli.db.sql_expressions import AddDaysToDate


def _active_habit_task_loader() -> Any:
    return selectinload(Habit.task.and_(Task.deleted_at.is_(None)))


def _apply_habit_filters(
    stmt: Any,
    *,
    status: str | None,
    title: str | None,
    active_window_only: bool,
) -> Any:
    stmt = stmt.where(Habit.deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(Habit.status == validate_habit_status(status))
    if title is not None:
        normalized_title = title.strip()
        if normalized_title:
            stmt = stmt.where(Habit.title == normalized_title)
    if active_window_only:
        local_today = get_operational_date()
        end_expr = _habit_end_expr()
        stmt = stmt.where(Habit.start_date <= local_today)
        stmt = stmt.where(end_expr >= local_today)
    return stmt


def _normalize_action_window(
    *,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date] | None:
    if start_date is None and end_date is None:
        return None
    if start_date is None or end_date is None:
        raise HabitValidationError("start_date and end_date must be provided together")
    if end_date < start_date:
        raise HabitValidationError("end_date must be on or after start_date")
    return start_date, end_date


def _habit_end_expr() -> Any:
    return AddDaysToDate(Habit.start_date, Habit.duration_days - 1)


def _build_habit_action_view(
    *,
    action_id: UUID | None,
    habit_id: UUID,
    habit_title: str,
    habit_cadence_frequency: str,
    action_date: date,
    status: str,
    notes: str | None,
    created_at: datetime | None,
    updated_at: datetime | None,
    deleted_at: datetime | None,
    linked_notes_count: int,
) -> HabitActionView:
    return HabitActionView(
        id=action_id,
        habit_id=habit_id,
        habit_title=habit_title,
        habit_cadence_frequency=habit_cadence_frequency,
        action_date=action_date,
        status=status,
        notes=notes,
        created_at=created_at,
        updated_at=updated_at,
        deleted_at=deleted_at,
        linked_notes_count=linked_notes_count,
    )


def _habit_cadence_frequency(habit: Habit) -> str:
    return str(getattr(habit, "cadence_frequency", "daily") or "daily")


async def _materialize_habit_action_for_date(
    session: AsyncSession,
    *,
    habit: Habit,
    action_date: date,
) -> HabitAction:
    """Create one materialized dated action for a scheduled occurrence."""
    if not habit_occurs_on_date(
        start_date=habit.start_date,
        end_date=get_habit_occurrence_end_date(habit),
        cadence_frequency=getattr(habit, "cadence_frequency", "daily"),
        cadence_weekdays=getattr(habit, "cadence_weekdays", None),
        cadence_monthdays=getattr(habit, "cadence_monthdays", None),
        target_date=action_date,
    ):
        raise HabitActionNotFoundError(
            f"Habit action for habit {habit.id} on {action_date} was not found"
        )
    action = HabitAction(
        habit_id=habit.id,
        action_date=action_date,
    )
    session.add(action)
    await session.flush()
    await session.refresh(action)
    return action


def _iter_habit_window_dates(
    *,
    habit: Habit,
    start_date: date,
    end_date: date,
) -> list[date]:
    effective_start = max(start_date, habit.start_date)
    occurrence_end_date = get_habit_occurrence_end_date(habit)
    effective_end = min(end_date, occurrence_end_date)
    if effective_end < effective_start:
        return []
    return iter_habit_scheduled_dates(
        start_date=effective_start,
        end_date=effective_end,
        cadence_frequency=getattr(habit, "cadence_frequency", "daily"),
        cadence_weekdays=getattr(habit, "cadence_weekdays", None),
        cadence_monthdays=getattr(habit, "cadence_monthdays", None),
    )


async def _load_materialized_actions_for_habits(
    session: AsyncSession,
    *,
    habit_ids: list[UUID],
    start_date: date | None,
    end_date: date | None,
    target_dates: tuple[date, ...] = (),
) -> list[HabitAction]:
    if not habit_ids:
        return []
    stmt = select(HabitAction).where(HabitAction.habit_id.in_(habit_ids))
    stmt = stmt.where(HabitAction.deleted_at.is_(None))
    if target_dates:
        stmt = stmt.where(HabitAction.action_date.in_(target_dates))
    elif start_date is not None:
        stmt = stmt.where(HabitAction.action_date >= start_date)
    if not target_dates and end_date is not None:
        stmt = stmt.where(HabitAction.action_date <= end_date)
    stmt = stmt.order_by(
        HabitAction.action_date.asc(),
        HabitAction.created_at.asc(),
        HabitAction.id.asc(),
    )
    return list((await session.execute(stmt)).scalars())


async def _load_note_metadata_for_actions(
    session: AsyncSession,
    *,
    action_ids: list[UUID],
) -> tuple[dict[UUID, str], dict[UUID, int]]:
    if not action_ids:
        return {}, {}
    stmt = (
        select(Association.target_id, Note.content)
        .join(Note, Note.id == Association.source_id)
        .where(
            Association.source_model == "note",
            Association.target_model == "habit_action",
            Association.target_id.in_(action_ids),
            Association.link_type == "captured_from",
            Note.deleted_at.is_(None),
        )
        .order_by(Association.created_at.asc(), Association.id.asc())
    )
    rows = await session.execute(stmt)
    grouped: dict[UUID, list[str]] = {}
    for action_id, content in rows.all():
        grouped.setdefault(action_id, []).append(content)
    return (
        {action_id: "\n\n".join(contents) for action_id, contents in grouped.items()},
        {action_id: len(contents) for action_id, contents in grouped.items()},
    )


async def _load_candidate_habits(
    session: AsyncSession,
    *,
    habit_id: UUID | None,
    action_window: tuple[date, date] | None,
    target_dates: tuple[date, ...] = (),
    cadence_frequency: str | None = None,
) -> list[Habit]:
    if habit_id is not None:
        habit = await get_habit(session, habit_id=habit_id)
        if habit is None:
            raise HabitNotFoundError(f"Habit {habit_id} was not found")
        if cadence_frequency is not None and _habit_cadence_frequency(habit) != cadence_frequency:
            return []
        return [habit]

    stmt = select(Habit).options(_active_habit_task_loader())
    stmt = stmt.where(Habit.deleted_at.is_(None))
    if cadence_frequency is not None:
        stmt = stmt.where(Habit.cadence_frequency == cadence_frequency)
    if target_dates:
        habit_end_expr = _habit_end_expr()
        stmt = stmt.where(
            or_(
                *(
                    and_(Habit.start_date <= target_date, habit_end_expr >= target_date)
                    for target_date in target_dates
                )
            )
        )
    elif action_window is not None:
        start_date, end_date = action_window
        stmt = stmt.where(Habit.start_date <= end_date, _habit_end_expr() >= start_date)
    stmt = stmt.order_by(Habit.created_at.desc(), Habit.id.desc())
    return list((await session.execute(stmt)).scalars())


def _build_habit_action_views_for_occurrence_dates(
    *,
    habit: Habit,
    materialized_actions: list[HabitAction],
    occurrence_dates: list[date],
) -> list[HabitActionView]:
    active_actions_by_date = {
        action.action_date: action for action in materialized_actions if action.deleted_at is None
    }
    views: list[HabitActionView] = []

    for action_date in occurrence_dates:
        materialized = active_actions_by_date.get(action_date)
        if materialized is None:
            views.append(
                _build_habit_action_view(
                    action_id=None,
                    habit_id=habit.id,
                    habit_title=habit.title,
                    habit_cadence_frequency=_habit_cadence_frequency(habit),
                    action_date=action_date,
                    status="pending",
                    notes=None,
                    created_at=None,
                    updated_at=None,
                    deleted_at=None,
                    linked_notes_count=0,
                )
            )
            continue
        views.append(
            _build_habit_action_view(
                action_id=materialized.id,
                habit_id=materialized.habit_id,
                habit_title=habit.title,
                habit_cadence_frequency=_habit_cadence_frequency(habit),
                action_date=materialized.action_date,
                status=materialized.status,
                notes=getattr(materialized, "notes", None),
                created_at=materialized.created_at,
                updated_at=materialized.updated_at,
                deleted_at=materialized.deleted_at,
                linked_notes_count=getattr(materialized, "linked_notes_count", 0),
            )
        )

    return views


async def build_habit_action_views(
    session: AsyncSession,
    *,
    habit_id: UUID | None,
    status: str | None,
    action_window: tuple[date, date] | None,
    target_dates: tuple[date, ...] = (),
    cadence_frequency: str | None = None,
) -> list[HabitActionView]:
    """Build sparse habit-action occurrence views without mutating status."""
    normalized_target_dates = tuple(deduplicate_preserving_order(target_dates))
    habits = await _load_candidate_habits(
        session,
        habit_id=habit_id,
        action_window=action_window,
        target_dates=normalized_target_dates,
        cadence_frequency=cadence_frequency,
    )
    if not habits:
        return []

    habit_ids = [habit.id for habit in habits]
    if normalized_target_dates:
        range_start = None
        range_end = None
    elif action_window is None:
        range_start = min(habit.start_date for habit in habits)
        range_end = max(habit.end_date for habit in habits)
    else:
        range_start, range_end = action_window

    materialized_actions = await _load_materialized_actions_for_habits(
        session,
        habit_ids=habit_ids,
        start_date=range_start,
        end_date=range_end,
        target_dates=normalized_target_dates,
    )
    note_content_by_action, note_count_by_action = await _load_note_metadata_for_actions(
        session,
        action_ids=[action.id for action in materialized_actions],
    )
    actions_by_habit: dict[UUID, list[HabitAction]] = {habit_id: [] for habit_id in habit_ids}
    for action in materialized_actions:
        action.__dict__["notes"] = note_content_by_action.get(action.id)
        action.__dict__["linked_notes_count"] = note_count_by_action.get(action.id, 0)
        actions_by_habit.setdefault(action.habit_id, []).append(action)

    views: list[HabitActionView] = []
    for habit in habits:
        if normalized_target_dates:
            occurrence_dates = [
                target_date
                for target_date in normalized_target_dates
                if habit_occurs_on_date(
                    start_date=habit.start_date,
                    end_date=get_habit_occurrence_end_date(habit),
                    cadence_frequency=getattr(habit, "cadence_frequency", "daily"),
                    cadence_weekdays=getattr(habit, "cadence_weekdays", None),
                    cadence_monthdays=getattr(habit, "cadence_monthdays", None),
                    target_date=target_date,
                )
            ]
            views.extend(
                _build_habit_action_views_for_occurrence_dates(
                    habit=habit,
                    materialized_actions=actions_by_habit.get(habit.id, []),
                    occurrence_dates=occurrence_dates,
                )
            )
            continue
        assert range_start is not None
        assert range_end is not None
        habit_start = range_start if action_window is None else action_window[0]
        habit_end = range_end if action_window is None else action_window[1]
        views.extend(
            _build_habit_action_views_for_occurrence_dates(
                habit=habit,
                materialized_actions=actions_by_habit.get(habit.id, []),
                occurrence_dates=_iter_habit_window_dates(
                    habit=habit,
                    start_date=habit_start,
                    end_date=habit_end,
                ),
            )
        )
    if status is not None:
        normalized_status = validate_habit_action_status(status)
        views = [view for view in views if view.status == normalized_status]
    return sorted(
        views,
        key=lambda view: (
            view.action_date,
            view.habit_title,
            view.habit_id,
            view.id is None,
            str(view.id or view.habit_id),
        ),
    )


async def get_habit(
    session: AsyncSession,
    *,
    habit_id: UUID,
) -> Habit | None:
    """Load a habit by identifier."""
    await refresh_habit_expiration(session, habit_id=habit_id)
    stmt = select(Habit).where(Habit.id == habit_id).options(_active_habit_task_loader()).limit(1)
    stmt = stmt.where(Habit.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_habits(
    session: AsyncSession,
    *,
    status: str | None = None,
    title: str | None = None,
    active_window_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[Habit]:
    """List habits with optional status and title filters."""
    await refresh_habit_expiration(session)
    stmt = select(Habit).options(_active_habit_task_loader())
    stmt = _apply_habit_filters(
        stmt,
        status=status,
        title=title,
        active_window_only=active_window_only,
    )
    stmt = stmt.order_by(Habit.created_at.desc(), Habit.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars())


async def count_habits(
    session: AsyncSession,
    *,
    status: str | None = None,
    title: str | None = None,
    active_window_only: bool = False,
) -> int:
    """Count habits with the same filters used by list_habits."""
    await refresh_habit_expiration(session)
    stmt = select(func.count()).select_from(Habit)
    stmt = _apply_habit_filters(
        stmt,
        status=status,
        title=title,
        active_window_only=active_window_only,
    )
    return int((await session.execute(stmt)).scalar_one())


async def get_habit_stats(session: AsyncSession, *, habit_id: UUID) -> dict[str, object]:
    """Return statistics for one habit."""
    habit = await get_habit(session, habit_id=habit_id)
    if habit is None:
        raise HabitNotFoundError(f"Habit {habit_id} was not found")
    actions = await build_habit_action_views(
        session,
        habit_id=habit.id,
        status=None,
        action_window=None,
    )
    return build_habit_stats_payload(habit, cast(list[HabitActionLike], actions))


async def get_habit_overview(
    session: AsyncSession,
    *,
    habit_id: UUID,
) -> dict[str, object]:
    """Return a habit plus its derived statistics."""
    habit = await get_habit(session, habit_id=habit_id)
    if habit is None:
        raise HabitNotFoundError(f"Habit {habit_id} was not found")
    actions = await build_habit_action_views(
        session,
        habit_id=habit.id,
        status=None,
        action_window=None,
    )
    return {
        "habit": habit,
        "stats": build_habit_stats_payload(habit, cast(list[HabitActionLike], actions)),
    }


async def list_habit_overviews(
    session: AsyncSession,
    *,
    status: str | None = None,
    title: str | None = None,
    active_window_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, object]]:
    """Return habits with derived statistics."""
    habits = await list_habits(
        session,
        status=status,
        title=title,
        active_window_only=active_window_only,
        limit=limit,
        offset=offset,
    )
    if not habits:
        return []
    overviews: list[dict[str, object]] = []
    for habit in habits:
        actions = await build_habit_action_views(
            session,
            habit_id=habit.id,
            status=None,
            action_window=None,
        )
        overviews.append(
            {
                "habit": habit,
                "stats": build_habit_stats_payload(habit, cast(list[HabitActionLike], actions)),
            }
        )
    return overviews


async def get_habit_task_associations(session: AsyncSession) -> dict[UUID, list[Habit]]:
    """Return task-to-habits mappings for non-deleted habits and tasks."""
    await refresh_habit_expiration(session)
    stmt = (
        select(Habit)
        .join(Task, Habit.task_id == Task.id)
        .where(
            Habit.deleted_at.is_(None),
            Habit.task_id.is_not(None),
            Task.deleted_at.is_(None),
        )
        .options(_active_habit_task_loader())
        .order_by(Habit.created_at.desc())
    )
    habits = list((await session.execute(stmt)).scalars())
    associations: dict[UUID, list[Habit]] = {}
    for habit in habits:
        if habit.task_id is None:
            continue
        associations.setdefault(habit.task_id, []).append(habit)
    return associations


async def list_habit_actions(
    session: AsyncSession,
    *,
    habit_id: UUID | None = None,
    status: str | None = None,
    cadence_frequency: str | None = None,
    date_values: tuple[date, ...] = (),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[HabitActionView]:
    """List habit-action occurrence views with optional filters."""
    await refresh_habit_expiration(session)
    target_dates = tuple(deduplicate_preserving_order(date_values))
    action_window = (
        None if target_dates else _normalize_action_window(start_date=start_date, end_date=end_date)
    )
    views = await build_habit_action_views(
        session,
        habit_id=habit_id,
        status=status,
        action_window=action_window,
        target_dates=target_dates,
        cadence_frequency=cadence_frequency,
    )
    paged_views = views[offset : offset + limit]
    synthetic_views = [view for view in paged_views if view.id is None]
    if not synthetic_views:
        return paged_views

    habit_ids = {view.habit_id for view in synthetic_views}
    habits = list(
        (
            await session.execute(
                select(Habit).where(Habit.id.in_(habit_ids), Habit.deleted_at.is_(None))
            )
        ).scalars()
    )
    habits_by_id = {habit.id: habit for habit in habits}
    materialized_by_key: dict[tuple[UUID, date], HabitActionView] = {}
    for view in synthetic_views:
        habit = habits_by_id.get(view.habit_id)
        if habit is None:
            continue
        action = await _materialize_habit_action_for_date(
            session,
            habit=habit,
            action_date=view.action_date,
        )
        materialized_by_key[(view.habit_id, view.action_date)] = _build_habit_action_view(
            action_id=action.id,
            habit_id=action.habit_id,
            habit_title=habit.title,
            habit_cadence_frequency=_habit_cadence_frequency(habit),
            action_date=action.action_date,
            status=action.status,
            notes=getattr(action, "notes", None),
            created_at=action.created_at,
            updated_at=action.updated_at,
            deleted_at=action.deleted_at,
            linked_notes_count=0,
        )

    return [
        materialized_by_key.get((view.habit_id, view.action_date), view) for view in paged_views
    ]


async def list_habit_actions_in_range(
    session: AsyncSession,
    *,
    start_date: date,
    end_date: date,
) -> list[HabitActionView]:
    """List habit-action occurrence views for an explicit inclusive date range."""
    if end_date < start_date:
        raise HabitValidationError("end_date must be on or after start_date")
    views = await build_habit_action_views(
        session,
        habit_id=None,
        status=None,
        action_window=(start_date, end_date),
    )
    return [view for view in views if start_date <= view.action_date <= end_date]


async def count_habit_actions(
    session: AsyncSession,
    *,
    habit_id: UUID | None = None,
    status: str | None = None,
    cadence_frequency: str | None = None,
    date_values: tuple[date, ...] = (),
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """Count habit-action occurrence views with the same filters used by list_habit_actions."""
    await refresh_habit_expiration(session)
    target_dates = tuple(deduplicate_preserving_order(date_values))
    action_window = (
        None if target_dates else _normalize_action_window(start_date=start_date, end_date=end_date)
    )
    views = await build_habit_action_views(
        session,
        habit_id=habit_id,
        status=status,
        action_window=action_window,
        target_dates=target_dates,
        cadence_frequency=cadence_frequency,
    )
    return len(views)


async def get_habit_action(
    session: AsyncSession,
    *,
    action_id: UUID,
) -> HabitAction | None:
    """Load one materialized habit action with its parent habit."""
    stmt = (
        select(HabitAction)
        .where(HabitAction.id == action_id)
        .options(selectinload(HabitAction.habit.and_(Habit.deleted_at.is_(None))))
        .limit(1)
    )
    stmt = stmt.where(
        HabitAction.deleted_at.is_(None),
        HabitAction.habit.has(Habit.deleted_at.is_(None)),
    )
    action = (await session.execute(stmt)).scalar_one_or_none()
    if action is None:
        return None
    note_content_by_action, note_count_by_action = await _load_note_metadata_for_actions(
        session,
        action_ids=[action.id],
    )
    action.__dict__["notes"] = note_content_by_action.get(action.id)
    action.__dict__["linked_notes_count"] = note_count_by_action.get(action.id, 0)
    return action
