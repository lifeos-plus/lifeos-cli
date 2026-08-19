"""CLI-level tests for the menstrual, body, and sleep health resources."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from lifeos_cli import cli
from lifeos_cli.cli_support.help_audit import build_machine_readable_reference
from lifeos_cli.config import clear_config_cache
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import body_measurements as body_services
from lifeos_cli.db.services import menstrual as menstrual_services
from lifeos_cli.db.services import sleep as sleep_services
from tests.support import make_record, make_session_scope

DAY_UUID = UUID("11111111-1111-1111-1111-111111111111")
MEASUREMENT_UUID = UUID("22222222-2222-2222-2222-222222222222")
SEGMENT_UUID = UUID("33333333-3333-3333-3333-333333333333")

_ID_PATTERN = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


def _extract_created_id(output: str) -> str:
    match = _ID_PATTERN.search(output)
    if match is None:
        raise AssertionError(f"could not find identifier in output: {output!r}")
    return match.group(1)


def test_health_commands_are_part_of_machine_reference() -> None:
    reference = build_machine_readable_reference(cli.build_parser())
    paths = {tuple(command["path"]) for command in reference["commands"]}

    assert ("body-measurement", "add") in paths
    assert ("body-measurement", "show") in paths
    assert ("menstrual", "add") in paths
    assert ("menstrual", "list") in paths
    assert ("menstrual-factor", "add") in paths
    assert ("sleep", "add") in paths
    assert ("sleep", "summary") in paths


def test_menstrual_add_prints_confirmation_and_passes_args(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}

    async def fake_create_day(_session: object, **kwargs: Any) -> object:
        captured.update(kwargs)
        return make_record(
            id=DAY_UUID,
            log_date=kwargs["log_date"],
            in_period=kwargs["in_period"],
            flow_amount=kwargs["flow_amount"],
            symptoms=kwargs["symptoms"],
            factors=[],
            notes=kwargs["notes"],
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(menstrual_services, "create_menstrual_day", fake_create_day)

    exit_code = cli.main(
        [
            "menstrual",
            "add",
            "--date",
            "2026-08-19",
            "--in-period",
            "--flow",
            "medium",
            "--symptom",
            "headache",
            "--factor",
            "travel",
            "--notes",
            "evening",
        ]
    )
    captured_output = capsys.readouterr()

    assert exit_code == 0
    assert str(DAY_UUID) in captured_output.out
    assert captured["in_period"] is True
    assert captured["flow_amount"] == "medium"
    assert captured["symptoms"] == ["headache"]
    assert captured["factor_names"] == ["travel"]
    assert captured["notes"] == "evening"


def test_body_add_passes_input_unit_to_service(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}

    async def fake_create(_session: object, *, payload: Any) -> object:
        captured["payload"] = payload
        return make_record(id=MEASUREMENT_UUID, weight_kg=63.5)

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(body_services, "create_body_measurement", fake_create)

    exit_code = cli.main(
        [
            "body-measurement",
            "add",
            "--weight",
            "127",
            "--unit",
            "jin",
            "--body-fat",
            "22.5",
        ]
    )
    captured_output = capsys.readouterr()

    assert exit_code == 0
    assert str(MEASUREMENT_UUID) in captured_output.out
    payload = captured["payload"]
    assert payload.weight == 127.0
    assert payload.unit == "jin"
    assert payload.body_fat_percentage == 22.5


def test_sleep_add_prints_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create(_session: object, **kwargs: Any) -> object:
        assert kwargs["start_at"].tzinfo is not None
        assert kwargs["end_at"].tzinfo is not None
        return make_record(
            id=SEGMENT_UUID,
            sleep_date=kwargs["start_at"].date(),
            start_at=kwargs["start_at"],
            end_at=kwargs["end_at"],
            duration_minutes=480,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(sleep_services, "create_sleep_segment", fake_create)

    exit_code = cli.main(
        [
            "sleep",
            "add",
            "--start-time",
            "2026-08-18T22:30:00",
            "--end-time",
            "2026-08-19T06:30:00",
        ]
    )
    captured_output = capsys.readouterr()

    assert exit_code == 0
    assert str(SEGMENT_UUID) in captured_output.out


@pytest.fixture(autouse=True)
def _clear_sqlite_runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    clear_config_cache()
    db_session.clear_session_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "UTC")
    yield
    clear_config_cache()
    db_session.clear_session_cache()


def test_health_sqlite_workflow_round_trip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "lifeos-config.toml"
    database_path = tmp_path / "sqlite" / "lifeos.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))

    assert (
        cli.main(
            [
                "init",
                "--non-interactive",
                "--database-url",
                database_url,
                "--skip-ping",
                "--skip-migrate",
                "--timezone",
                "UTC",
                "--language",
                "en",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert cli.main(["db", "upgrade"]) == 0
    capsys.readouterr()

    assert cli.main(["menstrual-factor", "add", "--name", "travel"]) == 0
    capsys.readouterr()

    assert (
        cli.main(
            [
                "menstrual",
                "add",
                "--date",
                "2026-08-19",
                "--in-period",
                "--flow",
                "medium",
                "--symptom",
                "headache",
                "--factor",
                "travel",
            ]
        )
        == 0
    )
    menstrual_output = capsys.readouterr()
    menstrual_day_id = _extract_created_id(menstrual_output.out)

    assert (
        cli.main(
            [
                "body-measurement",
                "add",
                "--weight",
                "127",
                "--unit",
                "jin",
                "--body-fat",
                "22.5",
                "--measured-at",
                "2026-08-19T08:00:00",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        cli.main(
            [
                "sleep",
                "add",
                "--start-time",
                "2026-08-18T22:30:00",
                "--end-time",
                "2026-08-19T06:30:00",
            ]
        )
        == 0
    )
    capsys.readouterr()

    menstrual_list = cli.main(["menstrual", "list"])
    list_output = capsys.readouterr()
    assert menstrual_list == 0
    assert menstrual_day_id in list_output.out
    assert "travel" in list_output.out

    menstrual_date_list = cli.main(["menstrual", "list", "--date", "2026-08-19"])
    date_list_output = capsys.readouterr()
    assert menstrual_date_list == 0
    assert menstrual_day_id in date_list_output.out

    body_list = cli.main(["body-measurement", "list", "--json"])
    body_output = capsys.readouterr()
    assert body_list == 0
    assert '"weight_kg": 63.5' in body_output.out

    body_date_list = cli.main(["body-measurement", "list", "--date", "2026-08-19", "--json"])
    body_date_output = capsys.readouterr()
    assert body_date_list == 0
    assert '"weight_kg": 63.5' in body_date_output.out

    sleep_summary = cli.main(["sleep", "summary", "--date", "2026-08-18"])
    summary_output = capsys.readouterr()
    assert sleep_summary == 0
    assert "2026-08-18" in summary_output.out
    assert "480" in summary_output.out

    sleep_date_list = cli.main(["sleep", "list", "--date", "2026-08-18"])
    sleep_list_output = capsys.readouterr()
    assert sleep_date_list == 0
    assert "2026-08-18" in sleep_list_output.out
    assert "480" in sleep_list_output.out
