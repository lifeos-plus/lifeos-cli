"""CLI handlers for the planning resource."""

from __future__ import annotations

import argparse
from datetime import timedelta

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.config import ConfigurationError
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import planning_views

PLANNING_VIEW_COLUMNS = (
    "status",
    "vision_id",
    "content",
    "planning_cycle_window",
    "estimated_effort",
)


def _format_cycle_window(node: planning_views.PlanningTaskNode) -> str:
    start = node.planning_cycle_start_date
    days = node.planning_cycle_days
    if start is None or days is None:
        return "-"
    return f"{start}..{start + timedelta(days=days - 1)}"


def _format_tree_rows(node: planning_views.PlanningTaskNode) -> list[str]:
    indent = "  " * node.depth
    content_prefix = "(context) " if node.is_context else ""
    rows = [
        f"{indent}{node.status}\t{node.vision_id}\t{content_prefix}{node.content}\t"
        f"{_format_cycle_window(node)}\t{node.estimated_effort or '-'}"
    ]
    for child in node.children:
        rows.extend(_format_tree_rows(child))
    return rows


def _format_planning_view(view: planning_views.PlanningView) -> str:
    lines = [
        f"planning_view: {view.cycle_type}",
        f"period_start: {view.period_start}",
        f"period_end: {view.period_end}",
        f"total_tasks: {view.total_tasks}",
    ]
    if not view.roots:
        lines.append("No planning tasks found.")
        return "\n".join(lines)
    lines.append("\t".join(PLANNING_VIEW_COLUMNS))
    for root in view.roots:
        lines.extend(_format_tree_rows(root))
    return "\n".join(lines)


async def handle_planning_show_async(args: argparse.Namespace) -> int:
    if args.at is not None and args.start is not None:
        return cli_handler_utils.print_mutually_exclusive_options("--at", "--start")
    if args.depth is not None and args.depth < 0:
        return cli_handler_utils.print_cli_error(
            ValueError("--depth must be a non-negative integer.")
        )
    async with db_session.session_scope() as session:
        try:
            view = await planning_views.get_planning_view(
                session,
                cycle_type=args.cycle_type,
                at_date=args.at,
                start_date=args.start,
                vision_in=args.vision,
                status_in=args.status,
                max_depth=args.depth,
                limit=args.limit,
                offset=args.offset,
            )
        except (ConfigurationError, ValueError) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(_format_planning_view(view))
    return 0
