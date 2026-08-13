"""Async CRUD helpers for events."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lifeos_cli.application.datetime_utils import normalize_storage_datetime
from lifeos_cli.application.time_preferences import (
    get_utc_window_for_local_date_range,
    to_storage_timezone,
)
from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.association import Association
from lifeos_cli.db.models.event import Event
from lifeos_cli.db.models.event_occurrence_exception import EventOccurrenceException
from lifeos_cli.db.models.tag_association import tag_associations
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.services.batching import BatchDeleteResult, batch_delete_records
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.entity_people import load_people_for_entities, sync_entity_people
from lifeos_cli.db.services.entity_tags import load_tags_for_entities, sync_entity_tags
from lifeos_cli.db.services.event_support import (
    EventAreaReferenceNotFoundError as EventAreaReferenceNotFoundError,
)
from lifeos_cli.db.services.event_support import (
    EventCreateInput,
    EventListInput,
    EventNotFoundError,
    EventOccurrenceQuery,
    EventQueryFilters,
    EventUpdateInput,
    EventValidationError,
    ensure_event_area_exists,
    ensure_event_task_exists,
    event_is_recurring,
    get_event_occurrence_index,
    get_event_occurrence_starts_in_range,
    get_previous_event_occurrence_start,
    validate_event_instance_start,
    validate_event_priority,
    validate_event_recurrence,
    validate_event_scope,
    validate_event_status,
    validate_event_time_range,
    validate_event_title,
    validate_event_type,
)
from lifeos_cli.db.services.event_support import (
    EventTaskReferenceNotFoundError as EventTaskReferenceNotFoundError,
)
from lifeos_cli.db.services.read_models import EventView, build_event_view


@dataclass(frozen=True)
class EventOccurrence:
    """Expanded event occurrence read model."""

    id: UUID
    title: str
    status: str
    event_type: str
    start_time: datetime
    end_time: datetime | None
    task_id: UUID | None
    deleted_at: datetime | None
    instance_start: datetime


@dataclass(frozen=True)
class _DerivedEventCreateOptions:
    start_time: datetime
    end_time: datetime | None
    tag_ids: list[UUID]
    person_ids: list[UUID]
    recurrence_frequency: str | None = None
    recurrence_interval: int | None = None
    recurrence_count: int | None = None
    recurrence_until: datetime | None = None
    recurrence_rule: dict[str, object] | None = None
    recurrence_parent_event_id: UUID | None = None
    recurrence_instance_start: datetime | None = None


async def _build_event_views(session: AsyncSession, events: list[Event]) -> list[EventView]:
    if not events:
        return []
    event_ids = [event.id for event in events]
    tags_map = await load_tags_for_entities(session, entity_ids=event_ids, entity_type="event")
    people_map = await load_people_for_entities(session, entity_ids=event_ids, entity_type="event")
    return [
        build_event_view(
            event,
            tags=tags_map.get(event.id, ()),
            people=people_map.get(event.id, ()),
        )
        for event in events
    ]


async def _build_event_view(session: AsyncSession, event: Event) -> EventView:
    views = await _build_event_views(session, [event])
    return views[0]


async def _get_event_model(
    session: AsyncSession,
    *,
    event_id: UUID,
) -> Event | None:
    stmt = (
        select(Event)
        .options(
            selectinload(Event.area.and_(Area.deleted_at.is_(None))),
            selectinload(Event.task.and_(Task.deleted_at.is_(None))),
        )
        .where(Event.id == event_id)
        .limit(1)
    )
    stmt = stmt.where(Event.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


def _event_duration(event: Event | EventOccurrence) -> timedelta | None:
    start_time = normalize_storage_datetime(event.start_time)
    end_time = normalize_storage_datetime(event.end_time)
    if end_time is None:
        return None
    return end_time - start_time


def _event_overlaps_window(
    event: Event | EventOccurrence,
    *,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    start_time = normalize_storage_datetime(event.start_time)
    end_time = normalize_storage_datetime(event.end_time)
    window_start = normalize_storage_datetime(window_start)
    window_end = normalize_storage_datetime(window_end)
    return start_time <= window_end and (end_time is None or end_time >= window_start)


def _event_occurrence_end(
    event: Event | EventOccurrence,
    *,
    occurrence_start: datetime,
) -> datetime | None:
    duration = _event_duration(event)
    return occurrence_start + duration if duration is not None else None


async def _record_skip_exception(
    session: AsyncSession,
    *,
    master_event_id: UUID,
    instance_start: datetime,
) -> None:
    stmt = (
        select(EventOccurrenceException)
        .where(
            EventOccurrenceException.master_event_id == master_event_id,
            EventOccurrenceException.instance_start == instance_start,
        )
        .limit(1)
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        existing.action = "skip"
        return
    session.add(
        EventOccurrenceException(
            master_event_id=master_event_id,
            action="skip",
            instance_start=instance_start,
        )
    )


async def _load_skip_exceptions(
    session: AsyncSession,
    *,
    master_event_ids: list[UUID],
) -> dict[UUID, set[datetime]]:
    if not master_event_ids:
        return {}
    stmt = select(EventOccurrenceException).where(
        EventOccurrenceException.master_event_id.in_(master_event_ids),
        EventOccurrenceException.deleted_at.is_(None),
    )
    rows = list((await session.execute(stmt)).scalars())
    result: dict[UUID, set[datetime]] = {}
    for row in rows:
        instance_start = normalize_storage_datetime(row.instance_start)
        result.setdefault(row.master_event_id, set()).add(instance_start)
    return result


async def _get_override_event_for_instance(
    session: AsyncSession,
    *,
    master_event_id: UUID,
    instance_start: datetime,
) -> Event | None:
    stmt = (
        select(Event)
        .where(
            Event.deleted_at.is_(None),
            Event.recurrence_parent_event_id == master_event_id,
            Event.recurrence_instance_start == instance_start,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _resolve_link_ids(
    *,
    explicit_ids: list[UUID] | None,
    clear_flag: bool,
    existing_ids: list[UUID] | None,
) -> list[UUID]:
    if clear_flag:
        return []
    if explicit_ids is not None:
        return explicit_ids
    return list(existing_ids or [])


async def _apply_event_links(
    session: AsyncSession,
    *,
    event: Event,
    tag_ids: list[UUID] | None,
    person_ids: list[UUID] | None,
) -> None:
    if tag_ids is not None:
        await sync_entity_tags(
            session,
            entity_id=event.id,
            entity_type="event",
            desired_tag_ids=tag_ids,
        )
    if person_ids is not None:
        await sync_entity_people(
            session,
            entity_id=event.id,
            entity_type="event",
            desired_person_ids=person_ids,
        )


def _resolve_updated_reference_id(
    *,
    explicit_id: UUID | None,
    clear_flag: bool,
    existing_id: UUID | None,
) -> UUID | None:
    if clear_flag:
        return None
    if explicit_id is not None:
        return explicit_id
    return existing_id


def _resolve_event_description(event: Event, changes: EventUpdateInput) -> str | None:
    if changes.clear_description:
        return None
    if changes.description is not None:
        return changes.description
    return event.description


def _resolve_event_times(
    event: Event,
    changes: EventUpdateInput,
) -> tuple[datetime | None, datetime | None, datetime]:
    normalized_start_time = (
        to_storage_timezone(changes.start_time) if changes.start_time is not None else None
    )
    normalized_end_time = to_storage_timezone(changes.end_time) if changes.end_time else None
    next_start_time = (
        normalized_start_time if normalized_start_time is not None else event.start_time
    )
    next_end_time = (
        None
        if changes.clear_end_time
        else normalized_end_time
        if normalized_end_time is not None
        else event.end_time
    )
    validate_event_time_range(start_time=next_start_time, end_time=next_end_time)
    return normalized_start_time, normalized_end_time, next_start_time


def _resolve_event_recurrence_update(
    event: Event,
    changes: EventUpdateInput,
    *,
    next_start_time: datetime,
) -> tuple[str | None, int | None, int | None, datetime | None, dict[str, object] | None]:
    normalized_recurrence_until = (
        to_storage_timezone(changes.recurrence_until) if changes.recurrence_until else None
    )
    next_recurrence_frequency = (
        None
        if changes.clear_recurrence
        else changes.recurrence_frequency
        if changes.recurrence_frequency is not None
        else event.recurrence_frequency
    )
    next_recurrence_interval = (
        None
        if changes.clear_recurrence
        else changes.recurrence_interval
        if changes.recurrence_interval is not None
        else event.recurrence_interval
    )
    next_recurrence_count = (
        None
        if changes.clear_recurrence
        else changes.recurrence_count
        if changes.recurrence_count is not None
        else event.recurrence_count
    )
    next_recurrence_until = (
        None
        if changes.clear_recurrence
        else normalized_recurrence_until
        if normalized_recurrence_until is not None
        else event.recurrence_until
    )
    next_recurrence_rule = (
        None
        if changes.clear_recurrence or changes.clear_recurrence_rule
        else changes.recurrence_rule
        if changes.recurrence_rule is not None
        else getattr(event, "recurrence_rule", None)
    )
    return validate_event_recurrence(
        start_time=next_start_time,
        recurrence_frequency=next_recurrence_frequency,
        recurrence_interval=next_recurrence_interval,
        recurrence_count=next_recurrence_count,
        recurrence_until=next_recurrence_until,
        recurrence_rule=next_recurrence_rule,
    )


def _apply_event_scalar_updates(
    event: Event,
    changes: EventUpdateInput,
    *,
    normalized_start_time: datetime | None,
    normalized_end_time: datetime | None,
) -> None:
    if changes.title is not None:
        event.title = validate_event_title(changes.title)
    event.description = _resolve_event_description(event, changes)
    if normalized_start_time is not None:
        event.start_time = normalized_start_time
    event.end_time = (
        None
        if changes.clear_end_time
        else normalized_end_time
        if normalized_end_time is not None
        else event.end_time
    )
    if changes.priority is not None:
        event.priority = validate_event_priority(changes.priority)
    if changes.status is not None:
        event.status = validate_event_status(changes.status)
    if changes.event_type is not None:
        event.event_type = validate_event_type(changes.event_type)
    if changes.is_all_day is not None:
        event.is_all_day = changes.is_all_day


async def _apply_event_reference_updates(
    session: AsyncSession,
    *,
    event: Event,
    changes: EventUpdateInput,
) -> None:
    next_area_id = _resolve_updated_reference_id(
        explicit_id=changes.area_id,
        clear_flag=changes.clear_area,
        existing_id=event.area_id,
    )
    next_task_id = _resolve_updated_reference_id(
        explicit_id=changes.task_id,
        clear_flag=changes.clear_task,
        existing_id=event.task_id,
    )
    if next_area_id != event.area_id:
        await ensure_event_area_exists(session, next_area_id)
        event.area_id = next_area_id
    if next_task_id != event.task_id:
        await ensure_event_task_exists(session, next_task_id)
        event.task_id = next_task_id


async def _apply_event_association_updates(
    session: AsyncSession,
    *,
    event: Event,
    changes: EventUpdateInput,
) -> None:
    next_tag_ids = [] if changes.clear_tags else changes.tag_ids
    next_person_ids = [] if changes.clear_people else changes.person_ids
    await _apply_event_links(
        session,
        event=event,
        tag_ids=next_tag_ids,
        person_ids=next_person_ids,
    )


def _resolve_event_create_description(
    master_event: Event,
    changes: EventUpdateInput,
) -> str | None:
    if changes.clear_description:
        return None
    if changes.description is not None:
        return changes.description
    return master_event.description


def _resolve_event_create_reference_id(
    *,
    explicit_id: UUID | None,
    clear_flag: bool,
    existing_id: UUID | None,
) -> UUID | None:
    if clear_flag:
        return None
    if explicit_id is not None:
        return explicit_id
    return existing_id


async def _resolve_derived_event_association_ids(
    session: AsyncSession,
    *,
    source_event: Event,
    changes: EventUpdateInput,
) -> tuple[list[UUID], list[UUID]]:
    existing_tag_map = await load_tags_for_entities(
        session,
        entity_ids=[source_event.id],
        entity_type="event",
    )
    existing_people_map = await load_people_for_entities(
        session,
        entity_ids=[source_event.id],
        entity_type="event",
    )
    existing_tag_ids = [tag.id for tag in existing_tag_map.get(source_event.id, ())]
    existing_person_ids = [person.id for person in existing_people_map.get(source_event.id, ())]
    return (
        _resolve_link_ids(
            explicit_ids=changes.tag_ids,
            clear_flag=changes.clear_tags,
            existing_ids=existing_tag_ids,
        ),
        _resolve_link_ids(
            explicit_ids=changes.person_ids,
            clear_flag=changes.clear_people,
            existing_ids=existing_person_ids,
        ),
    )


def _build_derived_event_create_input(
    master_event: Event,
    changes: EventUpdateInput,
    *,
    options: _DerivedEventCreateOptions,
) -> EventCreateInput:
    return EventCreateInput(
        title=changes.title or master_event.title,
        description=_resolve_event_create_description(master_event, changes),
        start_time=options.start_time,
        end_time=options.end_time,
        priority=changes.priority if changes.priority is not None else master_event.priority,
        status=changes.status or master_event.status,
        event_type=changes.event_type or master_event.event_type,
        is_all_day=(
            changes.is_all_day if changes.is_all_day is not None else master_event.is_all_day
        ),
        area_id=_resolve_event_create_reference_id(
            explicit_id=changes.area_id,
            clear_flag=changes.clear_area,
            existing_id=master_event.area_id,
        ),
        task_id=_resolve_event_create_reference_id(
            explicit_id=changes.task_id,
            clear_flag=changes.clear_task,
            existing_id=master_event.task_id,
        ),
        tag_ids=options.tag_ids,
        person_ids=options.person_ids,
        recurrence_frequency=options.recurrence_frequency,
        recurrence_interval=options.recurrence_interval,
        recurrence_count=options.recurrence_count,
        recurrence_until=options.recurrence_until,
        recurrence_rule=options.recurrence_rule,
        recurrence_parent_event_id=options.recurrence_parent_event_id,
        recurrence_instance_start=options.recurrence_instance_start,
    )


def _normalize_event_filters(filters: EventQueryFilters) -> EventQueryFilters:
    normalized_status = (
        validate_event_status(filters.status) if filters.status is not None else None
    )
    normalized_event_type = (
        validate_event_type(filters.event_type) if filters.event_type is not None else None
    )
    return EventQueryFilters(
        title_contains=filters.title_contains,
        status=normalized_status,
        event_type=normalized_event_type,
        area_id=filters.area_id,
        task_id=filters.task_id,
        person_id=filters.person_id,
        tag_id=filters.tag_id,
        date_values=tuple(deduplicate_preserving_order(filters.date_values)),
        start_date=filters.start_date,
        end_date=filters.end_date,
        window_start=filters.window_start,
        window_end=filters.window_end,
    )


def _apply_event_query_filters(stmt: Any, *, filters: EventQueryFilters) -> Any:
    if filters.title_contains:
        stmt = stmt.where(Event.title.ilike(f"%{filters.title_contains.strip()}%"))
    if filters.status is not None:
        stmt = stmt.where(Event.status == filters.status)
    if filters.event_type is not None:
        stmt = stmt.where(Event.event_type == filters.event_type)
    if filters.area_id is not None:
        stmt = stmt.where(Event.area_id == filters.area_id)
    if filters.task_id is not None:
        stmt = stmt.where(Event.task_id == filters.task_id)
    if filters.person_id is not None:
        stmt = stmt.join(
            Association,
            (Association.source_model == "event")
            & (Association.source_id == Event.id)
            & (Association.target_model == "person"),
        ).where(Association.target_id == filters.person_id)
    if filters.tag_id is not None:
        stmt = stmt.join(
            tag_associations,
            (tag_associations.c.entity_id == Event.id)
            & (tag_associations.c.entity_type == "event"),
        ).where(tag_associations.c.tag_id == filters.tag_id)
    return stmt


def _resolve_event_list_filters(filters: EventQueryFilters) -> EventQueryFilters:
    normalized = _normalize_event_filters(filters)
    if normalized.start_date is not None and normalized.end_date is not None:
        window_start, window_end = get_utc_window_for_local_date_range(
            normalized.start_date,
            normalized.end_date,
        )
        return EventQueryFilters(
            title_contains=normalized.title_contains,
            status=normalized.status,
            event_type=normalized.event_type,
            area_id=normalized.area_id,
            task_id=normalized.task_id,
            person_id=normalized.person_id,
            tag_id=normalized.tag_id,
            date_values=normalized.date_values,
            window_start=window_start,
            window_end=window_end,
        )
    return normalized


def _event_list_item_key(item: EventOccurrence | EventView) -> tuple[UUID, datetime]:
    instance_start = item.instance_start if isinstance(item, EventOccurrence) else item.start_time
    return item.id, instance_start


async def _list_events_for_discrete_dates(
    session: AsyncSession,
    *,
    filters: EventQueryFilters,
    offset: int,
    limit: int,
) -> list[EventOccurrence | EventView]:
    items_by_key: dict[tuple[UUID, datetime], EventOccurrence | EventView] = {}
    for target_date in filters.date_values:
        window_start, window_end = get_utc_window_for_local_date_range(target_date, target_date)
        occurrences = await list_event_occurrences(
            session,
            query=EventOccurrenceQuery(
                window_start=window_start,
                window_end=window_end,
                filters=replace(
                    filters,
                    date_values=(),
                    window_start=window_start,
                    window_end=window_end,
                ),
            ),
        )
        for item in occurrences:
            items_by_key.setdefault(_event_list_item_key(item), item)
    sorted_items = sorted(items_by_key.values(), key=lambda item: (item.start_time, item.id))
    return sorted_items[offset : offset + limit]


async def create_event(
    session: AsyncSession,
    *,
    payload: EventCreateInput,
) -> EventView:
    """Create a new event."""
    normalized_start_time = to_storage_timezone(payload.start_time)
    normalized_end_time = to_storage_timezone(payload.end_time) if payload.end_time else None
    normalized_recurrence_until = (
        to_storage_timezone(payload.recurrence_until) if payload.recurrence_until else None
    )
    normalized_instance_start = (
        to_storage_timezone(payload.recurrence_instance_start)
        if payload.recurrence_instance_start
        else None
    )
    normalized_title = validate_event_title(payload.title)
    validate_event_time_range(start_time=normalized_start_time, end_time=normalized_end_time)
    normalized_priority = validate_event_priority(payload.priority)
    normalized_status = validate_event_status(payload.status)
    normalized_event_type = validate_event_type(payload.event_type)
    (
        normalized_recurrence_frequency,
        normalized_recurrence_interval,
        normalized_recurrence_count,
        normalized_recurrence_until,
        normalized_recurrence_rule,
    ) = validate_event_recurrence(
        start_time=normalized_start_time,
        recurrence_frequency=payload.recurrence_frequency,
        recurrence_interval=payload.recurrence_interval,
        recurrence_count=payload.recurrence_count,
        recurrence_until=normalized_recurrence_until,
        recurrence_rule=payload.recurrence_rule,
    )
    await ensure_event_area_exists(session, payload.area_id)
    await ensure_event_task_exists(session, payload.task_id)
    event = Event(
        title=normalized_title,
        start_time=normalized_start_time,
        end_time=normalized_end_time,
        description=payload.description,
        priority=normalized_priority,
        status=normalized_status,
        event_type=normalized_event_type,
        is_all_day=payload.is_all_day,
        area_id=payload.area_id,
        task_id=payload.task_id,
        recurrence_frequency=normalized_recurrence_frequency,
        recurrence_interval=normalized_recurrence_interval,
        recurrence_count=normalized_recurrence_count,
        recurrence_until=normalized_recurrence_until,
        recurrence_rule=normalized_recurrence_rule,
        recurrence_parent_event_id=payload.recurrence_parent_event_id,
        recurrence_instance_start=normalized_instance_start,
    )
    session.add(event)
    await session.flush()
    await _apply_event_links(
        session,
        event=event,
        tag_ids=payload.tag_ids,
        person_ids=payload.person_ids,
    )
    await session.refresh(event)
    return await _build_event_view(session, event)


async def get_event(
    session: AsyncSession,
    *,
    event_id: UUID,
) -> EventView | None:
    """Load an event by identifier."""
    event = await _get_event_model(session, event_id=event_id)
    if event is None:
        return None
    return await _build_event_view(session, event)


async def list_event_occurrences(
    session: AsyncSession,
    *,
    query: EventOccurrenceQuery,
) -> list[EventOccurrence]:
    """List expanded event occurrences that overlap one time window."""
    normalized_filters = _normalize_event_filters(query.filters)
    window_start = query.window_start
    window_end = query.window_end

    master_stmt = select(Event).where(
        Event.recurrence_parent_event_id.is_(None),
        Event.start_time <= window_end,
        or_(
            Event.recurrence_frequency.is_not(None),
            Event.end_time.is_(None),
            Event.end_time >= window_start,
        ),
    )
    master_stmt = master_stmt.where(Event.deleted_at.is_(None))
    master_stmt = _apply_event_query_filters(master_stmt, filters=normalized_filters)
    masters = list((await session.execute(master_stmt)).scalars())
    master_ids = [event.id for event in masters if event_is_recurring(event)]
    skip_map = await _load_skip_exceptions(session, master_event_ids=master_ids)

    override_stmt = select(Event).where(
        Event.recurrence_parent_event_id.is_not(None),
        Event.start_time <= window_end,
        or_(Event.end_time.is_(None), Event.end_time >= window_start),
    )
    override_stmt = override_stmt.where(Event.deleted_at.is_(None))
    override_stmt = _apply_event_query_filters(override_stmt, filters=normalized_filters)
    overrides = list((await session.execute(override_stmt)).scalars())
    override_keys = {
        (
            override.recurrence_parent_event_id,
            normalize_storage_datetime(override.recurrence_instance_start),
        ): override
        for override in overrides
        if override.recurrence_parent_event_id is not None
        and override.recurrence_instance_start is not None
    }

    occurrences: list[EventOccurrence] = []
    for master in masters:
        if not event_is_recurring(master):
            if _event_overlaps_window(master, window_start=window_start, window_end=window_end):
                start_time = normalize_storage_datetime(master.start_time)
                occurrences.append(
                    EventOccurrence(
                        id=master.id,
                        title=master.title,
                        status=master.status,
                        event_type=master.event_type,
                        start_time=start_time,
                        end_time=normalize_storage_datetime(master.end_time),
                        task_id=master.task_id,
                        deleted_at=normalize_storage_datetime(master.deleted_at),
                        instance_start=start_time,
                    )
                )
            continue

        for occurrence_start in get_event_occurrence_starts_in_range(
            master,
            window_start=window_start,
            window_end=window_end,
        ):
            if occurrence_start in skip_map.get(master.id, set()):
                continue
            if (master.id, occurrence_start) in override_keys:
                continue
            occurrences.append(
                EventOccurrence(
                    id=master.id,
                    title=master.title,
                    status=master.status,
                    event_type=master.event_type,
                    start_time=occurrence_start,
                    end_time=_event_occurrence_end(master, occurrence_start=occurrence_start),
                    task_id=master.task_id,
                    deleted_at=master.deleted_at,
                    instance_start=occurrence_start,
                )
            )

    for override in overrides:
        override_start = normalize_storage_datetime(override.start_time)
        occurrences.append(
            EventOccurrence(
                id=override.id,
                title=override.title,
                status=override.status,
                event_type=override.event_type,
                start_time=override_start,
                end_time=normalize_storage_datetime(override.end_time),
                task_id=override.task_id,
                deleted_at=normalize_storage_datetime(override.deleted_at),
                instance_start=(
                    normalize_storage_datetime(override.recurrence_instance_start) or override_start
                ),
            )
        )

    return sorted(occurrences, key=lambda item: (item.start_time, item.id))


async def list_events(
    session: AsyncSession,
    *,
    query: EventListInput,
) -> list[EventOccurrence | EventView]:
    """List events with optional filters."""
    resolved_filters = _resolve_event_list_filters(query.filters)
    if resolved_filters.date_values:
        return await _list_events_for_discrete_dates(
            session,
            filters=resolved_filters,
            offset=query.offset,
            limit=query.limit,
        )
    window_start = resolved_filters.window_start
    window_end = resolved_filters.window_end

    if window_start is not None and window_end is not None:
        occurrences = await list_event_occurrences(
            session,
            query=EventOccurrenceQuery(
                window_start=window_start,
                window_end=window_end,
                filters=resolved_filters,
            ),
        )
        return list(occurrences[query.offset : query.offset + query.limit])

    stmt = select(Event).options(
        selectinload(Event.area.and_(Area.deleted_at.is_(None))),
        selectinload(Event.task.and_(Task.deleted_at.is_(None))),
    )
    stmt = stmt.where(Event.deleted_at.is_(None))
    stmt = _apply_event_query_filters(stmt, filters=resolved_filters)
    if window_start is not None:
        stmt = stmt.where(or_(Event.end_time.is_(None), Event.end_time >= window_start))
    if window_end is not None:
        stmt = stmt.where(Event.start_time <= window_end)
    stmt = (
        stmt.order_by(Event.start_time.desc(), Event.id.desc())
        .offset(query.offset)
        .limit(query.limit)
    )
    events = list((await session.execute(stmt)).scalars())
    return list(await _build_event_views(session, events))


async def _update_event_record(
    session: AsyncSession,
    *,
    event: Event,
    changes: EventUpdateInput,
) -> EventView:
    (
        normalized_start_time,
        normalized_end_time,
        next_start_time,
    ) = _resolve_event_times(event, changes)
    (
        event.recurrence_frequency,
        event.recurrence_interval,
        event.recurrence_count,
        event.recurrence_until,
        event.recurrence_rule,
    ) = _resolve_event_recurrence_update(
        event,
        changes,
        next_start_time=next_start_time,
    )
    _apply_event_scalar_updates(
        event,
        changes,
        normalized_start_time=normalized_start_time,
        normalized_end_time=normalized_end_time,
    )
    await _apply_event_reference_updates(session, event=event, changes=changes)
    await _apply_event_association_updates(session, event=event, changes=changes)
    await session.flush()
    await session.refresh(event)
    return await _build_event_view(session, event)


def _without_event_recurrence_changes(changes: EventUpdateInput) -> EventUpdateInput:
    """Return one event update payload with recurrence edits stripped out."""
    return replace(
        changes,
        recurrence_frequency=None,
        recurrence_interval=None,
        recurrence_count=None,
        recurrence_until=None,
        recurrence_rule=None,
        clear_recurrence_rule=False,
        clear_recurrence=False,
    )


async def _update_single_occurrence(
    session: AsyncSession,
    *,
    master_event: Event,
    instance_start: datetime,
    changes: EventUpdateInput,
) -> EventView:
    override_event_model = await _get_override_event_for_instance(
        session,
        master_event_id=master_event.id,
        instance_start=instance_start,
    )
    if override_event_model is None:
        override_start_time = (
            changes.start_time if changes.start_time is not None else instance_start
        )
        override_end_time = (
            None
            if changes.clear_end_time
            else changes.end_time
            if changes.end_time is not None
            else _event_occurrence_end(master_event, occurrence_start=instance_start)
        )
        resolved_tag_ids, resolved_person_ids = await _resolve_derived_event_association_ids(
            session,
            source_event=master_event,
            changes=changes,
        )
        override_event_view = await create_event(
            session,
            payload=_build_derived_event_create_input(
                master_event,
                changes,
                options=_DerivedEventCreateOptions(
                    start_time=override_start_time,
                    end_time=override_end_time,
                    tag_ids=resolved_tag_ids,
                    person_ids=resolved_person_ids,
                    recurrence_parent_event_id=master_event.id,
                    recurrence_instance_start=instance_start,
                ),
            ),
        )
    else:
        override_event_view = await _update_event_record(
            session,
            event=override_event_model,
            changes=_without_event_recurrence_changes(changes),
        )
    await _record_skip_exception(
        session,
        master_event_id=master_event.id,
        instance_start=instance_start,
    )
    return override_event_view


async def _update_future_series(
    session: AsyncSession,
    *,
    master_event: Event,
    instance_start: datetime,
    changes: EventUpdateInput,
) -> EventView:
    previous_start = get_previous_event_occurrence_start(
        master_event,
        instance_start=instance_start,
    )
    if previous_start is None:
        return await _update_event_record(
            session,
            event=master_event,
            changes=changes,
        )

    master_event.recurrence_until = previous_start
    await session.flush()
    resolved_tag_ids, resolved_person_ids = await _resolve_derived_event_association_ids(
        session,
        source_event=master_event,
        changes=changes,
    )
    next_recurrence_frequency = (
        None
        if changes.clear_recurrence
        else changes.recurrence_frequency
        if changes.recurrence_frequency is not None
        else master_event.recurrence_frequency
    )
    next_recurrence_interval = (
        None
        if changes.clear_recurrence
        else changes.recurrence_interval
        if changes.recurrence_interval is not None
        else master_event.recurrence_interval
    )
    next_recurrence_count = changes.recurrence_count
    if (
        next_recurrence_count is None
        and not changes.clear_recurrence
        and master_event.recurrence_count is not None
    ):
        remaining = master_event.recurrence_count - get_event_occurrence_index(
            master_event,
            instance_start=instance_start,
        )
        next_recurrence_count = remaining
    next_recurrence_until = (
        None
        if changes.clear_recurrence
        else changes.recurrence_until
        if changes.recurrence_until is not None
        else master_event.recurrence_until
    )
    next_recurrence_rule = (
        None
        if changes.clear_recurrence or changes.clear_recurrence_rule
        else changes.recurrence_rule
        if changes.recurrence_rule is not None
        else getattr(master_event, "recurrence_rule", None)
    )
    return await create_event(
        session,
        payload=_build_derived_event_create_input(
            master_event,
            changes,
            options=_DerivedEventCreateOptions(
                start_time=changes.start_time or instance_start,
                end_time=None
                if changes.clear_end_time
                else changes.end_time
                if changes.end_time is not None
                else _event_occurrence_end(master_event, occurrence_start=instance_start),
                tag_ids=resolved_tag_ids,
                person_ids=resolved_person_ids,
                recurrence_frequency=next_recurrence_frequency,
                recurrence_interval=next_recurrence_interval,
                recurrence_count=next_recurrence_count,
                recurrence_until=next_recurrence_until,
                recurrence_rule=next_recurrence_rule,
            ),
        ),
    )


async def update_event(
    session: AsyncSession,
    *,
    event_id: UUID,
    changes: EventUpdateInput,
    scope: str = "all",
    instance_start: datetime | None = None,
) -> EventView:
    """Update one event."""
    event = await _get_event_model(session, event_id=event_id)
    if event is None:
        raise EventNotFoundError(f"Event {event_id} was not found")

    normalized_scope = validate_event_scope(scope)
    normalized_instance_start = to_storage_timezone(instance_start) if instance_start else None
    if normalized_scope in {"single", "all_future"}:
        if normalized_instance_start is None:
            raise EventValidationError("Instance-level recurring updates require --instance-start.")
        validate_event_instance_start(event, instance_start=normalized_instance_start)
    if normalized_scope == "single":
        if normalized_instance_start is None:
            raise EventValidationError("Single-occurrence updates require --instance-start.")
        return await _update_single_occurrence(
            session,
            master_event=event,
            instance_start=normalized_instance_start,
            changes=changes,
        )
    if normalized_scope == "all_future":
        if normalized_instance_start is None:
            raise EventValidationError("Future-series updates require --instance-start.")
        return await _update_future_series(
            session,
            master_event=event,
            instance_start=normalized_instance_start,
            changes=changes,
        )
    return await _update_event_record(session, event=event, changes=changes)


async def delete_event(
    session: AsyncSession,
    *,
    event_id: UUID,
    scope: str = "all",
    instance_start: datetime | None = None,
) -> None:
    """Soft-delete one event or one recurring slice."""
    event = await _get_event_model(session, event_id=event_id)
    if event is None:
        raise EventNotFoundError(f"Event {event_id} was not found")

    normalized_scope = validate_event_scope(scope)
    normalized_instance_start = to_storage_timezone(instance_start) if instance_start else None
    if normalized_scope == "all":
        event.soft_delete()
        await session.flush()
        return

    if normalized_instance_start is None:
        raise EventValidationError("Instance-level recurring deletes require --instance-start.")
    validate_event_instance_start(event, instance_start=normalized_instance_start)

    if normalized_scope == "single":
        override_event = await _get_override_event_for_instance(
            session,
            master_event_id=event.id,
            instance_start=normalized_instance_start,
        )
        if override_event is not None:
            override_event.soft_delete()
        await _record_skip_exception(
            session,
            master_event_id=event.id,
            instance_start=normalized_instance_start,
        )
        await session.flush()
        return

    previous_start = get_previous_event_occurrence_start(
        event,
        instance_start=normalized_instance_start,
    )
    if previous_start is None:
        event.soft_delete()
    else:
        event.recurrence_until = previous_start
    await session.flush()


async def batch_delete_events(
    session: AsyncSession,
    *,
    event_ids: list[UUID],
) -> BatchDeleteResult:
    """Soft-delete multiple events."""
    return await batch_delete_records(
        identifiers=deduplicate_preserving_order(event_ids),
        delete_record=lambda event_id: delete_event(session, event_id=event_id),
        handled_exceptions=(EventNotFoundError,),
    )
