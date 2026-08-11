"""Shared RRULE-style recurrence primitives for recurring domain resources."""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal, TypedDict, cast

from dateutil.rrule import (
    DAILY,
    FR,
    MO,
    MONTHLY,
    SA,
    SU,
    TH,
    TU,
    WE,
    WEEKLY,
    YEARLY,
    rrule,
)

from lifeos_cli.db.services.validation_utils import (
    DomainValidationError,
    choice_validator,
    validate_choice,
)

VALID_RECURRENCE_FREQUENCY_ORDER = ("daily", "weekly", "monthly", "yearly")
VALID_RECURRENCE_FREQUENCIES = set(VALID_RECURRENCE_FREQUENCY_ORDER)
VALID_WEEKDAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
VALID_EVALUATION_MODES = {"none", "per_occurrence", "quota_per_cycle"}
RRuleFrequency = Literal[0, 1, 2, 3, 4, 5, 6]

_FREQUENCY_TO_RRULE: dict[str, RRuleFrequency] = {
    "daily": DAILY,
    "weekly": WEEKLY,
    "monthly": MONTHLY,
    "yearly": YEARLY,
}
_WEEKDAY_TO_RRULE = {
    "monday": MO,
    "tuesday": TU,
    "wednesday": WE,
    "thursday": TH,
    "friday": FR,
    "saturday": SA,
    "sunday": SU,
}
_WEEKDAY_TO_INDEX = {weekday: index for index, weekday in enumerate(VALID_WEEKDAY_NAMES)}


class RecurrenceValidationError(DomainValidationError):
    """Raised when a shared recurrence rule is invalid."""


class RecurrenceRuleKwargs(TypedDict, total=False):
    """Keyword arguments for advanced recurrence details."""

    byweekday: Sequence[str] | None
    bymonthday: Sequence[object] | None
    bymonth: Sequence[object] | None
    byweekday_ordinals: Sequence[Mapping[str, object]] | None


@dataclass(frozen=True)
class WeekdayOrdinal:
    """One nth-weekday selector, such as the second Monday or last Friday."""

    weekday: str
    ordinal: int


@dataclass(frozen=True)
class RecurrenceRule:
    """Structured RRULE-style definition for recurring series."""

    frequency: str
    interval: int = 1
    count: int | None = None
    until: datetime | None = None
    byweekday: tuple[str, ...] | None = None
    bymonthday: tuple[int, ...] | None = None
    bymonth: tuple[int, ...] | None = None
    byweekday_ordinals: tuple[WeekdayOrdinal, ...] | None = None
    week_starts_on: str = "monday"


@dataclass(frozen=True)
class EvaluationPolicy:
    """Shared cycle-evaluation policy for recurring series."""

    mode: str = "none"
    cycle_frequency: str = "daily"
    target_per_cycle: int = 1


@dataclass(frozen=True)
class SeriesDefinition:
    """Unified recurring series definition used by event and habit services."""

    anchor_start: datetime
    anchor_end: datetime | None
    rule: RecurrenceRule
    evaluation: EvaluationPolicy = field(default_factory=EvaluationPolicy)


def normalize_weekday_names(weekdays: Sequence[str] | None) -> tuple[str, ...] | None:
    """Normalize an optional weekday name set."""
    if weekdays is None:
        return None
    normalized: list[str] = []
    for weekday in weekdays:
        if not weekday.strip():
            continue
        normalized_weekday = validate_choice(
            weekday,
            VALID_WEEKDAY_NAMES,
            error_cls=RecurrenceValidationError,
            label="weekday",
            display_order=VALID_WEEKDAY_NAMES,
        )
        if normalized_weekday not in normalized:
            normalized.append(normalized_weekday)
    if not normalized:
        return None
    return tuple(sorted(normalized, key=lambda weekday: _WEEKDAY_TO_INDEX[weekday]))


