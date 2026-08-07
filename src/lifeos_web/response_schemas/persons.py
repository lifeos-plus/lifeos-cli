"""Person response contracts."""

from typing import Literal

from lifeos_web.response_schemas.common import ResponseModel, TagSummaryResponse


class PersonResponse(ResponseModel):
    id: str
    name: str
    description: str | None
    nicknames: list[str]
    birth_date: str | None
    location: str | None
    tags: list[TagSummaryResponse]
    anniversaries: list["AnniversaryResponse"]
    display_name: str
    primary_nickname: str


class PersonListMeta(ResponseModel):
    search: str | None
    tag_filter: str | None
    tag_id: str | None


class PersonActivityResponse(ResponseModel):
    id: str
    type: Literal["vision", "task", "planned_event", "timelog", "note"]
    title: str
    description: str | None
    date: str
    status: str | None
    start_time: str | None = None
    end_time: str | None = None
    area_id: str | None = None


class PersonActivityMeta(ResponseModel):
    person_id: str
    person_name: str
    activity_type: str | None
    timelog_count: int
    timelog_total_minutes: int


class AnniversaryResponse(ResponseModel):
    id: str
    person_id: str
    name: str
    date: str
    created_at: str
    updated_at: str


class AnniversaryListMeta(ResponseModel):
    person_id: str
