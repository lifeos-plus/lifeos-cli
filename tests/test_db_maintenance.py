from __future__ import annotations

import asyncio
import sqlite3
from contextlib import ExitStack, closing
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from sqlalchemy import JSON, CheckConstraint
from sqlalchemy.ext.asyncio import create_async_engine

from lifeos_cli.db import maintenance
from lifeos_cli.db.base import Base
from lifeos_cli.db.models.event import Event


def test_check_rebuilds_effort_without_overwriting_history_or_manual_experience(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from lifeos_cli.config import clear_config_cache
    from lifeos_cli.db.models import Task, Timelog, Vision
    from lifeos_cli.db.session import clear_session_cache, get_async_session_factory

    monkeypatch.setenv("LIFEOS_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'effort.db'}")
    monkeypatch.delenv("LIFEOS_DATABASE_SCHEMA", raising=False)
    clear_config_cache()
    clear_session_cache()
    maintenance.upgrade_database()

    async def scenario() -> None:
        factory = get_async_session_factory()
        async with factory() as session:
            vision = Vision(name="Manual", experience_points=777)
            session.add(vision)
            await session.flush()
            parent = Task(vision_id=vision.id, content="Parent", actual_effort_total=380)
            session.add(parent)
            await session.flush()
            child = Task(vision_id=vision.id, parent_task_id=parent.id, content="Child")
            archived = Task(vision_id=vision.id, parent_task_id=parent.id, content="History")
            archived.soft_delete()
            session.add_all([child, archived])
            await session.flush()
            start = datetime(2026, 9, 12, tzinfo=UTC)
            session.add(
                Timelog(
                    title="Source",
                    task_id=child.id,
                    start_time=start,
                    end_time=start + timedelta(minutes=265),
                )
            )
            await session.commit()
            parent_id, child_id, vision_id = parent.id, child.id, vision.id
        report = await maintenance.check_database(repair=True)
        assert not report.ok and len(report.derived_issues) == 2
        assert report.rebuilt_task_count == 0
        assert any("Manual experience" in item for item in report.data_warnings)
        report = await maintenance.check_database(rebuild_effort=True)
        assert report.ok and not report.derived_issues and report.rebuilt_task_count == 2
        async with factory() as session:
            assert (
                await session.scalar(select(Vision.experience_points).where(Vision.id == vision_id))
                == 777
            )
            for task_id in (parent_id, child_id):
                assert (
                    await session.scalar(select(Task.actual_effort_total).where(Task.id == task_id))
                    == 265
                )
        assert (await maintenance.check_database(rebuild_effort=True)).rebuilt_task_count == 0

    try:
        asyncio.run(scenario())
    finally:
        clear_session_cache()
        clear_config_cache()


def test_database_check_reports_hierarchy_errors_without_repairing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lifeos_cli.config import clear_config_cache
    from lifeos_cli.db.models import Task, Vision
    from lifeos_cli.db.session import clear_session_cache, get_async_session_factory

    monkeypatch.setenv("LIFEOS_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'check.db'}")
    monkeypatch.delenv("LIFEOS_DATABASE_SCHEMA", raising=False)
    clear_config_cache()
    clear_session_cache()
    maintenance.upgrade_database()

    async def scenario() -> None:
        async with get_async_session_factory()() as session:
            vision = Vision(name="Check")
            session.add(vision)
            await session.flush()
            task = Task(vision_id=vision.id, content="Corrupt")
            session.add(task)
            await session.flush()
            task.parent_task_id = task.id
            await session.commit()
        report = await maintenance.check_database(repair=True)
        assert not report.ok
        assert any("circular" in issue for issue in report.hierarchy_issues)
        assert report.repaired_count == 0

    try:
        asyncio.run(scenario())
    finally:
        clear_session_cache()
        clear_config_cache()


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


def test_sqlite_batch_migrations_preserve_referencing_rows(tmp_path: Path) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from lifeos_cli.db.models import Task, Vision
    from lifeos_cli.db.session import configure_async_engine

    database_path = tmp_path / "populated-migration.db"
    url = f"sqlite+aiosqlite:///{database_path}"

    async def seed() -> None:
        engine = configure_async_engine(create_async_engine(url))
        try:
            async with async_sessionmaker(engine)() as session:
                vision = Vision(name="Keep parent")
                session.add(vision)
                await session.flush()
                session.add(Task(vision_id=vision.id, content="Keep child"))
                await session.commit()
        finally:
            await engine.dispose()

    async def verify() -> None:
        engine = configure_async_engine(create_async_engine(url))
        try:
            async with async_sessionmaker(engine)() as session:
                assert (await session.scalars(select(Task.content))).all() == ["Keep child"]
                assert (await session.scalars(select(Vision.name))).all() == ["Keep parent"]
        finally:
            await engine.dispose()

    with ExitStack() as stack:
        config = maintenance.build_alembic_config(sqlalchemy_url=url, stack=stack)
        command.upgrade(config, "20260906_1200")
        asyncio.run(seed())
        for direction, revision in (
            (command.upgrade, "head"),
            (command.downgrade, "20260906_1200"),
            (command.upgrade, "head"),
        ):
            direction(config, revision)
            asyncio.run(verify())


def test_sqlite_failed_migration_rolls_back_schema_and_revision(tmp_path: Path) -> None:
    database_path = tmp_path / "invalid-foreign-key.db"
    url = f"sqlite+aiosqlite:///{database_path}"
    with ExitStack() as stack:
        config = maintenance.build_alembic_config(sqlalchemy_url=url, stack=stack)
        command.upgrade(config, "20260906_1200")
        with closing(sqlite3.connect(database_path)) as connection, connection:
            connection.execute(
                "INSERT INTO tasks (id, vision_id, content, created_at, updated_at, "
                "status, priority, display_order, actual_effort_self, actual_effort_total) "
                "VALUES ('11111111111111111111111111111111', '22222222222222222222222222222222', "
                "'Missing vision', '2026-09-08', '2026-09-08', 'todo', 0, 0, 0, 0)"
            )
            schema_before = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'"
            ).fetchone()
        with pytest.raises(RuntimeError, match="foreign-key violations"):
            command.upgrade(config, "head")
        with closing(sqlite3.connect(database_path)) as connection:
            assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
                "20260906_1200",
            )
            assert (
                connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'"
                ).fetchone()
                == schema_before
            )
            assert connection.execute("SELECT count(*) FROM tasks").fetchone() == (1,)


