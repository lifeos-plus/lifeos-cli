from __future__ import annotations

from datetime import date

import pytest

from lifeos_cli.application.calendar_adapter import (
    GregorianCalendarAdapter,
    MayanCalendarAdapter,
    get_calendar_adapter,
    get_calendar_period_range,
    iter_calendar_periods,
)
from lifeos_cli.config import ConfigurationError
from lifeos_cli.db.services.task_queries import _planning_cycle_date_filter_range


def test_gregorian_calendar_adapter_uses_configured_week_start() -> None:
    adapter = GregorianCalendarAdapter()

    assert adapter.week_range(date(2026, 7, 1), 1) == (
        date(2026, 6, 29),
        date(2026, 7, 5),
    )
    assert adapter.week_range(date(2026, 7, 1), 7) == (
        date(2026, 6, 28),
        date(2026, 7, 4),
    )


def test_mayan_calendar_adapter_resolves_year_moons_weeks_and_day_out_of_time() -> None:
    adapter = MayanCalendarAdapter()

    assert adapter.year_range(date(2026, 7, 26)) == (
        date(2026, 7, 26),
        date(2027, 7, 25),
    )
    assert adapter.year_range(date(2026, 7, 25)) == (
        date(2025, 7, 26),
        date(2026, 7, 25),
    )
    assert adapter.month_range(date(2026, 7, 26)) == (
        date(2026, 7, 26),
        date(2026, 8, 22),
    )
    assert adapter.month_range(date(2027, 7, 24)) == (
        date(2027, 6, 27),
        date(2027, 7, 24),
    )
    assert adapter.week_range(date(2026, 8, 2), 7) == (
        date(2026, 8, 2),
        date(2026, 8, 8),
    )
    assert adapter.month_range(date(2027, 7, 25)) == (
        date(2027, 7, 25),
        date(2027, 7, 25),
    )
    assert adapter.week_range(date(2027, 7, 25), 1) == (
        date(2027, 7, 25),
        date(2027, 7, 25),
    )
    assert adapter.month_range(date(2028, 2, 29)) == (
        date(2028, 2, 7),
        date(2028, 3, 6),
    )
    assert adapter.week_range(date(2028, 7, 24), 1) == (
        date(2028, 7, 18),
        date(2028, 7, 24),
    )
    assert adapter.week_range(date(2028, 7, 25), 1) == (
        date(2028, 7, 25),
        date(2028, 7, 25),
    )


def test_calendar_period_helpers_validate_calendar_system() -> None:
    with pytest.raises(ConfigurationError):
        get_calendar_adapter("martian")

    assert get_calendar_period_range(
        "7years",
        date(2026, 4, 10),
        calendar_system="gregorian",
    ) == (date(2026, 1, 1), date(2032, 12, 31))

    assert get_calendar_period_range(
        "month",
        date(2026, 8, 23),
        calendar_system="mayan_13_moon",
    ) == (date(2026, 8, 23), date(2026, 9, 19))


def test_iter_calendar_periods_deduplicates_mayan_buckets() -> None:
    periods = iter_calendar_periods(
        start=date(2026, 7, 24),
        end=date(2026, 7, 27),
        granularity="month",
        calendar_system="mayan_13_moon",
    )

    assert periods == (
        (date(2026, 6, 27), date(2026, 7, 24)),
        (date(2026, 7, 25), date(2026, 7, 25)),
        (date(2026, 7, 26), date(2026, 8, 22)),
    )


def test_iter_calendar_periods_keeps_mayan_week_boundaries_across_new_year() -> None:
    periods = iter_calendar_periods(
        start=date(2026, 7, 20),
        end=date(2026, 7, 28),
        granularity="week",
        calendar_system="mayan_13_moon",
    )

    assert periods == (
        (date(2026, 7, 18), date(2026, 7, 24)),
        (date(2026, 7, 25), date(2026, 7, 25)),
        (date(2026, 7, 26), date(2026, 8, 1)),
    )


def test_task_planning_cycle_filter_range_is_opt_in() -> None:
    assert (
        _planning_cycle_date_filter_range(
            planning_cycle_type="month",
            planning_cycle_start_date=date(2026, 7, 26),
            calendar_system=None,
            first_day_of_week=None,
        )
        is None
    )


def test_task_planning_cycle_filter_range_uses_mayan_periods() -> None:
    assert _planning_cycle_date_filter_range(
        planning_cycle_type="month",
        planning_cycle_start_date=date(2026, 7, 26),
        calendar_system="mayan_13_moon",
        first_day_of_week=1,
    ) == (date(2026, 7, 26), date(2026, 8, 22))

    assert _planning_cycle_date_filter_range(
        planning_cycle_type="7years",
        planning_cycle_start_date=date(2026, 7, 26),
        calendar_system="mayan_13_moon",
        first_day_of_week=1,
    ) == (date(2026, 7, 26), date(2033, 7, 25))

    assert _planning_cycle_date_filter_range(
        planning_cycle_type="week",
        planning_cycle_start_date=date(2027, 7, 25),
        calendar_system="mayan_13_moon",
        first_day_of_week=7,
    ) == (date(2027, 7, 25), date(2027, 7, 25))
