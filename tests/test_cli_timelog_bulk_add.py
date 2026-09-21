from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from lifeos_cli.cli_support.resources.timelog.bulk_add import parse_bulk_timelog_text
from lifeos_cli.config import clear_config_cache


def _set_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "America/Toronto")


def test_parse_bulk_timelog_text_infers_start_times_from_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_timezone(monkeypatch)
    drafts = parse_bulk_timelog_text(
        "0700 Breakfast\n0830 Deep work\n0100 Wrap up",
        first_start_time=datetime.fromisoformat("2026-04-10T06:30:00"),
    )

    assert len(drafts) == 3
    assert drafts[0].start_time.isoformat() == "2026-04-10T06:30:00-04:00"
    assert drafts[0].end_time.isoformat() == "2026-04-10T07:00:00-04:00"
    assert drafts[1].start_time.isoformat() == "2026-04-10T07:00:00-04:00"
    assert drafts[1].end_time.isoformat() == "2026-04-10T08:30:00-04:00"
    assert drafts[2].start_time.isoformat() == "2026-04-10T08:30:00-04:00"
    assert drafts[2].end_time.isoformat() == "2026-04-11T01:00:00-04:00"
    assert drafts[2].warnings == ("end crossed midnight into the next day",)
    clear_config_cache()


def test_parse_bulk_timelog_text_handles_time_ranges_with_rollover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_timezone(monkeypatch)
    drafts = parse_bulk_timelog_text(
        "23:00-00:30 Night review",
        first_start_time=datetime.fromisoformat("2026-04-10T06:30:00"),
    )

    assert len(drafts) == 1
    assert drafts[0].start_time.isoformat() == "2026-04-10T23:00:00-04:00"
    assert drafts[0].end_time.isoformat() == "2026-04-11T00:30:00-04:00"
    assert drafts[0].warnings == ("end crossed midnight into the next day",)
    clear_config_cache()


def test_parse_bulk_timelog_text_keeps_zero_length_end_only_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_timezone(monkeypatch)
    drafts = parse_bulk_timelog_text(
        "0800 Meditation",
        first_start_time=datetime.fromisoformat("2026-04-10T08:00:00"),
    )

    assert len(drafts) == 1
    assert drafts[0].start_time.isoformat() == "2026-04-10T08:00:00-04:00"
    assert drafts[0].end_time.isoformat() == "2026-04-10T08:00:00-04:00"
    assert drafts[0].end_time - drafts[0].start_time == timedelta(0)
    assert drafts[0].warnings == ()
    clear_config_cache()


def test_parse_bulk_timelog_text_keeps_zero_length_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_timezone(monkeypatch)
    drafts = parse_bulk_timelog_text(
        "10:00-10:00 Meditation",
        first_start_time=datetime.fromisoformat("2026-04-10T06:30:00"),
    )

    assert len(drafts) == 1
    assert drafts[0].start_time.isoformat() == "2026-04-10T10:00:00-04:00"
    assert drafts[0].end_time.isoformat() == "2026-04-10T10:00:00-04:00"
    assert drafts[0].end_time - drafts[0].start_time == timedelta(0)
    assert drafts[0].warnings == ()
    clear_config_cache()


def test_parse_bulk_timelog_text_rejects_unparseable_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_timezone(monkeypatch)
    with pytest.raises(RuntimeError, match="could not parse quick timelog entry"):
        parse_bulk_timelog_text(
            "Breakfast without time",
            first_start_time=datetime.fromisoformat("2026-04-10T06:30:00"),
        )
    clear_config_cache()
