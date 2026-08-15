"""Builder helpers for core timelog actions."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_parser,
    help_message,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.output_utils import format_summary_column_list
from lifeos_cli.cli_support.parser_common import (
    add_date_range_arguments,
    add_limit_offset_arguments,
    add_start_end_date_arguments,
)
from lifeos_cli.cli_support.resources.timelog.handlers import (
    TIMELOG_SUMMARY_COLUMNS,
    TIMELOG_SUMMARY_COLUMNS_WITH_COUNTS,
    handle_timelog_add_async,
    handle_timelog_delete_async,
    handle_timelog_list_async,
    handle_timelog_show_async,
    handle_timelog_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.cli_support.time_args import parse_datetime_or_date_value, parse_user_datetime_value
from lifeos_cli.i18n import cli_message as _


def build_timelog_add_parser(
    timelog_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the timelog add command."""
    add_parser = add_documented_parser(
        timelog_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.timelog.parser_actions.create_timelog"),
            description=_(
                "resources.timelog.parser_actions.create_one_actual_time_record_or_preview_quick_batch_add"
            ),
            examples=(
                'lifeos timelog add "Deep work" --start-time 2026-04-10T13:00:00 '
                "--end-time 2026-04-10T14:30:00",
                'lifeos timelog add "Run" --start-time 2026-04-10T07:00:00 '
                "--end-time 2026-04-10T07:30:00 --area-id <area-id> --energy-level 4",
                'lifeos timelog add "Shared pairing" --start-time 2026-04-10T15:00:00 '
                "--end-time 2026-04-10T16:30:00 "
                "--person-id <person-id-1> --person-id <person-id-2> "
                "--tag-id <tag-id-1> --tag-id <tag-id-2>",
                'lifeos timelog add --entry "0700 Breakfast" --entry "0830 Deep work" '
                "--first-start-time 2026-04-10T06:30:00",
                "printf '0700 Breakfast\\n0830 Deep work\\n' | lifeos timelog add --stdin "
                "--first-start-time 2026-04-10T06:30:00",
                "lifeos timelog add --file quick-timelog.txt",
            ),
            notes=(
                help_message("notes.relations.repeatTagOrPersonAttach"),
                _(
                    "resources.timelog.parser_actions.single_record_mode_requires_both_start_time_and_end_time_because_record"
                ),
                _(
                    "resources.timelog.parser_actions.quick_batch_mode_accepts_hhmm_title_and_hh_mm_hh_mm_title"
                ),
                help_message("notes.datetime.configuredTimezone"),
                _(
                    "resources.timelog.parser_actions.when_quick_batch_mode_omits_first_start_time_first_row_inherits_latest"
                ),
                _(
                    "resources.timelog.parser_actions.when_agent_records_actual_work_use_person_id_to_state_whether_effort"
                ),
            ),
        ),
    )
    add_parser.add_argument(
        "title", nargs="?", help=_("resources.timelog.parser_actions.timelog_title")
    )
    add_parser.add_argument(
        "--start-time", type=parse_user_datetime_value, help=_("common.messages.start_time")
    )
    add_parser.add_argument(
        "--end-time",
        type=parse_user_datetime_value,
        help=_("resources.timelog.parser_actions.end_time"),
    )
    add_parser.add_argument(
        "--entry",
        dest="entry_lines",
        action="append",
        default=None,
        help=_("resources.timelog.parser_actions.repeat_to_add_one_quick_batch_entry_line"),
    )
    add_parser.add_argument(
        "--stdin",
        action="store_true",
        help=_("resources.timelog.parser_actions.read_quick_batch_entries_from_standard_input"),
    )
    add_parser.add_argument(
        "--file",
        help=_("resources.timelog.parser_actions.read_quick_batch_entries_from_utf_8_text_file"),
    )
    add_parser.add_argument(
        "--first-start-time",
        type=parse_user_datetime_value,
        help=_(
            "resources.timelog.parser_actions.first_quick_batch_start_time_defaults_to_latest_active_timelog_end_time"
        ),
    )
    add_parser.add_argument(
        "--yes",
        action="store_true",
        help=_(
            "resources.timelog.parser_actions.write_quick_batch_timelogs_without_interactive_confirmation_after_preview"
        ),
    )
    add_parser.add_argument(
        "--tracking-method",
        default="manual",
        help=_("resources.timelog.parser_actions.tracking_method"),
    )
    add_parser.add_argument(
        "--location", help=_("resources.timelog.parser_actions.optional_location")
    )
    add_parser.add_argument(
        "--energy-level",
        type=int,
        help=_("resources.timelog.parser_actions.optional_energy_level_from_1_to_5"),
    )
    add_parser.add_argument("--notes", help=_("resources.timelog.parser_actions.optional_notes"))
    add_parser.add_argument(
        "--area-id", type=UUID, help=_("common.messages.optional_linked_area_identifier")
    )
    add_parser.add_argument(
        "--task-id", type=UUID, help=_("common.messages.optional_linked_task_identifier")
    )
    add_parser.add_argument(
        "--tag-id",
        dest="tag_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("resources.timelog.parser_actions.repeat_to_attach_one_or_more_timelog_tags"),
    )
    add_parser.add_argument(
        "--person-id",
        dest="person_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_attach_one_or_more_people"),
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_timelog_add_async))


