"""End-to-end HTTP integration tests for the local LifeOS Web API.

These tests exercise real HTTP round-trips through FastAPI's TestClient
against an isolated temporary SQLite database. They cover routing assembly,
query/body parsing, dependency injection, transactional sessions, status
codes, and representative error paths for a set of core routers.

They complement the payload/serialization tests in ``test_web_cli.py`` and
the OpenAPI contract tests in ``test_web_api_contracts.py``: this module
verifies what endpoints actually execute, not just their declared schemas.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from lifeos_cli import cli
from lifeos_cli.config import clear_config_cache
from lifeos_cli.db import session as db_session
from tests.config_support import write_test_config

pytest.importorskip("fastapi")


@pytest.fixture
def http_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide a TestClient backed by an isolated temporary SQLite database."""
    from fastapi.testclient import TestClient

    from lifeos_web.app import create_app

    database_path = tmp_path / "lifeos-http-test.db"
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


def test_health_endpoint_round_trip(http_client) -> None:
    response = http_client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["timestamp"]


def test_vision_task_create_list_detail_and_not_found(http_client) -> None:
    vision_response = http_client.post(
        "/api/v1/visions/",
        json={"name": "HTTP integration vision"},
    )
    assert vision_response.status_code == 200
    vision_id = vision_response.json()["id"]

    task_response = http_client.post(
        "/api/v1/tasks/",
        json={
            "vision_id": vision_id,
            "content": "Exercise HTTP task lifecycle",
        },
    )
    assert task_response.status_code == 200
    task = task_response.json()
    task_id = task["id"]
    assert task["content"] == "Exercise HTTP task lifecycle"

    list_response = http_client.get(
        "/api/v1/tasks/",
        params={"page": 1, "size": 10},
    )
    assert list_response.status_code == 200
    assert any(item["id"] == task_id for item in list_response.json()["items"])

    detail_response = http_client.get(f"/api/v1/tasks/{task_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == task_id

    missing_response = http_client.get(f"/api/v1/tasks/{uuid.uuid4()}")
    assert missing_response.status_code == 404


def test_note_create_list_and_delete(http_client) -> None:
    create_response = http_client.post(
        "/api/v1/notes/",
        json={"content": "HTTP integration note"},
    )
    assert create_response.status_code == 200
    note_id = create_response.json()["id"]

    list_response = http_client.get("/api/v1/notes/")
    assert list_response.status_code == 200
    assert any(item["id"] == note_id for item in list_response.json()["items"])

    delete_response = http_client.delete(f"/api/v1/notes/{note_id}")
    assert delete_response.status_code == 204


def test_validation_error_maps_to_422(http_client) -> None:
    response = http_client.post(
        "/api/v1/tasks/",
        json={"content": "missing vision_id"},
    )

    assert response.status_code == 422


def test_tag_business_error_maps_to_400(http_client) -> None:
    response = http_client.post(
        "/api/v1/tags/",
        json={"name": "invalid-entity", "entity_type": "not-a-real-entity"},
    )

    assert response.status_code == 400
    assert "not-a-real-entity" in response.json()["detail"]
