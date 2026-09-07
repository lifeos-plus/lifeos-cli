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

import sqlite3
import uuid
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

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
    monkeypatch.setenv("LIFEOS_WEB_RATE_LIMIT_PER_MINUTE", "100000")

    assert cli.main(["db", "upgrade"]) == 0

    app = create_app(
        allowed_hosts=["testserver", "127.0.0.1", "localhost", "::1"],
    )
    with TestClient(app) as client:
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


def test_task_list_supports_id_in_batch_filter(http_client) -> None:
    vision_response = http_client.post(
        "/api/v1/visions/",
        json={"name": "Batch filter vision"},
    )
    vision_id = vision_response.json()["id"]

    created_ids = []
    for content in ("Batch task one", "Batch task two"):
        task_response = http_client.post(
            "/api/v1/tasks/",
            json={"vision_id": vision_id, "content": content},
        )
        assert task_response.status_code == 200
        created_ids.append(task_response.json()["id"])

    batch_response = http_client.get(
        "/api/v1/tasks/",
        params={"id_in": ",".join(created_ids), "fields": "full"},
    )
    assert batch_response.status_code == 200
    payload = batch_response.json()
    assert {item["id"] for item in payload["items"]} == set(created_ids)
    assert payload["meta"]["id_in"] == ",".join(created_ids)
    assert payload["pagination"]["total"] == len(created_ids)


