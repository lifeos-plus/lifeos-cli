from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from lifeos_cli.config import clear_config_cache
from lifeos_cli.db.models import Area, DailyTimelogStatsGroupByArea, Task, Vision
from lifeos_cli.db.models.finance import FinanceTreeNode
from lifeos_cli.db.services import finance, timelogs
from lifeos_cli.db.services.timelog_support import TimelogCreateInput
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
            assert stale_parent is not None
        async with factory() as session:
            stored_parent = await session.get(FinanceTreeNode, parent_id)
            assert stored_parent is not None and stored_parent.children_count == 2

    try:
        asyncio.run(scenario())
    finally:
        clear_session_cache()
        clear_config_cache()
