"""Task response contracts."""

from __future__ import annotations

from lifeos_web.response_schemas.common import PersonNameResponse, ResponseModel


class TaskResponse(ResponseModel):
    id: str
    vision_id: str | None
    parent_task_id: str | None
    content: str
    description: str | None = None
    status: str
    priority: int
    display_order: int
    estimated_effort: int | None = None
    planning_cycle_type: str | None
    planning_cycle_days: int | None
    planning_cycle_start_date: str | None
    actual_effort_self: int | None = None
    actual_effort_total: int | None = None
    notes_count: int | None = None
    timelogs_count: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    people: list[PersonNameResponse] | None = None


class TaskTreeResponse(TaskResponse):
    subtasks: list[TaskTreeResponse]
    completion_percentage: float
    depth: int


class TaskHierarchyResponse(ResponseModel):
    vision_id: str
    root_tasks: list[TaskTreeResponse]


class TaskStatsResponse(ResponseModel):
    total_subtasks: int
    completed_subtasks: int
    completion_percentage: float
    total_estimated_effort: int | None
    total_actual_effort: int | None


class TaskMoveResponse(TaskResponse):
    updated_descendants: list[TaskResponse]


class TaskListMeta(ResponseModel):
    vision_id: str | None
    vision_in: str | None
    status_filter: str | None
    status_in: str | None
    exclude_status: str | None
    planning_cycle_type: str | None
    planning_cycle_start_date: str | None
    calendar_system: str | None
    first_day_of_week: int | None
    seven_year_anchor_date: str | None
    query: str | None
    fields: str
