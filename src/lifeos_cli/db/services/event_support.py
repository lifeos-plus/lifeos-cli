"""Support utilities and validations for event services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.datetime_utils import normalize_storage_datetime
from lifeos_cli.config import get_preferences_settings
from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.services.model_utils import ensure_optional_reference_exists
from lifeos_cli.db.services.recurrence_core import (
    RecurrenceValidationError,
    SeriesDefinition,
    build_series_definition,
    get_occurrence_index,
    get_occurrence_starts_in_range,
    get_previous_occurrence_start,
    normalize_recurrence_rule_details,
    recurrence_rule_details_to_kwargs,
    serialize_recurrence_rule_details,
    validate_occurrence_start,
)
from lifeos_cli.db.services.validation_utils import DomainValidationError, validate_choice

VALID_EVENT_STATUSES = {"planned", "cancelled", "completed"}
VALID_EVENT_TYPES = {"appointment", "timeblock", "deadline"}
VALID_EVENT_OPERATION_SCOPES = {"single", "all_future", "all"}


class EventNotFoundError(LookupError):
    """Raised when an event cannot be found."""


class EventAreaReferenceNotFoundError(LookupError):
    """Raised when a referenced area cannot be found."""


class EventTaskReferenceNotFoundError(LookupError):
    """Raised when a referenced task cannot be found."""


class EventValidationError(DomainValidationError):
    """Raised when event data is invalid."""


@dataclass(frozen=True)
class EventUpdateInput:
    """Normalized mutable fields for event update operations."""

    title: str | None = None
    description: str | None = None
    clear_description: bool = False
    start_time: datetime | None = None
    end_time: datetime | None = None
    clear_end_time: bool = False
    priority: int | None = None
    status: str | None = None
    event_type: str | None = None
    is_all_day: bool | None = None
    area_id: UUID | None = None
    clear_area: bool = False
    task_id: UUID | None = None
    clear_task: bool = False
    tag_ids: list[UUID] | None = None
    clear_tags: bool = False
    person_ids: list[UUID] | None = None
    clear_people: bool = False
    recurrence_frequency: str | None = None
    recurrence_interval: int | None = None
    recurrence_count: int | None = None
    recurrence_until: datetime | None = None
    recurrence_rule: dict[str, object] | None = None
    clear_recurrence_rule: bool = False
    clear_recurrence: bool = False


@dataclass(frozen=True)
class EventCreateInput:
    """Normalized writable fields for event creation."""

    title: str
    start_time: datetime
    end_time: datetime | None = None
    description: str | None = None
    priority: int = 0
    status: str = "planned"
    event_type: str = "appointment"
    is_all_day: bool = False
    area_id: UUID | None = None
    task_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    person_ids: list[UUID] | None = None
    recurrence_frequency: str | None = None
    recurrence_interval: int | None = None
    recurrence_count: int | None = None
    recurrence_until: datetime | None = None
    recurrence_rule: dict[str, object] | None = None
    recurrence_parent_event_id: UUID | None = None
    recurrence_instance_start: datetime | None = None


@dataclass(frozen=True)
class EventQueryFilters:
    """Shared filter set for event list and occurrence operations."""

    title_contains: str | None = None
    status: str | None = None
    event_type: str | None = None
    area_id: UUID | None = None
    task_id: UUID | None = None
    person_id: UUID | None = None
    tag_id: UUID | None = None
    date_values: tuple[date, ...] = ()
    start_date: date | None = None
    end_date: date | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


@dataclass(frozen=True)
class EventOccurrenceQuery:
    """Occurrence expansion intent for one UTC time window."""

    window_start: datetime
    window_end: datetime
    filters: EventQueryFilters = field(default_factory=EventQueryFilters)


@dataclass(frozen=True)
class EventListInput:
    """List intent for events with optional occurrence expansion."""

    filters: EventQueryFilters = field(default_factory=EventQueryFilters)
    limit: int = 100
    offset: int = 0


def validate_event_scope(scope: str) -> str:
    """Validate an event operation scope."""
    return validate_choice(
        scope,
        VALID_EVENT_OPERATION_SCOPES,
        error_cls=EventValidationError,
        label="event scope",
    )


def validate_event_status(status: str) -> str:
    """Validate an event status value."""
    return validate_choice(
        status,
        VALID_EVENT_STATUSES,
        error_cls=EventValidationError,
        label="event status",
    )


def validate_event_type(event_type: str) -> str:
    """Validate an event type value."""
    return validate_choice(
        event_type,
        VALID_EVENT_TYPES,
        error_cls=EventValidationError,
        label="event type",
    )


def validate_event_title(title: str) -> str:
    """Validate and normalize an event title."""
    normalized = title.strip()
    if not normalized:
        raise EventValidationError("Event title must not be empty")
    if len(normalized) > 200:
        raise EventValidationError("Event title must be 200 characters or fewer")
    return normalized


def validate_event_time_range(
    *,
    start_time: datetime,
    end_time: datetime | None,
) -> None:
    """Validate that an event time range is coherent."""
    if end_time is not None and end_time < start_time:
        raise EventValidationError("Event end time must be on or after the start time")


def validate_event_priority(priority: int) -> int:
    """Validate event priority."""
    if priority < 0 or priority > 5:
        raise EventValidationError("Event priority must be between 0 and 5")
    return priority


def validate_event_recurrence(
    *,
    start_time: datetime,
    recurrence_frequency: str | None,
    recurrence_interval: int | None,
    recurrence_count: int | None,
    recurrence_until: datetime | None,
    recurrence_rule: dict[str, object] | None = None,
) -> tuple[str | None, int | None, int | None, datetime | None, dict[str, object] | None]:
    """Validate recurrence fields and normalize defaults."""
    if recurrence_frequency is None:
        if any(
            value is not None
            for value in (
                recurrence_interval,
                recurrence_count,
                recurrence_until,
                recurrence_rule,
            )
        ):
            raise EventValidationError(
                "Recurrence interval, count, until, and rule details require recurrence_frequency."
            )
        return None, None, None, None, None

    try:
        normalized_details = normalize_recurrence_rule_details(recurrence_rule)
        normalized_rule = build_series_definition(
            anchor_start=start_time,
            anchor_end=None,
            frequency=recurrence_frequency,
            interval=recurrence_interval,
            count=recurrence_count,
            until=recurrence_until,
            **recurrence_rule_details_to_kwargs(normalized_details),
            week_starts_on=get_preferences_settings().week_starts_on,
        ).rule
    except RecurrenceValidationError as exc:
        raise EventValidationError(str(exc)) from exc
    return (
        normalized_rule.frequency,
        normalized_rule.interval,
        normalized_rule.count,
        normalized_rule.until,
        serialize_recurrence_rule_details(normalized_rule),
    )


class RecurringEventLike(Protocol):
    """Structural event shape required for recurrence calculations."""

    start_time: datetime
    end_time: datetime | None
    recurrence_parent_event_id: UUID | None
    recurrence_frequency: str | None
    recurrence_interval: int | None
    recurrence_count: int | None
    recurrence_until: datetime | None


def _build_event_series(event: RecurringEventLike) -> SeriesDefinition:
    if event.recurrence_frequency is None:
        raise EventValidationError("Recurring event operations require recurrence_frequency.")
    return build_series_definition(
        anchor_start=normalize_storage_datetime(event.start_time),
        anchor_end=normalize_storage_datetime(event.end_time),
        frequency=event.recurrence_frequency,
        interval=event.recurrence_interval,
        count=event.recurrence_count,
        until=normalize_storage_datetime(event.recurrence_until),
        **recurrence_rule_details_to_kwargs(getattr(event, "recurrence_rule", None)),
        week_starts_on=get_preferences_settings().week_starts_on,
    )


def event_is_recurring(event: RecurringEventLike) -> bool:
    """Return whether the event is a recurring master event."""
    return event.recurrence_parent_event_id is None and event.recurrence_frequency is not None


def get_event_occurrence_index(event: RecurringEventLike, *, instance_start: datetime) -> int:
    """Return the zero-based occurrence index for one recurring event instance."""
    try:
        normalized_instance_start = normalize_storage_datetime(instance_start)
        return get_occurrence_index(
            _build_event_series(event),
            instance_start=normalized_instance_start,
        )
    except RecurrenceValidationError as exc:
        raise EventValidationError(str(exc)) from exc


def validate_event_instance_start(event: RecurringEventLike, *, instance_start: datetime) -> None:
    """Validate one recurring event instance start."""
    if not event_is_recurring(event):
        raise EventValidationError("Instance-level operations require a recurring master event")
    try:
        normalized_instance_start = normalize_storage_datetime(instance_start)
        validate_occurrence_start(
            _build_event_series(event),
            instance_start=normalized_instance_start,
        )
    except RecurrenceValidationError as exc:
        raise EventValidationError(str(exc)) from exc


def get_previous_event_occurrence_start(
    event: RecurringEventLike, *, instance_start: datetime
) -> datetime | None:
    """Return the previous occurrence start for one recurring event instance."""
    try:
        normalized_instance_start = normalize_storage_datetime(instance_start)
        return get_previous_occurrence_start(
            _build_event_series(event),
            instance_start=normalized_instance_start,
        )
    except RecurrenceValidationError as exc:
        raise EventValidationError(str(exc)) from exc


def get_event_occurrence_starts_in_range(
    event: RecurringEventLike,
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[datetime]:
    """Return occurrence start times that overlap the requested window."""
    if not event_is_recurring(event):
        return []
    normalized_window_start = normalize_storage_datetime(window_start)
    normalized_window_end = normalize_storage_datetime(window_end)
    return get_occurrence_starts_in_range(
        _build_event_series(event),
        window_start=normalized_window_start,
        window_end=normalized_window_end,
    )


async def ensure_event_area_exists(session: AsyncSession, area_id: UUID | None) -> None:
    """Ensure an optional event area reference exists."""
    await ensure_optional_reference_exists(
        session,
        model_cls=Area,
        model_id=area_id,
        not_found_error_factory=lambda missing_id: EventAreaReferenceNotFoundError(
            f"Area {missing_id} was not found"
        ),
    )


async def ensure_event_task_exists(session: AsyncSession, task_id: UUID | None) -> None:
    """Ensure an optional event task reference exists."""
    await ensure_optional_reference_exists(
        session,
        model_cls=Task,
        model_id=task_id,
        not_found_error_factory=lambda missing_id: EventTaskReferenceNotFoundError(
            f"Task {missing_id} was not found"
        ),
    )
