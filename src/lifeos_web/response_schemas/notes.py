"""Note response contracts."""

from lifeos_web.response_schemas.common import (
    HabitActionSummaryResponse,
    PersonSummaryResponse,
    ResponseModel,
    TagSummaryResponse,
    TaskSummaryResponse,
    TimelogSummaryResponse,
    VisionSummaryResponse,
)


class EventSummaryResponse(ResponseModel):
    id: str
    title: str


class NoteResponse(ResponseModel):
    id: str
    content: str
    created_at: str
    updated_at: str
    deleted_at: str | None
    tags: list[TagSummaryResponse]
    people: list[PersonSummaryResponse]
    tasks: list[TaskSummaryResponse]
    task: TaskSummaryResponse | None
    visions: list[VisionSummaryResponse]
    events: list[EventSummaryResponse]
    timelogs: list[TimelogSummaryResponse]
    habit_actions: list[HabitActionSummaryResponse]


class NoteListMeta(ResponseModel):
    keyword: str | None
    tag_id: str | None
    person_id: str | None
    task_id: str | None
    timelog_id: str | None
    habit_action_id: str | None


class NotePersonStat(ResponseModel):
    id: str
    name: str
    display_name: str
    usage_count: int


class NotePersonStatsResponse(ResponseModel):
    person_stats: list[NotePersonStat]
    total_persons: int
