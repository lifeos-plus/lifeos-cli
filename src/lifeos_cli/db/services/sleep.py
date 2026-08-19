"""Async CRUD helpers for sleep segments and on-demand daily summaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.time_preferences import get_operational_date
from lifeos_cli.db.models.sleep_segment import SleepSegment
from lifeos_cli.db.services.validation_utils import DomainValidationError

MAX_SLEEP_SEGMENT_HOURS = 48


class SleepSegmentNotFoundError(LookupError):
    """Raised when a sleep segment cannot be found."""


class SleepValidationError(DomainValidationError):
    """Raised when sleep segment input cannot be applied."""


def compute_duration_minutes(start_at: datetime, end_at: datetime) -> int:
    """Validate a sleep interval and return its whole-minute duration."""
    if start_at.tzinfo is None or end_at.tzinfo is None:
        raise SleepValidationError("Sleep start and end times must be timezone-aware.")
    if end_at <= start_at:
        raise SleepValidationError("Sleep `--end-time` must be after `--start-time`.")
    duration_minutes = int((end_at - start_at).total_seconds() // 60)
    if duration_minutes < 1:
        raise SleepValidationError("A sleep segment must last at least one minute.")
    if duration_minutes > MAX_SLEEP_SEGMENT_HOURS * 60:
        raise SleepValidationError(
            f"A sleep segment cannot exceed {MAX_SLEEP_SEGMENT_HOURS} hours."
        )
    return duration_minutes


def resolve_sleep_date(start_at: datetime) -> date:
    """Return the local operational date a segment belongs to."""
    return get_operational_date(start_at)


async def _get_segment_model(
    session: AsyncSession,
    segment_id: UUID,
) -> SleepSegment | None:
    stmt = (
        select(SleepSegment)
        .where(SleepSegment.id == segment_id, SleepSegment.deleted_at.is_(None))
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_sleep_segment(
    session: AsyncSession,
    *,
    start_at: datetime,
    end_at: datetime,
) -> SleepSegment:
    """Create one sleep segment; the attribution date is derived from start time."""
    duration_minutes = compute_duration_minutes(start_at, end_at)
    segment = SleepSegment(
        sleep_date=resolve_sleep_date(start_at),
        start_at=start_at,
        end_at=end_at,
        duration_minutes=duration_minutes,
    )
    session.add(segment)
    await session.flush()
    return segment


async def get_sleep_segment(
    session: AsyncSession,
    *,
    segment_id: UUID,
) -> SleepSegment | None:
    """Return one active sleep segment."""
    return await _get_segment_model(session, segment_id)


async def list_sleep_segments(
    session: AsyncSession,
    *,
    dates: tuple[date, ...] | None = None,
    sleep_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[SleepSegment]:
    """List active sleep segments with optional attribution-date filtering."""
    stmt = (
        select(SleepSegment)
        .where(SleepSegment.deleted_at.is_(None))
        .order_by(SleepSegment.start_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if dates:
        stmt = stmt.where(SleepSegment.sleep_date.in_(dates))
    if sleep_date is not None:
        stmt = stmt.where(SleepSegment.sleep_date == sleep_date)
    if start_date is not None:
        stmt = stmt.where(SleepSegment.sleep_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(SleepSegment.sleep_date <= end_date)
    return list((await session.execute(stmt)).scalars().all())


async def count_sleep_segments(
    session: AsyncSession,
    *,
    dates: tuple[date, ...] | None = None,
    sleep_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """Count active sleep segments for pagination metadata."""
    stmt = select(func.count(SleepSegment.id)).where(SleepSegment.deleted_at.is_(None))
    if dates:
        stmt = stmt.where(SleepSegment.sleep_date.in_(dates))
    if sleep_date is not None:
        stmt = stmt.where(SleepSegment.sleep_date == sleep_date)
    if start_date is not None:
        stmt = stmt.where(SleepSegment.sleep_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(SleepSegment.sleep_date <= end_date)
    return int((await session.execute(stmt)).scalar_one())


async def update_sleep_segment(
    session: AsyncSession,
    *,
    segment_id: UUID,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> SleepSegment:
    """Update sleep segment times and recompute duration and attribution."""
    segment = await _get_segment_model(session, segment_id)
    if segment is None:
        raise SleepSegmentNotFoundError(f"Sleep segment {segment_id} was not found")
    new_start = start_at if start_at is not None else segment.start_at
    new_end = end_at if end_at is not None else segment.end_at
    duration_minutes = compute_duration_minutes(new_start, new_end)
    segment.start_at = new_start
    segment.end_at = new_end
    segment.duration_minutes = duration_minutes
    segment.sleep_date = resolve_sleep_date(new_start)
    await session.flush()
    return segment


async def delete_sleep_segment(
    session: AsyncSession,
    *,
    segment_id: UUID,
) -> None:
    """Soft-delete one sleep segment."""
    segment = await _get_segment_model(session, segment_id)
    if segment is None:
        raise SleepSegmentNotFoundError(f"Sleep segment {segment_id} was not found")
    segment.soft_delete()
    await session.flush()


@dataclass(frozen=True)
class SleepDailySummary:
    """Computed daily sleep summary for one attribution date."""

    sleep_date: date
    total_minutes: int
    segment_count: int
    first_start_at: datetime | None
    last_end_at: datetime | None


async def get_sleep_daily_summaries(
    session: AsyncSession,
    *,
    dates: tuple[date, ...] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[SleepDailySummary]:
    """Compute on-demand daily sleep summaries for an optional date range."""
    stmt = (
        select(
            SleepSegment.sleep_date,
            func.sum(SleepSegment.duration_minutes),
            func.count(SleepSegment.id),
            func.min(SleepSegment.start_at),
            func.max(SleepSegment.end_at),
        )
        .where(SleepSegment.deleted_at.is_(None))
        .group_by(SleepSegment.sleep_date)
        .order_by(SleepSegment.sleep_date.desc())
    )
    if dates:
        stmt = stmt.where(SleepSegment.sleep_date.in_(dates))
    if start_date is not None:
        stmt = stmt.where(SleepSegment.sleep_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(SleepSegment.sleep_date <= end_date)
    rows = (await session.execute(stmt)).all()
    return [
        SleepDailySummary(
            sleep_date=row.sleep_date,
            total_minutes=int(row[1] or 0),
            segment_count=int(row[2] or 0),
            first_start_at=row[3],
            last_end_at=row[4],
        )
        for row in rows
    ]