def _coerce_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise RecurrenceValidationError(f"{field_name} must contain integers.")
    try:
        return int(str(value))
    except (TypeError, ValueError) as exc:
        raise RecurrenceValidationError(f"{field_name} must contain integers.") from exc


def normalize_month_days(values: Sequence[object] | None) -> tuple[int, ...] | None:
    """Normalize optional BYMONTHDAY values."""
    if values is None:
        return None
    normalized: list[int] = []
    for value in values:
        day = _coerce_int(value, field_name="bymonthday")
        if day == 0 or day < -31 or day > 31:
            raise RecurrenceValidationError("bymonthday values must be between -31 and 31, not 0.")
        if day not in normalized:
            normalized.append(day)
    if not normalized:
        return None
    return tuple(sorted(normalized))


def normalize_months(values: Sequence[object] | None) -> tuple[int, ...] | None:
    """Normalize optional BYMONTH values."""
    if values is None:
        return None
    normalized: list[int] = []
    for value in values:
        month = _coerce_int(value, field_name="bymonth")
        if month < 1 or month > 12:
            raise RecurrenceValidationError("bymonth values must be between 1 and 12.")
        if month not in normalized:
            normalized.append(month)
    if not normalized:
        return None
    return tuple(sorted(normalized))


def normalize_weekday_ordinals(
    values: Sequence[Mapping[str, object]] | None,
) -> tuple[WeekdayOrdinal, ...] | None:
    """Normalize optional nth-weekday selectors."""
    if values is None:
        return None
    normalized: list[WeekdayOrdinal] = []
    seen: set[tuple[str, int]] = set()
    for value in values:
        weekday_value = value.get("weekday")
        if not isinstance(weekday_value, str):
            raise RecurrenceValidationError("byweekday_ordinals require weekday strings.")
        weekday = normalize_weekday_names([weekday_value])
        assert weekday is not None
        ordinal = _coerce_int(value.get("ordinal"), field_name="byweekday_ordinals.ordinal")
        if ordinal == 0 or ordinal < -5 or ordinal > 5:
            raise RecurrenceValidationError(
                "byweekday ordinal values must be between -5 and 5, not 0."
            )
        key = (weekday[0], ordinal)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(WeekdayOrdinal(weekday=weekday[0], ordinal=ordinal))
    if not normalized:
        return None
    return tuple(
        sorted(normalized, key=lambda item: (_WEEKDAY_TO_INDEX[item.weekday], item.ordinal))
    )


def normalize_recurrence_rule_details(
    details: Mapping[str, object] | None,
) -> dict[str, object] | None:
    """Normalize JSON-compatible advanced recurrence details."""
    if not details:
        return None
    byweekday_value = details.get("byweekday")
    bymonthday_value = details.get("bymonthday")
    bymonth_value = details.get("bymonth")
    byweekday_ordinals_value = details.get("byweekday_ordinals")

    if byweekday_value is not None and not isinstance(byweekday_value, Sequence):
        raise RecurrenceValidationError("byweekday must be a list of weekday names.")
    if isinstance(byweekday_value, (str, bytes)):
        byweekday_value = [str(byweekday_value)]

    if bymonthday_value is not None and not isinstance(bymonthday_value, Sequence):
        raise RecurrenceValidationError("bymonthday must be a list of integers.")
    if isinstance(bymonthday_value, (str, bytes)):
        bymonthday_value = [str(bymonthday_value)]

    if bymonth_value is not None and not isinstance(bymonth_value, Sequence):
        raise RecurrenceValidationError("bymonth must be a list of integers.")
    if isinstance(bymonth_value, (str, bytes)):
        bymonth_value = [str(bymonth_value)]

    if byweekday_ordinals_value is not None:
        if not isinstance(byweekday_ordinals_value, Sequence) or isinstance(
            byweekday_ordinals_value,
            (str, bytes),
        ):
            raise RecurrenceValidationError(
                "byweekday_ordinals must be a list of weekday ordinal objects."
            )
        for item in byweekday_ordinals_value:
            if not isinstance(item, Mapping):
                raise RecurrenceValidationError(
                    "byweekday_ordinals must be a list of weekday ordinal objects."
                )

    normalized_byweekday = normalize_weekday_names(byweekday_value)
    normalized_bymonthday = normalize_month_days(bymonthday_value)
    normalized_bymonth = normalize_months(bymonth_value)
    normalized_ordinals = normalize_weekday_ordinals(byweekday_ordinals_value)
    payload: dict[str, object] = {}
    if normalized_byweekday is not None:
        payload["byweekday"] = list(normalized_byweekday)
    if normalized_bymonthday is not None:
        payload["bymonthday"] = list(normalized_bymonthday)
    if normalized_bymonth is not None:
        payload["bymonth"] = list(normalized_bymonth)
    if normalized_ordinals is not None:
        payload["byweekday_ordinals"] = [
            {"weekday": item.weekday, "ordinal": item.ordinal} for item in normalized_ordinals
        ]
    return payload or None


