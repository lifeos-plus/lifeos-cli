"""Builder helpers for sleep actions."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_parser,
    help_message,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.parser_common import (
    add_date_range_arguments,
    add_limit_offset_arguments,
    add_start_end_date_arguments,
)
from lifeos_cli.cli_support.resources.sleep.handlers import (
    handle_sleep_add_async,
    handle_sleep_delete_async,
    handle_sleep_list_async,
    handle_sleep_show_async,
    handle_sleep_summary_async,
    handle_sleep_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.cli_support.time_args import parse_user_datetime_value
from lifeos_cli.i18n import cli_message as _


def build_sleep_add_parser(
    sleep_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the sleep add command."""
    add_parser = add_documented_parser(
        sleep_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.sleep.parser_actions.add_sleep_segment"),
            description=_(
                "resources.sleep.parser_actions.create_one_sleep_segment_with_start_and_end_times"
            ),
            examples=(
                "lifeos sleep add --start-time 2026-08-18T22:30:00 --end-time 2026-08-19T06:30:00",
            ),
            notes=(
                _(
                    "resources.sleep.parser_actions.segment_belongs_to_local_operational_date_of_its_start_time"
                ),
                help_message("notes.datetime.configuredTimezone"),
            ),
        ),
    )
    add_parser.add_argument(
        "--start-time",
        type=parse_user_datetime_value,
        required=True,
        help=_("common.messages.start_time"),
    )
    add_parser.add_argument(
        "--end-time",
        type=parse_user_datetime_value,
        required=True,
        help=_("resources.sleep.parser_actions.end_time"),
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_sleep_add_async))


def build_sleep_list_parser(
    sleep_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the sleep list command."""
    list_parser = add_documented_parser(
        sleep_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.sleep.parser_actions.list_sleep_segments"),
            description=_("resources.sleep.parser_actions.list_sleep_segments_by_attribution_date"),
            examples=(
                "lifeos sleep list --date 2026-08-19",
                "lifeos sleep list --start-date 2026-08-01 --end-date 2026-08-31 --json",
            ),
            notes=(help_message("notes.dateSelection.dateOrRange"),),
        ),
    )
    add_date_range_arguments(
        list_parser,
        date_help=_("common.messages.repeat_date_for_one_or_more_local_dates"),
    )
    add_start_end_date_arguments(
        list_parser,
        start_date_help=_("common.messages.inclusive_local_date_range_start_date"),
        end_date_help=_("common.messages.inclusive_local_date_range_end_date"),
    )
    add_limit_offset_arguments(list_parser)
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_sleep_list_async))


def build_sleep_show_parser(
    sleep_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the sleep show command."""
    show_parser = add_documented_parser(
        sleep_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.sleep.parser_actions.show_sleep_segment"),
            description=_("resources.sleep.parser_actions.show_one_sleep_segment"),
            examples=("lifeos sleep show <sleep-segment-id>",),
        ),
    )
    show_parser.add_argument(
        "segment_id",
        type=UUID,
        help=_("resources.sleep.parser_actions.sleep_segment_identifier"),
    )
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_sleep_show_async))


def build_sleep_update_parser(
    sleep_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the sleep update command."""
    update_parser = add_documented_parser(
        sleep_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.sleep.parser_actions.update_sleep_segment"),
            description=_(
                "resources.sleep.parser_actions.update_sleep_segment_times_and_recompute_duration"
            ),
            examples=("lifeos sleep update <sleep-segment-id> --start-time 2026-08-18T23:00:00",),
            notes=(
                _(
                    "common.messages.only_explicitly_provided_flags_are_changed_omitted_values_are_preserved"
                ),
            ),
        ),
    )
    update_parser.add_argument(
        "segment_id",
        type=UUID,
        help=_("resources.sleep.parser_actions.sleep_segment_identifier"),
    )
    update_parser.add_argument(
        "--start-time",
        type=parse_user_datetime_value,
        help=_("common.messages.start_time"),
    )
    update_parser.add_argument(
        "--end-time",
        type=parse_user_datetime_value,
        help=_("resources.sleep.parser_actions.end_time"),
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_sleep_update_async))


def build_sleep_delete_parser(
    sleep_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the sleep delete command."""
    delete_parser = add_documented_parser(
        sleep_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.sleep.parser_actions.delete_sleep_segments"),
            description=_("resources.sleep.parser_actions.soft_delete_one_or_more_sleep_segments"),
            examples=(
                "lifeos sleep delete <sleep-segment-id>",
                "lifeos sleep delete <id-1> <id-2>",
            ),
            notes=(_("common.messages.delete_accepts_one_or_more_identifiers"),),
        ),
    )
    delete_parser.add_argument(
        "segment_ids",
        type=UUID,
        nargs="+",
        metavar="sleep-segment-id",
        help=_("common.parser.noun_identifiers_to_delete").format(noun="Sleep segment"),
    )
    delete_parser.set_defaults(handler=make_sync_handler(handle_sleep_delete_async))


def build_sleep_summary_parser(
    sleep_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the sleep summary command."""
    summary_parser = add_documented_parser(
        sleep_subparsers,
        "summary",
        help_content=HelpContent(
            summary=_("resources.sleep.parser_actions.show_sleep_daily_summary"),
            description=_(
                "resources.sleep.parser_actions.show_daily_sleep_summaries_for_one_or_more_dates"
            ),
            examples=(
                "lifeos sleep summary --date 2026-08-19",
                "lifeos sleep summary --start-date 2026-08-01 --end-date 2026-08-31 --json",
            ),
            notes=(
                _(
                    "resources.sleep.parser_actions.total_duration_minutes_plus_segment_count_per_day"
                ),
                help_message("notes.dateSelection.dateOrRange"),
            ),
        ),
    )
    add_date_range_arguments(
        summary_parser,
        date_help=_("common.messages.repeat_date_for_one_or_more_local_dates"),
    )
    add_start_end_date_arguments(
        summary_parser,
        start_date_help=_("common.messages.inclusive_local_date_range_start_date"),
        end_date_help=_("common.messages.inclusive_local_date_range_end_date"),
    )
    add_json_output_argument(summary_parser)
    summary_parser.set_defaults(handler=make_sync_handler(handle_sleep_summary_async))
