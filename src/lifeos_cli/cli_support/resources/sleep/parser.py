"""Sleep resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
)
from lifeos_cli.cli_support.resources.sleep.parser_actions import (
    build_sleep_add_parser,
    build_sleep_delete_parser,
    build_sleep_list_parser,
    build_sleep_show_parser,
    build_sleep_summary_parser,
    build_sleep_update_parser,
)
from lifeos_cli.i18n import cli_message as _


def build_sleep_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the sleep command tree."""
    sleep_parser = add_documented_help_parser(
        subparsers,
        "sleep",
        help_content=HelpContent(
            summary=_("resources.sleep.parser.manage_sleep_segments_and_daily_summaries"),
            description=(
                _("resources.sleep.parser.create_inspect_update_and_delete_sleep_segments")
                + "\n\n"
                + _(
                    "resources.sleep.parser.segments_are_attributed_to_their_local_operational_start_date"
                )
            ),
            examples=(
                "lifeos sleep add --help",
                "lifeos sleep list --help",
                "lifeos sleep summary --help",
            ),
            notes=(
                _("resources.sleep.parser.use_summary_for_daily_totals"),
                _("resources.sleep.parser.a_local_day_can_contain_multiple_sleep_segments"),
            ),
        ),
    )
    sleep_subparsers = sleep_parser.add_subparsers(
        dest="sleep_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    build_sleep_add_parser(sleep_subparsers)
    build_sleep_list_parser(sleep_subparsers)
    build_sleep_show_parser(sleep_subparsers)
    build_sleep_update_parser(sleep_subparsers)
    build_sleep_delete_parser(sleep_subparsers)
    build_sleep_summary_parser(sleep_subparsers)
