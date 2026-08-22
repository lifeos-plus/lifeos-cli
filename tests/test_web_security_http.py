"""HTTP boundary tests for the local LifeOS Web API security hardening.

These tests cover the request-level security middleware: Host and Origin
boundaries, request body size limits, bulk payload caps, rate limiting, and
Swagger documentation exposure. They reuse an isolated temporary SQLite
database so API routes can be exercised end to end.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lifeos_cli import cli
from lifeos_cli.config import clear_config_cache
from lifeos_cli.db import session as db_session
from tests.config_support import write_test_config

TEST_HOSTS = ["testserver", "127.0.0.1", "localhost", "::1"]


@pytest.fixture
def prepared_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide an isolated SQLite database with a permissive default rate limit."""
    from fastapi.testclient import TestClient

    from lifeos_web.app import create_app

    database_path = tmp_path / "lifeos-security-test.db"
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

    def make_client(
        *,
        base_url: str = "http://testserver",
        allowed_hosts: list[str] | None = None,
        docs_enabled: bool = False,
    ) -> TestClient:
        app = create_app(
            docs_enabled=docs_enabled,
            allowed_hosts=allowed_hosts,
        )
        return TestClient(app, base_url=base_url)

    yield make_client

    clear_config_cache()
    db_session.clear_session_cache()


def test_swagger_docs_disabled_by_default(prepared_env) -> None:
    client = prepared_env(allowed_hosts=TEST_HOSTS)

    assert client.get("/api/v1/docs").status_code == 404
    assert client.get("/api/v1/openapi.json").status_code == 404


def test_swagger_docs_enabled_explicitly(prepared_env) -> None:
    client = prepared_env(docs_enabled=True, allowed_hosts=TEST_HOSTS)

    assert client.get("/api/v1/docs").status_code == 200
    assert client.get("/api/v1/openapi.json").status_code == 200


def test_rejects_non_loopback_host_by_default(prepared_env) -> None:
    client = prepared_env(allowed_hosts=["127.0.0.1"])

    assert client.get("/healthy").status_code == 400


def test_allows_loopback_host(prepared_env) -> None:
    client = prepared_env(base_url="http://127.0.0.1")

    assert client.get("/healthy").status_code == 200


def test_allows_environment_configured_extra_host(
    prepared_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIFEOS_WEB_ALLOWED_HOSTS", "lifeos.lan")
    client = prepared_env(base_url="http://lifeos.lan")

    assert client.get("/healthy").status_code == 200


def test_rejects_disallowed_origin(prepared_env) -> None:
    client = prepared_env(allowed_hosts=TEST_HOSTS)

    response = client.get("/healthy", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403


def test_allows_same_origin_and_allowlisted_origin(prepared_env) -> None:
    same_origin = prepared_env(base_url="http://127.0.0.1")
    assert (
        same_origin.get(
            "/healthy",
            headers={"Origin": "http://127.0.0.1"},
        ).status_code
        == 200
    )

    dev_origin = prepared_env(base_url="http://127.0.0.1")
    assert (
        dev_origin.get(
            "/healthy",
            headers={"Origin": "http://localhost:5173"},
        ).status_code
        == 200
    )


def test_rejects_request_body_over_configured_limit(
    prepared_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIFEOS_WEB_MAX_BODY_BYTES", "100")
    client = prepared_env(allowed_hosts=TEST_HOSTS)

    response = client.post(
        "/api/v1/visions/",
        json={"name": "x" * 500},
    )
    assert response.status_code == 413


def test_rejects_bulk_create_payload_over_item_cap(prepared_env) -> None:
    client = prepared_env(allowed_hosts=TEST_HOSTS)
    oversized = {"items": [{"title": f"template-{index}"} for index in range(101)]}

    response = client.post("/api/v1/timelogs/templates/bulk", json=oversized)
    assert response.status_code == 422

    accepted = client.post("/api/v1/timelogs/templates/bulk", json={"items": [{"title": "ok"}]})
    assert accepted.status_code == 201


def test_rate_limit_applies_to_api_but_not_health(
    prepared_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIFEOS_WEB_RATE_LIMIT_PER_MINUTE", "3")
    client = prepared_env(allowed_hosts=TEST_HOSTS)

    for _ in range(4):
        assert client.get("/healthy").status_code == 200

    assert client.get("/api/v1/visions/").status_code == 200
    assert client.get("/api/v1/visions/").status_code == 200
    assert client.get("/api/v1/visions/").status_code == 200
    assert client.get("/api/v1/visions/").status_code == 429
