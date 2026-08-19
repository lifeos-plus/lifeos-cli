"""Sleep endpoints for the local Web API."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.datetime_utils import format_utc_iso
from lifeos_cli.application.time_preferences import to_storage_timezone
from lifeos_cli.db.models.sleep_segment import SleepSegment
from lifeos_cli.db.services import sleep as sleep_services
from lifeos_cli.db.services.validation_utils import DomainValidationError
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.common import EmptyMeta
from lifeos_web.response_schemas.sleep import (
    SleepDailySummaryResponse,
    SleepSegmentResponse,
)
from lifeos_web.router_utils import page_envelope, soft_delete
from lifeos_web.schemas import (
    ListResponse,
    SleepSegmentCreate,
    SleepSegmentUpdate,
)

router = APIRouter(prefix="/sleep-segments", tags=["sleep-segments"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _segment_payload(segment: SleepSegment) -> dict[str, object]:
    return {
        "id": str(segment.id),
        "sleep_date": segment.sleep_date.isoformat(),
        "start_at": format_utc_iso(segment.start_at),
        "end_at": format_utc_iso(segment.end_at),
        "duration_minutes": segment.duration_minutes,
        "created_at": format_utc_iso(segment.created_at),
        "updated_at": format_utc_iso(segment.updated_at),
    }


def _summary_payload(summary: sleep_services.SleepDailySummary) -> dict[str, object]:
    return {
        "sleep_date": summary.sleep_date.isoformat(),
        "total_minutes": summary.total_minutes,
        "segment_count": summary.segment_count,
        "first_start_at": (
            format_utc_iso(summary.first_start_at) if summary.first_start_at else None
        ),
        "last_end_at": (format_utc_iso(summary.last_end_at) if summary.last_end_at else None),
    }


@router.get(
    "/",
    response_model=ListResponse[SleepSegmentResponse, EmptyMeta],
    response_model_exclude_unset=True,
)
async def list_sleep_segments(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    sleep_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ListResponse:
    """List sleep segments for the local Web UI."""
    if (start_date is None) != (end_date is None):
        raise HTTPException(
            status_code=400,
            detail="start_date and end_date must be provided together.",
        )
    segments = await sleep_services.list_sleep_segments(
        session,
        sleep_date=sleep_date,
        start_date=start_date,
        end_date=end_date,
        limit=size,
        offset=(page - 1) * size,
    )
    total = await sleep_services.count_sleep_segments(
        session,
        sleep_date=sleep_date,
        start_date=start_date,
        end_date=end_date,
    )
    return page_envelope(
        items=[_segment_payload(segment) for segment in segments],
        page=page,
        size=size,
        total=total,
    )


@router.get(
    "/summary",
    response_model=ListResponse[SleepDailySummaryResponse, EmptyMeta],
    response_model_exclude_unset=True,
)
async def list_sleep_summaries(
    session: SessionDep,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ListResponse:
    """Return computed daily sleep summaries for an optional date range."""
    if (start_date is None) != (end_date is None):
        raise HTTPException(
            status_code=400,
            detail="start_date and end_date must be provided together.",
        )
    summaries = await sleep_services.get_sleep_daily_summaries(
        session,
        start_date=start_date,
        end_date=end_date,
    )
    return page_envelope(
        items=[_summary_payload(summary) for summary in summaries],
        page=1,
        size=max(len(summaries), 1),
        total=len(summaries),
    )


@router.post(
    "/",
    response_model=SleepSegmentResponse,
    response_model_exclude_unset=True,
)
async def create_sleep_segment(
    payload: SleepSegmentCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Create one sleep segment."""
    try:
        segment = await sleep_services.create_sleep_segment(
            session,
            start_at=to_storage_timezone(payload.start_at),
            end_at=to_storage_timezone(payload.end_at),
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _segment_payload(segment)


@router.get(
    "/{segment_id}",
    response_model=SleepSegmentResponse,
    response_model_exclude_unset=True,
)
async def get_sleep_segment(segment_id: UUID, session: SessionDep) -> dict[str, object]:
    """Return one active sleep segment."""
    segment = await sleep_services.get_sleep_segment(session, segment_id=segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail=f"Sleep segment {segment_id} was not found")
    return _segment_payload(segment)


@router.patch(
    "/{segment_id}",
    response_model=SleepSegmentResponse,
    response_model_exclude_unset=True,
)
async def update_sleep_segment(
    segment_id: UUID,
    payload: SleepSegmentUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update one sleep segment."""
    try:
        segment = await sleep_services.update_sleep_segment(
            session,
            segment_id=segment_id,
            start_at=(to_storage_timezone(payload.start_at) if payload.start_at else None),
            end_at=to_storage_timezone(payload.end_at) if payload.end_at else None,
        )
    except sleep_services.SleepSegmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _segment_payload(segment)


@router.delete("/{segment_id}", status_code=204)
async def delete_sleep_segment(segment_id: UUID, session: SessionDep) -> None:
    """Soft-delete one sleep segment."""
    await soft_delete(
        sleep_services.delete_sleep_segment,
        session=session,
        segment_id=segment_id,
    )
