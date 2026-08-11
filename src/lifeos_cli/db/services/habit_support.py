"""Support constants and helpers for habit services."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.calendar_adapter import CalendarGranularity, get_calendar_period_range
from lifeos_cli.application.time_preferences import (
    get_day_start_datetime,
    get_operational_date,
    get_week_bounds,
)
from lifeos_cli.config import get_preferences_settings
from lifeos_cli.db.base import utc_now
from lifeos_cli.db.services.recurrence_core import (
    VALID_WEEKDAY_NAMES,
    RecurrenceValidationError,
    SeriesDefinition,
    build_series_definition,
    get_cycle_date_bounds,
    normalize_month_days,
    normalize_recurrence_frequency,
    normalize_weekday_names,
)
from lifeos_cli.db.sql_expressions import AddDaysToDate

if TYPE_CHECKING:
    from lifeos_cli.db.models.habit import Habit

VALID_HABIT_STATUSES = {"active", "completed", "paused", "expired"}
CADENCE_TO_CALENDAR_GRANULARITY: dict[str, CalendarGranularity] = {
    "weekly": "week",
    "monthly": "month",
    "yearly": "year",
}
HABIT_ACTION_STATUS_CONFIG = {
    "pending": {
        "display_name": "Pending",
        "default_for_new": True,
        "manual_status": False,
        "count_as_completed": False,
    },
    "done": {
        "display_name": "Done",
        "default_for_new": False,
        "manual_status": True,
        "count_as_completed": True,
    },
    "skip": {
        "display_name": "Skip",
        "default_for_new": False,
        "manual_status": True,
        "count_as_completed": False,
    },
    "miss": {
        "display_name": "Miss",
        "default_for_new": False,
        "manual_status": True,
        "count_as_completed": False,
    },
}
VALID_HABIT_ACTION_STATUSES = set(HABIT_ACTION_STATUS_CONFIG)
MAX_HABIT_DURATION_DAYS = 10000
WEEKEND_HABIT_WEEKDAYS = ("saturday", "sunday")
HABIT_EDITABLE_DAYS = 10000
HABIT_ACTION_AUTO_MISS_AFTER_DAYS = 3
MAX_ACTIVE_HABITS = 99
DEFAULT_HABIT_ACTION_WINDOW_DAYS = 5
MAX_HABIT_ACTION_WINDOW_DAYS = 100


class HabitNotFoundError(LookupError):
    """Raised when a habit cannot be found."""


class HabitActionNotFoundError(LookupError):
    """Raised when a habit action cannot be found."""


class HabitTaskReferenceNotFoundError(LookupError):
    """Raised when a referenced task cannot be found."""


class HabitValidationError(ValueError):
    """Raised when habit input validation fails."""


class InvalidHabitOperationError(ValueError):
    """Raised when a habit operation is not allowed."""


@dataclass(frozen=True)
class HabitCycleSummary:
    """Derived summary for one habit cadence cycle."""

    start_date: date
    end_date: date
    completed_count: int
    required_completion_count: int

    @property
    def is_complete(self) -> bool:
        """Return whether the cycle reached its completion target."""
        return self.completed_count >= self.required_completion_count


class HabitActionLike(Protocol):
    """Structural occurrence shape used by habit stats helpers."""

    action_date: date
    status: str


def get_default_habit_action_status() -> str:
    """Return the configured default status for newly generated actions."""
    for status, config in HABIT_ACTION_STATUS_CONFIG.items():
        if config["default_for_new"]:
            return status
    raise HabitValidationError("No default habit action status is configured")


def validate_habit_status(status: str) -> str:
    """Validate and normalize a habit status."""
    normalized = status.strip().lower()
    if normalized not in VALID_HABIT_STATUSES:
        allowed = ", ".join(sorted(VALID_HABIT_STATUSES))
        raise HabitValidationError(
            f"Invalid habit status {normalized!r}. Expected one of: {allowed}"
        )
    return normalized


def validate_habit_action_status(status: str) -> str:
    """Validate and normalize a habit-action status."""
    normalized = status.strip().lower()
    if normalized not in VALID_HABIT_ACTION_STATUSES:
        allowed = ", ".join(sorted(VALID_HABIT_ACTION_STATUSES))
        raise HabitValidationError(
            f"Invalid habit-action status {normalized!r}. Expected one of: {allowed}"
        )
    return normalized


def validate_habit_duration(duration_days: int) -> int:
    """Validate habit duration length."""
    if duration_days <= 0:
        raise HabitValidationError("duration_days must be greater than zero")
    if duration_days > MAX_HABIT_DURATION_DAYS:
        raise HabitValidationError(
            f"duration_days must be no greater than {MAX_HABIT_DURATION_DAYS}"
        )
    return duration_days


def validate_habit_repeat_count(repeat_count: int) -> int:
    """Validate a requested number of scheduled habit occurrences."""
    if repeat_count <= 0:
        raise HabitValidationError("repeat_count must be greater than zero")
    if repeat_count > MAX_HABIT_DURATION_DAYS:
        raise HabitValidationError(
            f"repeat_count must be no greater than {MAX_HABIT_DURATION_DAYS}"
        )
    return repeat_count


def validate_habit_end_date(*, start_date: date, end_date: date) -> int:
    """Return duration days for an inclusive habit end date."""
    if end_date < start_date:
        raise HabitValidationError("end_date must be on or after start_date")
    return validate_habit_duration((end_date - start_date).days + 1)


def validate_habit_start_date(start_date: date) -> date:
    """Validate that a habit does not begin too far in the past."""
    if start_date < get_operational_date() - timedelta(days=HABIT_EDITABLE_DAYS):
        raise HabitValidationError(
            f"Start date cannot be more than {HABIT_EDITABLE_DAYS} days in the past"
        )
    return start_date


def normalize_habit_weekdays(weekdays: Sequence[str] | None) -> tuple[str, ...] | None:
    """Normalize an optional weekday selection."""
    try:
        return normalize_weekday_names(weekdays)
    except RecurrenceValidationError as exc:
        raise HabitValidationError(str(exc)) from exc


def normalize_habit_monthdays(monthdays: Sequence[object] | None) -> tuple[int, ...] | None:
    """Normalize optional calendar month day selections."""
    try:
        normalized = normalize_month_days(monthdays)
    except RecurrenceValidationError as exc:
        raise HabitValidationError(str(exc)) from exc
    if normalized is not None and any(day < 1 for day in normalized):
        raise HabitValidationError("cadence_monthdays values must be between 1 and 31.")
    return normalized


def validate_habit_cadence(
    *,
    cadence_frequency: str | None,
    cadence_weekdays: Sequence[str] | None,
    cadence_monthdays: Sequence[object] | None = None,
    target_per_cycle: int | None,
) -> tuple[str, tuple[str, ...] | None, tuple[int, ...] | None, int]:
    """Validate cadence fields and normalize defaults."""
    try:
        normalized_frequency = (
            "daily"
            if cadence_frequency is None
            else normalize_recurrence_frequency(cadence_frequency)
        )
    except RecurrenceValidationError as exc:
        raise HabitValidationError(str(exc)) from exc
    normalized_weekdays = normalize_habit_weekdays(cadence_weekdays)
    normalized_monthdays = normalize_habit_monthdays(cadence_monthdays)
    normalized_target = 1 if target_per_cycle is None else target_per_cycle
    if normalized_target <= 0:
        raise HabitValidationError("target_per_cycle must be greater than zero")

    if normalized_frequency == "daily":
        if normalized_target != 1:
            raise HabitValidationError(
                "Daily cadence only supports target_per_cycle 1. "
                "Use weekly cadence for quota-based habits."
            )
    if normalized_frequency == "weekly":
        max_cycle_capacity = len(normalized_weekdays) if normalized_weekdays else 7
        if normalized_target > max_cycle_capacity:
            raise HabitValidationError(
                f"target_per_cycle {normalized_target!r} exceeds the cadence "
                f"capacity {max_cycle_capacity}."
            )
    if normalized_frequency == "monthly" and normalized_monthdays is not None:
        max_cycle_capacity = len(normalized_monthdays)
        if normalized_target > max_cycle_capacity:
            raise HabitValidationError(
                f"target_per_cycle {normalized_target!r} exceeds the cadence "
                f"capacity {max_cycle_capacity}."
            )
    if normalized_frequency == "daily" and normalized_weekdays is not None:
        raise HabitValidationError(
            "Daily cadence does not accept weekday restrictions. "
            "Use weekly or longer cycles instead."
        )
    if normalized_frequency == "daily" and normalized_monthdays is not None:
        raise HabitValidationError(
            "Daily cadence does not accept monthday restrictions. Use monthly cadence instead."
        )
    if normalized_frequency != "monthly" and normalized_monthdays is not None:
        raise HabitValidationError("Monthday restrictions require monthly cadence.")
    return normalized_frequency, normalized_weekdays, normalized_monthdays, normalized_target


def _build_habit_series_definition(
    *,
    start_date: date,
    cadence_frequency: str,
    cadence_weekdays: Sequence[str] | None,
    target_per_cycle: int,
) -> SeriesDefinition:
    return build_series_definition(
        anchor_start=get_day_start_datetime(start_date),
        anchor_end=None,
        frequency="daily",
        byweekday=cadence_weekdays,
        week_starts_on=get_preferences_settings().week_starts_on,
        evaluation_mode=(
            "per_occurrence"
            if cadence_frequency == "daily" and target_per_cycle == 1
            else "quota_per_cycle"
        ),
        cycle_frequency=cadence_frequency,
        target_per_cycle=target_per_cycle,
    )


def get_habit_cycle_bounds(
    *,
    action_date: date,
    cadence_frequency: str,
) -> tuple[date, date]:
    """Return cadence cycle bounds for one scheduled action date."""
    try:
        if cadence_frequency == "daily":
            return get_cycle_date_bounds(
                reference_date=action_date,
                cycle_frequency=cadence_frequency,
                week_starts_on=get_preferences_settings().week_starts_on,
            )
        preferences = get_preferences_settings()
        granularity = CADENCE_TO_CALENDAR_GRANULARITY[cadence_frequency]
        return get_calendar_period_range(
            granularity,
            action_date,
            calendar_system=preferences.calendar_system,
            first_day_of_week=preferences.calendar_first_day_of_week,
        )
    except (KeyError, RecurrenceValidationError, ValueError) as exc:
        raise HabitValidationError(str(exc)) from exc


def iter_habit_scheduled_dates(
    *,
    start_date: date,
    end_date: date,
    cadence_frequency: str,
    cadence_weekdays: Sequence[str] | None,
    cadence_monthdays: Sequence[object] | None = None,
) -> list[date]:
    """Return scheduled habit-action dates for the requested window."""
    normalized_frequency, normalized_weekdays, normalized_monthdays, _ = validate_habit_cadence(
        cadence_frequency=cadence_frequency,
        cadence_weekdays=cadence_weekdays,
        cadence_monthdays=cadence_monthdays,
        target_per_cycle=1,
    )
    return _iter_scheduled_dates_with_normalized_cadence(
        start_date=start_date,
        end_date=end_date,
        normalized_frequency=normalized_frequency,
        normalized_weekdays=normalized_weekdays,
        normalized_monthdays=normalized_monthdays,
    )


def _iter_scheduled_dates_with_normalized_cadence(
    *,
    start_date: date,
    end_date: date,
    normalized_frequency: str,
    normalized_weekdays: tuple[str, ...] | None,
    normalized_monthdays: tuple[int, ...] | None,
) -> list[date]:
    """Iterate occurrence dates for already-normalized habit cadence fields."""
    if end_date < start_date:
        return []
    if normalized_frequency == "monthly" and normalized_monthdays is not None:
        return _iter_monthly_monthday_dates(
            start_date=start_date,
            end_date=end_date,
            normalized_monthdays=normalized_monthdays,
        )
    if normalized_weekdays is not None:
        weekday_names = set(normalized_weekdays)
        return [
            current_date
            for current_date in (
                start_date + timedelta(days=offset)
                for offset in range((end_date - start_date).days + 1)
            )
            if VALID_WEEKDAY_NAMES[current_date.weekday()] in weekday_names
        ]
    return [
        start_date + timedelta(days=offset) for offset in range((end_date - start_date).days + 1)
    ]


def _iter_monthly_monthday_dates(
    *,
    start_date: date,
    end_date: date,
    normalized_monthdays: tuple[int, ...],
) -> list[date]:
    """Iterate monthly occurrence dates by walking calendar months."""
    preferences = get_preferences_settings()
    scheduled_dates: list[date] = []
    period_start, period_end = get_calendar_period_range(
        "month",
        start_date,
        calendar_system=preferences.calendar_system,
        first_day_of_week=preferences.calendar_first_day_of_week,
    )
    while period_start <= end_date:
        for monthday in normalized_monthdays:
            candidate = period_start + timedelta(days=monthday - 1)
            if candidate > period_end:
                continue
            if candidate < start_date or candidate > end_date:
                continue
            scheduled_dates.append(candidate)
        if period_end >= end_date:
            break
        next_start = period_end + timedelta(days=1)
        period_start, period_end = get_calendar_period_range(
            "month",
            next_start,
            calendar_system=preferences.calendar_system,
            first_day_of_week=preferences.calendar_first_day_of_week,
        )
    return scheduled_dates


def calculate_habit_duration_for_repeat_count(
    *,
    start_date: date,
    repeat_count: int,
    cadence_frequency: str,
    cadence_weekdays: Sequence[str] | None,
    cadence_monthdays: Sequence[object] | None = None,
) -> int:
    """Return duration days needed to include a requested occurrence count."""
    normalized_repeat_count = validate_habit_repeat_count(repeat_count)
    scheduled_dates: list[date] = []
    cursor = start_date
    latest_allowed_date = start_date + timedelta(days=MAX_HABIT_DURATION_DAYS - 1)
    while cursor <= latest_allowed_date and len(scheduled_dates) < normalized_repeat_count:
        if habit_occurs_on_date(
            start_date=start_date,
            end_date=latest_allowed_date,
            cadence_frequency=cadence_frequency,
            cadence_weekdays=cadence_weekdays,
            cadence_monthdays=cadence_monthdays,
            target_date=cursor,
        ):
            scheduled_dates.append(cursor)
        cursor += timedelta(days=1)
    if len(scheduled_dates) < normalized_repeat_count:
        raise HabitValidationError(
            "repeat_count does not fit within the maximum habit duration window"
        )
    return validate_habit_duration((scheduled_dates[-1] - start_date).days + 1)


def _calendar_monthday(target_date: date) -> int:
    preferences = get_preferences_settings()
    month_start, _ = get_calendar_period_range(
        "month",
        target_date,
        calendar_system=preferences.calendar_system,
        first_day_of_week=preferences.calendar_first_day_of_week,
    )
    return (target_date - month_start).days + 1


def habit_occurs_on_date(
    *,
    start_date: date,
    end_date: date,
    cadence_frequency: str = "daily",
    cadence_weekdays: Sequence[str] | None,
    cadence_monthdays: Sequence[object] | None = None,
    target_date: date,
) -> bool:
    """Return whether one habit schedules an occurrence on the requested date."""
    if target_date < start_date or target_date > end_date:
        return False
    normalized_frequency, normalized_weekdays, normalized_monthdays, _ = validate_habit_cadence(
        cadence_frequency=cadence_frequency,
        cadence_weekdays=cadence_weekdays,
        cadence_monthdays=cadence_monthdays,
        target_per_cycle=1,
    )
    return _occurs_on_date_with_normalized_cadence(
        start_date=start_date,
        end_date=end_date,
        normalized_frequency=normalized_frequency,
        normalized_weekdays=normalized_weekdays,
        normalized_monthdays=normalized_monthdays,
        target_date=target_date,
    )


def _occurs_on_date_with_normalized_cadence(
    *,
    start_date: date,
    end_date: date,
    normalized_frequency: str,
    normalized_weekdays: tuple[str, ...] | None,
    normalized_monthdays: tuple[int, ...] | None,
    target_date: date,
) -> bool:
    """Occurrence predicate for already-normalized habit cadence fields."""
    if target_date < start_date or target_date > end_date:
        return False
    if normalized_weekdays is not None:
        weekday_name = VALID_WEEKDAY_NAMES[target_date.weekday()]
        if weekday_name not in normalized_weekdays:
            return False
    if normalized_frequency == "monthly" and normalized_monthdays is not None:
        return _calendar_monthday(target_date) in normalized_monthdays
    return True


def get_habit_occurrence_end_date(habit: object) -> date:
    """Return the final date where a habit should produce action occurrences."""
    end_date = getattr(habit, "end_date", None)
    if not isinstance(end_date, date):
        raise HabitValidationError("Habit occurrence end date is unavailable")
    status = getattr(habit, "status", "active")
    status_changed_date = getattr(habit, "status_changed_date", None)
    if status != "active" and isinstance(status_changed_date, date):
        return min(end_date, status_changed_date - timedelta(days=1))
    return end_date


def validate_habit_schedule_window(
    *,
    start_date: date,
    end_date: date,
    cadence_frequency: str,
    cadence_weekdays: Sequence[str] | None,
    cadence_monthdays: Sequence[object] | None = None,
) -> None:
    """Ensure one habit definition produces at least one scheduled date."""
    desired_dates = iter_habit_scheduled_dates(
        start_date=start_date,
        end_date=end_date,
        cadence_frequency=cadence_frequency,
        cadence_weekdays=cadence_weekdays,
        cadence_monthdays=cadence_monthdays,
    )
    if desired_dates:
        return
    raise InvalidHabitOperationError(
        "Habit cadence does not produce any scheduled action dates inside the requested window."
    )


def build_habit_cycle_summaries(
    habit: Habit,
    actions: Sequence[HabitActionLike],
) -> list[HabitCycleSummary]:
    """Build cadence-cycle summaries for one habit."""
    cadence_frequency, cadence_weekdays, _, target_per_cycle = validate_habit_cadence(
        cadence_frequency=getattr(habit, "cadence_frequency", None),
        cadence_weekdays=getattr(habit, "cadence_weekdays", None),
        cadence_monthdays=getattr(habit, "cadence_monthdays", None),
        target_per_cycle=getattr(habit, "target_per_cycle", None),
    )
    series = _build_habit_series_definition(
        start_date=habit.start_date,
        cadence_frequency=cadence_frequency,
        cadence_weekdays=cadence_weekdays,
        target_per_cycle=target_per_cycle,
    )
    actions_by_cycle: dict[date, list[HabitActionLike]] = {}
    for action in sorted(actions, key=lambda row: row.action_date):
        cycle_start, _ = get_habit_cycle_bounds(
            action_date=action.action_date,
            cadence_frequency=series.evaluation.cycle_frequency,
        )
        actions_by_cycle.setdefault(cycle_start, []).append(action)

    summaries: list[HabitCycleSummary] = []
    for cycle_start in sorted(actions_by_cycle):
        cycle_actions = actions_by_cycle[cycle_start]
        _, cycle_end = get_habit_cycle_bounds(
            action_date=cycle_actions[0].action_date,
            cadence_frequency=series.evaluation.cycle_frequency,
        )
        completed_count = len(
            [
                action
                for action in cycle_actions
                if HABIT_ACTION_STATUS_CONFIG.get(action.status, {}).get(
                    "count_as_completed",
                    False,
                )
            ]
        )
        required_completion_count = min(target_per_cycle, len(cycle_actions))
        summaries.append(
            HabitCycleSummary(
                start_date=cycle_start,
                end_date=cycle_end,
                completed_count=completed_count,
                required_completion_count=required_completion_count,
            )
        )
    return summaries


def _count_streak_cycles(cycles: Sequence[HabitCycleSummary], *, today: date) -> int:
    streak = 0
    for cycle in reversed(cycles):
        if cycle.start_date > today:
            continue
        if cycle.end_date > today and not cycle.is_complete:
            continue
        if cycle.is_complete:
            streak += 1
            continue
        break
    return streak


def calculate_current_streak(
    actions: Sequence[HabitActionLike],
    *,
    habit: Habit,
) -> int:
    """Return the current streak of completed cadence cycles."""
    cycles = build_habit_cycle_summaries(habit, actions)
    return _count_streak_cycles(cycles, today=get_operational_date())


def calculate_longest_streak(
    actions: Sequence[HabitActionLike],
    *,
    habit: Habit,
) -> int:
    """Return the longest historical streak of completed cadence cycles."""
    today = get_operational_date()
    cycles = build_habit_cycle_summaries(habit, actions)
    max_streak = 0
    current_streak = 0
    for cycle in cycles:
        if cycle.start_date > today:
            continue
        if cycle.end_date > today and not cycle.is_complete:
            continue
        if cycle.is_complete:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    return max_streak


async def ensure_task_exists(session: AsyncSession, task_id: UUID | None) -> None:
    """Ensure an optional task reference exists."""
    from lifeos_cli.db.models.task import Task

    if task_id is None:
        return
    result = await session.execute(
        select(Task.id).where(Task.id == task_id, Task.deleted_at.is_(None)).limit(1)
    )
    if result.scalar_one_or_none() is None:
        raise HabitTaskReferenceNotFoundError(f"Task {task_id} was not found")


async def ensure_active_capacity(
    session: AsyncSession,
    *,
    exclude_habit_id: UUID | None = None,
) -> None:
    """Ensure the active habit cap has not been exceeded."""
    from lifeos_cli.db.models.habit import Habit

    local_today = get_operational_date()
    end_expr = AddDaysToDate(Habit.start_date, Habit.duration_days - 1)
    filters = [
        Habit.deleted_at.is_(None),
        Habit.status == "active",
        end_expr >= local_today,
    ]
    if exclude_habit_id is not None:
        filters.append(Habit.id != exclude_habit_id)
    stmt = select(func.count()).where(*filters)
    active_count = (await session.execute(stmt)).scalar_one()
    if active_count >= MAX_ACTIVE_HABITS:
        raise InvalidHabitOperationError(
            f"You already have {MAX_ACTIVE_HABITS} active habits. Pause or complete one first."
        )


async def refresh_habit_expiration(
    session: AsyncSession,
    *,
    habit_id: UUID | None = None,
) -> int:
    """Mark active habits as expired when their end date is in the past."""
    from lifeos_cli.db.models.habit import Habit

    local_today = get_operational_date()
    end_expr = AddDaysToDate(Habit.start_date, Habit.duration_days - 1)
    filters = [
        Habit.deleted_at.is_(None),
        Habit.status == "active",
        end_expr < local_today,
    ]
    if habit_id is not None:
        filters.append(Habit.id == habit_id)
    stmt = (
        update(Habit)
        .where(*filters)
        .values(
            status="expired",
            status_changed_date=local_today,
            updated_at=utc_now(),
        )
    )
    result = await session.execute(stmt)
    rowcount = getattr(result, "rowcount", 0)
    return int(0 if rowcount is None else rowcount)


def build_habit_stats_payload(
    habit: Habit,
    actions: Sequence[HabitActionLike],
) -> dict[str, object]:
    """Build stats shared by overview, show, and stats commands."""
    current_week_start, current_week_end = get_week_bounds(get_operational_date())
    cadence_frequency, cadence_weekdays, cadence_monthdays, target_per_cycle = (
        validate_habit_cadence(
            cadence_frequency=getattr(habit, "cadence_frequency", None),
            cadence_weekdays=getattr(habit, "cadence_weekdays", None),
            cadence_monthdays=getattr(habit, "cadence_monthdays", None),
            target_per_cycle=getattr(habit, "target_per_cycle", None),
        )
    )
    series = _build_habit_series_definition(
        start_date=habit.start_date,
        cadence_frequency=cadence_frequency,
        cadence_weekdays=cadence_weekdays,
        target_per_cycle=target_per_cycle,
    )
    cycle_summaries = build_habit_cycle_summaries(habit, actions)
    today = get_operational_date()
    eligible_cycles = [cycle for cycle in cycle_summaries if cycle.start_date <= today]
    completed_cycles = [cycle for cycle in eligible_cycles if cycle.is_complete]
    progress_percentage = (
        (len(completed_cycles) / len(eligible_cycles)) * 100 if eligible_cycles else 0.0
    )
    current_cycle_start, current_cycle_end = get_habit_cycle_bounds(
        action_date=today,
        cadence_frequency=series.evaluation.cycle_frequency,
    )
    total_actions = len(actions)
    completed_actions = len(
        [
            action
            for action in actions
            if HABIT_ACTION_STATUS_CONFIG.get(action.status, {}).get("count_as_completed", False)
        ]
    )
    missed_actions = len([action for action in actions if action.status == "miss"])
    skipped_actions = len([action for action in actions if action.status == "skip"])
    return {
        "habit_id": habit.id,
        "cadence_frequency": cadence_frequency,
        "cadence_weekdays": cadence_weekdays,
        "cadence_monthdays": cadence_monthdays,
        "target_per_cycle": target_per_cycle,
        "total_actions": total_actions,
        "completed_actions": completed_actions,
        "missed_actions": missed_actions,
        "skipped_actions": skipped_actions,
        "total_cycles": len(cycle_summaries),
        "eligible_cycles": len(eligible_cycles),
        "completed_cycles": len(completed_cycles),
        "progress_percentage": progress_percentage,
        "current_streak": calculate_current_streak(actions, habit=habit),
        "longest_streak": calculate_longest_streak(actions, habit=habit),
        "current_cycle_start": current_cycle_start,
        "current_cycle_end": current_cycle_end,
        "current_week_start": current_week_start,
        "current_week_end": current_week_end,
    }
