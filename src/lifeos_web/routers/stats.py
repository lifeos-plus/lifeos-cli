"""Frontend-compatible stats endpoints backed by LifeOS timelog area stats."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.calendar_adapter import iter_calendar_periods
from lifeos_cli.application.time_preferences import get_calendar_preferences
from lifeos_cli.config import get_preferences_settings
from lifeos_cli.db.services import tags as tag_services
from lifeos_cli.db.services import timelog_stats
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.stats import (
    AggregatedAreaMeta,
    AggregatedAreaResponse,
    DailyAreaMeta,
    DailyAreaResponse,
    DayBreakdownMeta,
    DayBreakdownResponse,
    RecomputeDailyAreasResponse,
    TagUsageByEntityResponse,
)
from lifeos_web.schemas import ListResponse, Pagination

router = APIRouter(prefix="/stats", tags=["stats"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
Granularity = Literal["day", "week", "month", "year"]


def _filter_area(row_area_id: UUID, area_ids: set[UUID] | None) -> bool:
    return area_ids is None or row_area_id in area_ids


def _pagination(*, page: int, size: int, total: int) -> Pagination:
    pages = math.ceil(total / size) if size else 0
    return Pagination(page=page, size=size, total=total, pages=pages)


def _page_items(items: list[dict[str, object]], *, page: int, size: int) -> list[dict[str, object]]:
    start = (page - 1) * size
    return items[start : start + size]


def _parse_area_ids(values: list[UUID] | None) -> set[UUID] | None:
    if not values:
        return None
    return set(values)


@router.get("/daily-areas", response_model=ListResponse[DailyAreaResponse, DailyAreaMeta])
async def list_daily_areas(
    session: SessionDep,
    start: date,
    end: date,
    area_ids: Annotated[list[UUID] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> ListResponse:
    """Return daily timelog minutes by LifeOS area."""
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    selected_areas = _parse_area_ids(area_ids)
    rows: list[dict[str, object]] = []
    cursor = start
    while cursor <= end:
        report = await timelog_stats.get_timelog_stats_groupby_area_for_day(
            session,
            target_date=cursor,
        )
        for row in report.rows:
            if _filter_area(row.area_id, selected_areas):
                rows.append(
                    {
                        "date": cursor.isoformat(),
                        "area_id": str(row.area_id),
                        "minutes": row.minutes,
                    }
                )
        cursor += timedelta(days=1)
    timezone = get_preferences_settings().timezone
    return ListResponse(
        items=_page_items(rows, page=page, size=size),
        pagination=_pagination(page=page, size=size, total=len(rows)),
        meta={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timezone": timezone,
            "area_ids": [str(item) for item in area_ids] if area_ids else None,
        },
    )


@router.get(
    "/day-breakdown",
    response_model=ListResponse[DayBreakdownResponse, DayBreakdownMeta],
)
async def get_day_breakdown(
    session: SessionDep,
    day: date,
) -> ListResponse:
    """Return one local day's timelog minutes by LifeOS area."""
    report = await timelog_stats.get_timelog_stats_groupby_area_for_day(
        session,
        target_date=day,
    )
    rows = [
        {
            "area_id": str(row.area_id),
            "minutes": row.minutes,
        }
        for row in report.rows
    ]
    return ListResponse(
        items=rows,
        pagination=Pagination(page=1, size=100, total=len(rows), pages=1 if rows else 0),
        meta={"day": day.isoformat(), "timezone": report.timezone},
    )


@router.get(
    "/aggregated-areas",
    response_model=ListResponse[AggregatedAreaResponse, AggregatedAreaMeta],
)
async def list_aggregated_areas(
    session: SessionDep,
    granularity: Granularity,
    start: date,
    end: date,
    area_ids: Annotated[list[UUID] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> ListResponse:
    """Return aggregated timelog minutes by LifeOS area."""
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    calendar_preferences = get_calendar_preferences()
    selected_areas = _parse_area_ids(area_ids)
    rows: list[dict[str, object]] = []
    periods = iter_calendar_periods(
        start=start,
        end=end,
        granularity=granularity,
        calendar_system=calendar_preferences.system,
        first_day_of_week=calendar_preferences.first_day_of_week,
    )
    for period_start, period_end in periods:
        report = await timelog_stats.get_timelog_stats_groupby_area_for_range(
            session,
            start_date=period_start,
            end_date=period_end,
        )
        for row in report.rows:
            if _filter_area(row.area_id, selected_areas):
                rows.append(
                    {
                        "granularity": granularity,
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                        "area_id": str(row.area_id),
                        "minutes": row.minutes,
                    }
                )
    return ListResponse(
        items=_page_items(rows, page=page, size=size),
        pagination=_pagination(page=page, size=size, total=len(rows)),
        meta={
            "granularity": granularity,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timezone": get_preferences_settings().timezone,
            "area_ids": [str(item) for item in area_ids] if area_ids else None,
            "first_day_of_week": calendar_preferences.first_day_of_week,
            "calendar_system": calendar_preferences.system,
        },
    )


@router.post("/daily-areas/recompute", response_model=RecomputeDailyAreasResponse)
async def recompute_daily_areas(
    session: SessionDep,
    start: date,
    end: date,
) -> dict[str, object]:
    """Rebuild persisted LifeOS timelog stats for a local date range."""
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    try:
        rebuilt_dates = await timelog_stats.rebuild_timelog_stats_groupby_area(
            session,
            start_date=start,
            end_date=end,
        )
    except timelog_stats.TimelogStatsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"days_recomputed": len(rebuilt_dates)}


@router.get("/tags/usage/{entity_type}", response_model=TagUsageByEntityResponse)
async def get_tag_usage_by_entity_type(
    entity_type: str,
    session: SessionDep,
) -> dict[str, object]:
    """Return active tagged-record counts for tags of one entity type."""
    try:
        normalized_entity_type = tag_services.validate_tag_entity_type(entity_type)
        usage_counts = await tag_services.count_tag_usage_by_entity_type(
            session,
            entity_type=normalized_entity_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "entity_type": normalized_entity_type,
        "tag_stats": [
            {"id": str(tag_id), "usage_count": count}
            for tag_id, count in sorted(usage_counts.items(), key=lambda item: str(item[0]))
        ],
        "total_tags": len(usage_counts),
    }
