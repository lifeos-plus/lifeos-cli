from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lifeos_cli.cli_support.resources.data.handlers import _import_rows
from lifeos_cli.db import session as db_session
from lifeos_cli.db.base import Base
from lifeos_cli.db.models import Area, DailyTimelogStatsGroupByArea, Event, Task, Timelog, Vision
from lifeos_cli.db.models.finance import FinanceTreeNode
from lifeos_cli.db.models.sleep_segment import SleepSegment
from lifeos_cli.db.services import data_ops, finance, task_effort, timelog_stats
from lifeos_cli.db.services.hierarchy import HierarchyValidationError
from tests.support import sqlite_session_factory


def test_soft_deleted_owners_are_warned_without_cascading_or_hiding_id_access() -> None:
    from lifeos_cli.db.models.event_occurrence_exception import EventOccurrenceException
    from lifeos_cli.db.services import task_mutations, task_queries, visions
    from lifeos_cli.db.services.derived_audit import audit_soft_deleted_references

    async def run() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                old, target = Vision(name="Deleted owner"), Vision(name="Recovery")
                session.add_all([old, target])
                await session.flush()
                hidden = await task_mutations.create_task(
                    session, vision_id=old.id, content="Hidden"
                )
                deleted = await task_mutations.create_task(
                    session, vision_id=old.id, content="Deleted"
                )
                await task_mutations.delete_task(session, task_id=deleted.id)
                start = datetime(2026, 9, 12, tzinfo=UTC)
                event = Event(title="Preserved", task_id=deleted.id, start_time=start)
                master = Event(title="Master", start_time=start)
                master.soft_delete()
                session.add_all([event, master])
                await session.flush()
                exception = EventOccurrenceException(
                    master_event_id=master.id, instance_start=start
                )
                session.add(exception)
                await visions.delete_vision(session, vision_id=old.id)
                await session.flush()
                warnings = await audit_soft_deleted_references(session)
                assert len(warnings) == 3
                assert await task_queries.list_tasks(session) == []
                assert await task_queries.get_task(session, task_id=hidden.id) is not None
                await task_mutations.move_task(session, task_id=hidden.id, new_vision_id=target.id)
                assert len(await task_queries.list_tasks(session)) == 1
                assert event.deleted_at is None and exception.deleted_at is None

    asyncio.run(run())


def test_move_task_preserves_soft_deleted_hierarchy_and_bundle(tmp_path: Path) -> None:
    from lifeos_cli.db.services import task_mutations, task_support
    from lifeos_cli.db.services.hierarchy import validate_persisted_hierarchies

    async def run() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                old, new = Vision(name="Old"), Vision(name="New")
                session.add_all([old, new])
                await session.flush()
                root = await task_mutations.create_task(session, vision_id=old.id, content="Root")
                active = await task_mutations.create_task(
                    session, vision_id=old.id, content="Active", parent_task_id=root.id
                )
                archived = await task_mutations.create_task(
                    session, vision_id=old.id, content="Archived", parent_task_id=root.id
                )
                grandchild = await task_mutations.create_task(
                    session, vision_id=old.id, content="History", parent_task_id=archived.id
                )
                await task_mutations.delete_task(session, task_id=archived.id)
                await session.commit()
                historical = {
                    row["id"]: (row["parent_task_id"], row["deleted_at"])
                    for row in (await session.execute(select(Task.__table__))).mappings()
                }
                for target in (new.id, old.id, new.id):
                    result = await task_mutations.move_task(
                        session, task_id=root.id, new_vision_id=target
                    )
                    assert {task.id for task in result.updated_descendants} == {active.id}
                    await validate_persisted_hierarchies(session, finance=False)
                    rows = (await session.execute(select(Task.__table__))).mappings().all()
                    assert {row["vision_id"] for row in rows} == {target}
                    assert {
                        row["id"]: (row["parent_task_id"], row["deleted_at"]) for row in rows
                    } == historical
                    assert {
                        task.id
                        for task in await task_support.load_task_subtree(
                            session, root_task_id=root.id
                        )
                    } == {root.id, active.id}
                    await session.commit()
                assert historical[grandchild.id][1] is not None
            path = tmp_path / "moved.zip"
            async with factory() as session:
                await data_ops.export_bundle(session, output_path=path)
            bundle = data_ops.read_bundle(path)
            async with sqlite_session_factory() as restored_factory:
                async with restored_factory() as session:
                    await data_ops.import_bundle(session, bundle=bundle)
                    await validate_persisted_hierarchies(session, finance=False)
                    rows = (await session.execute(select(Task.__table__))).mappings().all()
                    assert len(rows) == 4
                    assert {row["vision_id"] for row in rows} == {new.id}
                    assert {
                        row["id"]: (row["parent_task_id"], row["deleted_at"]) for row in rows
                    } == historical

    asyncio.run(run())


