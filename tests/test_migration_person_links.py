"""SQLite roundtrip test for the person-links-to-associations migration."""

from __future__ import annotations

import sqlite3
from contextlib import ExitStack
from pathlib import Path
from uuid import UUID

from alembic import command

from lifeos_cli.db import maintenance

_PERSON_ID = "11111111-1111-1111-1111-111111111111"
_TASK_ID = "22222222-2222-2222-2222-222222222222"
_NOTE_ID = "33333333-3333-3333-3333-333333333333"
_PREVIOUS_REVISION = "20260704_1500"
_MIGRATION_REVISION = "20260812_1200"
_TIMESTAMP = "2026-08-12 00:00:00+00:00"


def _table_names(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {row[0] for row in rows}


def _association_rows(
    database_path: Path,
) -> list[tuple[str, UUID, str, UUID, str]]:
    with sqlite3.connect(database_path) as connection:
        return [
            (source_model, UUID(source_id), target_model, UUID(target_id), link_type)
            for source_model, source_id, target_model, target_id, link_type in connection.execute(
                "SELECT source_model, source_id, target_model, target_id, link_type "
                "FROM associations ORDER BY source_model"
            ).fetchall()
        ]


def _person_association_rows(
    database_path: Path,
) -> list[tuple[str, UUID, UUID]]:
    with sqlite3.connect(database_path) as connection:
        return [
            (entity_type, UUID(entity_id), UUID(person_id))
            for entity_type, entity_id, person_id in connection.execute(
                "SELECT entity_type, entity_id, person_id FROM person_associations"
            ).fetchall()
        ]


def test_person_links_migration_roundtrip(tmp_path: Path) -> None:
    database_path = tmp_path / "migrate.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"

    with ExitStack() as stack:
        alembic_config = maintenance.build_alembic_config(
            sqlalchemy_url=database_url,
            stack=stack,
        )
        command.upgrade(alembic_config, _PREVIOUS_REVISION)

        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "INSERT INTO people (id, name, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (_PERSON_ID.replace("-", ""), "Alice", _TIMESTAMP, _TIMESTAMP),
            )
            connection.execute(
                "INSERT INTO person_associations (entity_type, entity_id, person_id) "
                "VALUES ('task', ?, ?)",
                (_TASK_ID, _PERSON_ID),
            )
            connection.execute(
                "INSERT INTO associations "
                "(id, source_model, source_id, target_model, target_id, link_type, "
                "created_at, updated_at) "
                "VALUES (?, 'note', ?, 'person', ?, 'is_about', ?, ?)",
                (
                    "44444444-4444-4444-4444-444444444444",
                    _NOTE_ID,
                    _PERSON_ID,
                    _TIMESTAMP,
                    _TIMESTAMP,
                ),
            )

        command.upgrade(alembic_config, _MIGRATION_REVISION)

        assert "person_associations" not in _table_names(database_path)
        association_rows = _association_rows(database_path)
        assert (
            "note",
            UUID(_NOTE_ID),
            "person",
            UUID(_PERSON_ID),
            "is_about",
        ) in association_rows
        assert (
            "task",
            UUID(_TASK_ID),
            "person",
            UUID(_PERSON_ID),
            "is_about",
        ) in association_rows

        command.downgrade(alembic_config, _PREVIOUS_REVISION)

        assert "person_associations" in _table_names(database_path)
        assert _person_association_rows(database_path) == [
            ("task", UUID(_TASK_ID), UUID(_PERSON_ID))
        ]
        association_rows = _association_rows(database_path)
        assert (
            "task",
            UUID(_TASK_ID),
            "person",
            UUID(_PERSON_ID),
            "is_about",
        ) not in association_rows
        assert (
            "note",
            UUID(_NOTE_ID),
            "person",
            UUID(_PERSON_ID),
            "is_about",
        ) in association_rows