def build_timelog_list_parser(
    timelog_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the timelog list command."""
    _build_timelog_query_parser(
        timelog_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.timelog.parser_actions.list_timelogs"),
            description=(
                _(
                    "resources.timelog.parser_actions.list_timelogs_with_optional_time_window_relation_and_method_filters"
                )
                + "\n\n"
                + _(
                    "resources.timelog.parser_actions.use_this_command_as_primary_query_entrypoint_for_timelogs"
                )
            ),
            examples=(
                "lifeos timelog list",
                "lifeos timelog list --date 2026-04-10",
                "lifeos timelog list --date 2026-04-10 --date 2026-04-16",
                "lifeos timelog list --start-date 2026-04-10 --end-date 2026-04-16",
                "lifeos timelog list --tracking-method manual "
                "--start-time 2026-04-10T00:00:00 "
                "--end-time 2026-04-10T23:59:59",
                "lifeos timelog list --task-id <task-id> --person-id <person-id>",
                'lifeos timelog list --query "deep work" --count',
            ),
            notes=(
                help_message("notes.dateSelection.dateOrRange"),
                _(
                    "resources.timelog.parser_actions.use_start_time_end_time_as_overlap_window_not_exact_field_matches"
                ),
                _(
                    "resources.timelog.parser_actions.use_query_for_lightweight_text_filtering_across_titles_and_notes"
                ),
                _(
                    "common.messages.when_results_exist_list_command_prints_header_row_followed_by_tab_separated"
                ).format(columns=format_summary_column_list(TIMELOG_SUMMARY_COLUMNS)),
                _(
                    "common.messages.use_with_counts_to_add_relationship_count_columns_columns"
                ).format(columns=format_summary_column_list(TIMELOG_SUMMARY_COLUMNS_WITH_COUNTS)),
            ),
        ),
    )


def build_timelog_search_parser(
    timelog_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the timelog search command."""
    _build_timelog_query_parser(
        timelog_subparsers,
        "search",
        help_content=HelpContent(
            summary=_("resources.timelog.parser_actions.search_timelogs"),
            description=(
                _(
                    "resources.timelog.parser_actions.search_timelogs_with_keyword_time_window_relation_and_method_filters"
                )
                + "\n\n"
                + _(
                    "resources.timelog.parser_actions.search_reuses_timelog_list_filters_and_output"
                )
            ),
            examples=(
                'lifeos timelog search --query "洗" '
                "--start-time 2026-06-16T16:00:00.000Z "
                "--end-time 2026-06-17T15:59:59.999Z --limit 500 --count",
                'lifeos timelog search --query "deep work" --area-name Work --without-task',
                "lifeos timelog search --start-date 2026-04-10 "
                "--end-date 2026-04-16 --task-id <task-id>",
            ),
            notes=(
                help_message("notes.dateSelection.dateOrRange"),
                _(
                    "resources.timelog.parser_actions.use_start_time_end_time_as_overlap_window_not_exact_field_matches"
                ),
                _(
                    "resources.timelog.parser_actions.use_query_for_lightweight_text_filtering_across_titles_and_notes"
                ),
                _(
                    "resources.timelog.parser_actions.use_area_and_task_flags_for_structured_relation_filters"
                ),
                _(
                    "resources.timelog.parser_actions.when_results_exist_search_prints_header_row_followed_by_tab_separated"
                ).format(columns=format_summary_column_list(TIMELOG_SUMMARY_COLUMNS)),
                _(
                    "common.messages.use_with_counts_to_add_relationship_count_columns_columns"
                ).format(columns=format_summary_column_list(TIMELOG_SUMMARY_COLUMNS_WITH_COUNTS)),
            ),
        ),
    )


def _build_timelog_query_parser(
    timelog_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    *,
    help_content: HelpContent,
) -> None:
    parser = add_documented_parser(
        timelog_subparsers,
        name,
        help_content=help_content,
    )
    _add_timelog_query_arguments(parser)
    parser.set_defaults(handler=make_sync_handler(handle_timelog_list_async))


def _add_timelog_query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title-contains", help=_("common.messages.filter_by_title_substring"))
    parser.add_argument(
        "--notes-contains", help=_("resources.timelog.parser_actions.filter_by_notes_substring")
    )
    parser.add_argument(
        "--query", help=_("resources.timelog.parser_actions.search_title_and_notes_by_keyword")
    )
    parser.add_argument(
        "--tracking-method", help=_("resources.timelog.parser_actions.filter_by_tracking_method")
    )
    parser.add_argument("--area-id", type=UUID, help=_("common.messages.filter_by_linked_area"))
    parser.add_argument(
        "--area-name", help=_("resources.timelog.parser_actions.filter_by_exact_linked_area_name")
    )
    parser.add_argument(
        "--without-area",
        action="store_true",
        help=_("resources.timelog.parser_actions.filter_timelogs_without_linked_area"),
    )
    parser.add_argument("--task-id", type=UUID, help=_("common.messages.filter_by_linked_task"))
    parser.add_argument(
        "--without-task",
        action="store_true",
        help=_("resources.timelog.parser_actions.filter_timelogs_without_linked_task"),
    )
    parser.add_argument("--person-id", type=UUID, help=_("common.messages.filter_by_linked_person"))
    parser.add_argument("--tag-id", type=UUID, help=_("common.messages.filter_by_linked_tag"))
    parser.add_argument(
        "--with-counts",
        action="store_true",
        help=_("common.messages.include_relationship_count_columns_in_summary_output"),
    )
    add_date_range_arguments(
        parser,
        date_help=help_message("arguments.dateSelection.repeatedDate"),
    )
    add_start_end_date_arguments(
        parser,
        start_date_help=_("common.messages.inclusive_local_date_range_start_date"),
        end_date_help=_("common.messages.inclusive_local_date_range_end_date"),
    )
    parser.add_argument(
        "--start-time",
        dest="window_start",
        type=parse_datetime_or_date_value,
        help=_(
            "common.messages.inclusive_time_filter_start_date_only_values_use_configured_timezone"
        ),
    )
    parser.add_argument(
        "--end-time",
        dest="window_end",
        type=parse_datetime_or_date_value,
        help=_(
            "common.messages.inclusive_time_filter_end_date_only_values_use_configured_timezone"
        ),
    )
    parser.add_argument(
        "--count", action="store_true", help=_("common.messages.print_total_matched_count")
    )
    add_limit_offset_arguments(parser)
    add_json_output_argument(parser)


def build_timelog_show_parser(
    timelog_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the timelog show command."""
    show_parser = add_documented_parser(
        timelog_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.timelog.parser_actions.show_timelog"),
            description=_(
                "resources.timelog.parser_actions.show_one_timelog_with_full_metadata_and_derived_note_link_counts"
            ),
            examples=(
                "lifeos timelog show 11111111-1111-1111-1111-111111111111",
                "lifeos timelog show 11111111-1111-1111-1111-111111111111",
            ),
        ),
    )
    show_parser.add_argument(
        "timelog_id", type=UUID, help=_("resources.timelog.parser_actions.timelog_identifier")
    )
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_timelog_show_async))


def build_timelog_update_parser(
    timelog_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the timelog update command."""
    update_parser = add_documented_parser(
        timelog_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.timelog.parser_actions.update_timelog"),
            description=_("resources.timelog.parser_actions.update_mutable_timelog_fields"),
            examples=(
                "lifeos timelog update 11111111-1111-1111-1111-111111111111 --energy-level 5",
                "lifeos timelog update 11111111-1111-1111-1111-111111111111 "
                "--start-time 2026-04-10T13:00:00 --end-time 2026-04-10T14:00:00",
                "lifeos timelog update 11111111-1111-1111-1111-111111111111 "
                "--person-id <person-id-1> --person-id <person-id-2> "
                "--tag-id <tag-id-1> --tag-id <tag-id-2>",
                "lifeos timelog update 11111111-1111-1111-1111-111111111111 "
                "--clear-task --clear-area",
                "lifeos timelog update 11111111-1111-1111-1111-111111111111 "
                "--clear-people --clear-tags",
            ),
            notes=(
                help_message("notes.clearFlags.explicitOptionalValues"),
                help_message("notes.clearFlags.valueConflict"),
                help_message("notes.datetime.configuredTimezone"),
                _(
                    "resources.timelog.parser_actions.use_repeated_person_id_to_keep_actual_human_effort_agent_effort_and"
                ),
            ),
        ),
    )
    update_parser.add_argument(
        "timelog_id", type=UUID, help=_("resources.timelog.parser_actions.timelog_identifier")
    )
    update_parser.add_argument(
        "--title", help=_("resources.timelog.parser_actions.updated_timelog_title")
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
        "--tracking-method", help=_("resources.timelog.parser_actions.updated_tracking_method")
    )
    update_parser.add_argument("--location", help=_("common.messages.updated_location"))
    update_parser.add_argument(
        "--clear-location",
        action="store_true",
        help=_("resources.timelog.parser_actions.clear_location"),
    )
    update_parser.add_argument(
        "--energy-level",
        type=int,
        help=_("resources.timelog.parser_actions.updated_energy_level_from_1_to_5"),
    )
    update_parser.add_argument(
        "--clear-energy-level",
        action="store_true",
        help=_("resources.timelog.parser_actions.clear_energy_level"),
    )
    update_parser.add_argument("--notes", help=_("common.messages.updated_notes"))
    update_parser.add_argument(
        "--clear-notes", action="store_true", help=_("resources.timelog.parser_actions.clear_notes")
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
        help=_("common.messages.repeat_to_replace_people_with_one_or_more_identifiers"),
    )
    update_parser.add_argument(
        "--clear-people", action="store_true", help=_("common.messages.remove_all_people")
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_timelog_update_async))


def build_timelog_delete_parser(
    timelog_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the timelog delete command."""
    delete_parser = add_documented_parser(
        timelog_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.timelog.parser_actions.delete_timelog"),
            description=_("resources.timelog.parser_actions.delete_one_timelog"),
            examples=("lifeos timelog delete 11111111-1111-1111-1111-111111111111",),
        ),
    )
    delete_parser.add_argument(
        "timelog_id", type=UUID, help=_("resources.timelog.parser_actions.timelog_identifier")
    )
    delete_parser.set_defaults(handler=make_sync_handler(handle_timelog_delete_async))
