from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lifeos_cli.application.calendar_adapter import (
    GregorianCalendarAdapter,
    MayanCalendarAdapter,
    get_calendar_adapter,
    get_calendar_period_range,
    iter_calendar_periods,
)
from lifeos_cli.application.preferences import CalendarPreferences
from lifeos_cli.config import ConfigurationError
from lifeos_cli.db.base import Base
from lifeos_cli.db.models import Task, Vision
from lifeos_cli.db.services import task_queries
from lifeos_cli.db.services.task_queries import (
    _planning_cycle_date_filter_range,
    count_tasks,
)


def test_get_calendar_preferences_reads_persisted_user_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lifeos_cli.application import preferences as preference_access

    monkeypatch.setattr(
        preference_access,
        "get_preferences_settings",
        lambda: SimpleNamespace(
            calendar_system="mayan_13_moon",
            calendar_first_day_of_week=7,
            calendar_seven_year_anchor_date="2025-07-26",
        ),
    )

    resolved = preference_access.get_calendar_preferences()

    assert resolved == CalendarPreferences(
        system="mayan_13_moon",
        first_day_of_week=7,
        seven_year_anchor_date=date(2025, 7, 26),
    )


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
    ) == (date(2025, 1, 1), date(2031, 12, 31))

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


def test_task_planning_cycle_filter_range_reads_persisted_preferences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_queries,
        "get_calendar_preferences",
        lambda: CalendarPreferences(
            system="mayan_13_moon",
            first_day_of_week=7,
            seven_year_anchor_date=date(2025, 7, 26),
        ),
    )

    assert _planning_cycle_date_filter_range(
        planning_cycle_type="month",
        planning_cycle_start_date=date(2026, 7, 26),
    ) == (date(2026, 7, 26), date(2026, 8, 22))
    assert (
        _planning_cycle_date_filter_range(
            planning_cycle_type="unsupported",
            planning_cycle_start_date=date(2026, 7, 26),
        )
        is None
    )


def test_task_planning_cycle_filter_range_uses_mayan_periods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_queries,
        "get_calendar_preferences",
        lambda: CalendarPreferences(
            system="mayan_13_moon",
            first_day_of_week=7,
            seven_year_anchor_date=date(2025, 7, 26),
        ),
    )

    assert _planning_cycle_date_filter_range(
        planning_cycle_type="month",
        planning_cycle_start_date=date(2026, 7, 26),
    ) == (date(2026, 7, 26), date(2026, 8, 22))

    assert _planning_cycle_date_filter_range(
        planning_cycle_type="7years",
        planning_cycle_start_date=date(2026, 7, 26),
    ) == (date(2025, 7, 26), date(2032, 7, 25))

    assert _planning_cycle_date_filter_range(
        planning_cycle_type="week",
        planning_cycle_start_date=date(2027, 7, 25),
    ) == (date(2027, 7, 25), date(2027, 7, 25))


def test_task_planning_cycle_filter_includes_overlapping_physical_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_queries,
        "get_calendar_preferences",
        lambda: CalendarPreferences(
            system="gregorian",
            first_day_of_week=1,
            seven_year_anchor_date=date(2025, 7, 26),
        ),
    )

    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                vision = Vision(name="Planning")
                session.add(vision)
                await session.flush()
                session.add_all(
                    [
                        Task(
                            vision_id=vision.id,
                            content="Overlaps August",
                            planning_cycle_type="month",
                            planning_cycle_days=22,
                            planning_cycle_start_date=date(2026, 7, 25),
                        ),
                        Task(
                            vision_id=vision.id,
                            content="Ends before August",
                            planning_cycle_type="month",
                            planning_cycle_days=24,
                            planning_cycle_start_date=date(2026, 7, 1),
                        ),
                    ]
                )
                await session.commit()

                count = await count_tasks(
                    session,
                    planning_cycle_type="month",
                    planning_cycle_start_date=date(2026, 8, 1),
                )

                assert count == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_seven_year_ranges_follow_the_configured_anchor_for_each_calendar() -> None:
    anchor = date(2028, 3, 15)

    assert get_calendar_period_range(
        "7years",
        date(2027, 12, 31),
        calendar_system="gregorian",
        seven_year_anchor_date=anchor,
    ) == (date(2021, 1, 1), date(2027, 12, 31))
    assert get_calendar_period_range(
        "7years",
        date(2028, 1, 1),
        calendar_system="mayan_13_moon",
        seven_year_anchor_date=anchor,
    ) == (date(2027, 7, 26), date(2034, 7, 25))
