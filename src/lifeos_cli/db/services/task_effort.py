"""Task effort aggregation helpers."""

from __future__ import annotations

from collections import deque
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.services.hierarchy import order_hierarchy
from lifeos_cli.db.services.write_locks import lock_planning_writes


async def expected_task_efforts(session: AsyncSession) -> dict[UUID, tuple[int, int]]:
    """Calculate active effort from sources, independent of persisted aggregates."""
    table = Task.__table__
    rows = [
        dict(row)
        for row in (
            await session.execute(select(table).where(table.c.deleted_at.is_(None)))
        ).mappings()
    ]
    ids = {row["id"] for row in rows}
    for row in rows:
        if row["parent_task_id"] not in ids:
            row["parent_task_id"] = None
    ordered = order_hierarchy(rows, parent_field="parent_task_id", table_name="tasks")
    direct = dict.fromkeys(ids, 0)
    logs = (await session.scalars(select(Timelog).execution_options(populate_existing=True))).all()
    for log in logs:
        if log.task_id in direct:
            direct[log.task_id] += _timelog_minutes(log)
    totals = dict(direct)
    for row in reversed(ordered):
        if row["parent_task_id"] is not None:
            totals[row["parent_task_id"]] += totals[row["id"]]
    return {task_id: (direct[task_id], totals[task_id]) for task_id in ids}


async def rebuild_task_efforts(session: AsyncSession) -> int:
    """Repair active task aggregates without changing manual vision experience."""
    from sqlalchemy import update

    await lock_planning_writes(session)
    await session.flush()
    expected = await expected_task_efforts(session)
    repaired = 0
    for task_id, (direct, total) in expected.items():
        result = await session.execute(
            update(Task)
            .where(
                Task.id == task_id,
                (Task.actual_effort_self != direct) | (Task.actual_effort_total != total),
            )
            .values(actual_effort_self=direct, actual_effort_total=total)
            .returning(Task.id)
        )
        repaired += len(result.all())
    return repaired


def _timelog_minutes(timelog: Timelog) -> int:
    """Return whole minutes for a finished timelog; zero if invalid."""
    delta = timelog.end_time - timelog.start_time
    if delta.total_seconds() <= 0:
        return 0
    return int(delta.total_seconds() // 60)


async def _load_active_task(session: AsyncSession, task_id: UUID) -> Task | None:
    stmt = (
        select(Task)
        .where(Task.id == task_id, Task.deleted_at.is_(None))
        .limit(1)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _load_children(session: AsyncSession, parent_id: UUID) -> list[Task]:
    stmt = (
        select(Task)
        .where(Task.parent_task_id == parent_id, Task.deleted_at.is_(None))
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(stmt)).scalars())


async def recompute_task_self_minutes(session: AsyncSession, task_id: UUID) -> int:
    """Recompute direct timelog minutes for one task."""
    await lock_planning_writes(session)
    await session.flush()
    task = await _load_active_task(session, task_id)
    if task is None:
        return 0

    stmt = (
        select(Timelog)
        .execution_options(populate_existing=True)
        .where(
            Timelog.task_id == task_id,
            Timelog.deleted_at.is_(None),
        )
    )
    timelogs = list((await session.execute(stmt)).scalars())
    total_minutes = sum(_timelog_minutes(timelog) for timelog in timelogs)
    task.actual_effort_self = total_minutes
    await session.flush()
    return total_minutes


async def recompute_totals_upwards(session: AsyncSession, start_task_id: UUID) -> None:
    """Recompute total effort for a task and its ancestor chain."""
    await lock_planning_writes(session)
    chain: list[Task] = []
    await session.flush()
    visited: set[UUID] = set()
    current = await _load_active_task(session, start_task_id)
    while current is not None:
        if current.id in visited:
            raise ValueError("Task hierarchy contains a circular parent reference.")
        visited.add(current.id)
        chain.append(current)
        if current.parent_task_id is None:
            break
        current = await _load_active_task(session, current.parent_task_id)

    for node in chain:
        await recompute_task_self_minutes(session, node.id)

    for node in chain:
        children = await _load_children(session, node.id)
        child_total = sum(child.actual_effort_total or 0 for child in children)
        node.actual_effort_total = (node.actual_effort_self or 0) + child_total
        await session.flush()


async def recompute_subtree_totals(session: AsyncSession, subtree_root_id: UUID) -> None:
    """Recompute effort totals for every task in a subtree."""
    await lock_planning_writes(session)
    await session.flush()
    root = await _load_active_task(session, subtree_root_id)
    if root is None:
        return

    queue: deque[Task] = deque([root])
    nodes: list[Task] = []
    visited: set[UUID] = set()
    while queue:
        node = queue.popleft()
        if node.id in visited:
            raise ValueError("Task hierarchy contains a circular parent reference.")
        visited.add(node.id)
        nodes.append(node)
        queue.extend(await _load_children(session, node.id))

    for node in nodes:
        await recompute_task_self_minutes(session, node.id)

    processed: set[UUID] = set()

    async def _compute(node: Task) -> int:
        if node.id in processed:
            return node.actual_effort_total or 0
        children = await _load_children(session, node.id)
        total_children = 0
        for child in children:
            total_children += await _compute(child)
        node.actual_effort_total = (node.actual_effort_self or 0) + total_children
        processed.add(node.id)
        return node.actual_effort_total

    await _compute(root)
    await session.flush()


async def recompute_task_effort_after_timelog_change(
    session: AsyncSession,
    *,
    old_task_id: UUID | None,
    new_task_id: UUID | None,
) -> None:
    """Recompute affected task effort after a timelog mutation."""
    task_ids = [task_id for task_id in (old_task_id, new_task_id) if task_id is not None]
    for task_id in dict.fromkeys(task_ids):
        await recompute_task_self_minutes(session, task_id)
        await recompute_totals_upwards(session, task_id)
