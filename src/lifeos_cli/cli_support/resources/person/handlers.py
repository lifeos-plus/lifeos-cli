"""CLI handlers for the person resource."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_timestamp,
    print_batch_result,
    print_summary_rows,
)
from lifeos_cli.cli_support.time_args import parse_optional_date_value
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import person as person_services
from lifeos_cli.db.services.read_models import PersonView

PERSON_SUMMARY_COLUMNS = ("person_id", "status", "name", "location", "tags")


def _format_person_summary(person: PersonView) -> str:
    status = "deleted" if person.deleted_at is not None else "active"
    tag_names = ",".join(tag.name for tag in person.tags) or "-"
    return f"{person.id}\t{status}\t{person.name}\t{person.location or '-'}\t{tag_names}"


def _format_person_detail(person: PersonView) -> str:
    tag_names = ", ".join(tag.name for tag in person.tags) if person.tags else "-"
    nicknames = person.nicknames
    return "\n".join(
        (
            f"id: {person.id}",
            f"name: {person.name}",
            f"description: {person.description or '-'}",
            f"nicknames: {', '.join(nicknames) if nicknames else '-'}",
            f"birth_date: {person.birth_date or '-'}",
            f"location: {person.location or '-'}",
            f"tags: {tag_names}",
            f"created_at: {format_timestamp(person.created_at)}",
            f"updated_at: {format_timestamp(person.updated_at)}",
            f"deleted_at: {format_timestamp(person.deleted_at)}",
        )
    )


async def handle_person_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            person = await person_services.create_person(
                session,
                name=args.name,
                description=args.description,
                nicknames=args.nickname,
                birth_date=parse_optional_date_value(args.birth_date),
                location=args.location,
                tag_ids=args.tag_id,
            )
        except (person_services.PersonAlreadyExistsError, LookupError, ValueError) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created person {person.id}")
    return 0


async def handle_person_list_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        person = await person_services.list_person(
            session,
            search=args.search,
            tag_id=args.tag_id,
            limit=args.limit,
            offset=args.offset,
        )
    if args.json:
        print_json_items(person)
        return 0
    print_summary_rows(
        items=person,
        columns=PERSON_SUMMARY_COLUMNS,
        row_formatter=_format_person_summary,
        empty_message="No person found.",
    )
    return 0


async def handle_person_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        person = await person_services.get_person(
            session,
            person_id=args.person_id,
        )
    if person is None:
        return cli_handler_utils.print_missing_record_error("Person", args.person_id)
    if args.json:
        print_json_payload(person)
        return 0
    print(_format_person_detail(person))
    return 0


async def handle_person_update_async(args: argparse.Namespace) -> int:
    conflicting_flags = (
        (
            args.clear_description and args.description is not None,
            "--description",
            "--clear-description",
        ),
        (args.clear_nicknames and args.nickname is not None, "--nickname", "--clear-nicknames"),
        (
            args.clear_birth_date and args.birth_date is not None,
            "--birth-date",
            "--clear-birth-date",
        ),
        (args.clear_location and args.location is not None, "--location", "--clear-location"),
        (args.clear_tags and args.tag_id is not None, "--tag-id", "--clear-tags"),
    )
    conflict_error = cli_handler_utils.validate_mutually_exclusive_pairs(conflicting_flags)
    if conflict_error is not None:
        return conflict_error
    async with db_session.session_scope() as session:
        try:
            person = await person_services.update_person(
                session,
                person_id=args.person_id,
                name=args.name,
                description=args.description,
                clear_description=args.clear_description,
                nicknames=args.nickname,
                clear_nicknames=args.clear_nicknames,
                birth_date=parse_optional_date_value(args.birth_date),
                clear_birth_date=args.clear_birth_date,
                location=args.location,
                clear_location=args.clear_location,
                tag_ids=args.tag_id,
                clear_tags=args.clear_tags,
            )
        except (
            person_services.PersonNotFoundError,
            person_services.PersonAlreadyExistsError,
            LookupError,
            ValueError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated person {person.id}")
    return 0


async def handle_person_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        if len(args.person_ids) > 1:
            result = await person_services.batch_delete_person(
                session,
                person_ids=args.person_ids,
            )
            return print_batch_result(
                success_label="Deleted people",
                success_count=result.deleted_count,
                failed_label="Failed person IDs",
                result=result,
            )
        try:
            await person_services.delete_person(session, person_id=args.person_ids[0])
        except person_services.PersonNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted person {args.person_ids[0]}")
    return 0
