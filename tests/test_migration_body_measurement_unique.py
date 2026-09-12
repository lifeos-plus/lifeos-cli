"""SQLite coverage for the active body-measurement uniqueness migration."""

from __future__ import annotations

import sqlite3
from contextlib import ExitStack, closing
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command

from lifeos_cli.db import maintenance

_PREVIOUS_REVISION = "20260819_1200"
_MIGRATION_REVISION = "20260827_1200"
_MEASURED_AT = "2026-08-19 08:00:00+00:00"
_CREATED_AT = "2026-08-19 08:05:00+00:00"


def _insert_measurement(
    connection: sqlite3.Connection,
    *,
    row_id: str,
    measured_at: str = _MEASURED_AT,
    updated_at: str,
    deleted_at: str | None = None,
) -> None:
    connection.execute(
        "INSERT INTO body_measurements "
        "(id, measured_at, weight_kg, created_at, updated_at, deleted_at) "
        "VALUES (?, ?, 63.5, ?, ?, ?)",
        (row_id.replace("-", ""), measured_at, _CREATED_AT, updated_at, deleted_at),
    )


def test_body_measurement_unique_migration_deduplicates_active_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "body-measurement-migrate.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    older_id = "11111111-1111-1111-1111-111111111111"
    newest_id = "22222222-2222-2222-2222-222222222222"
    distinct_id = "33333333-3333-3333-3333-333333333333"
    deleted_id = "44444444-4444-4444-4444-444444444444"

    with ExitStack() as stack:
        alembic_config = maintenance.build_alembic_config(
            sqlalchemy_url=database_url,
            stack=stack,
        )
        command.upgrade(alembic_config, _PREVIOUS_REVISION)

        with closing(sqlite3.connect(database_path)) as connection, connection:
            _insert_measurement(
                connection,
                row_id=older_id,
                updated_at="2026-08-19 08:10:00+00:00",
            )
            _insert_measurement(
                connection,
                row_id=newest_id,
                updated_at="2026-08-19 08:20:00+00:00",
            )
            _insert_measurement(
                connection,
                row_id=distinct_id,
                measured_at="2026-08-20 08:00:00+00:00",
                updated_at="2026-08-20 08:10:00+00:00",
            )
            _insert_measurement(
                connection,
                row_id=deleted_id,
                updated_at="2026-08-19 08:30:00+00:00",
                deleted_at="2026-08-19 08:31:00+00:00",
            )

        command.upgrade(alembic_config, _MIGRATION_REVISION)

        with closing(sqlite3.connect(database_path)) as connection, connection:
            rows = connection.execute(
                "SELECT id, deleted_at FROM body_measurements ORDER BY id"
            ).fetchall()
            deleted_at_by_id = {UUID(row_id): deleted_at for row_id, deleted_at in rows}
            assert deleted_at_by_id[UUID(older_id)] == "2026-08-19 08:10:00+00:00"
            assert deleted_at_by_id[UUID(newest_id)] is None
            assert deleted_at_by_id[UUID(distinct_id)] is None
            assert deleted_at_by_id[UUID(deleted_id)] == "2026-08-19 08:31:00+00:00"

            index_sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'index' "
                "AND name = 'uq_body_measurements_measured_at_active'"
            ).fetchone()
            assert index_sql is not None
            assert "UNIQUE INDEX" in index_sql[0]
            assert "WHERE deleted_at IS NULL" in index_sql[0]

            with pytest.raises(sqlite3.IntegrityError):
                _insert_measurement(
                    connection,
                    row_id="55555555-5555-5555-5555-555555555555",
                    updated_at="2026-08-19 08:40:00+00:00",
                )

        command.downgrade(alembic_config, _PREVIOUS_REVISION)

        with closing(sqlite3.connect(database_path)) as connection, connection:
            assert (
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'index' "
                    "AND name = 'uq_body_measurements_measured_at_active'"
                ).fetchone()
                is None
            )
            _insert_measurement(
                connection,
                row_id="66666666-6666-6666-6666-666666666666",
                updated_at="2026-08-19 08:50:00+00:00",
            )
