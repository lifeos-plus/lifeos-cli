"""Shared hierarchy invariants for live data and portable snapshots."""

from __future__ import annotations

from collections import deque
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models import Task
from lifeos_cli.db.models.finance import FinanceTreeNode
from lifeos_cli.db.services.task_support import MAX_TASK_DEPTH


class HierarchyValidationError(ValueError):
    """Raised when persisted hierarchy semantics are inconsistent."""


def order_hierarchy(
    rows: list[dict[str, Any]], *, parent_field: str, table_name: str
) -> list[dict[str, Any]]:
    """Return parents before children, rejecting missing parents and cycles."""
    by_id = {row["id"]: row for row in rows}
    children: dict[Any, list[dict[str, Any]]] = {}
    roots: deque[dict[str, Any]] = deque()
    for row in rows:
        parent_id = row[parent_field]
        if parent_id is None:
            roots.append(row)
        elif parent_id not in by_id:
            raise HierarchyValidationError(f"{table_name} contains a missing parent.")
        else:
            children.setdefault(parent_id, []).append(row)
    ordered = []
    while roots:
        row = roots.popleft()
        ordered.append(row)
        roots.extend(children.get(row["id"], ()))
    if len(ordered) != len(rows):
        raise HierarchyValidationError(f"{table_name} contains a circular self-reference.")
    return ordered


def validate_task_hierarchy(rows: list[dict[str, Any]]) -> None:
    rows = order_hierarchy(rows, parent_field="parent_task_id", table_name="tasks")
    tasks_by_id = {row["id"]: row for row in rows}
    depth_by_id: dict[Any, int] = {}
    for row_number, row in enumerate(rows, start=1):
        parent_id = row["parent_task_id"]
        if parent_id is None:
            depth = 1
        else:
            parent = tasks_by_id[parent_id]
            if parent["vision_id"] != row["vision_id"]:
                raise HierarchyValidationError(
                    f"tasks row {row_number} has a parent from a different vision."
                )
            if row["deleted_at"] is None and parent["deleted_at"] is not None:
                raise HierarchyValidationError(
                    f"tasks row {row_number} has an active link to a deleted parent."
                )
            depth = depth_by_id[parent_id] + 1
        if depth > MAX_TASK_DEPTH:
            raise HierarchyValidationError(
                f"tasks row {row_number} exceeds the maximum hierarchy depth of {MAX_TASK_DEPTH}."
            )
        depth_by_id[row["id"]] = depth


def validate_finance_node_hierarchy(rows: list[dict[str, Any]]) -> None:
    rows = order_hierarchy(rows, parent_field="parent_id", table_name="finance_tree_nodes")
    nodes_by_id = {row["id"]: row for row in rows}
    active_child_counts: dict[Any, int] = {}
    for row in rows:
        if row["parent_id"] is not None and row["deleted_at"] is None:
            active_child_counts[row["parent_id"]] = active_child_counts.get(row["parent_id"], 0) + 1

    for row_number, row in enumerate(rows, start=1):
        parent_id = row["parent_id"]
        if parent_id is None:
            expected_depth = 0
            expected_path = str(row["id"])
        else:
            parent = nodes_by_id[parent_id]
            if parent["tree_id"] != row["tree_id"]:
                raise HierarchyValidationError(
                    f"finance_tree_nodes row {row_number} has a parent from a different tree."
                )
            if row["deleted_at"] is None and parent["deleted_at"] is not None:
                raise HierarchyValidationError(
                    f"finance_tree_nodes row {row_number} has an active link to a deleted parent."
                )
            expected_depth = parent["depth"] + 1
            expected_path = f"{parent['path']}/{row['id']}"
        if row["depth"] != expected_depth or row["path"] != expected_path:
            raise HierarchyValidationError(
                f"finance_tree_nodes row {row_number} has inconsistent path or depth."
            )
        if row["deleted_at"] is None and row["children_count"] != active_child_counts.get(
            row["id"], 0
        ):
            raise HierarchyValidationError(
                f"finance_tree_nodes row {row_number} has an inconsistent active child count."
            )


async def validate_persisted_hierarchies(
    session: AsyncSession,
    *,
    tasks: bool = True,
    finance: bool = True,
    rebuild_finance_counts: bool = False,
) -> None:
    """Validate the final database state, including rows absent from an import."""
    await session.flush()
    if tasks:
        rows = [dict(row) for row in (await session.execute(select(Task.__table__))).mappings()]
        validate_task_hierarchy(rows)
    if finance:
        table = FinanceTreeNode.__table__
        rows = [dict(row) for row in (await session.execute(select(table))).mappings()]
        if rebuild_finance_counts:
            counts: dict[Any, int] = {}
            for row in rows:
                if row["deleted_at"] is None and row["parent_id"] is not None:
                    counts[row["parent_id"]] = counts.get(row["parent_id"], 0) + 1
            for row in rows:
                if row["deleted_at"] is None:
                    row["children_count"] = counts.get(row["id"], 0)
                    await session.execute(
                        update(FinanceTreeNode)
                        .where(FinanceTreeNode.id == row["id"])
                        .values(children_count=row["children_count"])
                    )
        validate_finance_node_hierarchy(rows)
