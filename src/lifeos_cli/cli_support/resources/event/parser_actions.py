"""Builder helpers for event commands."""

from __future__ import annotations

import argparse
import re
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_parser,
    help_message,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.output_utils import format_summary_column_list
from lifeos_cli.cli_support.parser_common import (
    add_batch_delete_namespace,
    add_date_range_arguments,
    add_limit_offset_arguments,
    add_start_end_date_arguments,
)
from lifeos_cli.cli_support.resources.event.handlers import (
    EVENT_SUMMARY_COLUMNS,
    handle_event_add_async,
    handle_event_batch_delete_async,
    handle_event_delete_async,
    handle_event_list_async,
    handle_event_show_async,
    handle_event_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.cli_support.time_args import parse_datetime_or_date_value, parse_user_datetime_value
from lifeos_cli.i18n import cli_message as _

_VALUE_SPLIT_PATTERN = re.compile(r"[\s,]+")


def _parse_recurrence_name_list(value: str) -> list[str]:
    """Parse one comma-separated recurrence token list."""
    values = [part.strip() for part in _VALUE_SPLIT_PATTERN.split(value.strip()) if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("Expected at least one recurrence value.")
    return values


def _parse_recurrence_int_list(value: str) -> list[int]:
    """Parse one comma-separated integer recurrence token list."""
    values: list[int] = []
    for part in _VALUE_SPLIT_PATTERN.split(value.strip()):
        if not part.strip():
            continue
        try:
            values.append(int(part))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                "Expected comma-separated integer recurrence values."
            ) from exc
    if not values:
        raise argparse.ArgumentTypeError("Expected at least one integer recurrence value.")
    return values


def _parse_recurrence_weekday_ordinal(value: str) -> dict[str, object]:
    """Parse one nth-weekday selector as `ordinal:weekday`."""
    ordinal_text, separator, weekday = value.strip().partition(":")
    if not separator:
        raise argparse.ArgumentTypeError(
            "Expected recurrence weekday ordinal in `ordinal:weekday` form."
        )
    try:
        ordinal = int(ordinal_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Expected recurrence weekday ordinal to start with an integer."
        ) from exc
    return {"ordinal": ordinal, "weekday": weekday.strip()}


def build_event_add_parser(
    event_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the event add command."""
    add_parser = add_documented_parser(
        event_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.event.parser_actions.create_event"),
            description=_("resources.event.parser_actions.create_planned_schedule_event"),
            examples=(
                'lifeos event add "Doctor appointment" --start-time 2026-04-10T09:00:00 '
                "--end-time 2026-04-10T10:00:00",
                'lifeos event add "Deep work block" --type timeblock '
                "--start-time 2026-04-10T13:00:00 "
                "--task-id <task-id> --area-id <area-id>",
                'lifeos event add "Shared planning session" '
                "--start-time 2026-04-10T15:00:00 "
                "--end-time 2026-04-10T16:00:00 "
                "--person-id <person-id-1> --person-id <person-id-2> "
                "--tag-id <tag-id-1> --tag-id <tag-id-2>",
            ),
            notes=(
                _(
                    "resources.event.parser_actions.appointment_is_default_type_use_type_for_timeblocks_and_deadlines"
                ),
                help_message("notes.relations.repeatTagOrPersonAttach"),
                _(
                    "resources.event.parser_actions.if_end_time_is_omitted_event_is_treated_as_open_ended"
                ),
                help_message("notes.datetime.configuredTimezone"),
                _(
                    "resources.event.parser_actions.use_recurrence_flags_to_create_recurring_daily_weekly_monthly_or_yearly_series"
                ),
                _(
                    "resources.event.parser_actions.when_agent_creates_events_for_human_use_person_id_to_keep_human"
                ),
            ),
        ),
    )
    add_parser.add_argument("title", help=_("resources.event.parser_actions.event_title"))
    add_parser.add_argument(
        "--description", help=_("resources.event.parser_actions.optional_event_description")
    )
    add_parser.add_argument(
        "--start-time",
        required=True,
        type=parse_user_datetime_value,
        help=_("common.messages.start_time"),
    )
    add_parser.add_argument(
        "--end-time",
        type=parse_user_datetime_value,
        help=_("resources.event.parser_actions.optional_end_time"),
    )
    add_parser.add_argument(
        "--priority",
        type=int,
        default=0,
        help=_("resources.event.parser_actions.priority_from_0_to_5"),
    )
    add_parser.add_argument(
        "--status", default="planned", help=_("resources.event.parser_actions.event_status")
    )
    add_parser.add_argument(
        "--type",
        dest="event_type",
        default="appointment",
        help=_("resources.event.parser_actions.event_type_appointment_timeblock_or_deadline"),
    )
    add_parser.add_argument(
        "--all-day",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=_("resources.event.parser_actions.mark_event_as_all_day"),
    )
    add_parser.add_argument(
        "--area-id", type=UUID, help=_("common.messages.optional_linked_area_identifier")
    )
    add_parser.add_argument(
        "--task-id", type=UUID, help=_("common.messages.optional_linked_task_identifier")
    )
    add_parser.add_argument(
        "--recurrence-frequency",
        help=_(
            "resources.event.parser_actions.optional_recurrence_frequency_daily_weekly_monthly_or_yearly"
        ),
    )
    add_parser.add_argument(
        "--recurrence-interval",
        type=int,
        help=_("resources.event.parser_actions.optional_recurrence_interval_default_1"),
    )
    add_parser.add_argument(
        "--recurrence-count",
        type=int,
        help=_("resources.event.parser_actions.optional_total_occurrence_count"),
    )
    add_parser.add_argument(
        "--recurrence-until",
        type=parse_user_datetime_value,
        help=_("resources.event.parser_actions.optional_final_allowed_occurrence_start_time"),
    )
    add_parser.add_argument(
        "--recurrence-weekdays",
        type=_parse_recurrence_name_list,
        help=_("resources.event.parser_actions.optional_recurrence_weekdays"),
    )
    add_parser.add_argument(
        "--recurrence-month-days",
        type=_parse_recurrence_int_list,
        help=_("resources.event.parser_actions.optional_recurrence_month_days"),
    )
    add_parser.add_argument(
        "--recurrence-months",
        type=_parse_recurrence_int_list,
        help=_("resources.event.parser_actions.optional_recurrence_months"),
    )
    add_parser.add_argument(
        "--recurrence-weekday-ordinal",
        dest="recurrence_weekday_ordinals",
        type=_parse_recurrence_weekday_ordinal,
        action="append",
        default=None,
        help=_("resources.event.parser_actions.optional_recurrence_weekday_ordinal"),
    )
    add_parser.add_argument(
        "--tag-id",
        dest="tag_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("resources.event.parser_actions.repeat_to_attach_one_or_more_event_tags"),
    )
    add_parser.add_argument(
        "--person-id",
        dest="person_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_attach_one_or_more_person"),
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_event_add_async))


def build_event_list_parser(
    event_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the event list command."""
    list_parser = add_documented_parser(
        event_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.event.parser_actions.list_events"),
            description=(
                _(
                    "resources.event.parser_actions.list_events_with_optional_time_window_and_relation_filters"
                )
                + "\n\n"
                + _(
                    "resources.event.parser_actions.use_this_command_as_primary_query_entrypoint_for_scheduled_events"
                )
            ),
            examples=(
                "lifeos event list",
                "lifeos event list --date 2026-04-10",
                "lifeos event list --date 2026-04-10 --date 2026-04-16",
                "lifeos event list --start-date 2026-04-10 --end-date 2026-04-16",
                "lifeos event list --status planned --start-time 2026-04-10T00:00:00 "
                "--end-time 2026-04-10T23:59:59",
                "lifeos event list --type deadline --date 2026-04-10",
                "lifeos event list --task-id <task-id> --person-id <person-id>",
            ),
            notes=(
                help_message("notes.dateSelection.dateOrRange"),
                _(
                    "resources.event.parser_actions.when_both_start_time_and_end_time_are_given_overlapping_events_are"
                ),
                _(
                    "resources.event.parser_actions.recurring_series_are_expanded_for_bounded_window_queries_and_schedule_views"
                ),
                _(
                    "resources.event.parser_actions.use_type_to_narrow_results_to_one_event_topology"
                ),
                _(
                    "resources.event.parser_actions.use_title_contains_for_lightweight_text_filtering_instead_of_separate_search_command"
                ),
                _(
                    "common.messages.when_results_exist_list_command_prints_header_row_followed_by_tab_separated"
                ).format(columns=format_summary_column_list(EVENT_SUMMARY_COLUMNS)),
            ),
        ),
    )
    list_parser.add_argument(
        "--title-contains", help=_("common.messages.filter_by_title_substring")
    )
    list_parser.add_argument(
        "--status", help=_("resources.event.parser_actions.filter_by_event_status")
    )
    list_parser.add_argument(
        "--type",
        dest="event_type",
        help=_(
            "resources.event.parser_actions.filter_by_event_type_appointment_timeblock_or_deadline"
        ),
    )
    list_parser.add_argument(
        "--area-id", type=UUID, help=_("common.messages.filter_by_linked_area")
    )
    list_parser.add_argument(
        "--task-id", type=UUID, help=_("common.messages.filter_by_linked_task")
    )
    list_parser.add_argument(
        "--person-id", type=UUID, help=_("common.messages.filter_by_linked_person")
    )
    list_parser.add_argument("--tag-id", type=UUID, help=_("common.messages.filter_by_linked_tag"))
    add_date_range_arguments(
        list_parser,
        date_help=help_message("arguments.dateSelection.repeatedDate"),
    )
    add_start_end_date_arguments(
        list_parser,
        start_date_help=_("common.messages.inclusive_local_date_range_start_date"),
        end_date_help=_("common.messages.inclusive_local_date_range_end_date"),
    )
    list_parser.add_argument(
        "--start-time",
        dest="window_start",
        type=parse_datetime_or_date_value,
        help=_(
            "common.messages.inclusive_time_filter_start_date_only_values_use_configured_timezone"
        ),
    )
    list_parser.add_argument(
        "--end-time",
        dest="window_end",
        type=parse_datetime_or_date_value,
        help=_(
            "common.messages.inclusive_time_filter_end_date_only_values_use_configured_timezone"
        ),
    )
    add_limit_offset_arguments(list_parser)
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_event_list_async))


