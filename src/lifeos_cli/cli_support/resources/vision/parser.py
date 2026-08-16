"""Vision resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
)
from lifeos_cli.cli_support.resources.vision.parser_actions import (
    build_vision_add_experience_parser,
    build_vision_add_parser,
    build_vision_delete_parser,
    build_vision_harvest_parser,
    build_vision_list_parser,
    build_vision_show_parser,
    build_vision_stats_parser,
    build_vision_sync_experience_parser,
    build_vision_update_parser,
    build_vision_with_tasks_parser,
)
from lifeos_cli.i18n import cli_message as _


def build_vision_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the vision command tree."""
    vision_parser = add_documented_help_parser(
        subparsers,
        "vision",
        help_content=HelpContent(
            summary=_("resources.vision.parser.manage_visions"),
            description=(
                _(
                    "resources.vision.parser.create_and_maintain_high_level_containers_composed_of_one_or_more_task"
                )
                + "\n\n"
                + _(
                    "resources.vision.parser.a_vision_is_broader_than_single_task_and_usually_lives_under_area"
                )
            ),
            examples=(
                "lifeos vision add --help",
                "lifeos vision list --help",
                "lifeos vision batch --help",
            ),
            notes=(
                _("common.messages.use_list_as_primary_query_entrypoint_for_this_resource"),
                _("resources.vision.parser.visions_are_intended_to_group_related_task_trees"),
            ),
        ),
    )
    vision_subparsers = vision_parser.add_subparsers(
        dest="vision_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    build_vision_add_parser(vision_subparsers)
    build_vision_list_parser(vision_subparsers)
    build_vision_show_parser(vision_subparsers)
    build_vision_with_tasks_parser(vision_subparsers)
    build_vision_stats_parser(vision_subparsers)
    build_vision_update_parser(vision_subparsers)
    build_vision_add_experience_parser(vision_subparsers)
    build_vision_sync_experience_parser(vision_subparsers)
    build_vision_harvest_parser(vision_subparsers)
    build_vision_delete_parser(vision_subparsers)
