"""Vision response contracts."""

from lifeos_web.response_schemas.common import (
    PersonNameResponse,
    ResponseModel,
    TaskSummaryResponse,
)


class VisionResponse(ResponseModel):
    id: str
    name: str
    description: str | None
    area_id: str | None
    status: str
    stage: int
    experience_points: int
    experience_rate_per_hour: int | None
    created_at: str
    people: list[PersonNameResponse]


class VisionWithTasksResponse(VisionResponse):
    tasks: list[TaskSummaryResponse]


class VisionStatsResponse(ResponseModel):
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    todo_tasks: int
    completion_percentage: float
    total_estimated_effort: int | None
    total_actual_effort: int | None


class VisionRecomputeResponse(ResponseModel):
    vision_id: str
    recomputed_roots: list[str]


class VisionListMeta(ResponseModel):
    status_filter: str | None
