from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from lifeos_cli.application.time_preferences import (
    apply_preferred_timezone,
    get_day_start_datetime,
    get_operational_date,
    get_utc_half_open_window_for_local_date_range,
    get_utc_window_for_local_date,
    get_week_bounds,
    to_preferred_timezone,
    to_storage_timezone,
)
from lifeos_cli.config import clear_config_cache
from tests.config_support import install_test_config


def test_to_preferred_timezone_uses_configured_timezone(monkeypatch, tmp_path) -> None:
    install_test_config(monkeypatch=monkeypatch, tmp_path=tmp_path, include_preferences=True)

    converted = to_preferred_timezone(datetime(2026, 4, 10, 7, 30, tzinfo=UTC))

    assert converted.isoformat() == "2026-04-10T03:30:00-04:00"
    clear_config_cache()


def test_apply_preferred_timezone_attaches_configured_timezone(monkeypatch, tmp_path) -> None:
    install_test_config(monkeypatch=monkeypatch, tmp_path=tmp_path, include_preferences=True)

    converted = apply_preferred_timezone(datetime(2026, 4, 10, 9, 0))

    assert converted.isoformat() == "2026-04-10T09:00:00-04:00"
    clear_config_cache()


def test_apply_preferred_timezone_rejects_skipped_dst_time(monkeypatch, tmp_path) -> None:
    install_test_config(monkeypatch=monkeypatch, tmp_path=tmp_path, include_preferences=True)

    try:
        with pytest.raises(ValueError, match="does not exist"):
            apply_preferred_timezone(datetime(2026, 3, 8, 2, 30))
    finally:
        clear_config_cache()


def test_to_storage_timezone_preserves_explicit_timezone(monkeypatch, tmp_path) -> None:
    install_test_config(monkeypatch=monkeypatch, tmp_path=tmp_path, include_preferences=True)

    normalized = to_storage_timezone(datetime(2026, 4, 10, 9, 0, tzinfo=UTC))

    assert normalized.isoformat() == "2026-04-10T09:00:00+00:00"
    clear_config_cache()


def test_get_operational_date_respects_day_start_boundary(monkeypatch, tmp_path) -> None:
    install_test_config(monkeypatch=monkeypatch, tmp_path=tmp_path, include_preferences=True)

    before_boundary = datetime(2026, 4, 10, 6, 0, tzinfo=UTC)
    after_boundary = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)

    assert get_operational_date(before_boundary) == date(2026, 4, 9)
    assert get_operational_date(after_boundary) == date(2026, 4, 10)
    clear_config_cache()


def test_get_utc_window_for_local_date_respects_day_start_boundary(monkeypatch, tmp_path) -> None:
    install_test_config(monkeypatch=monkeypatch, tmp_path=tmp_path, include_preferences=True)

    window_start, window_end = get_utc_window_for_local_date(date(2026, 4, 10))

    assert window_start.isoformat() == "2026-04-10T08:00:00+00:00"
    assert window_end.isoformat() == "2026-04-11T08:00:00+00:00"
    clear_config_cache()


def test_get_day_start_datetime_uses_configured_timezone_and_day_start(
    monkeypatch,
    tmp_path,
) -> None:
    install_test_config(monkeypatch=monkeypatch, tmp_path=tmp_path, include_preferences=True)

    day_start = get_day_start_datetime(date(2026, 4, 10))

    assert day_start.isoformat() == "2026-04-10T04:00:00-04:00"
    clear_config_cache()


def test_get_utc_half_open_window_for_local_date_range_keeps_exclusive_end(
    monkeypatch,
    tmp_path,
) -> None:
    install_test_config(monkeypatch=monkeypatch, tmp_path=tmp_path, include_preferences=True)

    window_start, window_end = get_utc_half_open_window_for_local_date_range(
        date(2026, 4, 10),
        date(2026, 4, 11),
    )

    assert window_start.isoformat() == "2026-04-10T08:00:00+00:00"
    assert window_end.isoformat() == "2026-04-12T08:00:00+00:00"
    clear_config_cache()


def test_get_week_bounds_respects_configured_week_start(monkeypatch, tmp_path) -> None:
    install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        week_starts_on="sunday",
    )

    week_start, week_end = get_week_bounds(date(2026, 4, 9))

    assert week_start == date(2026, 4, 5)
    assert week_end == date(2026, 4, 11)
    clear_config_cache()