def build_event_show_parser(
    event_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the event show command."""
    show_parser = add_documented_parser(
        event_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.event.parser_actions.show_event"),
            description=_("resources.event.parser_actions.show_one_event_with_full_metadata"),
            examples=(
                "lifeos event show 11111111-1111-1111-1111-111111111111",
                "lifeos event show 11111111-1111-1111-1111-111111111111",
            ),
        ),
    )
    show_parser.add_argument(
        "event_id", type=UUID, help=_("resources.event.parser_actions.event_identifier")
    )
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_event_show_async))


def build_event_update_parser(
    event_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the event update command."""
    update_parser = add_documented_parser(
        event_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.event.parser_actions.update_event"),
            description=_("resources.event.parser_actions.update_mutable_event_fields"),
            examples=(
                "lifeos event update 11111111-1111-1111-1111-111111111111 --status completed",
                "lifeos event update 11111111-1111-1111-1111-111111111111 --type deadline",
                "lifeos event update 11111111-1111-1111-1111-111111111111 "
                "--start-time 2026-04-10T09:00:00 --end-time 2026-04-10T10:00:00",
                "lifeos event update 11111111-1111-1111-1111-111111111111 "
                "--scope single --instance-start 2026-04-10T09:00:00 "
                "--clear-end-time",
                "lifeos event update 11111111-1111-1111-1111-111111111111 "
                "--person-id <person-id-1> --person-id <person-id-2> "
                "--tag-id <tag-id-1> --tag-id <tag-id-2>",
                "lifeos event update 11111111-1111-1111-1111-111111111111 "
                "--clear-task --clear-area",
                "lifeos event update 11111111-1111-1111-1111-111111111111 "
                "--clear-person --clear-tags",
            ),
            notes=(
                _(
                    "resources.event.parser_actions.use_type_to_retag_event_as_appointment_timeblock_or_deadline"
                ),
                help_message("notes.clearFlags.explicitOptionalValues"),
                help_message("notes.clearFlags.valueConflict"),
                help_message("notes.datetime.configuredTimezone"),
                help_message("notes.recurringScope.updates"),
                help_message("notes.recurringScope.instanceStartRequired"),
                _(
                    "resources.event.parser_actions.distinction_between_clear_advanced_recurrence_and_clear_recurrence"
                ),
                _(
                    "resources.event.parser_actions.use_repeated_person_id_to_keep_human_only_agent_only_and_shared"
                ),
            ),
        ),
    )
    update_parser.add_argument(
        "event_id", type=UUID, help=_("resources.event.parser_actions.event_identifier")
    )
    update_parser.add_argument(
        "--title", help=_("resources.event.parser_actions.updated_event_title")
    )
    update_parser.add_argument("--description", help=_("common.messages.updated_description"))
    update_parser.add_argument(
        "--clear-description",
        action="store_true",
        help=_("resources.event.parser_actions.clear_description"),
    )
    update_parser.add_argument(
        "--start-time",
        type=parse_user_datetime_value,
        help=_("common.messages.updated_start_time"),
    )
    update_parser.add_argument(
        "--end-time", type=parse_user_datetime_value, help=_("common.messages.updated_end_time")
    )
    update_parser.add_argument(
        "--clear-end-time",
        action="store_true",
        help=_("resources.event.parser_actions.clear_end_time"),
    )
    update_parser.add_argument(
        "--priority",
        type=int,
        help=_("resources.event.parser_actions.updated_priority_from_0_to_5"),
    )
    update_parser.add_argument(
        "--status", help=_("resources.event.parser_actions.updated_event_status")
    )
    update_parser.add_argument(
        "--type",
        dest="event_type",
        help=_(
            "resources.event.parser_actions.updated_event_type_appointment_timeblock_or_deadline"
        ),
    )
    update_parser.add_argument(
        "--all-day",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=_("resources.event.parser_actions.toggle_all_day_status"),
    )
    update_parser.add_argument(
        "--area-id", type=UUID, help=_("common.messages.updated_linked_area_identifier")
    )
    update_parser.add_argument(
        "--clear-area", action="store_true", help=_("common.messages.clear_linked_area")
    )
    update_parser.add_argument(
        "--task-id", type=UUID, help=_("common.messages.updated_linked_task_identifier")
    )
    update_parser.add_argument(
        "--clear-task", action="store_true", help=_("common.messages.clear_linked_task")
    )
    update_parser.add_argument(
        "--recurrence-frequency",
        help=_(
            "resources.event.parser_actions.updated_recurrence_frequency_daily_weekly_monthly_or_yearly"
        ),
    )
    update_parser.add_argument(
        "--recurrence-interval",
        type=int,
        help=_("resources.event.parser_actions.updated_recurrence_interval"),
    )
    update_parser.add_argument(
        "--recurrence-count",
        type=int,
        help=_("resources.event.parser_actions.updated_recurrence_count"),
    )
    update_parser.add_argument(
        "--recurrence-until",
        type=parse_user_datetime_value,
        help=_("resources.event.parser_actions.updated_recurrence_until_datetime"),
    )
    update_parser.add_argument(
        "--recurrence-weekdays",
        type=_parse_recurrence_name_list,
        help=_("resources.event.parser_actions.updated_recurrence_weekdays"),
    )
    update_parser.add_argument(
        "--recurrence-month-days",
        type=_parse_recurrence_int_list,
        help=_("resources.event.parser_actions.updated_recurrence_month_days"),
    )
    update_parser.add_argument(
        "--recurrence-months",
        type=_parse_recurrence_int_list,
        help=_("resources.event.parser_actions.updated_recurrence_months"),
    )
    update_parser.add_argument(
        "--recurrence-weekday-ordinal",
        dest="recurrence_weekday_ordinals",
        type=_parse_recurrence_weekday_ordinal,
        action="append",
        default=None,
        help=_("resources.event.parser_actions.updated_recurrence_weekday_ordinal"),
    )
    update_parser.add_argument(
        "--clear-advanced-recurrence",
        dest="clear_recurrence_rule",
        action="store_true",
        help=_("resources.event.parser_actions.remove_advanced_recurrence_rule_details"),
    )
    update_parser.add_argument(
        "--clear-recurrence",
        action="store_true",
        help=_("resources.event.parser_actions.remove_recurrence_from_event"),
    )
    update_parser.add_argument(
        "--scope",
        default="all",
        help=_(
            "resources.event.parser_actions.update_scope_for_recurring_events_single_all_future_or_all"
        ),
    )
    update_parser.add_argument(
        "--instance-start",
        type=parse_user_datetime_value,
        help=_(
            "resources.event.parser_actions.instance_start_time_for_single_or_all_future_recurring_updates"
        ),
    )
    update_parser.add_argument(
        "--tag-id",
        dest="tag_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_replace_tags_with_one_or_more_identifiers"),
    )
    update_parser.add_argument(
        "--clear-tags", action="store_true", help=_("common.messages.remove_all_tags")
    )
    update_parser.add_argument(
        "--person-id",
        dest="person_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_replace_person_with_one_or_more_identifiers"),
    )
    update_parser.add_argument(
        "--clear-person", action="store_true", help=_("common.messages.remove_all_person")
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_event_update_async))


