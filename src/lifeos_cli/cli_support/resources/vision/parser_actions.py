"""Builder helpers for core vision commands."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_parser,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.output_utils import format_summary_column_list
from lifeos_cli.cli_support.parser_common import (
    add_batch_delete_namespace,
    add_limit_offset_arguments,
)
from lifeos_cli.cli_support.resources.vision.handlers import (
    VISION_SUMMARY_COLUMNS,
    VISION_WITH_TASKS_COLUMNS,
    handle_vision_add_async,
    handle_vision_add_experience_async,
    handle_vision_batch_delete_async,
    handle_vision_delete_async,
    handle_vision_harvest_async,
    handle_vision_list_async,
    handle_vision_show_async,
    handle_vision_stats_async,
    handle_vision_sync_experience_async,
    handle_vision_update_async,
    handle_vision_with_tasks_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_vision_add_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision add command."""
    add_parser = add_documented_parser(
        vision_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.vision.parser_actions.create_vision"),
            description=(
                _("resources.vision.parser_actions.create_new_vision")
                + "\n\n"
                + _(
                    "resources.vision.parser_actions.visions_usually_represent_medium_or_long_running_themes_that_will_own_multiple"
                )
            ),
            examples=(
                'lifeos vision add "Launch lifeos-cli" '
                "--area-id 11111111-1111-1111-1111-111111111111",
                'lifeos vision add "Improve sleep quality" --status active',
                'lifeos vision add "Strengthen family rhythm" '
                "--person-id 11111111-1111-1111-1111-111111111111",
                'lifeos vision add "Shared parenting rhythm" '
                "--person-id 11111111-1111-1111-1111-111111111111 "
                "--person-id 22222222-2222-2222-2222-222222222222",
            ),
            notes=(
                _(
                    "common.messages.repeat_same_person_id_flag_to_associate_multiple_people_in_one_command"
                ),
            ),
        ),
    )
    add_parser.add_argument("name", help=_("resources.vision.parser_actions.vision_name"))
    add_parser.add_argument(
        "--description", help=_("resources.vision.parser_actions.optional_vision_description")
    )
    add_parser.add_argument(
        "--status", default="active", help=_("resources.vision.parser_actions.vision_status")
    )
    add_parser.add_argument(
        "--area-id", type=UUID, help=_("resources.vision.parser_actions.owning_area_identifier")
    )
    add_parser.add_argument(
        "--person-id",
        dest="person_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_associate_one_or_more_people"),
    )
    add_parser.add_argument(
        "--experience-rate-per-hour",
        type=int,
        help=_("resources.vision.parser_actions.optional_experience_rate"),
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_vision_add_async))


def build_vision_list_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision list command."""
    list_parser = add_documented_parser(
        vision_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.vision.parser_actions.list_visions"),
            description=(
                _(
                    "resources.vision.parser_actions.list_visions_with_optional_status_or_area_filters"
                )
                + "\n\n"
                + _(
                    "resources.vision.parser_actions.use_this_as_primary_query_entrypoint_for_visions"
                )
            ),
            examples=(
                "lifeos vision list",
                "lifeos vision list --status active",
                "lifeos vision list --person-id 11111111-1111-1111-1111-111111111111",
                "lifeos vision list --area-id 11111111-1111-1111-1111-111111111111 --limit 20",
            ),
            notes=(
                _(
                    "common.messages.when_results_exist_list_command_prints_header_row_followed_by_tab_separated"
                ).format(columns=format_summary_column_list(VISION_SUMMARY_COLUMNS)),
            ),
        ),
    )
    list_parser.add_argument("--status", help=_("resources.vision.parser_actions.filter_by_status"))
    list_parser.add_argument(
        "--area-id", type=UUID, help=_("resources.vision.parser_actions.filter_by_area_identifier")
    )
    list_parser.add_argument(
        "--person-id", type=UUID, help=_("common.messages.filter_by_linked_person_identifier")
    )
    add_limit_offset_arguments(list_parser)
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_vision_list_async))


def build_vision_show_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision show command."""
    show_parser = add_documented_parser(
        vision_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.vision.parser_actions.show_vision"),
            description=_("resources.vision.parser_actions.show_one_vision_with_full_metadata"),
            examples=(
                "lifeos vision show 11111111-1111-1111-1111-111111111111",
                "lifeos vision show 11111111-1111-1111-1111-111111111111",
            ),
        ),
    )
    show_parser.add_argument("vision_id", type=UUID, help=_("common.messages.vision_identifier"))
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_vision_show_async))


