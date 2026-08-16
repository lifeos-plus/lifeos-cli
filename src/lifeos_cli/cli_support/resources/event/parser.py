"""Event resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
)
from lifeos_cli.cli_support.resources.event.parser_actions import (
    build_event_add_parser,
    build_event_delete_parser,
    build_event_list_parser,
    build_event_show_parser,
    build_event_update_parser,
)
from lifeos_cli.i18n import cli_message as _


def build_event_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the event command tree."""
    event_parser = add_documented_help_parser(
        subparsers,
        "event",
        help_content=HelpContent(
            summary=_("resources.event.parser.manage_planned_schedule_events"),
            description=(
                _("resources.event.parser.create_and_maintain_planned_schedule_blocks")
                + "\n\n"
                + _(
                    "resources.event.parser.events_represent_calendar_intent_and_time_allocation_not_todo_semantics"
                )
            ),
            examples=(
                "lifeos event add --help",
                "lifeos event list --help",
                "lifeos event batch --help",
            ),
            notes=(
                _("resources.event.parser.use_list_as_primary_query_entrypoint_for_events"),
                _("resources.event.parser.events_can_optionally_reference_one_area_and_one_task"),
                _(
                    "resources.event.parser.event_types_distinguish_hard_appointments_flexible_timeblocks_and_deadlines"
                ),
            ),
        ),
    )
    event_subparsers = event_parser.add_subparsers(
        dest="event_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    build_event_add_parser(event_subparsers)
    build_event_list_parser(event_subparsers)
    build_event_show_parser(event_subparsers)
    build_event_update_parser(event_subparsers)
    build_event_delete_parser(event_subparsers)
