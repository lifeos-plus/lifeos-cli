"""Calendar period adapters shared by Web and application services."""

from __future__ import annotations

from calendar import isleap
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Protocol

from lifeos_cli.config import (
    DEFAULT_CALENDAR_FIRST_DAY_OF_WEEK,
    DEFAULT_CALENDAR_MAYAN_NEW_YEAR_START,
    DEFAULT_CALENDAR_SEVEN_YEAR_ANCHOR_YEAR,
    DEFAULT_CALENDAR_SYSTEM,
    validate_calendar_first_day_of_week,
    validate_calendar_mayan_new_year_start,
    validate_calendar_seven_year_anchor_year,
    validate_calendar_system,
)

CalendarGranularity = Literal["day", "week", "month", "year", "7years"]
_MAYAN_NEW_YEAR_DEFAULT_PARTS = DEFAULT_CALENDAR_MAYAN_NEW_YEAR_START.split("-")
DEFAULT_MAYAN_NEW_YEAR_START = (
    int(_MAYAN_NEW_YEAR_DEFAULT_PARTS[0]),
    int(_MAYAN_NEW_YEAR_DEFAULT_PARTS[1]),
)


class CalendarAdapter(Protocol):
    """Interface for calendar-specific period boundaries."""

    def week_range(self, target: date, first_day_of_week: int) -> tuple[date, date]:
        """Return inclusive week boundaries for the target date."""

    def month_range(self, target: date) -> tuple[date, date]:
        """Return inclusive month boundaries for the target date."""

    def year_range(self, target: date) -> tuple[date, date]:
        """Return inclusive year boundaries for the target date."""

    def seven_year_range(self, target: date) -> tuple[date, date]:
        """Return inclusive seven-year boundaries containing the target date."""


