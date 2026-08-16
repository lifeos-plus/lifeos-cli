"""Builder helpers for batch timelog actions."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_parser,
)
from lifeos_cli.cli_support.parser_common import (
    add_batch_namespace,
    add_identifier_list_argument,
)
from lifeos_cli.cli_support.resources.timelog.handlers import (
    handle_timelog_batch_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_timelog_batch_parser(
    timelog_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the timelog batch command tree."""
    batch_subparsers = add_batch_namespace(
        timelog_subparsers,
        dest="timelog_batch_command",
        batch_summary=_("resources.timelog.parser_batch.run_batch_timelog_operations"),
        batch_description=_(
            "resources.timelog.parser_batch.run_bulk_update_operations_for_timelogs"
        ),
        batch_examples=("lifeos timelog batch update --help",),
        batch_notes=(
            _(
                "resources.timelog.parser_batch.use_update_to_edit_mutable_fields_across_active_timelogs"
            ),
        ),
    )

    batch_update_parser = add_documented_parser(
        batch_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.timelog.parser_batch.update_multiple_timelogs"),
            description=_(
                "resources.timelog.parser_batch.update_mutable_fields_across_multiple_active_timelogs"
            ),
            examples=(
                "lifeos timelog batch update --ids <timelog-id-1> <timelog-id-2> --clear-task",
                "lifeos timelog batch update --ids <timelog-id-1> <timelog-id-2> "
                '--find-title-text "deep" --replace-title-text "focused"',
                "lifeos timelog batch update --ids <timelog-id-1> "
                "--person-id <person-id-1> --person-id <person-id-2> "
                "--tag-id <tag-id-1> --tag-id <tag-id-2>",
            ),
            notes=(
                _(
                    "resources.timelog.parser_batch.repeat_same_tag_id_or_person_id_flag_to_replace_multiple_linked"
                ),
                _("resources.timelog.parser_batch.use_clear_flags_to_remove_optional_links"),
            ),
        ),
    )
    add_identifier_list_argument(
        batch_update_parser,
        dest="timelog_ids",
        noun="timelog",
        action_verb="update",
    )
    batch_update_parser.add_argument(
        "--title", help=_("resources.timelog.parser_batch.replace_full_title")
    )
    batch_update_parser.add_argument(
        "--find-title-text", help=_("resources.timelog.parser_batch.title_text_to_find")
    )
    batch_update_parser.add_argument(
        "--replace-title-text",
        help=_("resources.timelog.parser_batch.replacement_text_for_title_matches"),
    )
    batch_update_parser.add_argument(
        "--area-id", type=UUID, help=_("resources.timelog.parser_batch.replace_linked_area")
    )
    batch_update_parser.add_argument(
        "--clear-area", action="store_true", help=_("common.messages.clear_linked_area")
    )
    batch_update_parser.add_argument(
        "--task-id", type=UUID, help=_("resources.timelog.parser_batch.replace_linked_task")
    )
    batch_update_parser.add_argument(
        "--clear-task", action="store_true", help=_("common.messages.clear_linked_task")
    )
    batch_update_parser.add_argument(
        "--tag-id",
        dest="tag_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_replace_tags_with_one_or_more_identifiers"),
    )
    batch_update_parser.add_argument(
        "--clear-tags", action="store_true", help=_("common.messages.remove_all_tags")
    )
    batch_update_parser.add_argument(
        "--person-id",
        dest="person_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_replace_person_with_one_or_more_identifiers"),
    )
    batch_update_parser.add_argument(
        "--clear-person",
        action="store_true",
        help=_("common.messages.remove_all_person"),
    )
    batch_update_parser.set_defaults(handler=make_sync_handler(handle_timelog_batch_update_async))
