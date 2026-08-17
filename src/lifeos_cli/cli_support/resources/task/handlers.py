"""CLI handlers for the task resource."""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_timestamp,
    print_batch_result,
    print_summary_rows,
)
from lifeos_cli.cli_support.time_args import parse_optional_date_value
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import tasks as task_services


def _parse_task_order(value: str) -> tuple[UUID, int]:
    task_id_value, separator, display_order_value = value.partition(":")
    if not separator:
        raise ValueError("Task order must use <task-id>:<display-order>")
    try:
        return UUID(task_id_value), int(display_order_value)
    except ValueError as exc:
        raise ValueError("Task order must use <task-id>:<display-order>") from exc


TASK_SUMMARY_COLUMNS = ("task_id", "status", "vision_id", "parent_task_id", "content")


def _format_task_summary(task: task_services.TaskView) -> str:
    status = "deleted" if task.deleted_at is not None else task.status
    return f"{task.id}\t{status}\t{task.vision_id}\t{task.parent_task_id or '-'}\t{task.content}"


def _format_task_detail(task: task_services.TaskView) -> str:
    person_names = ", ".join(person.name for person in task.person) if task.person else "-"
    return "\n".join(
        (
            f"id: {task.id}",
            f"vision_id: {task.vision_id}",
            f"parent_task_id: {task.parent_task_id or '-'}",
            f"content: {task.content}",
            f"description: {task.description or '-'}",
            f"status: {task.status}",
            f"priority: {task.priority}",
            f"display_order: {task.display_order}",
            f"estimated_effort: {task.estimated_effort or '-'}",
            f"planning_cycle_type: {task.planning_cycle_type or '-'}",
            f"planning_cycle_days: {task.planning_cycle_days or '-'}",
            f"planning_cycle_start_date: {task.planning_cycle_start_date or '-'}",
            f"person: {person_names}",
            f"actual_effort_self: {task.actual_effort_self}",
            f"actual_effort_total: {task.actual_effort_total}",
            f"created_at: {format_timestamp(task.created_at)}",
            f"updated_at: {format_timestamp(task.updated_at)}",
            f"deleted_at: {format_timestamp(task.deleted_at)}",
        )
    )


def _format_task_tree(node: task_services.TaskWithSubtasks) -> str:
    lines: list[str] = []

    def collect(current: task_services.TaskWithSubtasks) -> None:
        indent = "  " * current.depth
        lines.append(
            f"{indent}{current.id}\t{current.status}\t{current.completion_percentage:.2f}\t"
            f"{current.content}"
        )
        for subtask in current.subtasks:
            collect(subtask)

    collect(node)
    return "\n".join(lines)


def _format_task_hierarchy(hierarchy: task_services.TaskHierarchy) -> str:
    task_lines: list[str] = []
    for root_task in hierarchy.root_tasks:
        task_lines.extend(_format_task_tree(root_task).splitlines())
    return "\n".join(
        (
            f"vision_id: {hierarchy.vision_id}",
            "root_tasks:",
            *(task_lines or ["  -"]),
        )
    )


def _format_task_stats(stats: task_services.TaskStats) -> str:
    return "\n".join(
        (
            f"total_subtasks: {stats.total_subtasks}",
            f"completed_subtasks: {stats.completed_subtasks}",
            f"completion_percentage: {stats.completion_percentage:.2f}",
            f"total_estimated_effort: {stats.total_estimated_effort or '-'}",
            f"total_actual_effort: {stats.total_actual_effort or '-'}",
        )
    )


