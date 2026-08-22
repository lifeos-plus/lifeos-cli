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
    response = http_client.get("/healthy")

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


def test_timelog_create_list_detail_and_not_found(http_client) -> None:
    create_response = http_client.post(
        "/api/v1/timelogs/",
        json={
            "title": "HTTP integration timelog",
            "start_time": "2026-08-14T01:20:00.000Z",
            "end_time": "2026-08-14T01:30:00.000Z",
            "tracking_method": "manual",
            "area_id": None,
            "person_ids": None,
        },
    )
    assert create_response.status_code == 200
    timelog_id = create_response.json()["id"]

    list_response = http_client.get(
        "/api/v1/timelogs/",
        params={
            "window_start": "2026-08-13T16:00:00.000Z",
            "window_end": "2026-08-14T15:59:59.999Z",
            "page": 1,
            "size": 500,
        },
    )
    assert list_response.status_code == 200
    assert any(item["id"] == timelog_id for item in list_response.json()["items"])

    detail_response = http_client.get(f"/api/v1/timelogs/{timelog_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == timelog_id

    missing_response = http_client.get(f"/api/v1/timelogs/{uuid.uuid4()}")
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


def test_tag_create_list_detail_update_and_delete(http_client) -> None:
    create_response = http_client.post(
        "/api/v1/tags/",
        json={
            "name": "HTTP integration tag",
            "entity_type": "note",
            "category": "topic",
            "description": "Created over HTTP",
        },
    )
    assert create_response.status_code == 200
    tag = create_response.json()
    tag_id = tag["id"]
    assert tag["name"] == "http integration tag"
    assert tag["category"] == "topic"
    assert "person" not in tag

    list_response = http_client.get(
        "/api/v1/tags/",
        params={"page": 1, "size": 100},
    )
    assert list_response.status_code == 200
    assert any(item["id"] == tag_id for item in list_response.json()["items"])

    detail_response = http_client.get(f"/api/v1/tags/{tag_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == tag_id
    assert "person" not in detail_response.json()

    update_response = http_client.patch(
        f"/api/v1/tags/{tag_id}",
        json={"color": "#123456"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["color"] == "#123456"

    second_response = http_client.post(
        "/api/v1/tags/",
        json={"name": "HTTP batch tag", "entity_type": "note"},
    )
    assert second_response.status_code == 200
    second_tag_id = second_response.json()["id"]

    batch_response = http_client.patch(
        "/api/v1/tags/batch-update",
        json={"ids": [tag_id, second_tag_id], "category": "work"},
    )
    assert batch_response.status_code == 200
    assert batch_response.json()["updated_count"] == 2
    assert all("person" not in item for item in batch_response.json()["updated_tags"])
    assert {item["category"] for item in batch_response.json()["updated_tags"]} == {"work"}

    missing_response = http_client.get(f"/api/v1/tags/{uuid.uuid4()}")
    assert missing_response.status_code == 404

    delete_response = http_client.delete(f"/api/v1/tags/{tag_id}")
    assert delete_response.status_code == 204


def test_habit_action_list_and_update(http_client) -> None:
    habit_response = http_client.post(
        "/api/v1/habits/",
        json={
            "title": "HTTP integration habit",
            "start_date": "2026-08-01",
            "duration_days": 30,
            "cadence_frequency": "daily",
            "target_per_cycle": 1,
        },
    )
    assert habit_response.status_code == 200
    habit_id = habit_response.json()["id"]

    actions_response = http_client.get(
        f"/api/v1/habits/{habit_id}/actions",
        params={"start_date": "2026-08-10", "end_date": "2026-08-12"},
    )
    assert actions_response.status_code == 200
    actions = actions_response.json()["items"]
    assert actions
    action = actions[0]
    assert set(action) == {"id", "habit_id", "action_date", "status", "notes", "linked_notes_count"}
    assert action["habit_id"] == habit_id

    update_response = http_client.patch(
        f"/api/v1/habits/{habit_id}/actions/{action['id']}",
        json={"status": "done"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "done"
    assert set(update_response.json()) == {
        "id",
        "habit_id",
        "action_date",
        "status",
        "notes",
        "linked_notes_count",
    }


def test_task_status_cascade_applies_done_to_open_subtasks(http_client) -> None:
    vision_response = http_client.post(
        "/api/v1/visions/",
        json={"name": "Cascade vision"},
    )
    assert vision_response.status_code == 200
    vision_id = vision_response.json()["id"]

    parent_response = http_client.post(
        "/api/v1/tasks/",
        json={"vision_id": vision_id, "content": "Cascade parent"},
    )
    assert parent_response.status_code == 200
    parent_id = parent_response.json()["id"]

    child_response = http_client.post(
        "/api/v1/tasks/",
        json={
            "vision_id": vision_id,
            "content": "Cascade child",
            "parent_task_id": parent_id,
        },
    )
    assert child_response.status_code == 200
    child_id = child_response.json()["id"]

    blocked_response = http_client.patch(
        f"/api/v1/tasks/{parent_id}/status",
        json={"status": "done"},
    )
    assert blocked_response.status_code == 400
    assert "cannot be completed" in blocked_response.json()["detail"]

    cascaded_response = http_client.patch(
        f"/api/v1/tasks/{parent_id}/status",
        json={"status": "done", "apply_to_subtasks": True},
    )
    assert cascaded_response.status_code == 200
    assert cascaded_response.json()["status"] == "done"

    child_detail_response = http_client.get(f"/api/v1/tasks/{child_id}")
    assert child_detail_response.status_code == 200
    assert child_detail_response.json()["status"] == "done"
