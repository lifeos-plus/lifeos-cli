"""Statistics response contracts."""

from typing import Literal

from lifeos_web.response_schemas.common import ResponseModel
from lifeos_web.schemas import Pagination


class DailyAreaResponse(ResponseModel):
    date: str
    area_id: str
    minutes: int


class DailyAreaMeta(ResponseModel):
    start: str
    end: str
    timezone: str
    area_ids: list[str] | None


class DayBreakdownResponse(ResponseModel):
    area_id: str
    minutes: int


class DayBreakdownMeta(ResponseModel):
    day: str
    timezone: str


class AggregatedAreaResponse(ResponseModel):
    granularity: Literal["day", "week", "month", "year"]
    period_start: str
    period_end: str
    area_id: str
    minutes: int


class AggregatedAreaMeta(ResponseModel):
    granularity: Literal["day", "week", "month", "year"]
    start: str
    end: str
    timezone: str
    area_ids: list[str] | None
    first_day_of_week: int
    calendar_system: str


class AggregatedAreaPeriodResponse(ResponseModel):
    period_start: str
    period_end: str


class AggregatedAreasListResponse(ResponseModel):
    """Complete bucket timeline plus per-area rows for aggregated stats."""

    items: list[AggregatedAreaResponse]
    periods: list[AggregatedAreaPeriodResponse]
    pagination: Pagination
    meta: AggregatedAreaMeta


class RecomputeDailyAreasResponse(ResponseModel):
    days_recomputed: int


class TagUsageStatResponse(ResponseModel):
    id: str
    usage_count: int


class TagUsageByEntityResponse(ResponseModel):
    entity_type: str
    tag_stats: list[TagUsageStatResponse]
    total_tags: int