def build_vision_update_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision update command."""
    update_parser = add_documented_parser(
        vision_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.vision.parser_actions.update_vision"),
            description=(
                _("resources.vision.parser_actions.update_mutable_vision_fields")
                + "\n\n"
                + _(
                    "common.messages.only_explicitly_provided_flags_are_changed_omitted_values_are_preserved"
                )
            ),
            examples=(
                "lifeos vision update 11111111-1111-1111-1111-111111111111 "
                '--name "Ship lifeos-cli"',
                "lifeos vision update 11111111-1111-1111-1111-111111111111 --status archived",
                "lifeos vision update 11111111-1111-1111-1111-111111111111 "
                "--person-id 11111111-1111-1111-1111-111111111111",
                "lifeos vision update 11111111-1111-1111-1111-111111111111 "
                "--person-id 11111111-1111-1111-1111-111111111111 "
                "--person-id 22222222-2222-2222-2222-222222222222",
                "lifeos vision update 11111111-1111-1111-1111-111111111111 "
                "--clear-description --clear-experience-rate",
                "lifeos vision update 11111111-1111-1111-1111-111111111111 --clear-area",
            ),
            notes=(
                _(
                    "resources.vision.parser_actions.valid_statuses_currently_include_active_archived_and_fruit"
                ),
                _(
                    "resources.vision.parser_actions.use_clear_flags_to_remove_optional_values_including_people"
                ),
                _("common.messages.repeat_same_person_id_flag_to_replace_multiple_linked_people"),
            ),
        ),
    )
    update_parser.add_argument("vision_id", type=UUID, help=_("common.messages.vision_identifier"))
    update_parser.add_argument(
        "--name", help=_("resources.vision.parser_actions.updated_vision_name")
    )
    update_parser.add_argument(
        "--description", help=_("resources.vision.parser_actions.updated_vision_description")
    )
    update_parser.add_argument(
        "--clear-description",
        action="store_true",
        help=_("resources.vision.parser_actions.clear_optional_vision_description"),
    )
    update_parser.add_argument("--status", help=_("resources.vision.parser_actions.updated_status"))
    update_parser.add_argument(
        "--area-id", type=UUID, help=_("resources.vision.parser_actions.updated_area_identifier")
    )
    update_parser.add_argument(
        "--clear-area",
        action="store_true",
        help=_("resources.vision.parser_actions.clear_optional_area_reference"),
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
    update_parser.add_argument(
        "--experience-rate-per-hour",
        type=int,
        help=_("resources.vision.parser_actions.updated_experience_rate"),
    )
    update_parser.add_argument(
        "--clear-experience-rate",
        action="store_true",
        help=_("resources.vision.parser_actions.clear_optional_experience_rate"),
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_vision_update_async))


def build_vision_delete_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision delete command."""
    delete_parser = add_documented_parser(
        vision_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.vision.parser_actions.delete_vision_summary"),
            description=_("resources.vision.parser_actions.delete_vision"),
            examples=("lifeos vision delete 11111111-1111-1111-1111-111111111111",),
        ),
    )
    delete_parser.add_argument("vision_id", type=UUID, help=_("common.messages.vision_identifier"))
    delete_parser.set_defaults(handler=make_sync_handler(handle_vision_delete_async))


def build_vision_with_tasks_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision with-tasks command."""
    with_tasks_parser = add_documented_parser(
        vision_subparsers,
        "with-tasks",
        help_content=HelpContent(
            summary=_("resources.vision.parser_actions.show_vision_task_tree"),
            description=_("resources.vision.parser_actions.show_one_vision_with_its_active_tasks"),
            examples=("lifeos vision with-tasks 11111111-1111-1111-1111-111111111111",),
            notes=(
                _(
                    "resources.vision.parser_actions.when_vision_has_tasks_tasks_section_prints_header_row_followed_by_tab"
                ).format(columns=format_summary_column_list(VISION_WITH_TASKS_COLUMNS)),
                _("resources.vision.parser_actions.with_tasks_related_views_note"),
            ),
        ),
    )
    with_tasks_parser.add_argument(
        "vision_id", type=UUID, help=_("common.messages.vision_identifier")
    )
    with_tasks_parser.set_defaults(handler=make_sync_handler(handle_vision_with_tasks_async))


def build_vision_stats_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision stats command."""
    stats_parser = add_documented_parser(
        vision_subparsers,
        "stats",
        help_content=HelpContent(
            summary=_("resources.vision.parser_actions.show_vision_stats"),
            description=_(
                "resources.vision.parser_actions.show_task_counts_and_effort_totals_for_one_vision"
            ),
            examples=("lifeos vision stats 11111111-1111-1111-1111-111111111111",),
            notes=(
                _(
                    "resources.vision.parser_actions.counts_and_effort_totals_aggregate_all_active_tasks_linked_to_vision"
                ),
                _(
                    "resources.vision.parser_actions.use_with_tasks_when_you_need_row_level_task_list_instead_of"
                ),
            ),
        ),
    )
    stats_parser.add_argument("vision_id", type=UUID, help=_("common.messages.vision_identifier"))
    stats_parser.set_defaults(handler=make_sync_handler(handle_vision_stats_async))