def recurrence_rule_details_to_kwargs(
    details: Mapping[str, object] | None,
) -> RecurrenceRuleKwargs:
    """Return build_series_definition keyword arguments for advanced recurrence details."""
    normalized = normalize_recurrence_rule_details(details)
    if normalized is None:
        return {}
    return {
        "byweekday": cast(Sequence[str] | None, normalized.get("byweekday")),
        "bymonthday": cast(Sequence[object] | None, normalized.get("bymonthday")),
        "bymonth": cast(Sequence[object] | None, normalized.get("bymonth")),
        "byweekday_ordinals": cast(
            Sequence[Mapping[str, object]] | None,
            normalized.get("byweekday_ordinals"),
        ),
    }


def serialize_recurrence_rule_details(rule: RecurrenceRule) -> dict[str, object] | None:
    """Return JSON-compatible advanced details from a normalized recurrence rule."""
    payload: dict[str, object] = {}
    if rule.byweekday is not None:
        payload["byweekday"] = list(rule.byweekday)
    if rule.bymonthday is not None:
        payload["bymonthday"] = list(rule.bymonthday)
    if rule.bymonth is not None:
        payload["bymonth"] = list(rule.bymonth)
    if rule.byweekday_ordinals is not None:
        payload["byweekday_ordinals"] = [
            {"weekday": item.weekday, "ordinal": item.ordinal} for item in rule.byweekday_ordinals
        ]
    return payload or None


normalize_recurrence_frequency = choice_validator(
    VALID_RECURRENCE_FREQUENCIES,
    error_cls=RecurrenceValidationError,
    label="recurrence frequency",
    display_order=VALID_RECURRENCE_FREQUENCY_ORDER,
)


def normalize_week_starts_on(week_starts_on: str) -> str:
    normalized = week_starts_on.strip().lower()
    if normalized not in {"monday", "sunday"}:
        raise RecurrenceValidationError("week_starts_on must be `monday` or `sunday`.")
    return normalized


def normalize_recurrence_rule(
    *,
    anchor_start: datetime,
    frequency: str,
    interval: int | None = None,
    count: int | None = None,
    until: datetime | None = None,
    byweekday: Sequence[str] | None = None,
    bymonthday: Sequence[object] | None = None,
    bymonth: Sequence[object] | None = None,
    byweekday_ordinals: Sequence[Mapping[str, object]] | None = None,
    week_starts_on: str = "monday",
) -> RecurrenceRule:
    """Validate and normalize a shared RRULE-style recurrence definition."""
    if anchor_start.tzinfo is None or anchor_start.utcoffset() is None:
        raise RecurrenceValidationError("Recurring anchors must be timezone-aware datetimes.")
    normalized_frequency = normalize_recurrence_frequency(frequency)
    normalized_interval = 1 if interval is None else interval
    if normalized_interval <= 0:
        raise RecurrenceValidationError("Recurrence interval must be greater than zero.")
    if count is not None and count <= 0:
        raise RecurrenceValidationError("Recurrence count must be greater than zero.")
    if until is not None:
        if until.tzinfo is None or until.utcoffset() is None:
            raise RecurrenceValidationError("Recurrence until must be timezone-aware.")
        if until < anchor_start:
            raise RecurrenceValidationError(
                "Recurrence until must be on or after the first occurrence start time."
            )
    return RecurrenceRule(
        frequency=normalized_frequency,
        interval=normalized_interval,
        count=count,
        until=until,
        byweekday=normalize_weekday_names(byweekday),
        bymonthday=normalize_month_days(bymonthday),
        bymonth=normalize_months(bymonth),
        byweekday_ordinals=normalize_weekday_ordinals(byweekday_ordinals),
        week_starts_on=normalize_week_starts_on(week_starts_on),
    )


