"""End-to-end HTTP tests for the health data Web API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest

from lifeos_cli import cli
from lifeos_cli.config import clear_config_cache
from lifeos_cli.db import session as db_session
from tests.config_support import write_test_config


@pytest.fixture
def http_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide a TestClient backed by an isolated temporary SQLite database."""
    from fastapi.testclient import TestClient

    from lifeos_web.app import create_app

    database_path = tmp_path / "lifeos-health-http-test.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    config_path = write_test_config(
        tmp_path / "lifeos-config.toml",
        include_database=True,
        database_url=database_url,
        database_schema=None,
        include_preferences=True,
        timezone="UTC",
        language="en",
    )
    clear_config_cache()
    db_session.clear_session_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))

    assert cli.main(["db", "upgrade"]) == 0

    with TestClient(create_app()) as client:
        yield client

    clear_config_cache()
    db_session.clear_session_cache()


def test_menstrual_day_and_factor_http_round_trip(http_client) -> None:
    factor_response = http_client.post(
        "/api/v1/menstrual-factors/",
        json={"name": "travel"},
    )
    assert factor_response.status_code == 200
    factor_id = factor_response.json()["id"]

    create_response = http_client.post(
        "/api/v1/menstrual-days/",
        json={
            "log_date": "2026-08-19",
            "in_period": True,
            "flow_amount": "medium",
            "symptoms": ["headache", "hot_flash"],
            "factor_names": ["travel"],
            "spotting": True,
            "notes": "evening",
        },
    )
    assert create_response.status_code == 200
    day = create_response.json()
    day_id = day["id"]
    assert day["log_date"] == "2026-08-19"
    assert day["in_period"] is True
    assert day["factors"] == [{"id": factor_id, "name": "travel"}]

    list_response = http_client.get(
        "/api/v1/menstrual-days/",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["pagination"]["total"] == 1

    update_response = http_client.patch(
        f"/api/v1/menstrual-days/{day_id}",
        json={"flow_amount": "low", "clear_symptoms": True},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["flow_amount"] == "low"
    assert updated["symptoms"] == []

    duplicate_response = http_client.post(
        "/api/v1/menstrual-days/",
        json={"log_date": "2026-08-19"},
    )
    assert duplicate_response.status_code == 400

    delete_response = http_client.delete(f"/api/v1/menstrual-days/{day_id}")
    assert delete_response.status_code == 204
    assert http_client.get(f"/api/v1/menstrual-days/{day_id}").status_code == 404


def test_body_measurement_http_round_trip_with_unit_conversion(http_client) -> None:
    create_response = http_client.post(
        "/api/v1/body-measurements/",
        json={
            "measured_at": "2026-08-19T08:00:00",
            "weight": 127,
            "unit": "jin",
            "body_fat_percentage": 22.5,
            "notes": "morning",
        },
    )
    assert create_response.status_code == 200
    measurement = create_response.json()
    measurement_id = measurement["id"]
    assert measurement["weight_kg"] == 63.5
    assert measurement["body_fat_percentage"] == 22.5

    update_response = http_client.patch(
        f"/api/v1/body-measurements/{measurement_id}",
        json={"weight": 65, "clear_fields": ["body_fat_percentage"]},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["weight_kg"] == 65.0
    assert updated["body_fat_percentage"] is None

    invalid_response = http_client.post(
        "/api/v1/body-measurements/",
        json={"measured_at": "2026-08-19T08:00:00", "weight": -5},
    )
    assert invalid_response.status_code == 400

    delete_response = http_client.delete(f"/api/v1/body-measurements/{measurement_id}")
    assert delete_response.status_code == 204


def test_sleep_segment_and_summary_http_round_trip(http_client) -> None:
    create_response = http_client.post(
        "/api/v1/sleep-segments/",
        json={
            "start_at": "2026-08-18T22:30:00",
            "end_at": "2026-08-19T06:30:00",
        },
    )
    assert create_response.status_code == 200
    segment = create_response.json()
    segment_id = segment["id"]
    assert segment["sleep_date"] == "2026-08-18"
    assert segment["duration_minutes"] == 480

    summary_response = http_client.get(
        "/api/v1/sleep-segments/summary",
        params={"start_date": "2026-08-18", "end_date": "2026-08-18"},
    )
    assert summary_response.status_code == 200
    summaries = summary_response.json()["items"]
    assert len(summaries) == 1
    assert summaries[0]["total_minutes"] == 480

    update_response = http_client.patch(
        f"/api/v1/sleep-segments/{segment_id}",
        json={"end_at": "2026-08-19T07:00:00"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["duration_minutes"] == 510

    invalid_response = http_client.post(
        "/api/v1/sleep-segments/",
        json={
            "start_at": "2026-08-18T22:30:00",
            "end_at": "2026-08-18T21:30:00",
        },
    )
    assert invalid_response.status_code == 400

    delete_response = http_client.delete(f"/api/v1/sleep-segments/{segment_id}")
    assert delete_response.status_code == 204
    assert http_client.get(f"/api/v1/sleep-segments/{segment_id}").status_code == 404
