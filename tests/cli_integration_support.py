from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.engine import make_url

psycopg: Any
sql: Any
try:
    psycopg = import_module("psycopg")
    sql = import_module("psycopg.sql")
except ImportError:  # pragma: no cover - exercised only without postgres extra
    psycopg = None
    sql = None

REPO_ROOT = Path(__file__).resolve().parents[1]
_ID_PATTERN = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
_TEST_DATABASE_MARKER = "test"


def normalize_integration_database_url(database_url: str) -> str:
    """Normalize one integration database URL so it clearly targets a test database."""
    parsed = make_url(database_url.strip())
    if parsed.drivername != "postgresql+psycopg":
        raise RuntimeError(
            "LIFEOS_TEST_DATABASE_URL must use the `postgresql+psycopg://` SQLAlchemy driver"
        )
    database_name = parsed.database
    if database_name is None or not database_name.strip():
        raise RuntimeError("LIFEOS_TEST_DATABASE_URL must include a PostgreSQL database name")
    if _TEST_DATABASE_MARKER not in database_name.casefold():
        database_name = f"{database_name}_test"
    return parsed.set(database=database_name).render_as_string(hide_password=False)


_RAW_INTEGRATION_DATABASE_URL = os.environ.get("LIFEOS_TEST_DATABASE_URL")
INTEGRATION_DATABASE_URL = (
    normalize_integration_database_url(_RAW_INTEGRATION_DATABASE_URL)
    if _RAW_INTEGRATION_DATABASE_URL is not None
    else None
)

INTEGRATION_PYTESTMARK = [
    pytest.mark.integration,
    pytest.mark.skipif(
        INTEGRATION_DATABASE_URL is None or psycopg is None or sql is None,
        reason=(
            "install the postgres extra and provide LIFEOS_TEST_DATABASE_URL "
            "to run real CLI integration tests"
        ),
    ),
]

_DEFAULT_INIT_PREFERENCES: tuple[str, ...] = (
    "--timezone",
    "America/Toronto",
    "--language",
    "en",
    "--day-starts-at",
    "00:00",
    "--week-starts-on",
    "monday",
    "--vision-experience-rate-per-hour",
    "60",
)


@dataclass(frozen=True)
class IntegrationContext:
    database_url: str
    schema: str
    config_path: Path
    env: dict[str, str]


def run_lifeos(
    context: IntegrationContext,
    *args: str,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "lifeos", *args],
        cwd=REPO_ROOT,
        env=context.env,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def run_alembic(
    context: IntegrationContext,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    """Run Alembic against the isolated integration schema."""
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=REPO_ROOT,
        env=context.env,
        text=True,
        capture_output=True,
        check=False,
    )


def assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr


def assert_missing(result: subprocess.CompletedProcess[str], record_label: str) -> None:
    assert result.returncode == 1
    assert record_label in result.stderr


def extract_created_id(output: str) -> str:
    match = _ID_PATTERN.search(output)
    if match is None:
        raise AssertionError(f"could not find identifier in output: {output!r}")
    return match.group(1)


def _drop_schema(database_url: str, schema_name: str) -> None:
    if psycopg is None or sql is None:
        raise RuntimeError("psycopg is required for PostgreSQL integration test cleanup")
    parsed = make_url(database_url)
    with psycopg.connect(
        dbname=parsed.database,
        user=parsed.username,
        password=parsed.password,
        host=parsed.host,
        port=parsed.port,
        autocommit=True,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_name))
            )


def _merge_default_init_preferences(extra_args: tuple[str, ...]) -> tuple[str, ...]:
    """Append stable init preference defaults unless the caller overrides them."""
    merged_args = list(extra_args)
    for option_name, option_value in zip(
        _DEFAULT_INIT_PREFERENCES[::2],
        _DEFAULT_INIT_PREFERENCES[1::2],
        strict=True,
    ):
        if option_name not in merged_args:
            merged_args.extend((option_name, option_value))
    return tuple(merged_args)


def init_context(context: IntegrationContext, *extra_args: str) -> None:
    init_args = _merge_default_init_preferences(extra_args)
    init_result = run_lifeos(
        context,
        "init",
        "--non-interactive",
        "--database-url",
        context.database_url,
        "--schema",
        context.schema,
        *init_args,
    )
    assert_ok(init_result)
    assert "Database connection succeeded." in init_result.stdout
    assert "Database migrations are up to date." in init_result.stdout