def normalize_evaluation_policy(
    *,
    mode: str = "none",
    cycle_frequency: str = "daily",
    target_per_cycle: int = 1,
) -> EvaluationPolicy:
    """Validate and normalize a shared evaluation policy."""
    normalized_mode = validate_choice(
        mode,
        VALID_EVALUATION_MODES,
        error_cls=RecurrenceValidationError,
        label="evaluation mode",
    )
    normalized_cycle_frequency = normalize_recurrence_frequency(cycle_frequency)
    if target_per_cycle <= 0:
        raise RecurrenceValidationError("target_per_cycle must be greater than zero.")
    if normalized_mode == "per_occurrence" and target_per_cycle != 1:
        raise RecurrenceValidationError("per_occurrence evaluation requires target_per_cycle 1.")
    return EvaluationPolicy(
        mode=normalized_mode,
        cycle_frequency=normalized_cycle_frequency,
        target_per_cycle=target_per_cycle,
    )


def build_series_definition(
    *,
    anchor_start: datetime,
    anchor_end: datetime | None,
    frequency: str,
    interval: int | None = None,
    count: int | None = None,
    until: datetime | None = None,
    byweekday: Sequence[str] | None = None,
    bymonthday: Sequence[object] | None = None,
    bymonth: Sequence[object] | None = None,
    byweekday_ordinals: Sequence[Mapping[str, object]] | None = None,
    week_starts_on: str = "monday",
    evaluation_mode: str = "none",
    cycle_frequency: str | None = None,
    target_per_cycle: int = 1,
) -> SeriesDefinition:
    """Build one normalized recurring series definition."""
    rule = normalize_recurrence_rule(
        anchor_start=anchor_start,
        frequency=frequency,
        interval=interval,
        count=count,
        until=until,
        byweekday=byweekday,
        bymonthday=bymonthday,
        bymonth=bymonth,
        byweekday_ordinals=byweekday_ordinals,
        week_starts_on=week_starts_on,
    )
    evaluation = normalize_evaluation_policy(
        mode=evaluation_mode,
        cycle_frequency=cycle_frequency or frequency,
        target_per_cycle=target_per_cycle,
    )
    return SeriesDefinition(
        anchor_start=anchor_start,
        anchor_end=anchor_end,
        rule=rule,
        evaluation=evaluation,
    )


def _build_rrule_for_series(series: SeriesDefinition) -> rrule:
    byweekday: list[Any] = []
    if series.rule.byweekday is not None:
        byweekday.extend(_WEEKDAY_TO_RRULE[weekday] for weekday in series.rule.byweekday)
    if series.rule.byweekday_ordinals is not None:
        byweekday.extend(
            _WEEKDAY_TO_RRULE[item.weekday](item.ordinal) for item in series.rule.byweekday_ordinals
        )
    return rrule(
        _FREQUENCY_TO_RRULE[series.rule.frequency],
        dtstart=series.anchor_start,
        interval=series.rule.interval,
        count=series.rule.count,
        until=series.rule.until,
        byweekday=None if not byweekday else tuple(byweekday),
        bymonthday=series.rule.bymonthday,
        bymonth=series.rule.bymonth,
        wkst=_WEEKDAY_TO_RRULE[series.rule.week_starts_on],
    )


