"""Note resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
)
from lifeos_cli.cli_support.resources.note.parser_actions import (
    build_note_add_parser,
    build_note_batch_parser,
    build_note_delete_parser,
    build_note_list_parser,
    build_note_search_parser,
    build_note_show_parser,
    build_note_update_parser,
)
from lifeos_cli.i18n import cli_message as _


def build_note_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the note command tree."""
    note_parser = add_documented_help_parser(
        subparsers,
        "note",
        help_content=HelpContent(
            summary=_("resources.note.parser.capture_and_manage_notes"),
            description=_("resources.note.parser.create_inspect_update_and_delete_note_records"),
            examples=(
                "lifeos note add --help",
                "lifeos note list --help",
                "lifeos note batch --help",
            ),
            notes=(
                _(
                    "resources.note.parser.run_lifeos_init_before_using_note_commands_for_first_time"
                ),
                _(
                    "resources.note.parser.see_lifeos_note_batch_help_for_bulk_update_content_workflows"
                ),
            ),
        ),
    )
    note_subparsers = note_parser.add_subparsers(
        dest="note_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )
    build_note_add_parser(note_subparsers)
    build_note_list_parser(note_subparsers)
    build_note_search_parser(note_subparsers)
    build_note_show_parser(note_subparsers)
    build_note_update_parser(note_subparsers)
    build_note_delete_parser(note_subparsers)
    build_note_batch_parser(note_subparsers)
