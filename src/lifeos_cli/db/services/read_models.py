"""Read models and builders for CLI-facing database services."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from lifeos_cli.db.models.event import Event
    from lifeos_cli.db.models.habit_action import HabitAction
    from lifeos_cli.db.models.note import Note
    from lifeos_cli.db.models.person import Person
    from lifeos_cli.db.models.tag import Tag
    from lifeos_cli.db.models.task import Task
    from lifeos_cli.db.models.timelog import Timelog
    from lifeos_cli.db.models.timelog_template import TimelogTemplate
    from lifeos_cli.db.models.vision import Vision


@dataclass(frozen=True)
class PersonSummaryView:
    """Lightweight person summary."""

    id: UUID
    name: str


@dataclass(frozen=True)
class TagSummaryView:
    """Lightweight tag summary."""

    id: UUID
    name: str
    entity_type: str | None = None
    category: str | None = None
    description: str | None = None
    color: str | None = None


@dataclass(frozen=True)
class TaskSummaryView:
    """Lightweight task summary."""

    id: UUID
    vision_id: UUID
    parent_task_id: UUID | None
    content: str
    status: str
    priority: int | None = None
    planning_cycle_type: str | None = None
    planning_cycle_start_date: date | None = None
    actual_effort_self: int | None = None
    actual_effort_total: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    vision_name: str | None = None
    parent_content: str | None = None


TaskSummaryDetails = Mapping[UUID, tuple[str | None, str | None]]


@dataclass(frozen=True)
class VisionSummaryView:
    """Lightweight vision summary."""

    id: UUID
    name: str
    status: str


@dataclass(frozen=True)
class EventSummaryView:
    """Lightweight event summary."""

    id: UUID
    title: str


@dataclass(frozen=True)
class TimelogSummaryView:
    """Lightweight timelog summary."""

    id: UUID
    title: str


@dataclass(frozen=True)
class HabitActionSummaryView:
    """Lightweight habit-action summary."""

    id: UUID
    habit_id: UUID
    habit_title: str | None
    action_date: date
    status: str


@dataclass(frozen=True)
class PersonView:
    """CLI-facing person record."""

    id: UUID
    name: str
    description: str | None
    nicknames: tuple[str, ...]
    birth_date: date | None
    location: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    tags: tuple[TagSummaryView, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TagView:
    """CLI-facing tag record."""

    id: UUID
    name: str
    entity_type: str
    category: str
    description: str | None
    color: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    person: tuple[PersonSummaryView, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TaskView:
    """CLI-facing task record."""

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
    person: tuple[PersonSummaryView, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class VisionView:
    """CLI-facing vision record."""

    id: UUID
    name: str
    description: str | None
    status: str
    stage: int
    experience_points: int
    experience_rate_per_hour: int | None
    area_id: UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    person: tuple[PersonSummaryView, ...] = field(default_factory=tuple)
    tasks: tuple[TaskSummaryView, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EventView:
    """CLI-facing event record."""

    id: UUID
    title: str
    description: str | None
    status: str
    event_type: str
    priority: int
    is_all_day: bool
    start_time: datetime
    end_time: datetime | None
    recurrence_frequency: str | None
    recurrence_interval: int | None
    recurrence_count: int | None
    recurrence_until: datetime | None
    recurrence_rule: dict[str, object] | None
    recurrence_parent_event_id: UUID | None
    recurrence_instance_start: datetime | None
    area_id: UUID | None
    task_id: UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    tags: tuple[TagSummaryView, ...] = field(default_factory=tuple)
    person: tuple[PersonSummaryView, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HabitActionView:
    """CLI-facing habit-action occurrence view."""

    id: UUID | None
    habit_id: UUID
    habit_title: str
    habit_cadence_frequency: str
    action_date: date
    status: str
    notes: str | None
    created_at: datetime | None
    updated_at: datetime | None
    deleted_at: datetime | None
    linked_notes_count: int


@dataclass(frozen=True)
class TimelogView:
    """CLI-facing timelog record."""

    id: UUID
    title: str
    tracking_method: str
    start_time: datetime
    end_time: datetime
    location: str | None
    energy_level: int | None
    notes: str | None
    area_id: UUID | None
    task_id: UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    linked_notes_count: int
    task: TaskSummaryView | None = None
    tags: tuple[TagSummaryView, ...] = field(default_factory=tuple)
    person: tuple[PersonSummaryView, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TimelogTemplateView:
    """Web-facing timelog quick template record."""

    id: UUID
    title: str
    area_id: UUID | None
    area_name: str | None
    area_color: str | None
    person_ids: tuple[UUID, ...]
    person: tuple[PersonSummaryView, ...]
    default_duration_minutes: int | None
    position: int
    usage_count: int
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True)
class NoteView:
    """CLI-facing note record."""

    id: UUID
    content: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    tags: tuple[TagSummaryView, ...] = field(default_factory=tuple)
    person: tuple[PersonSummaryView, ...] = field(default_factory=tuple)
    tasks: tuple[TaskSummaryView, ...] = field(default_factory=tuple)
    visions: tuple[VisionSummaryView, ...] = field(default_factory=tuple)
    events: tuple[EventSummaryView, ...] = field(default_factory=tuple)
    timelogs: tuple[TimelogSummaryView, ...] = field(default_factory=tuple)
    habit_actions: tuple[HabitActionSummaryView, ...] = field(default_factory=tuple)


def build_person_summary(person: Person) -> PersonSummaryView:
    """Build one person summary view from a person model."""
    return PersonSummaryView(id=person.id, name=person.name)


def build_tag_summary(tag: Tag) -> TagSummaryView:
    """Build one tag summary view from a tag model."""
    return TagSummaryView(
        id=tag.id,
        name=tag.name,
        entity_type=tag.entity_type,
        category=tag.category,
        description=tag.description,
        color=tag.color,
    )


def build_task_summary(
    task: Task,
    *,
    vision_name: str | None = None,
    parent_content: str | None = None,
) -> TaskSummaryView:
    """Build one task summary view from a task model."""
    return TaskSummaryView(
        id=task.id,
        vision_id=task.vision_id,
        parent_task_id=task.parent_task_id,
        content=task.content,
        status=task.status,
        priority=task.priority,
        planning_cycle_type=task.planning_cycle_type,
        planning_cycle_start_date=task.planning_cycle_start_date,
        actual_effort_self=task.actual_effort_self,
        actual_effort_total=task.actual_effort_total,
        created_at=task.created_at,
        updated_at=task.updated_at,
        vision_name=vision_name,
        parent_content=parent_content,
    )


def build_task_summary_with_details(
    task: Task,
    details: TaskSummaryDetails | None,
) -> TaskSummaryView:
    """Build a task summary enriched with tooltip-consumed vision/parent fields."""
    if not details:
        return build_task_summary(task)
    vision_name, parent_content = details.get(task.id, (None, None))
    return build_task_summary(
        task,
        vision_name=vision_name,
        parent_content=parent_content,
    )


def build_vision_summary(vision: Vision) -> VisionSummaryView:
    """Build one vision summary view from a vision model."""
    return VisionSummaryView(id=vision.id, name=vision.name, status=vision.status)


def build_event_summary(event: Event) -> EventSummaryView:
    """Build one event summary view from an event model."""
    return EventSummaryView(id=event.id, title=event.title)


def build_timelog_summary(timelog: Timelog) -> TimelogSummaryView:
    """Build one timelog summary view from a timelog model."""
    return TimelogSummaryView(id=timelog.id, title=timelog.title)


def build_habit_action_summary(action: HabitAction) -> HabitActionSummaryView:
    """Build one habit-action summary view from a habit action model."""
    return HabitActionSummaryView(
        id=action.id,
        habit_id=action.habit_id,
        habit_title=action.habit.title if action.habit is not None else None,
        action_date=action.action_date,
        status=action.status,
    )


def build_person_view(person: Person, *, tags: Sequence[Tag] = ()) -> PersonView:
    """Build one person view from a person model and related tags."""
    return PersonView(
        id=person.id,
        name=person.name,
        description=person.description,
        nicknames=tuple(person.nicknames or ()),
        birth_date=person.birth_date,
        location=person.location,
        created_at=person.created_at,
        updated_at=person.updated_at,
        deleted_at=person.deleted_at,
        tags=tuple(build_tag_summary(tag) for tag in tags),
    )


def build_tag_view(tag: Tag, *, person_records: Sequence[Person] = ()) -> TagView:
    """Build one tag view from a tag model and related person."""
    return TagView(
        id=tag.id,
        name=tag.name,
        entity_type=tag.entity_type,
        category=tag.category,
        description=tag.description,
        color=tag.color,
        created_at=tag.created_at,
        updated_at=tag.updated_at,
        deleted_at=tag.deleted_at,
        person=tuple(build_person_summary(person) for person in person_records),
    )


def build_task_view(task: Task, *, person_records: Sequence[Person] = ()) -> TaskView:
    """Build one task view from a task model and related person."""
    return TaskView(
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
        person=tuple(build_person_summary(person) for person in person_records),
    )


def build_vision_view(
    vision: Vision,
    *,
    person_records: Sequence[Person] = (),
    tasks: Sequence[Task] = (),
    task_summary_details: TaskSummaryDetails | None = None,
) -> VisionView:
    """Build one vision view from a vision model and related records."""
    return VisionView(
        id=vision.id,
        name=vision.name,
        description=vision.description,
        status=vision.status,
        stage=vision.stage,
        experience_points=vision.experience_points,
        experience_rate_per_hour=vision.experience_rate_per_hour,
        area_id=vision.area_id,
        created_at=vision.created_at,
        updated_at=vision.updated_at,
        deleted_at=vision.deleted_at,
        person=tuple(build_person_summary(person) for person in person_records),
        tasks=tuple(build_task_summary_with_details(task, task_summary_details) for task in tasks),
    )


def build_event_view(
    event: Event,
    *,
    tags: Sequence[Tag] = (),
    person_records: Sequence[Person] = (),
) -> EventView:
    """Build one event view from an event model and related records."""
    return EventView(
        id=event.id,
        title=event.title,
        description=event.description,
        status=event.status,
        event_type=event.event_type,
        priority=event.priority,
        is_all_day=event.is_all_day,
        start_time=event.start_time,
        end_time=event.end_time,
        recurrence_frequency=event.recurrence_frequency,
        recurrence_interval=event.recurrence_interval,
        recurrence_count=event.recurrence_count,
        recurrence_until=event.recurrence_until,
        recurrence_rule=event.recurrence_rule,
        recurrence_parent_event_id=event.recurrence_parent_event_id,
        recurrence_instance_start=event.recurrence_instance_start,
        area_id=event.area_id,
        task_id=event.task_id,
        created_at=event.created_at,
        updated_at=event.updated_at,
        deleted_at=event.deleted_at,
        tags=tuple(build_tag_summary(tag) for tag in tags),
        person=tuple(build_person_summary(person) for person in person_records),
    )


def build_timelog_view(
    timelog: Timelog,
    *,
    tags: Sequence[Tag] = (),
    person_records: Sequence[Person] = (),
    linked_notes_count: int = 0,
    task_summary_details: TaskSummaryDetails | None = None,
) -> TimelogView:
    """Build one timelog view from a timelog model and related records."""
    return TimelogView(
        id=timelog.id,
        title=timelog.title,
        tracking_method=timelog.tracking_method,
        start_time=timelog.start_time,
        end_time=timelog.end_time,
        location=timelog.location,
        energy_level=timelog.energy_level,
        notes=timelog.notes,
        area_id=timelog.area_id,
        task_id=timelog.task_id,
        created_at=timelog.created_at,
        updated_at=timelog.updated_at,
        deleted_at=timelog.deleted_at,
        linked_notes_count=linked_notes_count,
        task=(
            build_task_summary_with_details(timelog.task, task_summary_details)
            if timelog.task
            else None
        ),
        tags=tuple(build_tag_summary(tag) for tag in tags),
        person=tuple(build_person_summary(person) for person in person_records),
    )


def build_timelog_template_view(
    template: TimelogTemplate,
    *,
    person_records: Sequence[Person] = (),
) -> TimelogTemplateView:
    """Build one timelog quick template view from a model and linked person."""
    person_summaries = tuple(build_person_summary(person) for person in person_records)
    return TimelogTemplateView(
        id=template.id,
        title=template.title,
        area_id=template.area_id,
        area_name=template.area.name if template.area else None,
        area_color=template.area.color if template.area else None,
        person_ids=tuple(person.id for person in person_records),
        person=person_summaries,
        default_duration_minutes=template.default_duration_minutes,
        position=template.position,
        usage_count=template.usage_count,
        last_used_at=template.last_used_at,
        created_at=template.created_at,
        updated_at=template.updated_at,
        deleted_at=template.deleted_at,
    )


def build_note_view(
    note: Note,
    *,
    tags: Sequence[Tag] = (),
    person_records: Sequence[Person] = (),
    tasks: Sequence[Task] = (),
    visions: Sequence[Vision] = (),
    events: Sequence[Event] = (),
    timelogs: Sequence[Timelog] = (),
    habit_actions: Sequence[HabitAction] = (),
    task_summary_details: TaskSummaryDetails | None = None,
) -> NoteView:
    """Build one note view from a note model and linked records."""
    return NoteView(
        id=note.id,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
        deleted_at=note.deleted_at,
        tags=tuple(build_tag_summary(tag) for tag in tags),
        person=tuple(build_person_summary(person) for person in person_records),
        tasks=tuple(build_task_summary_with_details(task, task_summary_details) for task in tasks),
        visions=tuple(build_vision_summary(vision) for vision in visions),
        events=tuple(build_event_summary(event) for event in events),
        timelogs=tuple(build_timelog_summary(timelog) for timelog in timelogs),
        habit_actions=tuple(build_habit_action_summary(action) for action in habit_actions),
    )