def build_event_delete_parser(
    event_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the event delete command."""
    delete_parser = add_documented_parser(
        event_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.event.parser_actions.delete_event"),
            description=_("resources.event.parser_actions.delete_one_event"),
            examples=(
                "lifeos event delete 11111111-1111-1111-1111-111111111111",
                "lifeos event delete 11111111-1111-1111-1111-111111111111 "
                "--scope single --instance-start 2026-04-10T09:00:00",
                "lifeos event delete 11111111-1111-1111-1111-111111111111 "
                "--scope all_future --instance-start 2026-04-10T09:00:00",
            ),
            notes=(
                help_message("notes.recurringScope.deletes"),
                help_message("notes.recurringScope.instanceStartRequired"),
                help_message("notes.datetime.configuredTimezone"),
            ),
        ),
    )
    delete_parser.add_argument(
        "event_id", type=UUID, help=_("resources.event.parser_actions.event_identifier")
    )
    delete_parser.add_argument(
        "--scope",
        default="all",
        help=_(
            "resources.event.parser_actions.delete_scope_for_recurring_events_single_all_future_or_all"
        ),
    )
    delete_parser.add_argument(
        "--instance-start",
        type=parse_user_datetime_value,
        help=_(
            "resources.event.parser_actions.instance_start_time_for_single_or_all_future_recurring_deletes"
        ),
    )
    delete_parser.set_defaults(handler=make_sync_handler(handle_event_delete_async))


def build_event_batch_parser(
    event_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the event batch command tree."""
    add_batch_delete_namespace(
        event_subparsers,
        dest="event_batch_command",
        ids_dest="event_ids",
        noun="event",
        delete_handler=make_sync_handler(handle_event_batch_delete_async),
        batch_summary=_("resources.event.parser_actions.run_batch_event_operations"),
        batch_description=_("resources.event.parser_actions.delete_multiple_events_in_one_command"),
        batch_examples=(
            "lifeos event batch delete --help",
            "lifeos event batch delete --ids <event-id-1> <event-id-2>",
        ),
        batch_notes=(
            _("common.messages.this_namespace_currently_exposes_only_delete_workflow"),
            _("common.messages.use_data_batch_delete_for_file_or_stream_bulk_workflows"),
        ),
        delete_summary=_("resources.event.parser_actions.delete_multiple_events"),
        delete_description=_("resources.event.parser_actions.delete_multiple_events_by_identifier"),
        delete_examples=("lifeos event batch delete --ids <event-id-1> <event-id-2>",),
        metavar=_("common.messages.batch_action_hyphenated_metavar"),
    )
