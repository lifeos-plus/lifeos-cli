from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any, cast

import pytest

from lifeos_cli.config import clear_config_cache
from lifeos_cli.db.services import timelog_stats
from tests.config_support import install_test_config


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


def test_rebuild_timelog_stats_groupby_area_sorts_and_deduplicates_discrete_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_daily_dates: list[tuple[date, ...]] = []
    captured_aggregated_dates: list[tuple[date, ...]] = []

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
