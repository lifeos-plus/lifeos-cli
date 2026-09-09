from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any, cast

import pytest

from lifeos_cli.config import clear_config_cache
from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.services import timelog_stats
from tests.config_support import install_test_config
from tests.support import sqlite_session_factory, utc_datetime


@pytest.fixture
def configured_time_preferences(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[None]:
    install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        week_starts_on="sunday",
    )
    yield
    clear_config_cache()


@pytest.fixture
def configured_mayan_time_preferences(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> Iterator[None]:
    install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        timezone="UTC",
        day_starts_at="00:00",
        calendar_system="mayan_13_moon",
    )
    yield
    clear_config_cache()


@pytest.fixture
def configured_gregorian_time_preferences(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> Iterator[None]:
    install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        timezone="UTC",
        day_starts_at="00:00",
        calendar_system="gregorian",
    )
    yield
    clear_config_cache()


@pytest.fixture
def configured_custom_mayan_time_preferences(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> Iterator[None]:
    install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        timezone="UTC",
        day_starts_at="00:00",
        calendar_system="mayan_13_moon",
        mayan_new_year_start="03-01",
    )
    yield
    clear_config_cache()


async def _seed_area_timelogs(session) -> Area:
    area = Area(name="Deep work")
    session.add(area)
    await session.flush()
    session.add_all(
        [
            Timelog(
                title="Day out of time only",
                start_time=utc_datetime(2026, 7, 25, 10),
                end_time=utc_datetime(2026, 7, 25, 11),
                area_id=area.id,
            ),
            Timelog(
                title="Multi-day around day out of time",
                start_time=utc_datetime(2026, 7, 24, 12),
                end_time=utc_datetime(2026, 7, 26, 12),
                area_id=area.id,
            ),
        ]
    )
    await session.flush()
    return area


async def _seed_custom_new_year_timelogs(session) -> Area:
    area = Area(name="Deep work")
    session.add(area)
    await session.flush()
    session.add_all(
        [
            Timelog(
                title="Day out of time only",
                start_time=utc_datetime(2028, 2, 28, 10),
                end_time=utc_datetime(2028, 2, 28, 11),
                area_id=area.id,
            ),
            Timelog(
                title="Leap day treated as day out of time",
                start_time=utc_datetime(2028, 2, 29, 10),
                end_time=utc_datetime(2028, 2, 29, 11),
                area_id=area.id,
            ),
            Timelog(
                title="Normal week day",
                start_time=utc_datetime(2028, 2, 27, 12),
                end_time=utc_datetime(2028, 2, 27, 13),
                area_id=area.id,
            ),
        ]
    )
    await session.flush()
    return area


@pytest.mark.usefixtures("configured_time_preferences")
def test_iter_local_dates_for_timelog_window_respects_day_boundary() -> None:
    local_dates = timelog_stats.iter_local_dates_for_timelog_window(
        start_time=datetime(2026, 4, 10, 7, 30, tzinfo=UTC),
        end_time=datetime(2026, 4, 10, 9, 30, tzinfo=UTC),
    )

    assert local_dates == (date(2026, 4, 9), date(2026, 4, 10))


def test_overlap_minutes_for_window_returns_whole_minutes() -> None:
    minutes = timelog_stats.overlap_minutes_for_window(
        start_time=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
        end_time=datetime(2026, 4, 10, 13, 1, tzinfo=UTC),
        window_start=datetime(2026, 4, 10, 12, 30, tzinfo=UTC),
        window_end=datetime(2026, 4, 10, 13, 0, 59, tzinfo=UTC),
    )

    assert minutes == 30


def test_overlap_minutes_for_window_treats_naive_storage_values_as_utc() -> None:
    minutes = timelog_stats.overlap_minutes_for_window(
        start_time=datetime(2026, 4, 10, 12, 0),
        end_time=datetime(2026, 4, 10, 13, 0),
        window_start=datetime(2026, 4, 10, 12, 30, tzinfo=UTC),
        window_end=datetime(2026, 4, 10, 13, 30, tzinfo=UTC),
    )

    assert minutes == 30


