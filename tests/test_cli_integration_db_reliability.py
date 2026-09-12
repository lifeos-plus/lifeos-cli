from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from lifeos_cli.config import clear_config_cache
from lifeos_cli.db.models import Area, DailyTimelogStatsGroupByArea, Task, Timelog, Vision
from lifeos_cli.db.models.finance import FinanceTreeNode
from lifeos_cli.db.services import finance, task_mutations, timelogs
from lifeos_cli.db.services.derived_audit import audit_derived_data
from lifeos_cli.db.services.hierarchy import validate_persisted_hierarchies
from lifeos_cli.db.services.task_effort import rebuild_task_efforts
from lifeos_cli.db.services.timelog_support import TimelogCreateInput, TimelogUpdateInput
from lifeos_cli.db.session import clear_session_cache, get_async_session_factory
from tests.cli_integration_support import INTEGRATION_PYTESTMARK, IntegrationContext, init_context

pytestmark = INTEGRATION_PYTESTMARK


def test_postgres_concurrent_planning_and_finance_writes(
    integration_context: IntegrationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_context(integration_context)
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(integration_context.config_path))
    clear_config_cache()
    clear_session_cache()

    async def scenario() -> None:
        factory = get_async_session_factory()
        async with factory() as session:
            area, vision = Area(name="Concurrent"), Vision(name="Concurrent")
            session.add_all([area, vision])
            await session.flush()
            task = Task(vision_id=vision.id, content="Concurrent")
            session.add(task)
            tree = await finance.create_finance_tree(
                session, name="Concurrent", primary_currency="USD"
            )
            parent = await finance.create_finance_node(session, tree_id=tree.id, name="Parent")
            await session.commit()
            task_id, area_id, tree_id, parent_id = task.id, area.id, tree.id, parent.id
            with pytest.raises(IntegrityError, match="planning_cycle_days_required"):
                async with session.begin_nested():
                    session.add(
                        Task(
                            vision_id=vision.id,
                            content="Incomplete",
                            planning_cycle_type="day",
                            planning_cycle_start_date=datetime(2026, 9, 9).date(),
                        )
                    )
                    await session.flush()

        start = datetime(2026, 9, 8, 12, tzinfo=UTC)

        async def add_timelog(session, hour):
            await timelogs.create_timelog(
                session,
                payload=TimelogCreateInput(
                    title=f"Work {hour}",
                    start_time=start + timedelta(hours=hour),
                    end_time=start + timedelta(hours=hour + 1),
                    task_id=task_id,
                    area_id=area_id,
                ),
            )

        async with factory() as first, factory() as second:
            await add_timelog(first, 0)
            pending = asyncio.create_task(add_timelog(second, 1))
            try:
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(pending), timeout=0.2)
                await first.commit()
                await asyncio.wait_for(pending, timeout=10)
                await second.commit()
            finally:
                if not pending.done():
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)

        async with factory() as session:
            stored_task = await session.get(Task, task_id)
            assert stored_task is not None and stored_task.actual_effort_total == 120
            assert (
                await session.scalar(select(func.sum(DailyTimelogStatsGroupByArea.minutes))) == 120
            )

        async with factory() as first, factory() as second:
            cached_timelog = await second.scalar(select(Timelog).order_by(Timelog.start_time))
            assert cached_timelog is not None
            await timelogs.update_timelog(
                first,
                timelog_id=cached_timelog.id,
                changes=TimelogUpdateInput(end_time=start + timedelta(minutes=90)),
            )
            await first.commit()
            await add_timelog(second, 2)
            await second.commit()
            assert cached_timelog.end_time == start + timedelta(minutes=90)
        async with factory() as session:
            fresh_task = await session.get(Task, task_id)
            assert fresh_task is not None and fresh_task.actual_effort_total == 210
            assert (
                await session.scalar(select(func.sum(DailyTimelogStatsGroupByArea.minutes))) == 210
            )

        async with factory() as first, factory() as second:
            # Keep a stale parent in the second identity map before the first write.
            stale_parent = await second.get(FinanceTreeNode, parent_id)
            await finance.create_finance_node(
                first, tree_id=tree_id, parent_id=parent_id, name="First"
            )
            await first.commit()
            await finance.create_finance_node(
                second, tree_id=tree_id, parent_id=parent_id, name="Second"
            )
            await second.commit()
            assert stale_parent is not None and stale_parent.children_count == 2
        async with factory() as session:
            stored_parent = await session.get(FinanceTreeNode, parent_id)
            assert stored_parent is not None and stored_parent.children_count == 2

        async with factory() as first, factory() as second:
            await second.get(FinanceTreeNode, parent_id)
            await finance.delete_finance_node(first, node_id=parent_id)
            pending = asyncio.create_task(
                finance.create_finance_node(
                    second, tree_id=tree_id, parent_id=parent_id, name="Too late"
                )
            )
            try:
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(pending), timeout=0.2)
                await first.commit()
                with pytest.raises(finance.FinanceTreeNodeNotFoundError):
                    await asyncio.wait_for(pending, timeout=10)
                await second.rollback()
            finally:
                if not pending.done():
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)

        async with factory() as session:
            root = await session.get(Task, task_id)
            assert root is not None
            archived = await task_mutations.create_task(
                session, vision_id=root.vision_id, content="History", parent_task_id=task_id
            )
            await task_mutations.delete_task(session, task_id=archived.id)
            target = Vision(name="Moved")
            session.add(target)
            await session.flush()
            result = await task_mutations.move_task(
                session, task_id=task_id, new_vision_id=target.id
            )
            assert result.updated_descendants == ()
            stored = (
                (
                    await session.execute(
                        select(Task.__table__).where(Task.__table__.c.id == archived.id)
                    )
                )
                .mappings()
                .one()
            )
            assert stored["vision_id"] == target.id
            assert stored["deleted_at"] is not None
            await validate_persisted_hierarchies(session, finance=False)
            root.actual_effort_total = 999
            await session.flush()
            issues, _ = await audit_derived_data(session)
            assert len(issues) == 1
            assert await rebuild_task_efforts(session) == 1
            issues, _ = await audit_derived_data(session)
            assert not issues
            await session.commit()

    try:
        asyncio.run(scenario())
    finally:
        clear_session_cache()
        clear_config_cache()
