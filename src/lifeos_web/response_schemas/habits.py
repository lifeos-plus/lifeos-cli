"""Habit response contracts."""

from __future__ import annotations

from lifeos_web.response_schemas.common import ResponseModel


class HabitStatsResponse(ResponseModel):
    habit_id: str
    total_actions: int
    completed_actions: int
    missed_actions: int
    skipped_actions: int
    progress_percentage: float
    current_streak: int
    longest_streak: int


class HabitResponse(ResponseModel):
    id: str
    title: str
    description: str | None
    start_date: str
    duration_days: int
    cadence_frequency: str
    cadence_weekdays: list[str] | None
    cadence_monthdays: list[int] | None
    target_per_cycle: int
    status: str
    task_id: str | None


class HabitOverviewResponse(ResponseModel):
    habit: HabitResponse
    stats: HabitStatsResponse


class HabitActionResponse(ResponseModel):
    id: str | None
    habit_id: str
    action_date: str
    status: str
    notes: str | None
    linked_notes_count: int


class HabitSummaryResponse(ResponseModel):
    title: str
    description: str | None
    start_date: str
    duration_days: int
    cadence_frequency: str


class HabitActionWithHabitResponse(HabitActionResponse):
    habit: HabitSummaryResponse


class HabitAssociationsResponse(ResponseModel):
    associations: dict[str, list[HabitResponse]]


class HabitListMeta(ResponseModel):
    status_filter: str | None


class HabitActionDateMeta(ResponseModel):
    action_date: str


class HabitActionRangeMeta(ResponseModel):
    start_date: str
    end_date: str
    reference_date: str
    cadence_frequency: str | None


class HabitActionListMeta(ResponseModel):
    status_filter: str | None
    center_date: str | None
    days_before: int | None
    days_after: int | None