def test_overlap_minutes_for_window_keeps_final_boundary_minute() -> None:
    minutes = timelog_stats.overlap_minutes_for_window(
        start_time=datetime(2026, 3, 22, 15, 10, tzinfo=UTC),
        end_time=datetime(2026, 3, 22, 22, 10, tzinfo=UTC),
        window_start=datetime(2026, 3, 15, 16, 0, tzinfo=UTC),
        window_end=datetime(2026, 3, 22, 16, 0, tzinfo=UTC),
    )

    assert minutes == 50


@pytest.mark.usefixtures("configured_time_preferences")
def test_resolve_stats_period_uses_configured_week_boundary() -> None:
    start_date, end_date = timelog_stats.resolve_stats_period(
        granularity="week",
        target_date=date(2026, 4, 9),
    )

    assert start_date == date(2026, 4, 5)
    assert end_date == date(2026, 4, 11)


def test_get_month_bounds_returns_full_calendar_month() -> None:
    start_date, end_date = timelog_stats.get_month_bounds(date(2026, 2, 1))

    assert start_date == date(2026, 2, 1)
    assert end_date == date(2026, 2, 28)


def test_get_year_bounds_returns_full_calendar_year() -> None:
    start_date, end_date = timelog_stats.get_year_bounds(2026)

    assert start_date == date(2026, 1, 1)
    assert end_date == date(2026, 12, 31)


@pytest.mark.usefixtures("configured_mayan_time_preferences")
def test_range_stats_keep_mayan_day_out_of_time_for_single_day_range() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await _seed_area_timelogs(session)

                report = await timelog_stats.get_timelog_stats_groupby_area_for_range(
                    session,
                    start_date=date(2026, 7, 25),
                    end_date=date(2026, 7, 25),
                )

                # A single-day range is a day query: the Day Out of Time keeps
                # its own stats (60 min on the day + 1440 min from the
                # multi-day timelog), matching the day view.
                assert len(report.rows) == 1
                assert report.rows[0].minutes == 1500
                assert report.rows[0].timelog_count == 2

    asyncio.run(scenario())


@pytest.mark.usefixtures("configured_mayan_time_preferences")
def test_day_stats_keep_mayan_day_out_of_time() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await _seed_area_timelogs(session)

                report = await timelog_stats.get_timelog_stats_groupby_area_for_day(
                    session,
                    target_date=date(2026, 7, 25),
                )

                assert len(report.rows) == 1
                assert report.rows[0].minutes == 1500
                assert report.rows[0].timelog_count == 2

    asyncio.run(scenario())


@pytest.mark.usefixtures("configured_mayan_time_preferences")
def test_range_stats_keep_mayan_day_out_of_time_in_wider_range() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await _seed_area_timelogs(session)

                report = await timelog_stats.get_timelog_stats_groupby_area_for_range(
                    session,
                    start_date=date(2026, 7, 24),
                    end_date=date(2026, 7, 26),
                )

                assert len(report.rows) == 1
                assert report.rows[0].minutes == 2940
                assert report.rows[0].timelog_count == 2

    asyncio.run(scenario())


@pytest.mark.usefixtures("configured_mayan_time_preferences")
def test_week_month_period_stats_exclude_mayan_day_out_of_time() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await _seed_area_timelogs(session)

                week_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="week",
                    target_date=date(2026, 7, 25),
                )
                month_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="month",
                    month=date(2026, 7, 1),
                )
                year_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="year",
                    year=2026,
                )

                assert week_report.start_date == date(2026, 7, 20)
                assert week_report.end_date == date(2026, 7, 26)
                assert len(week_report.rows) == 1
                assert week_report.rows[0].minutes == 1440
                assert week_report.rows[0].timelog_count == 1
                assert len(month_report.rows) == 1
                assert month_report.rows[0].minutes == 1440
                assert month_report.rows[0].timelog_count == 1
                assert len(year_report.rows) == 1
                assert year_report.rows[0].minutes == 2940
                assert year_report.rows[0].timelog_count == 2

    asyncio.run(scenario())


