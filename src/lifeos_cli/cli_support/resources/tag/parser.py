"""Tag resource parser construction."""

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
from lifeos_cli.cli_support.resources.tag.handlers import (
    TAG_SUMMARY_COLUMNS,
    handle_tag_add_async,
    handle_tag_batch_delete_async,
    handle_tag_delete_async,
    handle_tag_list_async,
    handle_tag_show_async,
    handle_tag_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_tag_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the tag command tree."""
    tag_parser = add_documented_help_parser(
        subparsers,
        "tag",
        help_content=HelpContent(
            summary=_("resources.tag.parser.manage_tags"),
            description=(
                _(
                    "resources.tag.parser.create_and_maintain_tags_for_notes_person_visions_tasks_and_areas"
                )
                + "\n\n"
                + _(
                    "resources.tag.parser.tags_provide_cross_cutting_classification_across_otherwise_separate_domains"
                )
            ),
            examples=(
                "lifeos tag add --help",
                "lifeos tag list --help",
                "lifeos tag batch --help",
            ),
            notes=(
                _("common.messages.use_list_as_primary_query_entrypoint_for_this_resource"),
                _("resources.tag.parser.a_tag_is_scoped_by_name_entity_type_and_category"),
                _("resources.tag.parser.see_lifeos_tag_batch_help_for_bulk_delete_operations"),
            ),
        ),
    )
    tag_subparsers = tag_parser.add_subparsers(
        dest="tag_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    add_parser = add_documented_parser(
        tag_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.tag.parser.create_tag"),
            description=(
                _("resources.tag.parser.create_new_tag")
                + "\n\n"
                + _(
                    "resources.tag.parser.tags_are_intended_for_structured_labeling_not_free_form_note_content"
                )
            ),
            examples=(
                'lifeos tag add "family" --entity-type person --category relation',
                'lifeos tag add "urgent" --entity-type task --color "#DC2626"',
                "lifeos tag add "
                '"coach" --entity-type vision --person-id '
                "11111111-1111-1111-1111-111111111111",
                "lifeos tag add "
                '"shared" --entity-type task --person-id '
                "11111111-1111-1111-1111-111111111111 "
                "--person-id 22222222-2222-2222-2222-222222222222",
            ),
            notes=(
                _(
                    "common.messages.repeat_same_person_id_flag_to_associate_multiple_person_in_one_command"
                ),
            ),
        ),
    )
    add_parser.add_argument("name", help=_("resources.tag.parser.tag_name"))
    add_parser.add_argument(
        "--entity-type", required=True, help=_("resources.tag.parser.target_entity_type")
    )
    add_parser.add_argument(
        "--category", default="general", help=_("resources.tag.parser.tag_category")
    )
    add_parser.add_argument(
        "--description", help=_("resources.tag.parser.optional_tag_description")
    )
    add_parser.add_argument("--color", help=_("resources.tag.parser.optional_hex_color_code"))
    add_parser.add_argument(
        "--person-id",
        dest="person_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_associate_one_or_more_person"),
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_tag_add_async))

    list_parser = add_documented_parser(
        tag_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.tag.parser.list_tags"),
            description=(
                _("resources.tag.parser.list_tags_with_optional_filters")
                + "\n\n"
                + _(
                    "resources.tag.parser.use_entity_type_and_category_to_narrow_result_set_before_inspecting_one"
                )
            ),
            examples=(
                "lifeos tag list",
                "lifeos tag list --entity-type person",
                "lifeos tag list --person-id 11111111-1111-1111-1111-111111111111",
                "lifeos tag list --entity-type task --category priority --limit 20",
            ),
            notes=(
                _(
                    "common.messages.when_results_exist_list_command_prints_header_row_followed_by_tab_separated"
                ).format(columns=format_summary_column_list(TAG_SUMMARY_COLUMNS)),
            ),
        ),
    )
    list_parser.add_argument("--entity-type", help=_("resources.tag.parser.filter_by_entity_type"))
    list_parser.add_argument("--category", help=_("resources.tag.parser.filter_by_category"))
    list_parser.add_argument(
        "--person-id", type=UUID, help=_("common.messages.filter_by_linked_person_identifier")
    )
    add_limit_offset_arguments(list_parser)
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_tag_list_async))

    show_parser = add_documented_parser(
        tag_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.tag.parser.show_tag"),
            description=_("resources.tag.parser.show_one_tag_with_full_metadata"),
            examples=("lifeos tag show 11111111-1111-1111-1111-111111111111",),
        ),
    )
    show_parser.add_argument("tag_id", type=UUID, help=_("resources.tag.parser.tag_identifier"))
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_tag_show_async))

    update_parser = add_documented_parser(
        tag_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.tag.parser.update_tag"),
            description=(
                _("resources.tag.parser.update_mutable_tag_fields")
                + "\n\n"
                + _(
                    "common.messages.only_explicitly_provided_flags_are_changed_omitted_values_are_preserved"
                )
            ),
            examples=(
                'lifeos tag update 11111111-1111-1111-1111-111111111111 --name "urgent"',
                "lifeos tag update 11111111-1111-1111-1111-111111111111 "
                "--person-id 11111111-1111-1111-1111-111111111111",
                "lifeos tag update 11111111-1111-1111-1111-111111111111 "
                "--person-id 11111111-1111-1111-1111-111111111111 "
                "--person-id 22222222-2222-2222-2222-222222222222",
                "lifeos tag update 11111111-1111-1111-1111-111111111111 "
                "--clear-description --clear-person",
                "lifeos tag update 11111111-1111-1111-1111-111111111111 --clear-color",
            ),
            notes=(
                _(
                    "resources.tag.parser.use_clear_description_clear_color_or_clear_person_to_remove_optional_values"
                ),
                _("common.messages.repeat_same_person_id_flag_to_replace_multiple_linked_person"),
            ),
        ),
    )
    update_parser.add_argument("tag_id", type=UUID, help=_("resources.tag.parser.tag_identifier"))
    update_parser.add_argument("--name", help=_("resources.tag.parser.updated_tag_name"))
    update_parser.add_argument("--entity-type", help=_("resources.tag.parser.updated_entity_type"))
    update_parser.add_argument("--category", help=_("resources.tag.parser.updated_tag_category"))
    update_parser.add_argument(
        "--description", help=_("resources.tag.parser.updated_tag_description")
    )
    update_parser.add_argument(
        "--clear-description",
        action="store_true",
        help=_("resources.tag.parser.clear_optional_tag_description"),
    )
    update_parser.add_argument("--color", help=_("common.messages.updated_hex_color_code"))
    update_parser.add_argument(
        "--clear-color",
        action="store_true",
        help=_("resources.tag.parser.clear_optional_tag_color"),
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
    update_parser.set_defaults(handler=make_sync_handler(handle_tag_update_async))

    delete_parser = add_documented_parser(
        tag_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.tag.parser.delete_tag"),
            description=_("resources.tag.parser.delete_tag_description"),
            examples=("lifeos tag delete 11111111-1111-1111-1111-111111111111",),
        ),
    )
    delete_parser.add_argument("tag_id", type=UUID, help=_("resources.tag.parser.tag_identifier"))
    delete_parser.set_defaults(handler=make_sync_handler(handle_tag_delete_async))

    add_batch_delete_namespace(
        tag_subparsers,
        dest="tag_batch_command",
        ids_dest="tag_ids",
        noun="tag",
        delete_handler=make_sync_handler(handle_tag_batch_delete_async),
        batch_summary=_("resources.tag.parser.run_batch_tag_operations"),
        batch_description=_("resources.tag.parser.delete_multiple_tags_in_one_command"),
        batch_examples=(
            "lifeos tag batch delete --help",
            "lifeos tag batch delete --ids <tag-id-1> <tag-id-2>",
        ),
        batch_notes=(
            _("common.messages.this_namespace_currently_exposes_only_delete_workflow"),
            _("common.messages.use_data_batch_delete_for_file_or_stream_bulk_workflows"),
        ),
        delete_summary=_("resources.tag.parser.delete_multiple_tags"),
        delete_description=_("resources.tag.parser.delete_multiple_tags_by_identifier"),
        delete_examples=("lifeos tag batch delete --ids <tag-id-1> <tag-id-2>",),
    )
