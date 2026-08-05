"""Frontend-compatible planned event endpoints backed by LifeOS Event records."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.datetime_utils import format_utc_iso, parse_iso_datetime_input
from lifeos_cli.db.services import events as event_services
from lifeos_cli.db.services.event_support import (
    EventCreateInput,
    EventListInput,
    EventQueryFilters,
    EventUpdateInput,
)
from lifeos_cli.db.services.events import EventOccurrence
from lifeos_cli.db.services.read_models import EventView
from lifeos_cli.db.services.recurrence_core import normalize_recurrence_rule_details
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.planned_events import (
    PlannedEventListMeta,
    PlannedEventResponse,
)
from lifeos_web.schemas import ListResponse, Pagination, PlannedEventCreate, PlannedEventUpdate

router = APIRouter(prefix="/planned-events", tags=["planned-events"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
_RRULE_WEEKDAY_TO_NAME = {
    "MO": "monday",
    "TU": "tuesday",
    "WE": "wednesday",
    "TH": "thursday",
    "FR": "friday",
    "SA": "saturday",
    "SU": "sunday",
}
_WEEKDAY_NAME_TO_RRULE = {value: key for key, value in _RRULE_WEEKDAY_TO_NAME.items()}
_BYDAY_PATTERN = re.compile(r"^(?P<ordinal>[+-]?\d+)?(?P<weekday>MO|TU|WE|TH|FR|SA|SU)$")


def _event_scope(value: str | None) -> str:
    if value in {"single", "all_future", "all"}:
        return value
    return "all"


def _parse_rrule(rrule_string: str | None) -> dict[str, object]:
    """Parse the subset of RRULE fields supported by planned events."""
    if not rrule_string:
        return {}
    values: dict[str, object] = {}
    byweekday: list[str] = []
    byweekday_ordinals: list[dict[str, object]] = []
    for part in rrule_string.split(";"):
        key, separator, value = part.partition("=")
        if not separator:
            continue
        normalized_key = key.strip().upper()
        normalized_value = value.strip()
        if normalized_key == "FREQ":
            values["frequency"] = normalized_value.lower()
        elif normalized_key == "INTERVAL":
            values["interval"] = int(normalized_value)
        elif normalized_key == "COUNT":
            values["count"] = int(normalized_value)
        elif normalized_key == "UNTIL":
            values["until"] = normalized_value
        elif normalized_key == "BYDAY":
            for token in normalized_value.split(","):
                match = _BYDAY_PATTERN.match(token.strip().upper())
                if match is None:
                    continue
                weekday = _RRULE_WEEKDAY_TO_NAME[match.group("weekday")]
                ordinal = match.group("ordinal")
                if ordinal:
                    byweekday_ordinals.append({"weekday": weekday, "ordinal": int(ordinal)})
                else:
                    byweekday.append(weekday)
        elif normalized_key == "BYMONTHDAY":
            values["bymonthday"] = [
                int(token.strip()) for token in normalized_value.split(",") if token.strip()
            ]
        elif normalized_key == "BYMONTH":
            values["bymonth"] = [
                int(token.strip()) for token in normalized_value.split(",") if token.strip()
            ]
    if byweekday:
        values["byweekday"] = byweekday
    if byweekday_ordinals:
        values["byweekday_ordinals"] = byweekday_ordinals
    return values


def _recurrence_rule_from_pattern(
    recurrence: Mapping[str, object],
) -> dict[str, object] | None:
    return normalize_recurrence_rule_details(
        {
            "byweekday": recurrence.get("byweekday"),
            "bymonthday": recurrence.get("bymonthday"),
            "bymonth": recurrence.get("bymonth"),
            "byweekday_ordinals": recurrence.get("byweekday_ordinals"),
        }
    )


def _recurrence_pattern(
    source_event: EventView,
) -> dict[str, object]:
    recurrence_pattern: dict[str, object] = {
        "frequency": source_event.recurrence_frequency,
        "interval": source_event.recurrence_interval,
        "count": source_event.recurrence_count,
        "until": (
            format_utc_iso(source_event.recurrence_until) if source_event.recurrence_until else None
        ),
    }
    if source_event.recurrence_rule:
        recurrence_pattern.update(source_event.recurrence_rule)
    return recurrence_pattern


def _rrule_string(source_event: EventView) -> str | None:
    frequency = source_event.recurrence_frequency
    if frequency is None:
        return None
    parts = [f"FREQ={frequency.upper()}"]
    if source_event.recurrence_interval and source_event.recurrence_interval != 1:
        parts.append(f"INTERVAL={source_event.recurrence_interval}")
    if source_event.recurrence_count is not None:
        parts.append(f"COUNT={source_event.recurrence_count}")
    if source_event.recurrence_until is not None:
        parts.append(f"UNTIL={format_utc_iso(source_event.recurrence_until)}")
    recurrence_rule = source_event.recurrence_rule or {}
    byday: list[str] = []
    for weekday in recurrence_rule.get("byweekday", []):
        byday.append(_WEEKDAY_NAME_TO_RRULE[str(weekday)])
    for item in recurrence_rule.get("byweekday_ordinals", []):
        if not isinstance(item, Mapping):
            continue
        weekday_code = _WEEKDAY_NAME_TO_RRULE[str(item["weekday"])]
        byday.append(f"{item['ordinal']}{weekday_code}")
    if byday:
        parts.append(f"BYDAY={','.join(byday)}")
    if recurrence_rule.get("bymonthday"):
        parts.append(
            "BYMONTHDAY=" + ",".join(str(value) for value in recurrence_rule.get("bymonthday", []))
        )
    if recurrence_rule.get("bymonth"):
        parts.append(
            "BYMONTH=" + ",".join(str(value) for value in recurrence_rule.get("bymonth", []))
        )
    return ";".join(parts)


def _optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    return int(str(value))


def _tag_names(planned_event_record: EventView | EventOccurrence) -> list[str]:
    if not isinstance(planned_event_record, EventView):
        return []
    return [tag.name for tag in planned_event_record.tags]


def _people(planned_event_record: EventView | EventOccurrence) -> list[dict[str, str]]:
    if not isinstance(planned_event_record, EventView):
        return []
    return [{"id": str(person.id), "name": person.name} for person in planned_event_record.people]


def _planned_event_payload(
    planned_event_record: EventView | EventOccurrence,
    *,
    master_event: EventView | None = None,
) -> dict[str, object]:
    is_occurrence = isinstance(planned_event_record, EventOccurrence)
    source = master_event if is_occurrence else planned_event_record
    source_event = source if isinstance(source, EventView) else None
    recurrence_frequency = source_event.recurrence_frequency if source_event else None
    recurrence_pattern = None
    if recurrence_frequency is not None and source_event is not None:
        recurrence_pattern = _recurrence_pattern(source_event)
    if is_occurrence:
        master_id = source_event.id if source_event else planned_event_record.id
    else:
        assert isinstance(planned_event_record, EventView)
        master_id = planned_event_record.recurrence_parent_event_id or planned_event_record.id
    area_id = source_event.area_id if source_event else None
    priority = source_event.priority if source_event else 0
    is_all_day = source_event.is_all_day if source_event else False
    rrule_string = _rrule_string(source_event) if source_event else None
    return {
        "id": str(planned_event_record.id),
        "title": planned_event_record.title,
        "start_time": format_utc_iso(planned_event_record.start_time),
        "end_time": (
            format_utc_iso(planned_event_record.end_time) if planned_event_record.end_time else None
        ),
        "priority": priority,
        "area_id": str(area_id) if area_id else None,
        "task_id": str(planned_event_record.task_id) if planned_event_record.task_id else None,
        "is_all_day": is_all_day,
        "is_recurring": recurrence_frequency is not None,
        "recurrence_pattern": recurrence_pattern,
        "rrule_string": rrule_string,
        "status": planned_event_record.status,
        "tags": _tag_names(source_event) if source_event else [],
        "extra_data": {"event_type": planned_event_record.event_type},
        "is_instance": is_occurrence and recurrence_frequency is not None,
        "master_event_id": str(master_id) if master_id else None,
        "instance_id": str(planned_event_record.id) if is_occurrence else None,
        "people": _people(source_event) if source_event else [],
    }


def _create_input(payload: PlannedEventCreate) -> EventCreateInput:
    recurrence = payload.recurrence_pattern or _parse_rrule(payload.rrule_string)
    has_recurrence_frequency = payload.is_recurring and recurrence.get("frequency")
    has_recurrence_interval = payload.is_recurring and recurrence.get("interval") is not None
    has_recurrence_count = payload.is_recurring and recurrence.get("count") is not None
    recurrence_rule = _recurrence_rule_from_pattern(recurrence) if payload.is_recurring else None
    return EventCreateInput(
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time,
        priority=payload.priority,
        status=payload.status,
        event_type="timeblock" if payload.task_id else "appointment",
        is_all_day=payload.is_all_day,
        area_id=payload.area_id,
        task_id=payload.task_id,
        person_ids=payload.person_ids,
        recurrence_frequency=str(recurrence.get("frequency")) if has_recurrence_frequency else None,
        recurrence_interval=(
            _optional_int(recurrence.get("interval")) if has_recurrence_interval else None
        ),
        recurrence_count=(_optional_int(recurrence.get("count")) if has_recurrence_count else None),
        recurrence_until=(
            parse_iso_datetime_input(str(recurrence["until"]))
            if payload.is_recurring and recurrence.get("until")
            else None
        ),
        recurrence_rule=recurrence_rule,
    )


def _update_input(payload: PlannedEventUpdate) -> EventUpdateInput:
    fields = payload.model_fields_set
    recurrence = payload.recurrence_pattern or _parse_rrule(payload.rrule_string)
    clear_recurrence = "is_recurring" in fields and payload.is_recurring is False
    recurrence_provided = "recurrence_pattern" in fields or "rrule_string" in fields
    recurrence_rule = _recurrence_rule_from_pattern(recurrence)
    return EventUpdateInput(
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time,
        clear_end_time="end_time" in fields and payload.end_time is None,
        priority=payload.priority,
        status=payload.status,
        event_type="timeblock" if payload.task_id else None,
        is_all_day=payload.is_all_day,
        area_id=payload.area_id,
        clear_area="area_id" in fields and payload.area_id is None,
        task_id=payload.task_id,
        clear_task="task_id" in fields and payload.task_id is None,
        person_ids=payload.person_ids,
        clear_people="person_ids" in fields and payload.person_ids == [],
        recurrence_frequency=(
            str(recurrence.get("frequency"))
            if payload.is_recurring is not False and recurrence.get("frequency")
            else None
        ),
        recurrence_interval=(
            _optional_int(recurrence.get("interval"))
            if payload.is_recurring is not False and recurrence.get("interval") is not None
            else None
        ),
        recurrence_count=(
            _optional_int(recurrence.get("count"))
            if payload.is_recurring is not False and recurrence.get("count") is not None
            else None
        ),
        recurrence_until=(
            parse_iso_datetime_input(str(recurrence["until"]))
            if payload.is_recurring is not False and recurrence.get("until")
            else None
        ),
        recurrence_rule=recurrence_rule,
        clear_recurrence_rule=(
            recurrence_provided and payload.is_recurring is not False and recurrence_rule is None
        ),
        clear_recurrence=clear_recurrence,
    )


async def _list_events(
    session: AsyncSession,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    status: str | None = None,
    task_id: UUID | None = None,
    page: int = 1,
    size: int = 100,
) -> ListResponse:
    filters = EventQueryFilters(
        status=status,
        task_id=task_id,
        window_start=start,
        window_end=end,
    )
    rows = await event_services.list_events(
        session,
        query=EventListInput(filters=filters, limit=size, offset=(page - 1) * size),
    )
    items: list[dict[str, object]] = []
    for row in rows:
        if start is not None and end is not None:
            row_end = row.end_time or row.start_time
            if row.start_time >= end or row_end <= start:
                continue
        master_event = None
        if isinstance(row, EventOccurrence):
            master_event = await event_services.get_event(session, event_id=row.id)
        items.append(_planned_event_payload(row, master_event=master_event))
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=size,
            total=len(items),
            pages=math.ceil(len(items) / size) if size else 0,
        ),
        meta={
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "status": status,
            "task_id": str(task_id) if task_id else None,
        },
    )


@router.get("/", response_model=ListResponse[PlannedEventResponse, PlannedEventListMeta])
async def list_planned_events(
    session: SessionDep,
    start: datetime | None = None,
    end: datetime | None = None,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ListResponse:
    """List expanded planned events for a calendar window."""
    return await _list_events(session, start=start, end=end, status=status, page=page, size=size)


@router.get("/raw", response_model=ListResponse[PlannedEventResponse, PlannedEventListMeta])
async def list_raw_planned_events(
    session: SessionDep,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ListResponse:
    """List stored planned event records without a required window."""
    return await _list_events(session, status=status, page=page, size=size)


@router.get(
    "/by-task/{task_id}",
    response_model=ListResponse[PlannedEventResponse, PlannedEventListMeta],
)
async def list_planned_events_by_task(
    task_id: UUID,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ListResponse:
    """List planned events linked to a task."""
    return await _list_events(session, task_id=task_id, page=page, size=size)


@router.get("/{planned_event_id}", response_model=PlannedEventResponse)
async def get_planned_event(
    planned_event_id: UUID,
    session: SessionDep,
) -> dict[str, object]:
    """Load one planned event."""
    planned_event_record = await event_services.get_event(session, event_id=planned_event_id)
    if planned_event_record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Planned event {planned_event_id} was not found",
        )
    return _planned_event_payload(planned_event_record)


@router.post("/", response_model=PlannedEventResponse)
async def create_planned_event(
    payload: PlannedEventCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Create a planned event through the frontend contract."""
    try:
        planned_event_record = await event_services.create_event(
            session,
            payload=_create_input(payload),
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _planned_event_payload(planned_event_record)


@router.patch("/{planned_event_id}", response_model=PlannedEventResponse)
async def update_planned_event(
    planned_event_id: UUID,
    payload: PlannedEventUpdate,
    session: SessionDep,
    updateType: str | None = None,
    instanceStart: datetime | None = None,
) -> dict[str, object]:
    """Update a planned event through the frontend contract."""
    try:
        planned_event_record = await event_services.update_event(
            session,
            event_id=planned_event_id,
            changes=_update_input(payload),
            scope=_event_scope(updateType),
            instance_start=instanceStart,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _planned_event_payload(planned_event_record)


@router.delete("/{planned_event_id}", status_code=204)
async def delete_planned_event(
    planned_event_id: UUID,
    session: SessionDep,
    deleteType: str | None = None,
    instanceStart: datetime | None = None,
) -> None:
    """Soft-delete a planned event through the frontend contract."""
    try:
        await event_services.delete_event(
            session,
            event_id=planned_event_id,
            scope=_event_scope(deleteType),
            instance_start=instanceStart,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
