"""Persisted timelog stats grouped by area."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.datetime_utils import normalize_storage_datetime
from lifeos_cli.application.time_preferences import (
    get_operational_date,
    get_utc_half_open_window_for_local_date_range,
    get_utc_window_for_local_date,
    get_week_bounds,
)
from lifeos_cli.config import get_preferences_settings
from lifeos_cli.db.models.aggregated_timelog_stats_groupby_area import (
    AggregatedTimelogStatsGroupByArea,
)
from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.daily_timelog_stats_groupby_area import DailyTimelogStatsGroupByArea
from lifeos_cli.db.models.timelog import Timelog


class TimelogStatsValidationError(RuntimeError):
    """Raised when timelog stats input is invalid."""


@dataclass(frozen=True)
class TimelogAreaStatsRow:
    """One grouped area row in a timelog stats report."""

    area_id: UUID
    area_name: str | None
    minutes: int
    timelog_count: int


@dataclass(frozen=True)
class TimelogStatsReport:
    """Grouped timelog stats for one requested period."""

    granularity: str
    start_date: date
    end_date: date
    timezone: str
    rows: tuple[TimelogAreaStatsRow, ...]


def iter_date_range(start_date: date, end_date: date) -> tuple[date, ...]:
    """Return the inclusive local date range between two dates."""
    if end_date < start_date:
        raise TimelogStatsValidationError("end_date must be on or after start_date.")
    cursor = start_date
    dates: list[date] = []
    while cursor <= end_date:
        dates.append(cursor)
        cursor += timedelta(days=1)
    return tuple(dates)


def get_month_bounds(target_month: date) -> tuple[date, date]:
    """Return the first and last local dates for one month."""
    month_start = target_month.replace(day=1)
    return month_start, month_start.replace(day=monthrange(month_start.year, month_start.month)[1])


def get_year_bounds(target_year: int) -> tuple[date, date]:
    """Return the first and last local dates for one year."""
    return date(target_year, 1, 1), date(target_year, 12, 31)


def iter_local_dates_for_timelog_window(
    *,
    start_time: datetime,
    end_time: datetime,
) -> tuple[date, ...]:
    """Return every configured local operational date touched by a timelog window."""
    start_time = normalize_storage_datetime(start_time)
    end_time = normalize_storage_datetime(end_time)
    if end_time <= start_time:
        return ()
    final_moment = end_time - timedelta(microseconds=1)
    return iter_date_range(get_operational_date(start_time), get_operational_date(final_moment))


def overlap_minutes_for_window(
    *,
    start_time: datetime,
    end_time: datetime,
    window_start: datetime,
    window_end: datetime,
) -> int:
    """Return whole overlap minutes for one half-open window intersection."""
    start_time = normalize_storage_datetime(start_time)
    end_time = normalize_storage_datetime(end_time)
    window_start = normalize_storage_datetime(window_start)
    window_end = normalize_storage_datetime(window_end)
    overlap_start = max(start_time, window_start)
    overlap_end = min(end_time, window_end)
    if overlap_end <= overlap_start:
        return 0
    return int((overlap_end - overlap_start).total_seconds() // 60)


def resolve_stats_period(
    *,
    granularity: str,
    target_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    month: date | None = None,
    year: int | None = None,
) -> tuple[date, date]:
    """Resolve one supported stats granularity into concrete local date bounds."""
    if granularity == "day":
        if target_date is None:
            raise TimelogStatsValidationError("`day` stats require `target_date`.")
        return target_date, target_date
    if granularity == "range":
        if start_date is None or end_date is None:
            raise TimelogStatsValidationError("`range` stats require `start_date` and `end_date`.")
        return iter_date_range(start_date, end_date)[0], end_date
    if granularity == "week":
        if target_date is None:
            raise TimelogStatsValidationError("`week` stats require `target_date`.")
        return get_week_bounds(target_date)
    if granularity == "month":
        if month is None:
            raise TimelogStatsValidationError("`month` stats require `month`.")
        return get_month_bounds(month)
    if granularity == "year":
        if year is None:
            raise TimelogStatsValidationError("`year` stats require `year`.")
        return get_year_bounds(year)
    raise TimelogStatsValidationError(f"Unsupported timelog stats granularity: {granularity}")


async def _load_area_name_map(
    session: AsyncSession,
    *,
    area_ids: set[UUID],
) -> dict[UUID, str]:
    if not area_ids:
        return {}
    stmt = select(Area.id, Area.name).where(Area.id.in_(area_ids), Area.deleted_at.is_(None))
    return {area_id: name for area_id, name in (await session.execute(stmt)).all()}


async def _load_overlapping_area_timelogs(
    session: AsyncSession,
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[Timelog]:
    stmt = select(Timelog).where(
        Timelog.deleted_at.is_(None),
        Timelog.area_id.is_not(None),
        Timelog.end_time > window_start,
        Timelog.start_time < window_end,
    )
    return list((await session.execute(stmt)).scalars())


async def _collect_area_stats_for_window(
    session: AsyncSession,
    *,
    window_start: datetime,
    window_end: datetime,
    granularity: str,
    start_date: date,
    end_date: date,
) -> TimelogStatsReport:
    timezone_name = get_preferences_settings().timezone
    metrics: dict[UUID, dict[str, int]] = defaultdict(lambda: {"minutes": 0, "timelog_count": 0})
    timelogs = await _load_overlapping_area_timelogs(
        session,
        window_start=window_start,
        window_end=window_end,
    )
    for timelog in timelogs:
        if timelog.area_id is None:
            raise RuntimeError("Area-based timelog stats encountered a timelog without area_id.")
        minutes = overlap_minutes_for_window(
            start_time=timelog.start_time,
            end_time=timelog.end_time,
            window_start=window_start,
            window_end=window_end,
        )
        if minutes <= 0:
            continue
        metrics[timelog.area_id]["minutes"] += minutes
        metrics[timelog.area_id]["timelog_count"] += 1
    area_name_map = await _load_area_name_map(session, area_ids=set(metrics))
    rows = tuple(
        TimelogAreaStatsRow(
            area_id=area_id,
            area_name=area_name_map.get(area_id),
            minutes=payload["minutes"],
            timelog_count=payload["timelog_count"],
        )
        for area_id, payload in sorted(
            metrics.items(),
            key=lambda item: (
                -item[1]["minutes"],
                area_name_map.get(item[0]) or "",
                str(item[0]),
            ),
        )
    )
    return TimelogStatsReport(
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        timezone=timezone_name,
        rows=rows,
    )


async def _build_report_from_daily_rows(
    session: AsyncSession,
    *,
    target_date: date,
    rows: list[DailyTimelogStatsGroupByArea],
) -> TimelogStatsReport:
    area_name_map = await _load_area_name_map(session, area_ids={row.area_id for row in rows})
    return TimelogStatsReport(
        granularity="day",
        start_date=target_date,
        end_date=target_date,
        timezone=get_preferences_settings().timezone,
        rows=tuple(
            TimelogAreaStatsRow(
                area_id=row.area_id,
                area_name=area_name_map.get(row.area_id),
                minutes=row.minutes,
                timelog_count=row.timelog_count,
            )
            for row in sorted(
                rows,
                key=lambda item: (
                    -item.minutes,
                    area_name_map.get(item.area_id) or "",
                    str(item.area_id),
                ),
            )
        ),
    )


async def _build_report_from_aggregated_rows(
    session: AsyncSession,
    *,
    granularity: str,
    start_date: date,
    end_date: date,
    rows: list[AggregatedTimelogStatsGroupByArea],
) -> TimelogStatsReport:
    area_name_map = await _load_area_name_map(session, area_ids={row.area_id for row in rows})
    return TimelogStatsReport(
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        timezone=get_preferences_settings().timezone,
        rows=tuple(
            TimelogAreaStatsRow(
                area_id=row.area_id,
                area_name=area_name_map.get(row.area_id),
                minutes=row.minutes,
                timelog_count=row.timelog_count,
            )
            for row in sorted(
                rows,
                key=lambda item: (
                    -item.minutes,
                    area_name_map.get(item.area_id) or "",
                    str(item.area_id),
                ),
            )
        ),
    )


async def recompute_daily_timelog_stats_groupby_area_for_dates(
    session: AsyncSession,
    *,
    local_dates: tuple[date, ...],
) -> None:
    """Recompute persisted daily timelog stats grouped by area for local dates."""
    timezone_name = get_preferences_settings().timezone
    unique_dates = tuple(sorted(set(local_dates)))
    if not unique_dates:
        return

    for target_date in unique_dates:
        window_start, window_end = get_utc_window_for_local_date(target_date)
        metrics: dict[UUID, dict[str, int]] = defaultdict(
            lambda: {"minutes": 0, "timelog_count": 0}
        )
        timelogs = await _load_overlapping_area_timelogs(
            session,
            window_start=window_start,
            window_end=window_end,
        )
        for timelog in timelogs:
            if timelog.area_id is None:
                raise RuntimeError(
                    "Area-based timelog stats encountered a timelog without area_id."
                )
            minutes = overlap_minutes_for_window(
                start_time=timelog.start_time,
                end_time=timelog.end_time,
                window_start=window_start,
                window_end=window_end,
            )
            if minutes <= 0:
                continue
            metrics[timelog.area_id]["minutes"] += minutes
            metrics[timelog.area_id]["timelog_count"] += 1

        await session.execute(
            delete(DailyTimelogStatsGroupByArea).where(
                DailyTimelogStatsGroupByArea.stat_date == target_date,
                DailyTimelogStatsGroupByArea.timezone == timezone_name,
            )
        )
        session.add_all(
            [
                DailyTimelogStatsGroupByArea(
                    stat_date=target_date,
                    timezone=timezone_name,
                    area_id=area_id,
                    minutes=payload["minutes"],
                    timelog_count=payload["timelog_count"],
                )
                for area_id, payload in metrics.items()
            ]
        )
    await session.flush()


async def _recompute_aggregated_period(
    session: AsyncSession,
    *,
    granularity: str,
    start_date: date,
    end_date: date,
) -> None:
    timezone_name = get_preferences_settings().timezone
    window_start, window_end = get_utc_half_open_window_for_local_date_range(
        start_date,
        end_date,
    )
    daily_rows = (
        await session.execute(
            select(DailyTimelogStatsGroupByArea).where(
                DailyTimelogStatsGroupByArea.stat_date >= start_date,
                DailyTimelogStatsGroupByArea.stat_date <= end_date,
                DailyTimelogStatsGroupByArea.timezone == timezone_name,
            )
        )
    ).scalars()
    minutes_by_area: dict[UUID, int] = defaultdict(int)
    for daily_row in daily_rows:
        minutes_by_area[daily_row.area_id] += daily_row.minutes

    timelog_columns = (
        await session.execute(
            select(Timelog.area_id, Timelog.start_time, Timelog.end_time).where(
                Timelog.deleted_at.is_(None),
                Timelog.area_id.is_not(None),
                Timelog.end_time > window_start,
                Timelog.start_time < window_end,
            )
        )
    ).all()
    count_by_area: dict[UUID, int] = defaultdict(int)
    for area_id, start_time, end_time in timelog_columns:
        minutes = overlap_minutes_for_window(
            start_time=start_time,
            end_time=end_time,
            window_start=window_start,
            window_end=window_end,
        )
        if minutes > 0:
            count_by_area[area_id] += 1

    area_ids = set(minutes_by_area) | set(count_by_area)
    await session.execute(
        delete(AggregatedTimelogStatsGroupByArea).where(
            AggregatedTimelogStatsGroupByArea.granularity == granularity,
            AggregatedTimelogStatsGroupByArea.period_start == start_date,
            AggregatedTimelogStatsGroupByArea.period_end == end_date,
            AggregatedTimelogStatsGroupByArea.timezone == timezone_name,
        )
    )
    session.add_all(
        [
            AggregatedTimelogStatsGroupByArea(
                granularity=granularity,
                period_start=start_date,
                period_end=end_date,
                timezone=timezone_name,
                area_id=area_id,
                minutes=minutes_by_area[area_id],
                timelog_count=count_by_area[area_id],
            )
            for area_id in sorted(area_ids)
        ]
    )


async def recompute_aggregated_timelog_stats_groupby_area_for_dates(
    session: AsyncSession,
    *,
    local_dates: tuple[date, ...],
) -> None:
    """Recompute persisted week/month/year timelog stats grouped by area."""
    unique_dates = tuple(sorted(set(local_dates)))
    if not unique_dates:
        return
    periods: set[tuple[str, date, date]] = set()
    for target_date in unique_dates:
        periods.add(("week", *get_week_bounds(target_date)))
        periods.add(("month", *get_month_bounds(target_date)))
        periods.add(("year", *get_year_bounds(target_date.year)))
    for granularity, start_date, end_date in sorted(periods):
        await _recompute_aggregated_period(
            session,
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
        )
    await session.flush()


async def recompute_timelog_stats_groupby_area_after_change(
    session: AsyncSession,
    *,
    old_start_time: datetime | None,
    old_end_time: datetime | None,
    old_area_id: UUID | None,
    new_start_time: datetime | None,
    new_end_time: datetime | None,
    new_area_id: UUID | None,
) -> tuple[date, ...]:
    """Recompute affected persisted timelog stats after one timelog mutation."""
    affected_dates: set[date] = set()
    if old_area_id is not None and old_start_time is not None and old_end_time is not None:
        affected_dates.update(
            iter_local_dates_for_timelog_window(start_time=old_start_time, end_time=old_end_time)
        )
    if new_area_id is not None and new_start_time is not None and new_end_time is not None:
        affected_dates.update(
            iter_local_dates_for_timelog_window(start_time=new_start_time, end_time=new_end_time)
        )
    local_dates = tuple(sorted(affected_dates))
    if not local_dates:
        return ()
    await recompute_daily_timelog_stats_groupby_area_for_dates(session, local_dates=local_dates)
    await recompute_aggregated_timelog_stats_groupby_area_for_dates(
        session, local_dates=local_dates
    )
    return local_dates


async def get_timelog_stats_groupby_area_for_day(
    session: AsyncSession,
    *,
    target_date: date,
) -> TimelogStatsReport:
    """Return day timelog stats grouped by area."""
    timezone_name = get_preferences_settings().timezone
    stmt = select(DailyTimelogStatsGroupByArea).where(
        DailyTimelogStatsGroupByArea.stat_date == target_date,
        DailyTimelogStatsGroupByArea.timezone == timezone_name,
    )
    rows = list((await session.execute(stmt)).scalars())
    if rows:
        return await _build_report_from_daily_rows(session, target_date=target_date, rows=rows)
    window_start, window_end = get_utc_window_for_local_date(target_date)
    return await _collect_area_stats_for_window(
        session,
        window_start=window_start,
        window_end=window_end,
        granularity="day",
        start_date=target_date,
        end_date=target_date,
    )


async def get_timelog_stats_groupby_area_for_range(
    session: AsyncSession,
    *,
    start_date: date,
    end_date: date,
) -> TimelogStatsReport:
    """Return range timelog stats grouped by area using direct aggregation."""
    normalized_start_date, normalized_end_date = resolve_stats_period(
        granularity="range",
        start_date=start_date,
        end_date=end_date,
    )
    window_start, window_end = get_utc_half_open_window_for_local_date_range(
        normalized_start_date,
        normalized_end_date,
    )
    return await _collect_area_stats_for_window(
        session,
        window_start=window_start,
        window_end=window_end,
        granularity="range",
        start_date=normalized_start_date,
        end_date=normalized_end_date,
    )


async def get_timelog_stats_groupby_area_for_period(
    session: AsyncSession,
    *,
    granularity: str,
    target_date: date | None = None,
    month: date | None = None,
    year: int | None = None,
) -> TimelogStatsReport:
    """Return week, month, or year timelog stats grouped by area."""
    start_date, end_date = resolve_stats_period(
        granularity=granularity,
        target_date=target_date,
        month=month,
        year=year,
    )
    timezone_name = get_preferences_settings().timezone
    stmt = select(AggregatedTimelogStatsGroupByArea).where(
        AggregatedTimelogStatsGroupByArea.granularity == granularity,
        AggregatedTimelogStatsGroupByArea.period_start == start_date,
        AggregatedTimelogStatsGroupByArea.period_end == end_date,
        AggregatedTimelogStatsGroupByArea.timezone == timezone_name,
    )
    rows = list((await session.execute(stmt)).scalars())
    if rows:
        return await _build_report_from_aggregated_rows(
            session,
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
            rows=rows,
        )
    window_start, window_end = get_utc_half_open_window_for_local_date_range(
        start_date,
        end_date,
    )
    return await _collect_area_stats_for_window(
        session,
        window_start=window_start,
        window_end=window_end,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
    )


async def load_rebuildable_timelog_date_range(
    session: AsyncSession,
) -> tuple[date, date] | None:
    """Return the local date range that covers persisted area-based timelogs."""
    stmt = select(func.min(Timelog.start_time), func.max(Timelog.end_time)).where(
        Timelog.deleted_at.is_(None),
        Timelog.area_id.is_not(None),
    )
    earliest_start, latest_end = (await session.execute(stmt)).one()
    if earliest_start is None or latest_end is None:
        return None
    return get_operational_date(earliest_start), get_operational_date(
        latest_end - timedelta(microseconds=1)
    )


async def rebuild_timelog_stats_groupby_area(
    session: AsyncSession,
    *,
    date_values: tuple[date, ...] = (),
    start_date: date | None = None,
    end_date: date | None = None,
    rebuild_all: bool = False,
) -> tuple[date, ...]:
    """Rebuild persisted timelog stats grouped by area for a selected local scope."""
    if rebuild_all:
        if date_values or start_date is not None or end_date is not None:
            raise TimelogStatsValidationError("Use `--all` by itself, without date filters.")
        date_range = await load_rebuildable_timelog_date_range(session)
        if date_range is None:
            return ()
        local_dates = iter_date_range(*date_range)
    elif date_values:
        local_dates = tuple(sorted(set(date_values)))
    elif start_date is not None or end_date is not None:
        if start_date is None or end_date is None:
            raise TimelogStatsValidationError(
                "Provide `--date`, `--start-date/--end-date`, or `--all`."
            )
        local_dates = iter_date_range(start_date, end_date)
    else:
        raise TimelogStatsValidationError(
            "Select one rebuild scope with `--date`, `--start-date/--end-date`, or `--all`."
        )

    await recompute_daily_timelog_stats_groupby_area_for_dates(session, local_dates=local_dates)
    await recompute_aggregated_timelog_stats_groupby_area_for_dates(
        session, local_dates=local_dates
    )
    return local_dates