@pytest.mark.usefixtures("configured_custom_mayan_time_preferences")
def test_week_month_period_stats_exclude_custom_mayan_day_out_of_time() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await _seed_custom_new_year_timelogs(session)

                doot_week_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="week",
                    target_date=date(2028, 2, 29),
                )
                normal_week_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="week",
                    target_date=date(2028, 2, 27),
                )
                month_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="month",
                    month=date(2028, 2, 1),
                )

                assert doot_week_report.rows == ()
                assert len(normal_week_report.rows) == 1
                assert normal_week_report.rows[0].minutes == 60
                assert normal_week_report.rows[0].timelog_count == 1
                assert len(month_report.rows) == 1
                assert month_report.rows[0].minutes == 60
                assert month_report.rows[0].timelog_count == 1

    asyncio.run(scenario())


@pytest.mark.usefixtures("configured_gregorian_time_preferences")
def test_week_month_period_stats_keep_july_25_for_gregorian_calendar() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await _seed_area_timelogs(session)

                week_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="week",
                    target_date=date(2026, 7, 25),
                )
                month_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="month",
                    month=date(2026, 7, 1),
                )

                assert len(week_report.rows) == 1
                assert week_report.rows[0].minutes == 2940
                assert week_report.rows[0].timelog_count == 2
                assert len(month_report.rows) == 1
                assert month_report.rows[0].minutes == 2940
                assert month_report.rows[0].timelog_count == 2

    asyncio.run(scenario())


@pytest.mark.usefixtures("configured_mayan_time_preferences")
def test_recompute_aggregated_week_month_excludes_mayan_day_out_of_time() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await _seed_area_timelogs(session)
                local_dates = (
                    date(2026, 7, 24),
                    date(2026, 7, 25),
                    date(2026, 7, 26),
                )
                await timelog_stats.recompute_daily_timelog_stats_groupby_area_for_dates(
                    session,
                    local_dates=local_dates,
                )
                await timelog_stats.recompute_aggregated_timelog_stats_groupby_area_for_dates(
                    session,
                    local_dates=local_dates,
                )

                week_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="week",
                    target_date=date(2026, 7, 25),
                )
                month_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="month",
                    month=date(2026, 7, 1),
                )
                year_report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                    session,
                    granularity="year",
                    year=2026,
                )

                assert week_report.granularity == "week"
                assert len(week_report.rows) == 1
                assert week_report.rows[0].minutes == 1440
                assert week_report.rows[0].timelog_count == 1
                assert len(month_report.rows) == 1
                assert month_report.rows[0].minutes == 1440
                assert month_report.rows[0].timelog_count == 1
                assert len(year_report.rows) == 1
                assert year_report.rows[0].minutes == 2940
                assert year_report.rows[0].timelog_count == 2

    asyncio.run(scenario())


def test_rebuild_timelog_stats_groupby_area_sorts_and_deduplicates_discrete_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_daily_dates: list[tuple[date, ...]] = []
    captured_aggregated_dates: list[tuple[date, ...]] = []

    async def fake_lock(_: object) -> None:
        return None

    monkeypatch.setattr(timelog_stats, "lock_planning_writes", fake_lock)

    async def fake_recompute_daily(_: object, *, local_dates: tuple[date, ...]) -> None:
        captured_daily_dates.append(local_dates)

    async def fake_recompute_aggregated(_: object, *, local_dates: tuple[date, ...]) -> None:
        captured_aggregated_dates.append(local_dates)

    monkeypatch.setattr(
        timelog_stats,
        "recompute_daily_timelog_stats_groupby_area_for_dates",
        fake_recompute_daily,
    )
    monkeypatch.setattr(
        timelog_stats,
        "recompute_aggregated_timelog_stats_groupby_area_for_dates",
        fake_recompute_aggregated,
    )

    rebuilt_dates = asyncio.run(
        timelog_stats.rebuild_timelog_stats_groupby_area(
            cast(Any, object()),
            date_values=(date(2026, 4, 3), date(2026, 4, 1), date(2026, 4, 3)),
        )
    )

    assert rebuilt_dates == (date(2026, 4, 1), date(2026, 4, 3))
    assert captured_daily_dates == [(date(2026, 4, 1), date(2026, 4, 3))]
    assert captured_aggregated_dates == [(date(2026, 4, 1), date(2026, 4, 3))]
