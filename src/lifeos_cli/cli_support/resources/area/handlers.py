"""CLI handlers for the area resource."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_timestamp,
    print_batch_result,
    print_summary_rows,
)
from lifeos_cli.db import session as db_session
from lifeos_cli.db.models.area import Area
from lifeos_cli.db.services import areas as area_services

AREA_SUMMARY_COLUMNS = ("area_id", "status", "display_order", "name")


def _format_area_summary(area: Area) -> str:
    status_parts: list[str] = []
    if area.deleted_at is not None:
        status_parts.append("deleted")
    status_parts.append("active" if area.is_active else "inactive")
    return f"{area.id}\t{'/'.join(status_parts)}\t{area.display_order}\t{area.name}"


def _format_area_detail(area: Area) -> str:
    return "\n".join(
        (
            f"id: {area.id}",
            f"name: {area.name}",
            f"description: {area.description or '-'}",
            f"color: {area.color}",
            f"icon: {area.icon or '-'}",
            f"is_active: {area.is_active}",
            f"display_order: {area.display_order}",
            f"created_at: {format_timestamp(area.created_at)}",
            f"updated_at: {format_timestamp(area.updated_at)}",
            f"deleted_at: {format_timestamp(area.deleted_at)}",
        )
    )


async def handle_area_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            area = await area_services.create_area(
                session,
                name=args.name,
                description=args.description,
                color=args.color,
                icon=args.icon,
                is_active=not args.inactive,
                display_order=args.display_order,
            )
        except area_services.AreaAlreadyExistsError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created area {area.id}")
    return 0


async def handle_area_list_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        areas = await area_services.list_areas(
            session,
            include_inactive=args.include_inactive,
            limit=args.limit,
            offset=args.offset,
        )
    if args.json:
        print_json_items(areas)
        return 0
    print_summary_rows(
        items=areas,
        columns=AREA_SUMMARY_COLUMNS,
        row_formatter=_format_area_summary,
        empty_message="No areas found.",
    )
    return 0


async def handle_area_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        area = await area_services.get_area(
            session,
            area_id=args.area_id,
        )
    if area is None:
        return cli_handler_utils.print_missing_record_error("Area", args.area_id)
    if args.json:
        print_json_payload(area)
        return 0
    print(_format_area_detail(area))
    return 0


async def handle_area_update_async(args: argparse.Namespace) -> int:
    conflict_error = cli_handler_utils.validate_mutually_exclusive_pairs(
        (
            (
                args.clear_description and args.description is not None,
                "--description",
                "--clear-description",
            ),
            (args.clear_icon and args.icon is not None, "--icon", "--clear-icon"),
        )
    )
    if conflict_error is not None:
        return conflict_error
    async with db_session.session_scope() as session:
        try:
            area = await area_services.update_area(
                session,
                area_id=args.area_id,
                name=args.name,
                description=args.description,
                clear_description=args.clear_description,
                color=args.color,
                icon=args.icon,
                clear_icon=args.clear_icon,
                is_active=args.active,
                display_order=args.display_order,
            )
        except (area_services.AreaNotFoundError, area_services.AreaAlreadyExistsError) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated area {area.id}")
    return 0


async def handle_area_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        if len(args.area_ids) > 1:
            result = await area_services.batch_delete_areas(
                session,
                area_ids=args.area_ids,
            )
            return print_batch_result(
                success_label="Deleted areas",
                success_count=result.deleted_count,
                failed_label="Failed area IDs",
                result=result,
            )
        try:
            await area_services.delete_area(session, area_id=args.area_ids[0])
        except area_services.AreaNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted area {args.area_ids[0]}")
    return 0
