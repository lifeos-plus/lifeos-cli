"""Planned-event response contracts."""

from lifeos_web.response_schemas.common import JsonObject, PersonNameResponse, ResponseModel


class WeekdayOrdinalResponse(ResponseModel):
    weekday: str
    ordinal: int


class RecurrencePatternResponse(ResponseModel):
    frequency: str | None
    interval: int | None
    count: int | None
    until: str | None
    byweekday: list[str] | None = None
    bymonthday: list[int] | None = None
    bymonth: list[int] | None = None
    byweekday_ordinals: list[WeekdayOrdinalResponse] | None = None


class PlannedEventResponse(ResponseModel):
    id: str
    title: str
    start_time: str
    end_time: str | None
    priority: int
    area_id: str | None
    task_id: str | None
    is_all_day: bool
    is_recurring: bool
    recurrence_pattern: RecurrencePatternResponse | None
    rrule_string: str | None
    status: str
    tags: list[str]
    extra_data: JsonObject
    is_instance: bool
    master_event_id: str | None
    instance_id: str | None
    people: list[PersonNameResponse]


class PlannedEventListMeta(ResponseModel):
    start: str | None
    end: str | None
    status: str | None
    task_id: str | None
