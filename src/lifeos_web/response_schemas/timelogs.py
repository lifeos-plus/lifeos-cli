"""Timelog response contracts."""

from lifeos_web.response_schemas.common import (
    PersonNameResponse,
    PersonSummaryResponse,
    ResponseModel,
    TagCompactResponse,
    TaskSummaryResponse,
)


class AreaSummaryResponse(ResponseModel):
    id: str
    name: str | None
    color: str | None


class TimelogResponse(ResponseModel):
    id: str
    title: str
    tracking_method: str
    start_time: str
    end_time: str
    location: str | None
    energy_level: int | None
    notes: str | None
    area_id: str | None
    task_id: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None
    linked_notes_count: int
    task: TaskSummaryResponse | None
    tags: list[TagCompactResponse]
    people: list[PersonNameResponse]
    area_summary: AreaSummaryResponse | None = None


class TimelogListMeta(ResponseModel):
    start_date: str | None
    end_date: str | None
    window_start: str | None
    window_end: str | None
    query: str | None
    tracking_method: str | None
    area_id: str | None
    area_name: str | None
    without_area: bool
    task_id: str | None
    without_task: bool
    with_task: bool
    limit: int
    returned_count: int
    total_count: int
    truncated: bool


class LatestTimelogEndResponse(ResponseModel):
    end_time: str | None


class TimelogBatchUpdateResponse(ResponseModel):
    updated_count: int
    unchanged_ids: list[str]
    failed_ids: list[str]
    errors: list[str]


class TimelogTemplateResponse(ResponseModel):
    id: str
    title: str
    area_id: str | None
    area_name: str | None
    area_color: str | None
    person_ids: list[str]
    people: list[PersonSummaryResponse]
    default_duration_minutes: int | None
    position: int
    usage_count: int
    last_used_at: str | None
    created_at: str


class TimelogTemplateListMeta(ResponseModel):
    order_by: str | None
