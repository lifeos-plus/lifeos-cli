"""Area resource parser construction."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.output_utils import format_summary_column_list
from lifeos_cli.cli_support.parser_common import (
    add_batch_delete_namespace,
    add_limit_offset_arguments,
)
from lifeos_cli.cli_support.resources.area.handlers import (
    AREA_SUMMARY_COLUMNS,
    handle_area_add_async,
    handle_area_batch_delete_async,
    handle_area_delete_async,
    handle_area_list_async,
    handle_area_show_async,
    handle_area_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_area_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the area command tree."""
    area_parser = add_documented_help_parser(
        subparsers,
        "area",
        help_content=HelpContent(
            summary=_("resources.area.parser.manage_life_areas"),
            description=(
                _(
                    "resources.area.parser.create_and_maintain_high_level_life_areas_such_as_work_health_or"
                )
                + "\n\n"
                + _(
                    "resources.area.parser.areas_provide_one_of_top_level_organizing_layers_for_rest_of_system"
                )
            ),
            examples=(
                "lifeos area add --help",
                "lifeos area list --help",
                "lifeos area batch --help",
            ),
            notes=(
                _("common.messages.use_list_as_primary_query_entrypoint_for_this_resource"),
                _(
                    "resources.area.parser.use_areas_to_group_visions_and_other_higher_level_planning_objects"
                ),
                _("resources.area.parser.see_lifeos_area_batch_help_for_bulk_delete_operations"),
            ),
        ),
    )
    area_subparsers = area_parser.add_subparsers(
        dest="area_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    add_parser = add_documented_parser(
        area_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.area.parser.create_area"),
            description=(
                _("resources.area.parser.create_new_area")
                + "\n\n"
                + _(
                    "resources.area.parser.areas_usually_represent_stable_parts_of_life_such_as_health_work_family"
                )
            ),
            examples=(
                'lifeos area add "Health"',
                'lifeos area add "Deep Work" --color "#2563EB" --icon brain --display-order 10',
                'lifeos area add "Travel" --inactive',
            ),
            notes=(
                _(
                    "resources.area.parser.use_inactive_when_area_should_exist_but_not_appear_as_active_yet"
                ),
            ),
        ),
    )
    add_parser.add_argument("name", help=_("resources.area.parser.area_name"))
    add_parser.add_argument(
        "--description", help=_("resources.area.parser.optional_area_description")
    )
    add_parser.add_argument(
        "--color", default="#3B82F6", help=_("resources.area.parser.hex_color_code")
    )
    add_parser.add_argument("--icon", help=_("resources.area.parser.optional_icon_identifier"))
    add_parser.add_argument(
        "--inactive",
        action="store_true",
        help=_("resources.area.parser.create_area_as_inactive"),
    )
    add_parser.add_argument(
        "--display-order", type=int, default=0, help=_("common.messages.display_order")
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_area_add_async))

    list_parser = add_documented_parser(
        area_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.area.parser.list_areas"),
            description=(
                _("resources.area.parser.list_areas_in_display_order")
                + "\n\n"
                + _(
                    "resources.area.parser.use_filters_and_pagination_flags_here_instead_of_expecting_separate_search_command"
                )
            ),
            examples=(
                "lifeos area list",
                "lifeos area list --include-inactive",
                "lifeos area list --limit 20 --offset 20",
            ),
            notes=(
                _(
                    "common.messages.when_results_exist_list_command_prints_header_row_followed_by_tab_separated"
                ).format(columns=format_summary_column_list(AREA_SUMMARY_COLUMNS)),
                _("resources.area.parser.use_limit_and_offset_together_for_pagination"),
            ),
        ),
    )
    list_parser.add_argument(
        "--include-inactive",
        action="store_true",
        help=_("resources.area.parser.include_inactive_areas"),
    )
    add_limit_offset_arguments(list_parser)
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_area_list_async))

    show_parser = add_documented_parser(
        area_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.area.parser.show_area"),
            description=(
                _("resources.area.parser.show_one_area_with_full_metadata")
                + "\n\n"
                + _(
                    "resources.area.parser.use_this_action_when_you_need_exact_field_values_instead_of_compact"
                )
            ),
            examples=("lifeos area show 11111111-1111-1111-1111-111111111111",),
        ),
    )
    show_parser.add_argument("area_id", type=UUID, help=_("resources.area.parser.area_identifier"))
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_area_show_async))

    update_parser = add_documented_parser(
        area_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.area.parser.update_area"),
            description=(
                _("resources.area.parser.update_mutable_area_fields")
                + "\n\n"
                + _(
                    "resources.area.parser.only_explicitly_provided_flags_are_changed_omitted_fields_stay_as_they_are"
                )
            ),
            examples=(
                'lifeos area update 11111111-1111-1111-1111-111111111111 --name "Fitness"',
                "lifeos area update 11111111-1111-1111-1111-111111111111 "
                "--display-order 20 --active",
                "lifeos area update 11111111-1111-1111-1111-111111111111 --clear-description",
                "lifeos area update 11111111-1111-1111-1111-111111111111 --clear-icon",
            ),
            notes=(
                _(
                    "resources.area.parser.use_clear_description_or_clear_icon_to_remove_optional_values"
                ),
            ),
        ),
    )
    update_parser.add_argument(
        "area_id", type=UUID, help=_("resources.area.parser.area_identifier")
    )
    update_parser.add_argument("--name", help=_("resources.area.parser.updated_area_name"))
    update_parser.add_argument("--description", help=_("common.messages.updated_description"))
    update_parser.add_argument(
        "--clear-description",
        action="store_true",
        help=_("resources.area.parser.clear_optional_area_description"),
    )
    update_parser.add_argument("--color", help=_("common.messages.updated_hex_color_code"))
    update_parser.add_argument("--icon", help=_("resources.area.parser.updated_icon_identifier"))
    update_parser.add_argument(
        "--clear-icon",
        action="store_true",
        help=_("resources.area.parser.clear_optional_icon_identifier"),
    )
    update_parser.add_argument(
        "--active",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=_("resources.area.parser.toggle_whether_area_is_active"),
    )
    update_parser.add_argument(
        "--display-order", type=int, help=_("common.messages.updated_display_order")
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_area_update_async))

    delete_parser = add_documented_parser(
        area_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.area.parser.delete_area"),
            description=_("resources.area.parser.delete_area_description"),
            examples=("lifeos area delete 11111111-1111-1111-1111-111111111111",),
        ),
    )
    delete_parser.add_argument(
        "area_id", type=UUID, help=_("resources.area.parser.area_identifier")
    )
    delete_parser.set_defaults(handler=make_sync_handler(handle_area_delete_async))

    add_batch_delete_namespace(
        area_subparsers,
        dest="area_batch_command",
        ids_dest="area_ids",
        noun="area",
        delete_handler=make_sync_handler(handle_area_batch_delete_async),
        batch_summary=_("resources.area.parser.run_batch_area_operations"),
        batch_description=_("resources.area.parser.delete_multiple_areas_in_one_command"),
        batch_examples=(
            "lifeos area batch delete --help",
            "lifeos area batch delete --ids <area-id-1> <area-id-2>",
        ),
        batch_notes=(
            _("common.messages.this_namespace_currently_exposes_only_delete_workflow"),
            _("common.messages.use_data_batch_delete_for_file_or_stream_bulk_workflows"),
        ),
        delete_summary=_("resources.area.parser.delete_multiple_areas"),
        delete_description=_("resources.area.parser.delete_multiple_areas_by_identifier"),
        delete_examples=("lifeos area batch delete --ids <area-id-1> <area-id-2>",),
    )