@pytest.mark.parametrize("resource", ["task", "event"])
def test_database_rejects_null_required_planning_fields(resource: str) -> None:
    async def run() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                vision = Vision(name="Required fields")
                session.add(vision)
                await session.flush()
                record: Task | Event
                if resource == "task":
                    record = Task(
                        vision_id=vision.id,
                        content="Incomplete",
                        planning_cycle_type="day",
                        planning_cycle_start_date=date(2026, 9, 9),
                    )
                else:
                    record = Event(
                        title="Incomplete",
                        start_time=datetime(2026, 9, 9, tzinfo=UTC),
                        recurrence_frequency="daily",
                    )
                with pytest.raises(IntegrityError, match="required"):
                    async with session.begin_nested():
                        session.add(record)
                        await session.flush()

    asyncio.run(run())


def test_partial_import_validates_the_complete_persisted_row(monkeypatch) -> None:
    async def run() -> None:
        async with sqlite_session_factory() as factory:
            monkeypatch.setattr(db_session, "get_async_session_factory", lambda: factory)
            async with factory() as session:
                start = datetime(2026, 9, 8, tzinfo=UTC)
                segment = SleepSegment(
                    start_at=start,
                    end_at=start + timedelta(hours=8),
                    sleep_date=start.date(),
                    duration_minutes=480,
                )
                session.add(segment)
                await session.commit()
                segment_id = segment.id
            report = await _import_rows(
                resource="sleep",
                rows=[{"id": str(segment_id), "duration_minutes": 5}],
                dry_run=False,
                continue_on_error=False,
            )
            assert report.failed_count == 1
            async with factory() as session:
                stored = await session.get(SleepSegment, segment_id)
                assert stored is not None and stored.duration_minutes == 480

    asyncio.run(run())


def test_post_import_rebuild_synchronizes_vision_experience() -> None:
    async def run() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                vision = Vision(name="Experience", experience_rate_per_hour=60)
                session.add(vision)
                await session.flush()
                task = Task(vision_id=vision.id, content="Work")
                session.add(task)
                await session.flush()
                start = datetime(2026, 9, 8, tzinfo=UTC)
                session.add(
                    Timelog(
                        title="Imported",
                        task_id=task.id,
                        start_time=start,
                        end_time=start + timedelta(hours=2),
                    )
                )
                await session.flush()
                await data_ops.run_post_import_hooks(
                    session, resources={"timelog"}, vision_ids=(vision.id,)
                )
                await session.refresh(vision)
                assert vision.experience_points == 120
                assert vision.stage == 1

    asyncio.run(run())