@pytest.mark.parametrize("initial_revision", ["20260906_1200", "20260907_1200"])
def test_planning_migration_rejects_preexisting_null_loophole(
    tmp_path: Path, initial_revision: str
) -> None:
    from datetime import date

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from lifeos_cli.db.models import Task, Vision
    from lifeos_cli.db.session import configure_async_engine

    path = tmp_path / "incomplete-planning.db"
    url = f"sqlite+aiosqlite:///{path}"

    async def seed() -> None:
        engine = configure_async_engine(create_async_engine(url))
        try:
            async with async_sessionmaker(engine)() as session:
                vision = Vision(name="Historical")
                session.add(vision)
                await session.flush()
                session.add(
                    Task(
                        vision_id=vision.id,
                        content="Incomplete",
                        planning_cycle_type="day",
                        planning_cycle_start_date=date(2026, 9, 9),
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    with ExitStack() as stack:
        config = maintenance.build_alembic_config(sqlalchemy_url=url, stack=stack)
        command.upgrade(config, initial_revision)
        asyncio.run(seed())
        with pytest.raises(RuntimeError, match="Repair the rows"):
            command.upgrade(config, "head")
        with closing(sqlite3.connect(path)) as connection:
            assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
                initial_revision,
            )
            assert connection.execute("SELECT count(*) FROM tasks").fetchone() == (1,)


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


def test_invariant_migration_normalizes_legacy_event_json_null(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy-event-json-null.db"
    sqlalchemy_url = f"sqlite+aiosqlite:///{database_path}"
    with ExitStack() as stack:
        config = maintenance.build_alembic_config(sqlalchemy_url=sqlalchemy_url, stack=stack)
        command.upgrade(config, "20260906_1200")
        with closing(sqlite3.connect(database_path)) as connection, connection:
            connection.execute(
                "INSERT INTO events "
                "(id, title, start_time, priority, status, is_all_day, event_type, "
                "recurrence_rule, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "11111111111111111111111111111111",
                    "legacy ordinary event",
                    "2026-09-07 09:00:00",
                    0,
                    "planned",
                    False,
                    "appointment",
                    "null",
                    "2026-09-07 00:00:00",
                    "2026-09-07 00:00:00",
                ),
            )

        command.upgrade(config, "head")

        with closing(sqlite3.connect(database_path)) as connection:
            recurrence_rule = connection.execute(
                "SELECT recurrence_rule FROM events WHERE title = ?",
                ("legacy ordinary event",),
            ).fetchone()
        assert recurrence_rule == (None,)


def test_optional_event_json_uses_sql_null_for_python_none() -> None:
    recurrence_rule_type = Event.__table__.c.recurrence_rule.type

    assert isinstance(recurrence_rule_type, JSON)
    assert recurrence_rule_type.none_as_null is True


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
