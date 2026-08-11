from __future__ import annotations

from datetime import UTC, datetime

from lifeos_cli.application.datetime_utils import (
    normalize_iso_datetime_input,
    parse_iso_datetime_input,
)


def test_normalize_iso_datetime_input_accepts_utc_z_suffix() -> None:
    assert (
        normalize_iso_datetime_input("2026-06-16T16:00:00.000Z") == "2026-06-16T16:00:00.000+00:00"
    )


def test_normalize_iso_datetime_input_preserves_offset_suffix() -> None:
    assert normalize_iso_datetime_input("2026-06-16T12:00:00-04:00") == "2026-06-16T12:00:00-04:00"


def test_parse_iso_datetime_input_parses_utc_z_suffix() -> None:
    parsed = parse_iso_datetime_input("2026-06-16T16:00:00.000Z")

    assert parsed == datetime(2026, 6, 16, 16, 0, tzinfo=UTC)