@pytest.mark.parametrize("legacy_bundle", [False, True])
def test_resource_import_only_synchronizes_affected_visions(monkeypatch, legacy_bundle) -> None:
    async def run() -> None:
        async with sqlite_session_factory() as factory:
            monkeypatch.setattr(db_session, "get_async_session_factory", lambda: factory)
            async with factory() as session:
                affected = Vision(name="Affected", experience_rate_per_hour=60)
                manual = Vision(name="Unrelated", experience_points=777)
                session.add_all([affected, manual])
                await session.flush()
                task = Task(vision_id=affected.id, content="Imported work")
                session.add(task)
                await session.commit()
                affected_id, manual_id, task_id = affected.id, manual.id, task.id
            rows = [
                {
                    "id": str(uuid4()),
                    "title": "Import",
                    "task_id": str(task_id),
                    "start_time": "2026-09-09T10:00:00Z",
                    "end_time": "2026-09-09T12:00:00Z",
                }
            ]
            result: data_ops.BundleImportReport | data_ops.DataImportReport
            if legacy_bundle:
                async with factory() as session:
                    result = await data_ops.import_bundle(
                        session,
                        bundle=data_ops.BundlePayload(
                            manifest={"schema_version": data_ops.LEGACY_BUNDLE_SCHEMA_VERSION},
                            resources={"timelog": rows},
                        ),
                    )
                    await session.commit()
            else:
                result = await _import_rows(
                    resource="timelog", rows=rows, dry_run=False, continue_on_error=False
                )
            assert result.failed_count == 0
            async with factory() as session:
                assert (
                    await session.scalar(
                        select(Vision.experience_points).where(Vision.id == affected_id)
                    )
                    == 120
                )
                assert (
                    await session.scalar(
                        select(Vision.experience_points).where(Vision.id == manual_id)
                    )
                    == 777
                )

    asyncio.run(run())


def test_full_stats_rebuild_removes_rows_without_remaining_timelogs() -> None:
    async def run() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                area = Area(name="Obsolete stats")
                session.add(area)
                await session.flush()
                session.add(
                    DailyTimelogStatsGroupByArea(
                        area_id=area.id,
                        stat_date=date(2026, 1, 1),
                        timezone="UTC",
                        minutes=60,
                        timelog_count=1,
                    )
                )
                await session.flush()
                assert (
                    await timelog_stats.rebuild_timelog_stats_groupby_area(
                        session, rebuild_all=True
                    )
                    == ()
                )
                assert (
                    await session.scalar(
                        select(func.count()).select_from(DailyTimelogStatsGroupByArea)
                    )
                    == 0
                )

    asyncio.run(run())


@pytest.mark.parametrize(
    "resource,payload",
    [
        ("person", {"nicknames": [float("inf")]}),
        ("area", {"display_order": 2**40}),
        ("body-measurement", {"weight_kg": "70.001"}),
    ],
)
def test_resource_import_uses_portable_snapshot_value_validation(resource, payload) -> None:
    with pytest.raises(data_ops.DataOperationError):
        data_ops.prepare_snapshot_row(resource, 1, {"id": str(uuid4()), **payload})


@pytest.mark.parametrize("dry_run", [True, False])
def test_sqlite_resource_import_rolls_back_released_savepoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dry_run: bool
) -> None:
    async def run() -> None:
        engine = db_session.configure_async_engine(
            create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rollback.db'}")
        )
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)
            monkeypatch.setattr(db_session, "get_async_session_factory", lambda: factory)
            rows = [{"id": str(uuid4()), "name": "must roll back"}]
            if not dry_run:
                rows.append({"id": str(uuid4()), "unknown": "invalid"})
            report = await _import_rows(
                resource="area", rows=rows, dry_run=dry_run, continue_on_error=False
            )
            assert report.created_count == 1
            assert report.failed_count == (0 if dry_run else 1)
            async with factory() as session:
                assert (await session.scalars(select(Area))).all() == []
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_sqlite_export_session_keeps_snapshot_across_reads(tmp_path: Path) -> None:
    async def run() -> None:
        engine = db_session.configure_async_engine(
            create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'snapshot.db'}")
        )
        try:
            async with engine.begin() as connection:
                await connection.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY)"))
                await connection.execute(text("INSERT INTO sample VALUES (1)"))
            async with async_sessionmaker(engine)() as session:
                await data_ops._start_bundle_export_snapshot(session)
                assert await session.scalar(text("SELECT count(*) FROM sample")) == 1
                async with engine.begin() as writer:
                    await writer.execute(text("INSERT INTO sample VALUES (2)"))
                assert await session.scalar(text("SELECT count(*) FROM sample")) == 1
            async with engine.connect() as connection:
                assert await connection.scalar(text("SELECT count(*) FROM sample")) == 2
        finally:
            await engine.dispose()

    asyncio.run(run())


