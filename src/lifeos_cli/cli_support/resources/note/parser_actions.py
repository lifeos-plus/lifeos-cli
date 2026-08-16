"""Builder helpers for note subcommands."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.output_utils import (
    NOTE_SUMMARY_COLUMNS,
    NOTE_SUMMARY_COLUMNS_WITH_COUNTS,
    format_summary_column_list,
)
from lifeos_cli.cli_support.parser_common import (
    add_batch_delete_action,
    add_limit_offset_arguments,
)
from lifeos_cli.cli_support.resources.note.handlers import (
    handle_note_add_async,
    handle_note_batch_delete_async,
    handle_note_batch_update_content_async,
    handle_note_delete_async,
    handle_note_list_async,
    handle_note_search_async,
    handle_note_show_async,
    handle_note_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_note_add_parser(
    note_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    add_parser = add_documented_parser(
        note_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.note.parser_actions.create_note"),
            description=(
                _("resources.note.parser_actions.create_new_note_from_inline_text_stdin_or_file")
                + "\n\n"
                + _(
                    "resources.note.parser_actions.use_this_action_to_capture_short_thoughts_prompts_or_raw_text_before"
                )
            ),
            examples=(
                'lifeos note add "Capture the sprint retrospective idea"',
                "printf 'line one\\nline two\\n' | lifeos note add --stdin",
                "lifeos note add --file ./note.md",
                'lifeos note add "Review shared feedback" --tag-id <tag-id-1> --tag-id <tag-id-2>',
                'lifeos note add "Review the monthly budget assumptions" --task-id <task-id>',
                'lifeos note add "Prepare the partner sync agenda" --event-id <event-id>',
                'lifeos note add "Completed after lunch" --habit-action-id <habit-action-id>',
            ),
            notes=(
                _(
                    "resources.note.parser_actions.wrap_inline_content_in_quotes_when_it_contains_spaces"
                ),
                _("resources.note.parser_actions.use_stdin_or_file_for_multi_line_note_content"),
                _(
                    "resources.note.parser_actions.repeat_same_relation_flag_to_link_multiple_records_of_that_type_in"
                ),
            ),
        ),
    )
    add_parser.add_argument(
        "content", nargs="?", help=_("resources.note.parser_actions.inline_note_content")
    )
    add_parser.add_argument(
        "--stdin",
        action="store_true",
        help=_("resources.note.parser_actions.read_note_content_from_standard_input"),
    )
    add_parser.add_argument(
        "--file", help=_("resources.note.parser_actions.read_note_content_from_utf_8_text_file")
    )
    add_parser.add_argument(
        "--tag-id",
        dest="tag_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("resources.note.parser_actions.repeat_to_associate_one_or_more_tags"),
    )
    add_parser.add_argument(
        "--person-id",
        dest="person_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_associate_one_or_more_person"),
    )
    add_parser.add_argument(
        "--task-id",
        dest="task_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("resources.note.parser_actions.repeat_to_associate_one_or_more_tasks"),
    )
    add_parser.add_argument(
        "--vision-id",
        dest="vision_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("resources.note.parser_actions.repeat_to_associate_one_or_more_visions"),
    )
    add_parser.add_argument(
        "--event-id",
        dest="event_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("resources.note.parser_actions.repeat_to_associate_one_or_more_events"),
    )
    add_parser.add_argument(
        "--timelog-id",
        dest="timelog_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("resources.note.parser_actions.repeat_to_associate_one_or_more_timelogs"),
    )
    add_parser.add_argument(
        "--habit-action-id",
        dest="habit_action_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("resources.note.parser_actions.repeat_to_associate_one_or_more_habit_actions"),
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_note_add_async))


def build_note_list_parser(
    note_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    list_parser = add_documented_parser(
        note_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.note.parser_actions.list_notes"),
            description=(
                _("resources.note.parser_actions.list_notes_in_reverse_creation_order")
                + "\n\n"
                + _(
                    "common.messages.when_results_exist_list_command_prints_header_row_followed_by_tab_separated"
                ).format(columns=format_summary_column_list(NOTE_SUMMARY_COLUMNS))
            ),
            examples=(
                "lifeos note list",
                "lifeos note list --tag-id <tag-id>",
                "lifeos note list --person-id <person-id>",
                "lifeos note list --event-id <event-id>",
                "lifeos note list --timelog-id <timelog-id>",
                "lifeos note list --habit-action-id <habit-action-id>",
                "lifeos note list --limit 20 --offset 20",
            ),
            notes=(
                _("resources.note.parser_actions.use_limit_and_offset_together_for_pagination"),
                _(
                    "common.messages.use_with_counts_to_add_relationship_count_columns_columns"
                ).format(columns=format_summary_column_list(NOTE_SUMMARY_COLUMNS_WITH_COUNTS)),
            ),
        ),
    )
    list_parser.add_argument("--tag-id", type=UUID, help=_("common.messages.filter_by_linked_tag"))
    list_parser.add_argument(
        "--event-id", type=UUID, help=_("resources.note.parser_actions.filter_by_linked_event")
    )
    list_parser.add_argument(
        "--person-id", type=UUID, help=_("common.messages.filter_by_linked_person")
    )
    list_parser.add_argument(
        "--task-id", type=UUID, help=_("common.messages.filter_by_linked_task")
    )
    list_parser.add_argument(
        "--timelog-id", type=UUID, help=_("resources.note.parser_actions.filter_by_linked_timelog")
    )
    list_parser.add_argument(
        "--vision-id", type=UUID, help=_("resources.note.parser_actions.filter_by_linked_vision")
    )
    list_parser.add_argument(
        "--habit-action-id",
        type=UUID,
        help=_("resources.note.parser_actions.filter_by_linked_habit_action"),
    )
    list_parser.add_argument(
        "--with-counts",
        action="store_true",
        help=_("common.messages.include_relationship_count_columns_in_summary_output"),
    )
    add_limit_offset_arguments(list_parser, row_noun="notes")
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_note_list_async))


def build_note_search_parser(
    note_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    search_parser = add_documented_parser(
        note_subparsers,
        "search",
        help_content=HelpContent(
            summary=_("resources.note.parser_actions.search_notes"),
            description=(
                _("resources.note.parser_actions.search_notes_by_keyword_tokens")
                + "\n\n"
                + _(
                    "resources.note.parser_actions.search_uses_case_insensitive_token_matching_each_token_is_checked_against_note_content"
                )
            ),
            examples=(
                'lifeos note search "meeting notes"',
                'lifeos note search "review" --task-id <task-id>',
                'lifeos note search "partner sync" --event-id <event-id>',
                'lifeos note search "completed" --habit-action-id <habit-action-id>',
                'lifeos note search "budget q2" --limit 20',
                'lifeos note search "archived idea"',
            ),
            notes=(
                _(
                    "resources.note.parser_actions.results_use_same_summary_format_as_lifeos_note_list"
                ),
                _(
                    "common.messages.use_with_counts_to_add_relationship_count_columns_columns"
                ).format(columns=format_summary_column_list(NOTE_SUMMARY_COLUMNS_WITH_COUNTS)),
                _(
                    "resources.note.parser_actions.multi_word_queries_are_split_into_tokens_and_matched_with_or_semantics"
                ),
            ),
        ),
    )
    search_parser.add_argument("query", help=_("resources.note.parser_actions.search_query_string"))
    search_parser.add_argument(
        "--tag-id", type=UUID, help=_("common.messages.filter_by_linked_tag")
    )
    search_parser.add_argument(
        "--event-id", type=UUID, help=_("resources.note.parser_actions.filter_by_linked_event")
    )
    search_parser.add_argument(
        "--person-id", type=UUID, help=_("common.messages.filter_by_linked_person")
    )
    search_parser.add_argument(
        "--task-id", type=UUID, help=_("common.messages.filter_by_linked_task")
    )
    search_parser.add_argument(
        "--timelog-id", type=UUID, help=_("resources.note.parser_actions.filter_by_linked_timelog")
    )
    search_parser.add_argument(
        "--vision-id", type=UUID, help=_("resources.note.parser_actions.filter_by_linked_vision")
    )
    search_parser.add_argument(
        "--habit-action-id",
        type=UUID,
        help=_("resources.note.parser_actions.filter_by_linked_habit_action"),
    )
    search_parser.add_argument(
        "--with-counts",
        action="store_true",
        help=_("common.messages.include_relationship_count_columns_in_summary_output"),
    )
    add_limit_offset_arguments(search_parser, row_noun="matching notes")
    add_json_output_argument(search_parser)
    search_parser.set_defaults(handler=make_sync_handler(handle_note_search_async))


def build_note_show_parser(
    note_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    show_parser = add_documented_parser(
        note_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.note.parser_actions.show_full_note_content"),
            description=(
                _(
                    "resources.note.parser_actions.show_single_note_with_full_metadata_and_original_content_body"
                )
                + "\n\n"
                + _(
                    "resources.note.parser_actions.use_this_action_when_you_need_to_inspect_preserved_line_breaks_instead"
                )
            ),
            examples=("lifeos note show 11111111-1111-1111-1111-111111111111",),
        ),
    )
    show_parser.add_argument(
        "note_id", type=UUID, help=_("resources.note.parser_actions.note_identifier")
    )
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_note_show_async))


def build_note_update_parser(
    note_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    update_parser = add_documented_parser(
        note_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.note.parser_actions.update_note"),
            description=(
                _(
                    "resources.note.parser_actions.update_note_content_and_weak_associations_in_place"
                )
                + "\n\n"
                + _(
                    "resources.note.parser_actions.omitted_fields_remain_unchanged_use_clear_flags_to_remove_links"
                )
            ),
            examples=(
                'lifeos note update 11111111-1111-1111-1111-111111111111 "Rewrite the note"',
                "lifeos note update 11111111-1111-1111-1111-111111111111 --task-id <task-id>",
                "lifeos note update 11111111-1111-1111-1111-111111111111 "
                "--tag-id <tag-id-1> --tag-id <tag-id-2>",
                "lifeos note update 11111111-1111-1111-1111-111111111111 "
                "--clear-tags --clear-events",
                "lifeos note update 11111111-1111-1111-1111-111111111111 --clear-timelogs",
                "lifeos note update 11111111-1111-1111-1111-111111111111 "
                "--habit-action-id <habit-action-id>",
            ),
            notes=(
                _(
                    "resources.note.parser_actions.repeat_same_relation_flag_to_replace_multiple_linked_tags_person_tasks_visions"
                ),
                _(
                    "resources.note.parser_actions.use_relation_flags_without_content_when_only_links_need_to_change"
                ),
            ),
        ),
    )
    update_parser.add_argument(
        "note_id", type=UUID, help=_("resources.note.parser_actions.note_identifier")
    )
    update_parser.add_argument(
        "content", nargs="?", help=_("resources.note.parser_actions.replacement_note_content")
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
    update_parser.add_argument(
        "--task-id",
        dest="task_ids",
        type=UUID,
        action="append",
        default=None,
        help=_(
            "resources.note.parser_actions.repeat_to_replace_tasks_with_one_or_more_identifiers"
        ),
    )
    update_parser.add_argument(
        "--clear-tasks",
        dest="clear_tasks",
        action="store_true",
        help=_("resources.note.parser_actions.remove_all_linked_tasks"),
    )
    update_parser.add_argument(
        "--vision-id",
        dest="vision_ids",
        type=UUID,
        action="append",
        default=None,
        help=_(
            "resources.note.parser_actions.repeat_to_replace_visions_with_one_or_more_identifiers"
        ),
    )
    update_parser.add_argument(
        "--clear-visions",
        action="store_true",
        help=_("resources.note.parser_actions.remove_all_linked_visions"),
    )
    update_parser.add_argument(
        "--event-id",
        dest="event_ids",
        type=UUID,
        action="append",
        default=None,
        help=_(
            "resources.note.parser_actions.repeat_to_replace_events_with_one_or_more_identifiers"
        ),
    )
    update_parser.add_argument(
        "--clear-events",
        action="store_true",
        help=_("resources.note.parser_actions.remove_all_linked_events"),
    )
    update_parser.add_argument(
        "--timelog-id",
        dest="timelog_ids",
        type=UUID,
        action="append",
        default=None,
        help=_(
            "resources.note.parser_actions.repeat_to_replace_timelogs_with_one_or_more_identifiers"
        ),
    )
    update_parser.add_argument(
        "--clear-timelogs",
        action="store_true",
        help=_("resources.note.parser_actions.remove_all_linked_timelogs"),
    )
    update_parser.add_argument(
        "--habit-action-id",
        dest="habit_action_ids",
        type=UUID,
        action="append",
        default=None,
        help=_(
            "resources.note.parser_actions.repeat_to_replace_habit_actions_with_one_or_more_identifiers"
        ),
    )
    update_parser.add_argument(
        "--clear-habit-actions",
        action="store_true",
        help=_("resources.note.parser_actions.remove_all_linked_habit_actions"),
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_note_update_async))


def build_note_delete_parser(
    note_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    delete_parser = add_documented_parser(
        note_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.note.parser_actions.delete_note"),
            description=_("resources.note.parser_actions.delete_note_by_identifier"),
            examples=("lifeos note delete 11111111-1111-1111-1111-111111111111",),
        ),
    )
    delete_parser.add_argument(
        "note_id", type=UUID, help=_("resources.note.parser_actions.note_identifier")
    )
    delete_parser.set_defaults(handler=make_sync_handler(handle_note_delete_async))


def build_note_batch_parser(
    note_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    batch_parser = add_documented_help_parser(
        note_subparsers,
        "batch",
        help_content=HelpContent(
            summary=_("resources.note.parser_actions.run_batch_note_operations"),
            description=_(
                "resources.note.parser_actions.run_note_operations_that_target_multiple_records_in_one_command"
            ),
            examples=(
                "lifeos note batch update-content --help",
                "lifeos note batch delete --help",
            ),
            notes=(
                _(
                    "resources.note.parser_actions.use_update_content_for_bulk_find_replace_across_active_note_content"
                ),
                _(
                    "resources.note.parser_actions.use_delete_to_remove_multiple_notes_by_identifier"
                ),
                _(
                    "resources.note.parser_actions.batch_commands_currently_accept_note_ids_directly"
                ),
            ),
        ),
    )
    batch_subparsers = batch_parser.add_subparsers(
        dest="note_batch_command",
        title=_("resources.note.parser_actions.operations"),
        metavar=_("resources.note.parser_actions.operation"),
    )

    batch_update_parser = add_documented_parser(
        batch_subparsers,
        "update-content",
        help_content=HelpContent(
            summary=_("resources.note.parser_actions.find_and_replace_note_content_in_bulk"),
            description=(
                _(
                    "resources.note.parser_actions.apply_find_replace_operation_across_multiple_active_notes"
                )
                + "\n\n"
                + _(
                    "resources.note.parser_actions.this_is_first_batch_editing_primitive_for_notes_and_provides_base_shape"
                )
            ),
            examples=(
                "lifeos note batch update-content --ids "
                "11111111-1111-1111-1111-111111111111 "
                "22222222-2222-2222-2222-222222222222 "
                '--find-text "draft" --replace-text "final"',
                "lifeos note batch update-content --ids "
                "11111111-1111-1111-1111-111111111111 "
                '--find-text "TODO" --replace-text "DONE" --case-sensitive',
            ),
            notes=(
                _("resources.note.parser_actions.only_active_notes_are_updated_by_this_command"),
                _(
                    "resources.note.parser_actions.failed_note_ids_are_printed_to_stderr_while_successful_updates_stay_on"
                ),
            ),
        ),
    )
    batch_update_parser.add_argument(
        "--ids",
        dest="note_ids",
        metavar="note-id",
        nargs="+",
        required=True,
        type=UUID,
        help=_("resources.note.parser_actions.one_or_more_note_identifiers_to_update"),
    )
    batch_update_parser.add_argument(
        "--find-text",
        required=True,
        help=_("resources.note.parser_actions.text_to_find_in_each_target_note"),
    )
    batch_update_parser.add_argument(
        "--replace-text",
        default="",
        help=_("resources.note.parser_actions.replacement_text_for_matched_content"),
    )
    batch_update_parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help=_(
            "resources.note.parser_actions.use_case_sensitive_find_replace_instead_of_case_insensitive_matching"
        ),
    )
    batch_update_parser.set_defaults(
        handler=make_sync_handler(handle_note_batch_update_content_async)
    )

    add_batch_delete_action(
        batch_subparsers,
        ids_dest="note_ids",
        noun="note",
        delete_handler=make_sync_handler(handle_note_batch_delete_async),
        delete_summary=_("resources.note.parser_actions.delete_multiple_notes"),
        delete_description=(
            _("resources.note.parser_actions.delete_multiple_notes_in_one_command")
            + "\n\n"
            + _(
                "resources.note.parser_actions.this_command_mirrors_lifeos_note_delete_but_works_across_many_note_ids"
            )
        ),
        delete_examples=(
            "lifeos note batch delete --ids "
            "11111111-1111-1111-1111-111111111111 "
            "22222222-2222-2222-2222-222222222222",
        ),
        delete_notes=(
            _(
                "resources.note.parser_actions.failed_note_ids_are_printed_to_stderr_while_successful_deletes_stay_on"
            ),
        ),
        ids_help=_("resources.note.parser_actions.one_or_more_note_identifiers_to_delete"),
    )
