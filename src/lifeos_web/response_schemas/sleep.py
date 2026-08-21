"""Sleep response contracts."""

from __future__ import annotations

from lifeos_web.response_schemas.common import ResponseModel


class SleepSegmentResponse(ResponseModel):
    """One sleep segment."""

    id: str
    sleep_date: str
    start_at: str
    end_at: str
    duration_minutes: int
    created_at: str
    updated_at: str


class SleepDailySummaryResponse(ResponseModel):
    """One computed daily sleep summary."""

    sleep_date: str
    total_minutes: int
    segment_count: int
    first_start_at: str | None
    last_end_at: str | None