@pytest.mark.parametrize("invalid_parent", ["self", "descendant", "other_vision", "deleted"])
def test_resource_import_validates_resulting_task_hierarchy(invalid_parent: str) -> None:
    async def run() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                vision = Vision(name="First")
                other = Vision(name="Second")
                session.add_all([vision, other])
                await session.flush()
                parent = Task(vision_id=vision.id, content="Parent")
                other_parent = Task(vision_id=other.id, content="Other")
                deleted = Task(vision_id=vision.id, content="Deleted")
                deleted.soft_delete()
                session.add_all([parent, other_parent, deleted])
                await session.flush()
                child = Task(vision_id=vision.id, parent_task_id=parent.id, content="Child")
                session.add(child)
                await session.commit()
                parent_id = parent.id
                target_id = {
                    "self": parent_id,
                    "descendant": child.id,
                    "other_vision": other_parent.id,
                    "deleted": deleted.id,
                }[invalid_parent]
                with pytest.raises(HierarchyValidationError):
                    async with session.begin_nested():
                        await data_ops.import_resource_snapshot(
                            session,
                            resource="task",
                            rows=[{"id": str(parent_id), "parent_task_id": str(target_id)}],
                        )
                await session.commit()
            async with factory() as session:
                restored = await session.get(Task, parent_id)
                assert restored is not None and restored.parent_task_id is None

    asyncio.run(run())


def test_effort_rebuild_rejects_existing_cycle_without_hanging() -> None:
    async def run() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                vision = Vision(name="Cycle")
                session.add(vision)
                await session.flush()
                task = Task(vision_id=vision.id, content="Invalid")
                session.add(task)
                await session.flush()
                task.parent_task_id = task.id
                await session.flush()
                for rebuild in (
                    task_effort.recompute_totals_upwards,
                    task_effort.recompute_subtree_totals,
                ):
                    with pytest.raises(ValueError, match="circular"):
                        await asyncio.wait_for(rebuild(session, task.id), timeout=2)

    asyncio.run(run())


def test_bundle_merge_rebuilds_finance_counts_from_final_state(tmp_path: Path) -> None:
    async def run() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                session.add(Vision(name="Manual snapshot experience", experience_points=777))
                tree = await finance.create_finance_tree(
                    session, name="Review", primary_currency="USD"
                )
                parent = await finance.create_finance_node(session, tree_id=tree.id, name="Parent")
                await session.commit()
                tree_id, parent_id = tree.id, parent.id
            path = tmp_path / "backup.zip"
            async with factory() as session:
                await data_ops.export_bundle(session, output_path=path)
            bundle = data_ops.read_bundle(path)
            async with factory() as session:
                await finance.create_finance_node(
                    session, tree_id=tree_id, parent_id=parent_id, name="Child"
                )
                await session.commit()
            async with factory() as session:
                await data_ops.import_bundle(session, bundle=bundle)
                await session.commit()
            async with factory() as session:
                stored_parent = await session.get(FinanceTreeNode, parent_id)
                assert stored_parent is not None and stored_parent.children_count == 1
                assert await session.scalar(select(Vision.experience_points)) == 777
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(FinanceTreeNode)
                        .where(FinanceTreeNode.parent_id == parent_id)
                    )
                    == 1
                )

    asyncio.run(run())