def _occurrence_duration(series: SeriesDefinition) -> timedelta | None:
    if series.anchor_end is None:
        return None
    return series.anchor_end - series.anchor_start


def _occurrence_end(series: SeriesDefinition, start_at: datetime) -> datetime | None:
    duration = _occurrence_duration(series)
    return None if duration is None else start_at + duration


def occurrence_overlaps_window(
    series: SeriesDefinition,
    *,
    start_at: datetime,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    """Return whether one series occurrence overlaps the requested window."""
    end_at = _occurrence_end(series, start_at)
    return start_at <= window_end and (end_at is None or end_at >= window_start)


def get_occurrence_starts_in_range(
    series: SeriesDefinition,
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[datetime]:
    """Return occurrence starts that overlap the requested window."""
    if window_end < window_start:
        return []
    compiled_rule = _build_rrule_for_series(series)
    start_candidates = set(compiled_rule.between(window_start, window_end, inc=True))
    previous_start = compiled_rule.before(window_start, inc=True)
    if previous_start is not None:
        start_candidates.add(previous_start)
    starts = [
        start_at
        for start_at in sorted(start_candidates)
        if occurrence_overlaps_window(
            series,
            start_at=start_at,
            window_start=window_start,
            window_end=window_end,
        )
    ]
    return starts


def get_occurrence_index(
    series: SeriesDefinition,
    *,
    instance_start: datetime,
) -> int:
    """Return the zero-based occurrence index for one exact occurrence start."""
    compiled_rule = _build_rrule_for_series(series)
    if instance_start not in compiled_rule.between(instance_start, instance_start, inc=True):
        raise RecurrenceValidationError(
            "Instance start does not match the recurring series cadence."
        )
    starts = compiled_rule.between(series.anchor_start, instance_start, inc=True)
    if not starts or starts[-1] != instance_start:
        raise RecurrenceValidationError(
            "Instance start does not match the recurring series cadence."
        )
    return len(starts) - 1


def validate_occurrence_start(
    series: SeriesDefinition,
    *,
    instance_start: datetime,
) -> None:
    """Validate one exact occurrence start against the series definition."""
    get_occurrence_index(series, instance_start=instance_start)


def get_previous_occurrence_start(
    series: SeriesDefinition,
    *,
    instance_start: datetime,
) -> datetime | None:
    """Return the previous occurrence start for one series occurrence."""
    validate_occurrence_start(series, instance_start=instance_start)
    compiled_rule = _build_rrule_for_series(series)
    return compiled_rule.before(instance_start, inc=False)


def get_cycle_date_bounds(
    *,
    reference_date: date,
    cycle_frequency: str,
    week_starts_on: str = "monday",
) -> tuple[date, date]:
    """Return the inclusive date bounds for one evaluation cycle."""
    normalized_frequency = normalize_recurrence_frequency(cycle_frequency)
    normalized_week_start = normalize_week_starts_on(week_starts_on)
    if normalized_frequency == "daily":
        return reference_date, reference_date
    if normalized_frequency == "weekly":
        weekday = reference_date.weekday()
        if normalized_week_start == "sunday":
            days_since_week_start = (weekday + 1) % 7
        else:
            days_since_week_start = weekday
        cycle_start = reference_date - timedelta(days=days_since_week_start)
        return cycle_start, cycle_start + timedelta(days=6)
    if normalized_frequency == "monthly":
        cycle_start = reference_date.replace(day=1)
        cycle_end = reference_date.replace(
            day=monthrange(reference_date.year, reference_date.month)[1]
        )
        return cycle_start, cycle_end
    cycle_start = reference_date.replace(month=1, day=1)
    cycle_end = reference_date.replace(month=12, day=31)
    return cycle_start, cycle_end