async def handle_task_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            task = await task_services.create_task(
                session,
                vision_id=args.vision_id,
                content=args.content,
                description=args.description,
                parent_task_id=args.parent_task_id,
                status=args.status,
                priority=args.priority,
                display_order=args.display_order,
                person_ids=args.person_ids,
                estimated_effort=args.estimated_effort,
                planning_cycle_type=args.planning_cycle_type,
                planning_cycle_days=args.planning_cycle_days,
                planning_cycle_start_date=parse_optional_date_value(args.planning_cycle_start_date),
            )
        except (
            task_services.VisionReferenceNotFoundError,
            task_services.ParentTaskReferenceNotFoundError,
            task_services.InvalidTaskDepthError,
            task_services.InvalidPlanningCycleError,
            ValueError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created task {task.id}")
    return 0


async def handle_task_list_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            tasks = await task_services.list_tasks(
                session,
                vision_id=args.vision_id,
                vision_in=args.vision_in,
                parent_task_id=args.parent_task_id,
                person_id=args.person_id,
                status=args.status,
                status_in=args.status_in,
                exclude_status=args.exclude_status,
                planning_cycle_type=args.planning_cycle_type,
                planning_cycle_start_date=parse_optional_date_value(args.planning_cycle_start_date),
                content=args.content,
                limit=args.limit,
                offset=args.offset,
            )
        except ValueError as exc:
            return cli_handler_utils.print_cli_error(exc)
    if args.json:
        print_json_items(tasks)
        return 0
    print_summary_rows(
        items=tasks,
        columns=TASK_SUMMARY_COLUMNS,
        row_formatter=_format_task_summary,
        empty_message="No tasks found.",
    )
    return 0


async def handle_task_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        task = await task_services.get_task(
            session,
            task_id=args.task_id,
        )
    if task is None:
        return cli_handler_utils.print_missing_record_error("Task", args.task_id)
    if args.json:
        print_json_payload(task)
        return 0
    print(_format_task_detail(task))
    return 0


async def handle_task_with_subtasks_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        task = await task_services.get_task_with_subtasks(
            session,
            task_id=args.task_id,
        )
    if task is None:
        return cli_handler_utils.print_missing_record_error("Task", args.task_id)
    print(_format_task_tree(task))
    return 0


async def handle_task_hierarchy_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            hierarchy = await task_services.get_vision_task_hierarchy(
                session,
                vision_id=args.vision_id,
            )
        except task_services.VisionReferenceNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(_format_task_hierarchy(hierarchy))
    return 0


async def handle_task_stats_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            stats = await task_services.get_task_stats(
                session,
                task_id=args.task_id,
            )
        except task_services.TaskNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(_format_task_stats(stats))
    return 0


async def handle_task_move_async(args: argparse.Namespace) -> int:
    if args.clear_parent and args.new_parent_task_id is not None:
        return cli_handler_utils.print_mutually_exclusive_options(
            "--new-parent-task-id", "--clear-parent"
        )
    if (
        not args.clear_parent
        and args.new_parent_task_id is None
        and args.new_vision_id is None
        and args.new_display_order is None
    ):
        print("Provide at least one target field to move the task.", file=sys.stderr)
        return 1
    async with db_session.session_scope() as session:
        try:
            if args.clear_parent or args.new_parent_task_id is not None:
                result = await task_services.move_task(
                    session,
                    task_id=args.task_id,
                    old_parent_task_id=args.old_parent_task_id,
                    new_parent_task_id=None if args.clear_parent else args.new_parent_task_id,
                    new_vision_id=args.new_vision_id,
                    new_display_order=args.new_display_order,
                )
            else:
                result = await task_services.move_task(
                    session,
                    task_id=args.task_id,
                    old_parent_task_id=args.old_parent_task_id,
                    new_vision_id=args.new_vision_id,
                    new_display_order=args.new_display_order,
                )
        except (
            task_services.TaskNotFoundError,
            task_services.VisionReferenceNotFoundError,
            task_services.ParentTaskReferenceNotFoundError,
            task_services.InvalidTaskDepthError,
            task_services.InvalidTaskOperationError,
            ValueError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Moved task {result.task.id}")
    if result.updated_descendants:
        print(f"Updated descendants: {len(result.updated_descendants)}")
    return 0


async def handle_task_reorder_async(args: argparse.Namespace) -> int:
    try:
        task_orders = [_parse_task_order(value) for value in args.order]
    except ValueError as exc:
        return cli_handler_utils.print_cli_error(exc)
    async with db_session.session_scope() as session:
        try:
            await task_services.reorder_tasks(
                session,
                task_orders=task_orders,
            )
        except task_services.TaskNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Reordered tasks: {len(task_orders)}")
    return 0


async def handle_task_update_async(args: argparse.Namespace) -> int:
    conflicting_flags = (
        (
            args.clear_description and args.description is not None,
            "--description",
            "--clear-description",
        ),
        (
            args.clear_parent and args.parent_task_id is not None,
            "--parent-task-id",
            "--clear-parent",
        ),
        (
            args.clear_estimated_effort and args.estimated_effort is not None,
            "--estimated-effort",
            "--clear-estimated-effort",
        ),
        (args.clear_person and args.person_ids is not None, "--person-id", "--clear-person"),
        (
            args.clear_planning_cycle
            and any(
                value is not None
                for value in (
                    args.planning_cycle_type,
                    args.planning_cycle_days,
                    args.planning_cycle_start_date,
                )
            ),
            "planning cycle fields",
            "--clear-planning-cycle",
        ),
    )
    conflict_error = cli_handler_utils.validate_mutually_exclusive_pairs(conflicting_flags)
    if conflict_error is not None:
        return conflict_error
    if args.apply_to_subtasks and args.status is None:
        return cli_handler_utils.print_cli_error(
            ValueError("--apply-to-subtasks requires --status")
        )
    async with db_session.session_scope() as session:
        try:
            task = await task_services.update_task(
                session,
                task_id=args.task_id,
                content=args.content,
                description=args.description,
                clear_description=args.clear_description,
                parent_task_id=args.parent_task_id,
                clear_parent=args.clear_parent,
                status=args.status,
                apply_to_subtasks=args.apply_to_subtasks,
                priority=args.priority,
                display_order=args.display_order,
                person_ids=args.person_ids,
                clear_person=args.clear_person,
                estimated_effort=args.estimated_effort,
                clear_estimated_effort=args.clear_estimated_effort,
                planning_cycle_type=args.planning_cycle_type,
                planning_cycle_days=args.planning_cycle_days,
                planning_cycle_start_date=parse_optional_date_value(args.planning_cycle_start_date),
                clear_planning_cycle=args.clear_planning_cycle,
            )
        except (
            task_services.TaskNotFoundError,
            task_services.ParentTaskReferenceNotFoundError,
            task_services.InvalidTaskDepthError,
            task_services.InvalidPlanningCycleError,
            ValueError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated task {task.id}")
    return 0


async def handle_task_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        if len(args.task_ids) > 1:
            result = await task_services.batch_delete_tasks(
                session,
                task_ids=args.task_ids,
            )
            return print_batch_result(
                success_label="Deleted tasks",
                success_count=result.deleted_count,
                failed_label="Failed task IDs",
                result=result,
            )
        try:
            await task_services.delete_task(session, task_id=args.task_ids[0])
        except task_services.TaskNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted task {args.task_ids[0]}")
    return 0
