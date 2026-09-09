from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lifeos_cli.cli_support.resources.data.handlers import _import_rows
from lifeos_cli.db import session as db_session
from lifeos_cli.db.base import Base
from lifeos_cli.db.models import Area, Task, Vision
from lifeos_cli.db.models.finance import FinanceTreeNode
from lifeos_cli.db.services import data_ops, finance, task_effort
from lifeos_cli.db.services.hierarchy import HierarchyValidationError
from tests.support import sqlite_session_factory


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
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(FinanceTreeNode)
                        .where(FinanceTreeNode.parent_id == parent_id)
                    )
                    == 1
                )

    asyncio.run(run())
