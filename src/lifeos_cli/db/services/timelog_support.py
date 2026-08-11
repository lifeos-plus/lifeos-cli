"""Support utilities and validations for timelog services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.services.model_utils import ensure_optional_reference_exists
from lifeos_cli.db.services.validation_utils import DomainValidationError, validate_choice

VALID_TIMELOG_TRACKING_METHODS = {"manual", "automatic", "imported"}


class TimelogNotFoundError(LookupError):
    """Raised when a timelog cannot be found."""


class TimelogAreaReferenceNotFoundError(LookupError):
    """Raised when a referenced area cannot be found."""


class TimelogTaskReferenceNotFoundError(LookupError):
    """Raised when a referenced task cannot be found."""


class TimelogValidationError(DomainValidationError):
    """Raised when timelog data is invalid."""


@dataclass(frozen=True)
class TimelogUpdateInput:
    """Normalized mutable fields for timelog update operations."""

    title: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    tracking_method: str | None = None
    location: str | None = None
    clear_location: bool = False
    energy_level: int | None = None
    clear_energy_level: bool = False
    notes: str | None = None
    clear_notes: bool = False
    area_id: UUID | None = None
    clear_area: bool = False
    task_id: UUID | None = None
    clear_task: bool = False
    tag_ids: list[UUID] | None = None
    clear_tags: bool = False
    person_ids: list[UUID] | None = None
    clear_people: bool = False

    def has_batch_update(self) -> bool:
        """Return whether this payload includes one batch-supported update."""
        return any(
            (
                self.title is not None,
                self.area_id is not None,
                self.clear_area,
                self.task_id is not None,
                self.clear_task,
                self.tag_ids is not None,
                self.clear_tags,
                self.person_ids is not None,
                self.clear_people,
            )
        )


@dataclass(frozen=True)
class TimelogCreateInput:
    """Normalized writable fields for timelog creation."""

    title: str
    start_time: datetime
    end_time: datetime
    tracking_method: str = "manual"
    location: str | None = None
    energy_level: int | None = None
    notes: str | None = None
    area_id: UUID | None = None
    task_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    person_ids: list[UUID] | None = None


@dataclass(frozen=True)
class TimelogBatchUpdateInput:
    """Batch-update intent for multiple timelogs."""

    title: str | None = None
    find_title_text: str | None = None
    replace_title_text: str = ""
    changes: TimelogUpdateInput = field(default_factory=TimelogUpdateInput)

    def has_non_title_update(self) -> bool:
        """Return whether the batch request includes non-title mutations."""
        return self.changes.has_batch_update()

    def has_update(self) -> bool:
        """Return whether the batch request includes any mutation."""
        return any(
            (self.title is not None, self.find_title_text is not None, self.has_non_title_update())
        )


@dataclass(frozen=True)
class TimelogQueryFilters:
    """Shared filter set for timelog list and count operations."""

    title_contains: str | None = None
    notes_contains: str | None = None
    query: str | None = None
    tracking_method: str | None = None
    area_id: UUID | None = None
    area_name: str | None = None
    without_area: bool = False
    task_id: UUID | None = None
    without_task: bool = False
    with_task: bool = False
    person_id: UUID | None = None
    tag_id: UUID | None = None
    date_values: tuple[date, ...] = ()
    start_date: date | None = None
    end_date: date | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


@dataclass(frozen=True)
class TimelogListInput:
    """List intent for timelog queries with pagination."""

    filters: TimelogQueryFilters = field(default_factory=TimelogQueryFilters)
    limit: int = 100
    offset: int = 0


def validate_timelog_title(title: str) -> str:
    """Validate and normalize a timelog title."""
    normalized = title.strip()
    if not normalized:
        raise TimelogValidationError("Timelog title must not be empty")
    if len(normalized) > 200:
        raise TimelogValidationError("Timelog title must be 200 characters or fewer")
    return normalized


def validate_timelog_time_range(*, start_time: datetime, end_time: datetime) -> None:
    """Validate a timelog time range."""
    if end_time < start_time:
        raise TimelogValidationError("Timelog end time must be on or after the start time")


def validate_tracking_method(tracking_method: str) -> str:
    """Validate and normalize a tracking method."""
    return validate_choice(
        tracking_method,
        VALID_TIMELOG_TRACKING_METHODS,
        error_cls=TimelogValidationError,
        label="tracking method",
    )


def validate_energy_level(energy_level: int | None) -> int | None:
    """Validate an optional energy level."""
    if energy_level is None:
        return None
    if energy_level < 1 or energy_level > 5:
        raise TimelogValidationError("Energy level must be between 1 and 5")
    return energy_level


async def ensure_timelog_area_exists(session: AsyncSession, area_id: UUID | None) -> None:
    """Ensure an optional timelog area reference exists."""
    await ensure_optional_reference_exists(
        session,
        model_cls=Area,
        model_id=area_id,
        not_found_error_factory=lambda missing_id: TimelogAreaReferenceNotFoundError(
            f"Area {missing_id} was not found"
        ),
    )


async def ensure_timelog_task_exists(session: AsyncSession, task_id: UUID | None) -> None:
    """Ensure an optional timelog task reference exists."""
    await ensure_optional_reference_exists(
        session,
        model_cls=Task,
        model_id=task_id,
        not_found_error_factory=lambda missing_id: TimelogTaskReferenceNotFoundError(
            f"Task {missing_id} was not found"
        ),
    )
