"""CLI handlers for the vision resource."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_summary_header,
    format_timestamp,
    print_batch_result,
    print_summary_rows,
)
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import visions as vision_services
from lifeos_cli.db.services.read_models import VisionView

VISION_SUMMARY_COLUMNS = ("vision_id", "status", "area_id", "name")
VISION_WITH_TASKS_COLUMNS = ("task_id", "status", "parent_task_id", "content")


def _format_vision_summary(vision: VisionView) -> str:
    status = "deleted" if vision.deleted_at is not None else vision.status
    return f"{vision.id}\t{status}\t{vision.area_id or '-'}\t{vision.name}"


def _format_vision_detail(vision: VisionView) -> str:
    person_names = ", ".join(person.name for person in vision.person) if vision.person else "-"
    return "\n".join(
        (
            f"id: {vision.id}",
            f"name: {vision.name}",
            f"description: {vision.description or '-'}",
            f"status: {vision.status}",
            f"stage: {vision.stage}",
            f"experience_points: {vision.experience_points}",
            f"experience_rate_per_hour: {vision.experience_rate_per_hour or '-'}",
            f"area_id: {vision.area_id or '-'}",
            f"person: {person_names}",
            f"created_at: {format_timestamp(vision.created_at)}",
            f"updated_at: {format_timestamp(vision.updated_at)}",
            f"deleted_at: {format_timestamp(vision.deleted_at)}",
        )
    )


def _format_vision_with_tasks(vision: VisionView) -> str:
    tasks = vision.tasks
    task_lines = [
        f"  {task.id}\t{task.status}\t{task.parent_task_id or '-'}\t{task.content}"
        for task in tasks
    ]
    task_section_lines = (
        [f"  {format_summary_header(VISION_WITH_TASKS_COLUMNS)}", *task_lines]
        if task_lines
        else ["  -"]
    )
    return "\n".join(
        (
            _format_vision_detail(vision),
            "tasks:",
            *task_section_lines,
        )
    )


def _format_vision_stats(stats: vision_services.VisionStats) -> str:
    return "\n".join(
        (
            f"total_tasks: {stats.total_tasks}",
            f"completed_tasks: {stats.completed_tasks}",
            f"in_progress_tasks: {stats.in_progress_tasks}",
            f"todo_tasks: {stats.todo_tasks}",
            f"completion_percentage: {stats.completion_percentage:.2f}",
            f"total_estimated_effort: {stats.total_estimated_effort or '-'}",
            f"total_actual_effort: {stats.total_actual_effort or '-'}",
        )
    )


async def handle_vision_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            vision = await vision_services.create_vision(
                session,
                name=args.name,
                description=args.description,
                status=args.status,
                area_id=args.area_id,
                person_ids=args.person_ids,
                experience_rate_per_hour=args.experience_rate_per_hour,
            )
        except (
            vision_services.VisionAlreadyExistsError,
            vision_services.AreaReferenceNotFoundError,
            ValueError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created vision {vision.id}")
    return 0


async def handle_vision_list_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            visions = await vision_services.list_visions(
                session,
                status=args.status,
                area_id=args.area_id,
                person_id=args.person_id,
                limit=args.limit,
                offset=args.offset,
            )
        except ValueError as exc:
            return cli_handler_utils.print_cli_error(exc)
    if args.json:
        print_json_items(visions)
        return 0
    print_summary_rows(
        items=visions,
        columns=VISION_SUMMARY_COLUMNS,
        row_formatter=_format_vision_summary,
        empty_message="No visions found.",
    )
    return 0


async def handle_vision_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        vision = await vision_services.get_vision(
            session,
            vision_id=args.vision_id,
        )
    if vision is None:
        return cli_handler_utils.print_missing_record_error("Vision", args.vision_id)
    if args.json:
        print_json_payload(vision)
        return 0
    print(_format_vision_detail(vision))
    return 0


async def handle_vision_with_tasks_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            vision = await vision_services.get_vision_with_tasks(
                session,
                vision_id=args.vision_id,
            )
        except vision_services.VisionNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(_format_vision_with_tasks(vision))
    return 0


async def handle_vision_stats_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            stats = await vision_services.get_vision_stats(
                session,
                vision_id=args.vision_id,
            )
        except vision_services.VisionNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(_format_vision_stats(stats))
    return 0


async def handle_vision_update_async(args: argparse.Namespace) -> int:
    conflicting_flags = (
        (
            args.clear_description and args.description is not None,
            "--description",
            "--clear-description",
        ),
        (args.clear_area and args.area_id is not None, "--area-id", "--clear-area"),
        (
            args.clear_experience_rate and args.experience_rate_per_hour is not None,
            "--experience-rate-per-hour",
            "--clear-experience-rate",
        ),
        (args.clear_person and args.person_ids is not None, "--person-id", "--clear-person"),
    )
    conflict_error = cli_handler_utils.validate_mutually_exclusive_pairs(conflicting_flags)
    if conflict_error is not None:
        return conflict_error
    async with db_session.session_scope() as session:
        try:
            vision = await vision_services.update_vision(
                session,
                vision_id=args.vision_id,
                name=args.name,
                description=args.description,
                clear_description=args.clear_description,
                status=args.status,
                area_id=args.area_id,
                clear_area=args.clear_area,
                person_ids=args.person_ids,
                clear_person=args.clear_person,
                experience_rate_per_hour=args.experience_rate_per_hour,
                clear_experience_rate=args.clear_experience_rate,
            )
        except (
            vision_services.VisionNotFoundError,
            vision_services.VisionAlreadyExistsError,
            vision_services.AreaReferenceNotFoundError,
            ValueError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated vision {vision.id}")
    return 0


async def handle_vision_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        if len(args.vision_ids) > 1:
            result = await vision_services.batch_delete_visions(
                session,
                vision_ids=args.vision_ids,
            )
            return print_batch_result(
                success_label="Deleted visions",
                success_count=result.deleted_count,
                failed_label="Failed vision IDs",
                result=result,
            )
        try:
            await vision_services.delete_vision(session, vision_id=args.vision_ids[0])
        except vision_services.VisionNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted vision {args.vision_ids[0]}")
    return 0


async def handle_vision_add_experience_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            vision = await vision_services.add_experience_to_vision(
                session,
                vision_id=args.vision_id,
                experience_points=args.experience_points,
            )
        except (vision_services.VisionNotFoundError, ValueError) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated vision {vision.id}")
    return 0


async def handle_vision_sync_experience_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            vision = await vision_services.sync_vision_experience(
                session,
                vision_id=args.vision_id,
            )
        except vision_services.VisionNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Synced vision {vision.id}")
    return 0


async def handle_vision_harvest_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            vision = await vision_services.harvest_vision(
                session,
                vision_id=args.vision_id,
            )
        except (
            vision_services.VisionNotFoundError,
            vision_services.VisionNotReadyForHarvestError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Harvested vision {vision.id}")
    return 0
