"""Mutation helpers for habits and habit actions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.time_preferences import get_operational_date
from lifeos_cli.db.base import utc_now
from lifeos_cli.db.models.association import Association
from lifeos_cli.db.models.habit import Habit
from lifeos_cli.db.models.habit_action import HabitAction
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.services.batching import BatchDeleteResult, batch_delete_records
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.habit_queries import (
    _materialize_habit_action_for_date,
    get_habit,
    get_habit_action,
    get_habit_action_model,
)
from lifeos_cli.db.services.habit_support import (
    HABIT_EDITABLE_DAYS,
    HabitActionNotFoundError,
    HabitNotFoundError,
    HabitValidationError,
    InvalidHabitOperationError,
    calculate_habit_duration_for_repeat_count,
    ensure_active_capacity,
    ensure_task_exists,
    get_habit_occurrence_end_date,
    habit_occurs_on_date,
    refresh_habit_expiration,
    validate_habit_action_status,
    validate_habit_cadence,
    validate_habit_duration,
    validate_habit_end_date,
    validate_habit_schedule_window,
    validate_habit_start_date,
    validate_habit_status,
)
from lifeos_cli.db.services.read_models import HabitActionView


async def create_habit(
    session: AsyncSession,
    *,
    title: str,
    description: str | None = None,
    start_date: date,
    duration_days: int | None = None,
    end_date: date | None = None,
    repeat_count: int | None = None,
    cadence_frequency: str | None = None,
    cadence_weekdays: Sequence[str] | None = None,
    cadence_monthdays: Sequence[object] | None = None,
    target_per_cycle: int | None = None,
    task_id: UUID | None = None,
) -> Habit:
    """Create a new habit without pre-generating dated action rows."""
    normalized_title = title.strip()
    validate_habit_start_date(start_date)
    (
        normalized_cadence_frequency,
        normalized_cadence_weekdays,
        normalized_cadence_monthdays,
        normalized_target_per_cycle,
    ) = validate_habit_cadence(
        cadence_frequency=cadence_frequency,
        cadence_weekdays=cadence_weekdays,
        cadence_monthdays=cadence_monthdays,
        target_per_cycle=target_per_cycle,
    )
    normalized_duration_days = _resolve_habit_duration_days(
        start_date=start_date,
        duration_days=duration_days,
        end_date=end_date,
        repeat_count=repeat_count,
        cadence_frequency=normalized_cadence_frequency,
        cadence_weekdays=normalized_cadence_weekdays,
        cadence_monthdays=normalized_cadence_monthdays,
    )
    await ensure_active_capacity(session)
    await ensure_task_exists(session, task_id)
    habit = Habit(
        title=normalized_title,
        description=description,
        start_date=start_date,
        duration_days=normalized_duration_days,
        cadence_frequency=normalized_cadence_frequency,
        cadence_weekdays=(
            None if normalized_cadence_weekdays is None else list(normalized_cadence_weekdays)
        ),
        cadence_monthdays=(
            None if normalized_cadence_monthdays is None else list(normalized_cadence_monthdays)
        ),
        target_per_cycle=normalized_target_per_cycle,
        status="active",
        status_changed_date=start_date,
        task_id=task_id,
    )
    session.add(habit)
    await session.flush()
    validate_habit_schedule_window(
        start_date=habit.start_date,
        end_date=habit.end_date,
        cadence_frequency=habit.cadence_frequency,
        cadence_weekdays=habit.cadence_weekdays,
        cadence_monthdays=habit.cadence_monthdays,
    )
    await refresh_habit_expiration(session, habit_id=habit.id)
    await session.refresh(habit)
    return habit


async def update_habit(
    session: AsyncSession,
    *,
    habit_id: UUID,
    title: str | None = None,
    description: str | None = None,
    clear_description: bool = False,
    start_date: date | None = None,
    duration_days: int | None = None,
    end_date: date | None = None,
    repeat_count: int | None = None,
    cadence_frequency: str | None = None,
    cadence_weekdays: Sequence[str] | None = None,
    clear_weekdays: bool = False,
    cadence_monthdays: Sequence[object] | None = None,
    clear_monthdays: bool = False,
    target_per_cycle: int | None = None,
    status: str | None = None,
    task_id: UUID | None = None,
    clear_task: bool = False,
) -> Habit:
    """Update a habit and reconcile materialized dated actions."""
    habit = await get_habit(session, habit_id=habit_id)
    if habit is None:
        raise HabitNotFoundError(f"Habit {habit_id} was not found")

    schedule_changed = False

    if title is not None:
        habit.title = title.strip()
    if clear_description:
        habit.description = None
    elif description is not None:
        habit.description = description
    if start_date is not None:
        validate_habit_start_date(start_date)
        habit.start_date = start_date
        schedule_changed = True
    if clear_weekdays:
        next_cadence_weekdays: Sequence[str] | None = None
    elif cadence_weekdays is not None:
        next_cadence_weekdays = cadence_weekdays
    else:
        next_cadence_weekdays = getattr(habit, "cadence_weekdays", None)
    if clear_monthdays:
        next_cadence_monthdays: Sequence[object] | None = None
    elif cadence_monthdays is not None:
        next_cadence_monthdays = cadence_monthdays
    else:
        next_cadence_monthdays = getattr(habit, "cadence_monthdays", None)
    if (
        cadence_frequency is not None
        or cadence_weekdays is not None
        or clear_weekdays
        or cadence_monthdays is not None
        or clear_monthdays
        or target_per_cycle is not None
    ):
        (
            normalized_cadence_frequency,
            normalized_cadence_weekdays,
            normalized_cadence_monthdays,
            normalized_target_per_cycle,
        ) = validate_habit_cadence(
            cadence_frequency=cadence_frequency or getattr(habit, "cadence_frequency", None),
            cadence_weekdays=next_cadence_weekdays,
            cadence_monthdays=next_cadence_monthdays,
            target_per_cycle=(
                target_per_cycle
                if target_per_cycle is not None
                else getattr(habit, "target_per_cycle", None)
            ),
        )
        habit.cadence_frequency = normalized_cadence_frequency
        habit.cadence_weekdays = (
            None if normalized_cadence_weekdays is None else list(normalized_cadence_weekdays)
        )
        habit.cadence_monthdays = (
            None if normalized_cadence_monthdays is None else list(normalized_cadence_monthdays)
        )
        habit.target_per_cycle = normalized_target_per_cycle
        schedule_changed = True
    if duration_days is not None or end_date is not None or repeat_count is not None:
        habit.duration_days = _resolve_habit_duration_days(
            start_date=habit.start_date,
            duration_days=duration_days,
            end_date=end_date,
            repeat_count=repeat_count,
            cadence_frequency=habit.cadence_frequency,
            cadence_weekdays=habit.cadence_weekdays,
            cadence_monthdays=habit.cadence_monthdays,
        )
        schedule_changed = True
    if clear_task:
        habit.task_id = None
    elif task_id is not None:
        await ensure_task_exists(session, task_id)
        habit.task_id = task_id
    if status is not None:
        normalized_status = validate_habit_status(status)
        if normalized_status == "active" and habit.status != "active":
            await ensure_active_capacity(session, exclude_habit_id=habit.id)
        if normalized_status != habit.status:
            habit.status_changed_date = get_operational_date()
        habit.status = normalized_status

    if schedule_changed:
        validate_habit_schedule_window(
            start_date=habit.start_date,
            end_date=habit.end_date,
            cadence_frequency=habit.cadence_frequency,
            cadence_weekdays=habit.cadence_weekdays,
            cadence_monthdays=habit.cadence_monthdays,
        )
        await _soft_delete_unscheduled_habit_actions(session, habit)

    await session.flush()
    await refresh_habit_expiration(session, habit_id=habit.id)
    await session.refresh(habit)
    return habit


async def delete_habit(session: AsyncSession, *, habit_id: UUID) -> None:
    """Soft-delete a habit."""
    habit = await get_habit(session, habit_id=habit_id)
    if habit is None:
        raise HabitNotFoundError(f"Habit {habit_id} was not found")
    habit.soft_delete()
    await session.flush()


async def batch_delete_habits(
    session: AsyncSession,
    *,
    habit_ids: list[UUID],
) -> BatchDeleteResult:
    """Soft-delete multiple habits."""
    return await batch_delete_records(
        identifiers=deduplicate_preserving_order(habit_ids),
        delete_record=lambda habit_id: delete_habit(session, habit_id=habit_id),
        handled_exceptions=(HabitNotFoundError,),
    )


async def update_habit_action(
    session: AsyncSession,
    *,
    action_id: UUID,
    status: str | None = None,
    notes: str | None = None,
    clear_notes: bool = False,
) -> HabitActionView:
    """Update one habit action within the editable window."""
    action = await get_habit_action_model(session, action_id=action_id)
    if action is None:
        raise HabitActionNotFoundError(f"Habit action {action_id} was not found")
    today = get_operational_date()
    if action.action_date > today or (today - action.action_date).days > HABIT_EDITABLE_DAYS:
        raise InvalidHabitOperationError(
            "Habit action cannot be modified outside the allowed time window"
        )
    if status is not None:
        action.status = validate_habit_action_status(status)
    if clear_notes:
        await _clear_habit_action_note_links(session, action_id=action.id)
    elif notes is not None:
        normalized_notes = _validate_habit_action_note_content(notes)
        await _upsert_habit_action_note(
            session,
            action_id=action.id,
            content=normalized_notes,
        )
    await session.flush()
    updated = await get_habit_action(session, action_id=action.id)
    if updated is None:
        raise HabitActionNotFoundError(f"Habit action {action_id} was not found")
    return updated


async def update_habit_action_by_date(
    session: AsyncSession,
    *,
    habit_id: UUID,
    action_date: date,
    status: str | None = None,
    notes: str | None = None,
    clear_notes: bool = False,
) -> HabitActionView:
    """Update one habit action by habit and action date, materializing it if needed."""
    habit = await get_habit(session, habit_id=habit_id)
    if habit is None:
        raise HabitNotFoundError(f"Habit {habit_id} was not found")
    if not habit_occurs_on_date(
        start_date=habit.start_date,
        end_date=get_habit_occurrence_end_date(habit),
        cadence_frequency=habit.cadence_frequency,
        cadence_weekdays=habit.cadence_weekdays,
        cadence_monthdays=habit.cadence_monthdays,
        target_date=action_date,
    ):
        raise HabitActionNotFoundError(
            f"Habit action for habit {habit.id} on {action_date} was not found"
        )
    action = (
        await session.execute(
            select(HabitAction).where(
                HabitAction.habit_id == habit_id,
                HabitAction.action_date == action_date,
                HabitAction.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if action is None:
        action = await _materialize_habit_action_for_date(
            session,
            habit=habit,
            action_date=action_date,
        )
    return await update_habit_action(
        session,
        action_id=action.id,
        status=status,
        notes=notes,
        clear_notes=clear_notes,
    )


async def delete_habit_action(
    session: AsyncSession,
    *,
    action_id: UUID,
) -> None:
    """Soft-delete one habit action within the editable window."""
    action = await get_habit_action_model(session, action_id=action_id)
    if action is None:
        raise HabitActionNotFoundError(f"Habit action {action_id} was not found")
    today = get_operational_date()
    if action.action_date > today or (today - action.action_date).days > HABIT_EDITABLE_DAYS:
        raise InvalidHabitOperationError(
            "Habit action cannot be modified outside the allowed time window"
        )
    await _clear_habit_action_note_links(session, action_id=action.id)
    action.soft_delete()
    await session.flush()


async def batch_delete_habit_actions(
    session: AsyncSession,
    *,
    action_ids: list[UUID],
) -> BatchDeleteResult:
    """Soft-delete multiple habit actions."""
    return await batch_delete_records(
        identifiers=deduplicate_preserving_order(action_ids),
        delete_record=lambda action_id: delete_habit_action(session, action_id=action_id),
        handled_exceptions=(HabitActionNotFoundError,),
    )


async def _soft_delete_unscheduled_habit_actions(session: AsyncSession, habit: Habit) -> None:
    """Soft-delete materialized action rows that no longer belong to the habit schedule."""
    existing_actions = await _load_active_actions(session, habit)
    for action in existing_actions:
        if not habit_occurs_on_date(
            start_date=habit.start_date,
            end_date=get_habit_occurrence_end_date(habit),
            cadence_frequency=habit.cadence_frequency,
            cadence_weekdays=habit.cadence_weekdays,
            cadence_monthdays=habit.cadence_monthdays,
            target_date=action.action_date,
        ):
            action.deleted_at = utc_now()
    await session.flush()


async def _load_active_actions(session: AsyncSession, habit: Habit) -> list[HabitAction]:
    stmt = select(HabitAction).where(
        HabitAction.habit_id == habit.id,
        HabitAction.deleted_at.is_(None),
    )
    return list((await session.execute(stmt)).scalars())


def _validate_habit_action_note_content(content: str) -> str:
    if not content.strip():
        raise HabitValidationError("Habit action notes must not be empty.")
    return content


async def _load_habit_action_note_models(
    session: AsyncSession,
    *,
    action_id: UUID,
) -> list[Note]:
    stmt = (
        select(Note)
        .join(Association, Association.source_id == Note.id)
        .where(
            Association.source_model == "note",
            Association.target_model == "habit_action",
            Association.target_id == action_id,
            Association.link_type == "captured_from",
            Note.deleted_at.is_(None),
        )
        .order_by(Association.created_at.asc(), Association.id.asc())
    )
    return list((await session.execute(stmt)).scalars())


async def _upsert_habit_action_note(
    session: AsyncSession,
    *,
    action_id: UUID,
    content: str,
) -> None:
    existing_notes = await _load_habit_action_note_models(session, action_id=action_id)
    if existing_notes:
        existing_notes[0].content = content
        return

    note = Note(content=content)
    session.add(note)
    await session.flush()
    session.add(
        Association(
            source_model="note",
            source_id=note.id,
            target_model="habit_action",
            target_id=action_id,
            link_type="captured_from",
        )
    )


async def _clear_habit_action_note_links(
    session: AsyncSession,
    *,
    action_id: UUID,
) -> None:
    await session.execute(
        delete(Association).where(
            Association.source_model == "note",
            Association.target_model == "habit_action",
            Association.target_id == action_id,
            Association.link_type == "captured_from",
        )
    )


def _resolve_habit_duration_days(
    *,
    start_date: date,
    duration_days: int | None,
    end_date: date | None,
    repeat_count: int | None,
    cadence_frequency: str,
    cadence_weekdays: Sequence[str] | None,
    cadence_monthdays: Sequence[object] | None,
) -> int:
    provided_modes = [
        duration_days is not None,
        end_date is not None,
        repeat_count is not None,
    ]
    if sum(provided_modes) != 1:
        raise HabitValidationError(
            "Provide exactly one of duration_days, end_date, or repeat_count."
        )
    if duration_days is not None:
        return validate_habit_duration(duration_days)
    if end_date is not None:
        return validate_habit_end_date(start_date=start_date, end_date=end_date)
    assert repeat_count is not None
    return calculate_habit_duration_for_repeat_count(
        start_date=start_date,
        repeat_count=repeat_count,
        cadence_frequency=cadence_frequency,
        cadence_weekdays=cadence_weekdays,
        cadence_monthdays=cadence_monthdays,
    )