def build_vision_add_experience_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision add-experience command."""
    add_experience_parser = add_documented_parser(
        vision_subparsers,
        "add-experience",
        help_content=HelpContent(
            summary=_("resources.vision.parser_actions.add_vision_experience"),
            description=_(
                "resources.vision.parser_actions.add_manual_experience_points_to_active_vision"
            ),
            examples=(
                "lifeos vision add-experience 11111111-1111-1111-1111-111111111111 --points 120",
            ),
            notes=(
                _(
                    "resources.vision.parser_actions.use_this_for_explicit_manual_credit_rather_than_for_task_effort_recalculation"
                ),
                _(
                    "resources.vision.parser_actions.use_sync_experience_when_experience_should_be_recomputed_from_task_effort"
                ),
            ),
        ),
    )
    add_experience_parser.add_argument(
        "vision_id", type=UUID, help=_("common.messages.vision_identifier")
    )
    add_experience_parser.add_argument(
        "--points",
        dest="experience_points",
        type=int,
        required=True,
        help=_("resources.vision.parser_actions.experience_points_to_add"),
    )
    add_experience_parser.set_defaults(
        handler=make_sync_handler(handle_vision_add_experience_async)
    )


def build_vision_sync_experience_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision sync-experience command."""
    sync_experience_parser = add_documented_parser(
        vision_subparsers,
        "sync-experience",
        help_content=HelpContent(
            summary=_("resources.vision.parser_actions.sync_vision_experience"),
            description=_(
                "resources.vision.parser_actions.synchronize_experience_points_from_root_task_actual_effort_totals"
            ),
            examples=("lifeos vision sync-experience 11111111-1111-1111-1111-111111111111",),
            notes=(
                _(
                    "resources.vision.parser_actions.use_this_after_task_effort_changes_when_vision_experience_should_match_current"
                ),
                _(
                    "resources.vision.parser_actions.the_effective_hourly_rate_comes_from_vision_override_when_set_otherwise_from"
                ),
            ),
        ),
    )
    sync_experience_parser.add_argument(
        "vision_id", type=UUID, help=_("common.messages.vision_identifier")
    )
    sync_experience_parser.set_defaults(
        handler=make_sync_handler(handle_vision_sync_experience_async)
    )


def build_vision_harvest_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision harvest command."""
    harvest_parser = add_documented_parser(
        vision_subparsers,
        "harvest",
        help_content=HelpContent(
            summary=_("resources.vision.parser_actions.harvest_vision"),
            description=_(
                "resources.vision.parser_actions.convert_mature_active_vision_to_fruit_status"
            ),
            examples=("lifeos vision harvest 11111111-1111-1111-1111-111111111111",),
            notes=(
                _(
                    "resources.vision.parser_actions.this_command_succeeds_only_when_vision_is_active_and_already_at_final"
                ),
                _(
                    "resources.vision.parser_actions.a_successful_harvest_changes_vision_status_from_active_to_fruit"
                ),
            ),
        ),
    )
    harvest_parser.add_argument("vision_id", type=UUID, help=_("common.messages.vision_identifier"))
    harvest_parser.set_defaults(handler=make_sync_handler(handle_vision_harvest_async))


def build_vision_batch_parser(
    vision_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the vision batch command tree."""
    add_batch_delete_namespace(
        vision_subparsers,
        dest="vision_batch_command",
        ids_dest="vision_ids",
        noun="vision",
        delete_handler=make_sync_handler(handle_vision_batch_delete_async),
        batch_summary=_("resources.vision.parser_actions.run_batch_vision_operations"),
        batch_description=_(
            "resources.vision.parser_actions.delete_multiple_visions_in_one_command"
        ),
        batch_examples=(
            "lifeos vision batch delete --help",
            "lifeos vision batch delete --ids <vision-id-1> <vision-id-2>",
        ),
        batch_notes=(
            _("common.messages.this_namespace_currently_exposes_only_delete_workflow"),
            _("common.messages.use_data_batch_delete_for_file_or_stream_bulk_workflows"),
        ),
        delete_summary=_("resources.vision.parser_actions.delete_multiple_visions"),
        delete_description=_(
            "resources.vision.parser_actions.delete_multiple_visions_by_identifier"
        ),
        delete_examples=("lifeos vision batch delete --ids <vision-id-1> <vision-id-2>",),
    )
