"""Pydantic schemas for the local LifeOS Web API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

PositiveIntField = Annotated[int, Field(ge=1)]


class Pagination(BaseModel):
    """Frontend-compatible pagination metadata."""

    page: int
    size: int
    total: int
    pages: int


ItemT = TypeVar("ItemT")
MetaT = TypeVar("MetaT")


class ListResponse(BaseModel, Generic[ItemT, MetaT]):
    """Frontend-compatible list envelope."""

    items: list[ItemT]
    pagination: Pagination
    meta: MetaT


class TaskCreate(BaseModel):
    """Payload for creating a task from the Web planning UI."""

    vision_id: UUID
    parent_task_id: UUID | None = None
    content: str
    priority: int = 0
    display_order: int = 0
    estimated_effort: int | None = None
    planning_cycle_type: str | None = None
    planning_cycle_days: int | None = None
    planning_cycle_start_date: date | None = None


class TaskUpdate(BaseModel):
    """Payload for updating a task from the Web planning UI."""

    content: str | None = None
    status: str | None = None
    priority: int | None = None
    display_order: int | None = None
    estimated_effort: int | None = None
    parent_task_id: UUID | None = None
    planning_cycle_type: str | None = None
    planning_cycle_days: int | None = None
    planning_cycle_start_date: date | None = None


class TaskStatusUpdate(BaseModel):
    """Payload for updating just a task status."""

    status: str


class TaskReorderItem(BaseModel):
    """One task display-order update."""

    id: UUID
    display_order: int


class TaskReorderRequest(BaseModel):
    """Payload for reordering tasks from the Web UI."""

    task_orders: list[TaskReorderItem] = Field(default_factory=list)


class NoteCreate(BaseModel):
    """Payload for creating a note from the Web UI."""

    content: str
    person_ids: list[UUID] | None = None
    tag_ids: list[UUID] | None = None
    task_id: UUID | None = None
    timelog_ids: list[UUID] | None = None
    habit_action_ids: list[UUID] | None = None


class NoteUpdate(BaseModel):
    """Payload for updating a note from the Web UI."""

    content: str | None = None
    person_ids: list[UUID] | None = None
    tag_ids: list[UUID] | None = None
    task_id: UUID | None = None
    timelog_ids: list[UUID] | None = None
    habit_action_ids: list[UUID] | None = None


class TagCreate(BaseModel):
    """Payload for creating a tag from the Web UI."""

    name: str
    entity_type: str = "note"
    category: str = "general"
    description: str | None = None
    color: str | None = None


class TagUpdate(BaseModel):
    """Payload for updating a tag from the Web UI."""

    name: str | None = None
    entity_type: str | None = None
    category: str | None = None
    description: str | None = None
    color: str | None = None


class TagCategoryCreate(BaseModel):
    """Payload for creating a tag category option from the Web UI."""

    label: str
    value: str | None = None


class TagCategoryUpdate(BaseModel):
    """Payload for renaming a tag category from the Web UI."""

    label: str


class TagBulkCategoryUpdate(BaseModel):
    """Payload for moving existing tags to another category."""

    ids: list[UUID] = Field(default_factory=list)
    category: str


class VisionCreate(BaseModel):
    """Payload for creating a vision from the Web UI."""

    name: str
    description: str | None = None
    status: str = "active"
    area_id: UUID | None = None
    person_ids: list[UUID] | None = None
    experience_rate_per_hour: int | None = None


class VisionUpdate(BaseModel):
    """Payload for updating a vision from the Web UI."""

    name: str | None = None
    description: str | None = None
    status: str | None = None
    area_id: UUID | None = None
    person_ids: list[UUID] | None = None
    experience_rate_per_hour: int | None = None


class HabitCreate(BaseModel):
    """Payload for creating a habit from the Web UI."""

    title: str
    description: str | None = None
    start_date: date
    duration_days: PositiveIntField | None = None
    end_date: date | None = None
    repeat_count: PositiveIntField | None = None
    cadence_frequency: str | None = None
    cadence_weekdays: list[str] | None = None
    cadence_monthdays: list[int] | None = None
    target_per_cycle: int | None = None
    task_id: UUID | None = None


class HabitUpdate(BaseModel):
    """Payload for updating a habit from the Web UI."""

    title: str | None = None
    description: str | None = None
    start_date: date | None = None
    duration_days: PositiveIntField | None = None
    end_date: date | None = None
    repeat_count: PositiveIntField | None = None
    cadence_frequency: str | None = None
    cadence_weekdays: list[str] | None = None
    cadence_monthdays: list[int] | None = None
    target_per_cycle: int | None = None
    status: str | None = None
    task_id: UUID | None = None


class HabitActionUpdate(BaseModel):
    """Payload for updating a habit action."""

    status: str | None = None
    notes: str | None = None


class TimelogCreate(BaseModel):
    """Payload for creating a timelog from the Web UI."""

    title: str
    start_time: datetime
    end_time: datetime
    tracking_method: str = "manual"
    location: str | None = None
    energy_level: int | None = Field(None, ge=1, le=5)
    notes: str | None = None
    area_id: UUID | None = None
    task_id: UUID | None = None
    person_ids: list[UUID] | None = None


class TimelogUpdate(BaseModel):
    """Payload for updating a timelog from the Web UI."""

    title: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    tracking_method: str | None = None
    location: str | None = None
    energy_level: int | None = Field(None, ge=1, le=5)
    notes: str | None = None
    area_id: UUID | None = None
    task_id: UUID | None = None
    person_ids: list[UUID] | None = None


class TimelogBatchTitleUpdate(BaseModel):
    """Title update payload for timelog batch edits."""

    mode: str = "replace"
    value: str
    find: str | None = None


class TimelogBatchTaskUpdate(BaseModel):
    """Task update payload for timelog batch edits."""

    mode: str = "replace"
    task_id: UUID | None = None


class TimelogBatchAreaUpdate(BaseModel):
    """Area update payload for timelog batch edits."""

    area_id: UUID | None = None


class TimelogBatchPersonUpdate(BaseModel):
    """Person association update payload for timelog batch edits."""

    mode: str = "replace"
    person_ids: list[UUID] = Field(default_factory=list)


class TimelogBatchUpdate(BaseModel):
    """Payload for updating multiple timelogs from the Web UI."""

    timelog_ids: list[UUID]
    update_type: str
    title: TimelogBatchTitleUpdate | None = None
    task: TimelogBatchTaskUpdate | None = None
    area: TimelogBatchAreaUpdate | None = None
    person: TimelogBatchPersonUpdate | None = None


class TimelogTemplateCreate(BaseModel):
    """Payload for creating a timelog quick template from the Web UI."""

    title: str = Field(..., min_length=1, max_length=200)
    area_id: UUID | None = None
    person_ids: list[UUID] | None = None
    default_duration_minutes: int | None = Field(None, ge=1, le=1440)
    position: int | None = Field(None, ge=0)
    usage_count: int = Field(0, ge=0)
    last_used_at: datetime | None = None


class TimelogTemplateUpdate(BaseModel):
    """Payload for updating a timelog quick template from the Web UI."""

    title: str | None = Field(None, min_length=1, max_length=200)
    area_id: UUID | None = None
    person_ids: list[UUID] | None = None
    default_duration_minutes: int | None = Field(None, ge=1, le=1440)
    position: int | None = Field(None, ge=0)
    usage_count: int | None = Field(None, ge=0)
    last_used_at: datetime | None = None


class TimelogTemplateReorderItem(BaseModel):
    """One timelog template display-order update."""

    id: UUID
    position: int = Field(..., ge=0)


class TimelogTemplateReorderRequest(BaseModel):
    """Payload for reordering timelog quick templates."""

    items: list[TimelogTemplateReorderItem] = Field(default_factory=list)


class TimelogTemplateBulkCreateRequest(BaseModel):
    """Payload for creating multiple timelog quick templates."""

    items: list[TimelogTemplateCreate] = Field(default_factory=list)


class PlannedEventCreate(BaseModel):
    """Frontend-compatible planned event creation payload backed by LifeOS Event records."""

    title: str
    start_time: datetime
    end_time: datetime | None = None
    priority: int = 0
    area_id: UUID | None = None
    task_id: UUID | None = None
    is_all_day: bool = False
    is_recurring: bool = False
    recurrence_pattern: dict[str, Any] | None = None
    rrule_string: str | None = None
    status: str = "planned"
    tags: list[str] | None = None
    person_ids: list[UUID] | None = None


class PlannedEventUpdate(BaseModel):
    """Frontend-compatible planned event update payload backed by LifeOS Event records."""

    title: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    priority: int | None = None
    area_id: UUID | None = None
    task_id: UUID | None = None
    is_all_day: bool | None = None
    is_recurring: bool | None = None
    recurrence_pattern: dict[str, Any] | None = None
    rrule_string: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    person_ids: list[UUID] | None = None


class HealthResponse(BaseModel):
    """LifeOS Web UI health payload."""

    status: str
    timestamp: datetime
