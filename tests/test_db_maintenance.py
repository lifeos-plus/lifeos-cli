from __future__ import annotations

import asyncio
import sqlite3
from contextlib import ExitStack, closing
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from sqlalchemy import CheckConstraint
from sqlalchemy.ext.asyncio import create_async_engine

from lifeos_cli.db import maintenance
from lifeos_cli.db.base import Base


def test_build_alembic_config_uses_packaged_migration_resources() -> None:
    with ExitStack() as stack:
        config = maintenance.build_alembic_config(
            sqlalchemy_url="postgresql+psycopg://localhost/lifeos_test",
            stack=stack,
        )
        script_location_text = config.get_main_option("script_location")

        assert script_location_text is not None
        script_location = Path(script_location_text)

        assert (
            config.get_main_option("sqlalchemy.url") == "postgresql+psycopg://localhost/lifeos_test"
        )
        assert script_location.name == "alembic"
        assert script_location.joinpath("env.py").is_file()
        assert script_location.joinpath("script.py.mako").is_file()
        assert script_location.joinpath(
            "versions",
            "20260410_1200_add_event_recurrence_support.py",
        ).is_file()
        assert script_location.joinpath(
            "versions",
            "20260411_1500_add_generic_associations.py",
        ).is_file()


def test_upgrade_database_uses_packaged_alembic_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_upgrade(config: object, revision: str) -> None:
        captured["config"] = config
        captured["revision"] = revision

    monkeypatch.setattr(
        maintenance,
        "get_database_settings",
        lambda: SimpleNamespace(
            require_database_url=lambda: "postgresql+psycopg://localhost/lifeos_test"
        ),
    )
    monkeypatch.setattr(maintenance, "ensure_database_driver_available", lambda database_url: None)
    monkeypatch.setattr(maintenance.command, "upgrade", fake_upgrade)

    maintenance.upgrade_database("head")

    config = captured["config"]
    assert captured["revision"] == "head"
    assert isinstance(config, maintenance.Config)
    assert config.get_main_option("sqlalchemy.url") == "postgresql+psycopg://localhost/lifeos_test"
    script_location_text = config.get_main_option("script_location")
    assert script_location_text is not None
    assert Path(script_location_text).joinpath("env.py").is_file()


def test_upgrade_database_supports_sqlite_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "missing-dir" / "lifeos.db"
    sqlalchemy_url = f"sqlite+aiosqlite:///{database_path}"
    monkeypatch.setattr(
        maintenance,
        "get_database_settings",
        lambda: SimpleNamespace(require_database_url=lambda: sqlalchemy_url),
    )
    maintenance.upgrade_database("head")

    with closing(sqlite3.connect(database_path)) as connection:
        table_names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

    assert "alembic_version" in table_names
    assert "notes" in table_names
    assert "events" in table_names
    assert "associations" in table_names


def test_full_sqlite_migration_chain_round_trips_without_metadata_drift(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration-round-trip.db"
    sqlalchemy_url = f"sqlite+aiosqlite:///{database_path}"
    with ExitStack() as stack:
        config = maintenance.build_alembic_config(sqlalchemy_url=sqlalchemy_url, stack=stack)
        command.upgrade(config, "head")
        command.check(config)
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.check(config)


def test_invariant_migration_rejects_existing_invalid_rows_with_actionable_error(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "invalid-existing-data.db"
    sqlalchemy_url = f"sqlite+aiosqlite:///{database_path}"
    with ExitStack() as stack:
        config = maintenance.build_alembic_config(sqlalchemy_url=sqlalchemy_url, stack=stack)
        command.upgrade(config, "20260906_1200")
        with closing(sqlite3.connect(database_path)) as connection, connection:
            connection.execute(
                "INSERT INTO habits "
                "(id, title, start_date, duration_days, cadence_frequency, "
                "target_per_cycle, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "11111111111111111111111111111111",
                    "invalid legacy habit",
                    "2026-09-07",
                    -1,
                    "daily",
                    1,
                    "active",
                    "2026-09-07 00:00:00",
                    "2026-09-07 00:00:00",
                ),
            )
        with pytest.raises(RuntimeError, match="Repair the rows and rerun"):
            command.upgrade(config, "head")


def test_new_check_constraints_use_canonical_naming_convention() -> None:
    expected = {
        "ck_events_recurrence_details_valid",
        "ck_event_occurrence_exceptions_action_valid",
        "ck_finance_snapshots_rate_snapshot_policy_valid",
        "ck_menstrual_days_flow_amount_valid",
        "ck_tag_associations_entity_type_valid",
        "ck_tags_entity_type_valid",
    }
    actual = {
        str(constraint.name)
        for table in Base.metadata.sorted_tables
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert expected <= actual


def test_database_check_reports_uninitialized_schema_without_running_domain_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> maintenance.DatabaseCheckReport:
        database_path = tmp_path / "uninitialized.db"
        sqlalchemy_url = f"sqlite+aiosqlite:///{database_path}"
        engine = create_async_engine(sqlalchemy_url)
        monkeypatch.setattr(
            maintenance,
            "get_database_settings",
            lambda: SimpleNamespace(
                database_schema=None,
                require_database_url=lambda: sqlalchemy_url,
            ),
        )
        monkeypatch.setattr(maintenance, "get_async_engine", lambda: engine)
        monkeypatch.setattr(
            maintenance,
            "get_async_session_factory",
            lambda: pytest.fail("domain audit must be skipped until the schema is current"),
        )
        try:
            return await maintenance.check_database()
        finally:
            await engine.dispose()

    report = asyncio.run(scenario())

    assert report.current_revision is None
    assert report.current_revision != report.head_revision
    assert report.association_issues == ()
    assert not report.ok