def test_task_list_id_in_composes_with_planning_filters(http_client) -> None:
    vision_response = http_client.post(
        "/api/v1/visions/",
        json={"name": "Planning batch vision"},
    )
    vision_id = vision_response.json()["id"]
    planned_response = http_client.post(
        "/api/v1/tasks/",
        json={
            "vision_id": vision_id,
            "content": "Planned batch task",
            "planning_cycle_type": "year",
            "planning_cycle_days": 366,
            "planning_cycle_start_date": "2026-07-26",
        },
    )
    assert planned_response.status_code == 200, planned_response.text
    planned_id = planned_response.json()["id"]
    unplanned_id = http_client.post(
        "/api/v1/tasks/",
        json={"vision_id": vision_id, "content": "Unplanned batch task"},
    ).json()["id"]

    response = http_client.get(
        "/api/v1/tasks/",
        params={
            "id_in": f"{planned_id},{unplanned_id}",
            "planning_cycle_type": "year",
            "planning_cycle_start_date": "2026-07-26",
        },
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [planned_id]


def test_task_list_id_in_rejects_malformed_and_oversized_input(http_client) -> None:
    malformed = http_client.get(
        "/api/v1/tasks/",
        params={"id_in": "not-a-uuid"},
    )
    assert malformed.status_code == 400

    oversized_ids = ",".join(str(uuid.uuid4()) for _ in range(101))
    oversized = http_client.get(
        "/api/v1/tasks/",
        params={"id_in": oversized_ids},
    )
    assert oversized.status_code == 400
    assert "at most 100" in oversized.json()["detail"]


def test_task_list_id_in_returns_empty_for_unknown_ids(http_client) -> None:
    response = http_client.get(
        "/api/v1/tasks/",
        params={"id_in": str(uuid.uuid4())},
    )
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["pagination"]["total"] == 0


def test_task_list_id_in_with_vision_id_returns_matching_subtasks(http_client) -> None:
    vision_id = http_client.post(
        "/api/v1/visions/",
        json={"name": "ID-in vision filter vision"},
    ).json()["id"]
    root_id = http_client.post(
        "/api/v1/tasks/",
        json={"vision_id": vision_id, "content": "Root task"},
    ).json()["id"]
    child_id = http_client.post(
        "/api/v1/tasks/",
        json={
            "vision_id": vision_id,
            "parent_task_id": root_id,
            "content": "Child task",
        },
    ).json()["id"]

    response = http_client.get(
        "/api/v1/tasks/",
        params={"id_in": child_id, "vision_id": vision_id},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [child_id]


def test_task_list_id_in_returns_all_matches_regardless_of_page_size(http_client) -> None:
    vision_id = http_client.post(
        "/api/v1/visions/",
        json={"name": "ID-in page size vision"},
    ).json()["id"]
    created_ids = [
        http_client.post(
            "/api/v1/tasks/",
            json={"vision_id": vision_id, "content": f"Bulk task {index}"},
        ).json()["id"]
        for index in range(3)
    ]

    response = http_client.get(
        "/api/v1/tasks/",
        params={"id_in": ",".join(created_ids), "size": 1},
    )

    assert response.status_code == 200
    assert {item["id"] for item in response.json()["items"]} == set(created_ids)


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


def test_habit_area_association_round_trip(http_client) -> None:
    area_response = http_client.post(
        "/api/v1/areas/",
        json={"name": "HTTP habit area"},
    )
    assert area_response.status_code == 200
    area_id = area_response.json()["id"]

    create_response = http_client.post(
        "/api/v1/habits/",
        json={
            "title": "Area-linked habit",
            "start_date": "2026-08-01",
            "duration_days": 30,
            "cadence_frequency": "daily",
            "target_per_cycle": 1,
            "area_id": area_id,
        },
    )
    assert create_response.status_code == 200
    habit = create_response.json()
    assert habit["area_id"] == area_id

    overview_response = http_client.get("/api/v1/habits/overviews")
    assert overview_response.status_code == 200
    overview_habit = next(
        item["habit"]
        for item in overview_response.json()["items"]
        if item["habit"]["id"] == habit["id"]
    )
    assert overview_habit["area_id"] == area_id

    filtered_response = http_client.get(
        "/api/v1/habits/",
        params={"area_id": area_id},
    )
    assert filtered_response.status_code == 200
    filtered = filtered_response.json()
    assert {item["id"] for item in filtered["items"]} == {habit["id"]}
    assert filtered["meta"]["area_id"] == area_id

    clear_response = http_client.patch(
        f"/api/v1/habits/{habit['id']}",
        json={"area_id": None},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["area_id"] is None


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


def test_finance_tree_copy_round_trip(http_client) -> None:
    create_response = http_client.post(
        "/api/v1/finance/trees",
        json={"name": "HTTP finance tree", "primary_currency": "USD"},
    )
    assert create_response.status_code == 200
    tree_id = create_response.json()["id"]

    node_response = http_client.post(
        f"/api/v1/finance/trees/{tree_id}/nodes",
        json={"name": "Cash"},
    )
    assert node_response.status_code == 200

    copy_response = http_client.post(
        f"/api/v1/finance/trees/{tree_id}/copy",
        json={},
    )
    assert copy_response.status_code == 200
    copy = copy_response.json()
    assert copy["id"] != tree_id
    assert copy["name"] == "HTTP finance tree Copy"
    assert copy["is_default"] is False
    assert [node["name"] for node in copy["nodes"]] == ["Cash"]

    missing_response = http_client.post(
        "/api/v1/finance/trees/ffffffff-ffff-ffff-ffff-ffffffffffff/copy",
        json={},
    )
    assert missing_response.status_code == 404


def test_area_order_round_trip(http_client) -> None:
    created_ids = [
        http_client.post(
            "/api/v1/areas/",
            json={"name": f"HTTP order area {index}"},
        ).json()["id"]
        for index in range(3)
    ]

    reordered = list(reversed(created_ids))
    response = http_client.put("/api/v1/areas/order", json=reordered)
    assert response.status_code == 204
    assert http_client.get("/api/v1/areas/order").json() == reordered


def test_area_order_unknown_id_returns_404(http_client) -> None:
    response = http_client.put(
        "/api/v1/areas/order",
        json=[str(uuid.uuid4())],
    )

    assert response.status_code == 404


def test_area_order_database_locked_retries_then_503(
    http_client,
    monkeypatch,
) -> None:
    from lifeos_web import routers

    area_id = http_client.post(
        "/api/v1/areas/",
        json={"name": "Locked retry area"},
    ).json()["id"]
    monkeypatch.setattr(
        routers.areas,
        "ORDER_WRITE_RETRY_BACKOFF_SECONDS",
        (0.0, 0.0, 0.0),
    )
    attempts = {"count": 0}

    async def flaky_reorder(session, *, order):
        attempts["count"] += 1
        raise OperationalError(
            "UPDATE areas SET display_order=?",
            {},
            Exception("(sqlite3.OperationalError) database is locked"),
        )

    monkeypatch.setattr(
        routers.areas.area_services,
        "reorder_areas",
        flaky_reorder,
    )

    response = http_client.put("/api/v1/areas/order", json=[area_id])

    assert response.status_code == 503
    assert response.headers.get("retry-after") == "1"
    assert attempts["count"] == len(routers.areas.ORDER_WRITE_RETRY_BACKOFF_SECONDS) + 1


def test_area_order_non_lock_operational_error_is_not_mapped_to_503(
    http_client,
    monkeypatch,
) -> None:
    from lifeos_web import routers

    area_id = http_client.post(
        "/api/v1/areas/",
        json={"name": "Broken database area"},
    ).json()["id"]

    async def broken_reorder(session, *, order):
        raise OperationalError(
            "UPDATE areas SET display_order=?",
            {},
            Exception("disk I/O error"),
        )

    monkeypatch.setattr(
        routers.areas.area_services,
        "reorder_areas",
        broken_reorder,
    )

    with pytest.raises(OperationalError, match="disk I/O error"):
        http_client.put("/api/v1/areas/order", json=[area_id])


@pytest.mark.parametrize("sqlstate", ["40001", "40P01", "55P03"])
def test_area_order_postgres_lock_sqlstates_are_retryable(sqlstate: str) -> None:
    from lifeos_web import routers

    class PostgreSQLLockError(Exception):
        def __init__(self, code: str) -> None:
            super().__init__("PostgreSQL operation failed")
            self.sqlstate = code

    original = PostgreSQLLockError(sqlstate)
    error = OperationalError("UPDATE areas", {}, original)

    assert routers.areas._is_lock_contention_error(error)


def test_area_order_recovers_after_transient_lock(
    http_client,
    monkeypatch,
) -> None:
    from lifeos_web import routers

    area_id = http_client.post(
        "/api/v1/areas/",
        json={"name": "Recovered area"},
    ).json()["id"]
    monkeypatch.setattr(
        routers.areas,
        "ORDER_WRITE_RETRY_BACKOFF_SECONDS",
        (0.0,),
    )
    original_reorder = routers.areas.area_services.reorder_areas
    attempts = {"count": 0}

    async def flaky_once(session, *, order):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OperationalError(
                "UPDATE areas SET display_order=?",
                {},
                Exception("(sqlite3.OperationalError) database is locked"),
            )
        await original_reorder(session, order=order)

    monkeypatch.setattr(
        routers.areas.area_services,
        "reorder_areas",
        flaky_once,
    )

    response = http_client.put("/api/v1/areas/order", json=[area_id])

    assert response.status_code == 204
    assert attempts["count"] == 2
    assert http_client.get("/api/v1/areas/order").json() == [area_id]


def test_area_order_database_locked_by_raw_connection_returns_503(
    http_client,
    monkeypatch,
) -> None:
    from lifeos_web import routers

    first_id = http_client.post(
        "/api/v1/areas/",
        json={"name": "Raw locked area A"},
    ).json()["id"]
    second_id = http_client.post(
        "/api/v1/areas/",
        json={"name": "Raw locked area B"},
    ).json()["id"]
    monkeypatch.setattr(routers.areas, "ORDER_WRITE_RETRY_BACKOFF_SECONDS", ())

    database_url = str(db_session.get_async_engine().url)
    database_path = database_url.removeprefix("sqlite+aiosqlite:///")
    lock_holder = sqlite3.connect(database_path, timeout=0.1)
    lock_holder.execute("PRAGMA busy_timeout=0")
    try:
        lock_holder.execute("BEGIN IMMEDIATE")
        lock_holder.execute(
            "UPDATE areas SET display_order=display_order WHERE id=?",
            (first_id,),
        )
        response = http_client.put(
            "/api/v1/areas/order",
            json=[second_id, first_id],
        )

        assert response.status_code == 503
        assert response.headers.get("retry-after") == "1"
    finally:
        lock_holder.rollback()
        lock_holder.close()