@dataclass(frozen=True)
class GregorianCalendarAdapter:
    """Standard Gregorian calendar adapter."""

    seven_year_anchor_year: int = DEFAULT_CALENDAR_SEVEN_YEAR_ANCHOR_YEAR

    def week_range(self, target: date, first_day_of_week: int) -> tuple[date, date]:
        normalized_first_day = validate_calendar_first_day_of_week(first_day_of_week)
        offset = (target.isoweekday() - normalized_first_day) % 7
        start = target - timedelta(days=offset)
        return start, start + timedelta(days=6)

    def month_range(self, target: date) -> tuple[date, date]:
        start = target.replace(day=1)
        if start.month == 12:
            next_month = date(start.year + 1, 1, 1)
        else:
            next_month = date(start.year, start.month + 1, 1)
        return start, next_month - timedelta(days=1)

    def year_range(self, target: date) -> tuple[date, date]:
        return date(target.year, 1, 1), date(target.year, 12, 31)

    def seven_year_range(self, target: date) -> tuple[date, date]:
        anchor_year = self.seven_year_anchor_year
        offset_years = ((target.year - anchor_year) // 7) * 7
        start = date(anchor_year + offset_years, 1, 1)
        end = date(start.year + 7, 1, 1) - timedelta(days=1)
        return start, end


@dataclass(frozen=True)
class MayanCalendarAdapter:
    """Mayan 13 Moon calendar adapter with 13 28-day moons and Day Out of Time."""

    moon_length_days: int = 28
    seven_year_anchor_year: int = DEFAULT_CALENDAR_SEVEN_YEAR_ANCHOR_YEAR
    new_year_start: tuple[int, int] = DEFAULT_MAYAN_NEW_YEAR_START

    def year_start(self, target: date) -> date:
        month, day = self.new_year_start
        start = date(target.year, month, day)
        if target >= start:
            return start
        return date(target.year - 1, month, day)

    def _day_out_of_time(self, target: date) -> date:
        """Return the Day Out of Time for the Mayan year containing target."""
        year_start = self.year_start(target)
        next_start = year_start.replace(year=year_start.year + 1)
        day_out_of_time = next_start - timedelta(days=1)
        if (day_out_of_time.month, day_out_of_time.day) == (2, 29):
            # February 29 is treated as February 28 so the 13-moon year stays
            # fixed at 365 days without intercalary-day boundary special cases.
            day_out_of_time = day_out_of_time.replace(day=28)
        return day_out_of_time

    def is_day_out_of_time(self, target: date) -> bool:
        """Return whether target is the Mayan Day Out of Time."""
        if (target.month, target.day) == (2, 29):
            target = target.replace(day=28)
        return target == self._day_out_of_time(target)

    def day_offset(self, target: date) -> int:
        start = self.year_start(target)
        offset = (target - start).days
        leap_day = self._leap_day(start)
        if leap_day is not None and target > leap_day:
            # February 29 is intercalary and must not shift later moon/week indices.
            offset -= 1
        return offset

    def _leap_day(self, year_start: date) -> date | None:
        leap_year = year_start.year + 1
        if not isleap(leap_year):
            return None
        return date(leap_year, 2, 29)

    def _date_for_offset(self, year_start: date, offset: int) -> date:
        target = year_start + timedelta(days=offset)
        leap_day = self._leap_day(year_start)
        if leap_day is not None and target >= leap_day:
            target += timedelta(days=1)
        return target

    def week_range(self, target: date, first_day_of_week: int) -> tuple[date, date]:
        del first_day_of_week
        if self.is_day_out_of_time(target):
            return target, target
        year_start = self.year_start(target)
        offset = self.day_offset(target)
        week_offset = (offset // 7) * 7
        return (
            self._date_for_offset(year_start, week_offset),
            self._date_for_offset(year_start, week_offset + 6),
        )

    def month_range(self, target: date) -> tuple[date, date]:
        if self.is_day_out_of_time(target):
            return target, target
        year_start = self.year_start(target)
        offset = self.day_offset(target)
        month_offset = (offset // self.moon_length_days) * self.moon_length_days
        return (
            self._date_for_offset(year_start, month_offset),
            self._date_for_offset(
                year_start,
                month_offset + self.moon_length_days - 1,
            ),
        )

    def year_range(self, target: date) -> tuple[date, date]:
        start = self.year_start(target)
        return start, start.replace(year=start.year + 1) - timedelta(days=1)

    def seven_year_range(self, target: date) -> tuple[date, date]:
        month, day = self.new_year_start
        anchor_start = date(self.seven_year_anchor_year, month, day)
        target_start = self.year_start(target)
        offset_years = ((target_start.year - anchor_start.year) // 7) * 7
        start = anchor_start.replace(year=anchor_start.year + offset_years)
        return start, start.replace(year=start.year + 7) - timedelta(days=1)


def get_calendar_adapter(
    system: str | None = None,
    *,
    seven_year_anchor_year: int | None = None,
    mayan_new_year_start: str | None = None,
) -> CalendarAdapter:
    """Return the adapter for a validated calendar system."""
    normalized = validate_calendar_system(system or DEFAULT_CALENDAR_SYSTEM)
    anchor_year = (
        validate_calendar_seven_year_anchor_year(seven_year_anchor_year)
        if seven_year_anchor_year is not None
        else DEFAULT_CALENDAR_SEVEN_YEAR_ANCHOR_YEAR
    )
    if normalized == "mayan_13_moon":
        new_year_start = (
            validate_calendar_mayan_new_year_start(mayan_new_year_start)
            if mayan_new_year_start is not None
            else DEFAULT_CALENDAR_MAYAN_NEW_YEAR_START
        )
        month, day = (int(part) for part in new_year_start.split("-"))
        return MayanCalendarAdapter(
            seven_year_anchor_year=anchor_year,
            new_year_start=(month, day),
        )
    return GregorianCalendarAdapter(seven_year_anchor_year=anchor_year)


def is_mayan_day_out_of_time(
    target: date,
    *,
    calendar_system: str | None = None,
    mayan_new_year_start: str | None = None,
) -> bool:
    """Return whether the date is the Mayan Day Out of Time for the user's calendar."""
    if validate_calendar_system(calendar_system or DEFAULT_CALENDAR_SYSTEM) != "mayan_13_moon":
        return False
    adapter = get_calendar_adapter(
        "mayan_13_moon",
        mayan_new_year_start=mayan_new_year_start,
    )
    if not isinstance(adapter, MayanCalendarAdapter):
        return False
    return adapter.is_day_out_of_time(target)


def get_calendar_period_range(
    granularity: CalendarGranularity,
    target: date,
    *,
    calendar_system: str | None = None,
    first_day_of_week: int | None = None,
    seven_year_anchor_year: int | None = None,
    mayan_new_year_start: str | None = None,
) -> tuple[date, date]:
    """Return inclusive period boundaries for a target date."""
    if granularity == "day":
        return target, target

    adapter = get_calendar_adapter(
        calendar_system,
        seven_year_anchor_year=seven_year_anchor_year,
        mayan_new_year_start=mayan_new_year_start,
    )
    normalized_first_day = validate_calendar_first_day_of_week(
        first_day_of_week or DEFAULT_CALENDAR_FIRST_DAY_OF_WEEK
    )
    if granularity == "week":
        return adapter.week_range(target, normalized_first_day)
    if granularity == "month":
        return adapter.month_range(target)
    if granularity == "year":
        return adapter.year_range(target)
    if granularity == "7years":
        return adapter.seven_year_range(target)
    raise ValueError(f"Unsupported calendar granularity: {granularity}")


def _is_out_of_time_singleton(
    period: tuple[date, date],
    *,
    granularity: CalendarGranularity,
    calendar_system: str | None,
    mayan_new_year_start: str | None,
) -> bool:
    """Return whether a week/month bucket is the Mayan Day Out of Time itself."""
    return (
        granularity in {"week", "month"}
        and period[0] == period[1]
        and is_mayan_day_out_of_time(
            period[0],
            calendar_system=calendar_system,
            mayan_new_year_start=mayan_new_year_start,
        )
    )


def iter_calendar_periods(
    *,
    start: date,
    end: date,
    granularity: CalendarGranularity,
    calendar_system: str | None = None,
    first_day_of_week: int | None = None,
    seven_year_anchor_year: int | None = None,
    mayan_new_year_start: str | None = None,
) -> tuple[tuple[date, date], ...]:
    """Return sorted unique period buckets touched by an inclusive date range.

    The walk advances by one full bucket at a time, so the cost scales with
    the number of buckets rather than the number of days. For the Mayan 13
    Moon calendar, the Day Out of Time (the day before the configured new year
    start) belongs to no week or moon, so week and month buckets never include
    it as a single-day bucket of its own; day, year, and seven-year buckets
    keep the date.
    """
    if end < start:
        raise ValueError("end must be on or after start")

    periods: dict[tuple[date, date], None] = {}
    cursor = start
    while cursor <= end:
        period = get_calendar_period_range(
            granularity,
            cursor,
            calendar_system=calendar_system,
            first_day_of_week=first_day_of_week,
            seven_year_anchor_year=seven_year_anchor_year,
            mayan_new_year_start=mayan_new_year_start,
        )
        if _is_out_of_time_singleton(
            period,
            granularity=granularity,
            calendar_system=calendar_system,
            mayan_new_year_start=mayan_new_year_start,
        ):
            cursor += timedelta(days=1)
            continue
        periods.setdefault(period, None)
        cursor = period[1] + timedelta(days=1)
    return tuple(sorted(periods, key=lambda period: (period[0], period[1])))
