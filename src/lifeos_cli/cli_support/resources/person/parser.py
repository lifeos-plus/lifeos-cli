"""People resource parser construction."""

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
from lifeos_cli.cli_support.resources.person.handlers import (
    PERSON_SUMMARY_COLUMNS,
    handle_person_add_async,
    handle_person_batch_delete_async,
    handle_person_delete_async,
    handle_person_list_async,
    handle_person_show_async,
    handle_person_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_person_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the person command tree."""
    person_parser = add_documented_help_parser(
        subparsers,
        "person",
        help_content=HelpContent(
            summary=_("resources.person.parser.manage_person_and_relationships"),
            description=(
                _(
                    "resources.person.parser.create_and_maintain_person_records_for_your_social_context"
                )
                + "\n\n"
                + _(
                    "resources.person.parser.this_resource_is_for_named_person_relationship_context_and_explicit_execution_subjects"
                )
                + "\n\n"
                + _(
                    "resources.person.parser.use_it_for_human_partner_and_when_useful_named_automation_identity_so"
                )
            ),
            examples=(
                "lifeos person add --help",
                "lifeos person list --help",
                "lifeos person batch --help",
            ),
            notes=(
                _(
                    "resources.person.parser.person_is_intentional_cli_resource_name_for_this_domain"
                ),
                _("common.messages.use_list_as_primary_query_entrypoint_for_this_resource"),
                _(
                    "resources.person.parser.see_lifeos_person_batch_help_for_bulk_delete_operations"
                ),
                _(
                    "resources.person.parser.agent_callers_should_keep_human_partner_and_automation_identity_as_separate_records"
                ),
            ),
        ),
    )
    person_subparsers = person_parser.add_subparsers(
        dest="person_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    add_parser = add_documented_parser(
        person_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.person.parser.create_person"),
            description=(
                _("resources.person.parser.create_new_person")
                + "\n\n"
                + _(
                    "resources.person.parser.use_tags_nicknames_and_location_to_capture_relationship_context_or_execution_subject"
                )
            ),
            examples=(
                'lifeos person add "Human Partner" --nickname ally --location Toronto',
                'lifeos person add "Local Agent" '
                '--description "Automation identity for CLI workflows"',
            ),
            notes=(
                _(
                    "resources.person.parser.create_separate_records_when_human_and_agent_should_remain_distinct_subjects_in"
                ),
            ),
        ),
    )
    add_parser.add_argument("name", help=_("resources.person.parser.person_name"))
    add_parser.add_argument(
        "--description", help=_("resources.person.parser.optional_person_description")
    )
    add_parser.add_argument(
        "--nickname",
        action="append",
        help=_("resources.person.parser.nickname_or_alias_repeatable"),
    )
    add_parser.add_argument(
        "--birth-date", help=_("resources.person.parser.birth_date_in_iso_format_yyyy_mm_dd")
    )
    add_parser.add_argument("--location", help=_("resources.person.parser.location_label"))
    add_parser.add_argument(
        "--tag-id",
        action="append",
        type=UUID,
        help=_("resources.person.parser.tag_identifier_repeatable"),
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_person_add_async))

    list_parser = add_documented_parser(
        person_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.person.parser.list_person"),
            description=(
                _("resources.person.parser.list_person_with_optional_search_or_tag_filters")
                + "\n\n"
                + _(
                    "resources.person.parser.use_this_as_primary_query_entrypoint_for_person_rather_than_expecting_separate"
                )
            ),
            examples=(
                "lifeos person list",
                "lifeos person list --search ali",
                "lifeos person list --tag-id 11111111-1111-1111-1111-111111111111 --limit 20",
            ),
            notes=(
                _("resources.person.parser.search_currently_matches_name_nicknames_and_location"),
                _(
                    "common.messages.when_results_exist_list_command_prints_header_row_followed_by_tab_separated"
                ).format(columns=format_summary_column_list(PERSON_SUMMARY_COLUMNS)),
            ),
        ),
    )
    list_parser.add_argument(
        "--search", help=_("resources.person.parser.search_by_name_nickname_or_location")
    )
    list_parser.add_argument(
        "--tag-id", type=UUID, help=_("resources.person.parser.filter_by_tag_identifier")
    )
    add_limit_offset_arguments(list_parser)
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_person_list_async))

    show_parser = add_documented_parser(
        person_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.person.parser.show_person"),
            description=_("resources.person.parser.show_one_person_with_full_metadata"),
            examples=(
                "lifeos person show 11111111-1111-1111-1111-111111111111",
                "lifeos person show 11111111-1111-1111-1111-111111111111",
            ),
        ),
    )
    show_parser.add_argument(
        "person_id", type=UUID, help=_("resources.person.parser.person_identifier")
    )
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_person_show_async))

    update_parser = add_documented_parser(
        person_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.person.parser.update_person"),
            description=(
                _("resources.person.parser.update_mutable_person_fields")
                + "\n\n"
                + _(
                    "resources.person.parser.only_explicitly_supplied_flags_are_changed_omitted_fields_are_preserved"
                )
            ),
            examples=(
                'lifeos person update 11111111-1111-1111-1111-111111111111 --location "New York"',
                "lifeos person update 11111111-1111-1111-1111-111111111111 --tag-id "
                "22222222-2222-2222-2222-222222222222",
                "lifeos person update 11111111-1111-1111-1111-111111111111 "
                "--clear-nicknames --clear-tags",
                "lifeos person update 11111111-1111-1111-1111-111111111111 --clear-location",
            ),
            notes=(
                _(
                    "resources.person.parser.use_clear_flags_to_remove_optional_values_instead_of_replacing_them"
                ),
            ),
        ),
    )
    update_parser.add_argument(
        "person_id", type=UUID, help=_("resources.person.parser.person_identifier")
    )
    update_parser.add_argument("--name", help=_("resources.person.parser.updated_person_name"))
    update_parser.add_argument("--description", help=_("common.messages.updated_description"))
    update_parser.add_argument(
        "--clear-description",
        action="store_true",
        help=_("resources.person.parser.clear_optional_person_description"),
    )
    update_parser.add_argument(
        "--nickname",
        action="append",
        help=_("resources.person.parser.updated_nicknames_repeatable"),
    )
    update_parser.add_argument(
        "--clear-nicknames",
        action="store_true",
        help=_("resources.person.parser.clear_all_nicknames"),
    )
    update_parser.add_argument(
        "--birth-date",
        help=_("resources.person.parser.updated_birth_date_in_iso_format_yyyy_mm_dd"),
    )
    update_parser.add_argument(
        "--clear-birth-date",
        action="store_true",
        help=_("resources.person.parser.clear_optional_birth_date"),
    )
    update_parser.add_argument("--location", help=_("common.messages.updated_location"))
    update_parser.add_argument(
        "--clear-location",
        action="store_true",
        help=_("resources.person.parser.clear_optional_location"),
    )
    update_parser.add_argument(
        "--tag-id",
        action="append",
        type=UUID,
        help=_("resources.person.parser.replacement_tag_identifiers"),
    )
    update_parser.add_argument(
        "--clear-tags",
        action="store_true",
        help=_("resources.person.parser.remove_all_tag_associations_from_person"),
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_person_update_async))

    delete_parser = add_documented_parser(
        person_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.person.parser.delete_person"),
            description=_("resources.person.parser.delete_person_description"),
            examples=("lifeos person delete 11111111-1111-1111-1111-111111111111",),
        ),
    )
    delete_parser.add_argument(
        "person_id", type=UUID, help=_("resources.person.parser.person_identifier")
    )
    delete_parser.set_defaults(handler=make_sync_handler(handle_person_delete_async))

    add_batch_delete_namespace(
        person_subparsers,
        dest="person_batch_command",
        ids_dest="person_ids",
        noun="person",
        delete_handler=make_sync_handler(handle_person_batch_delete_async),
        batch_summary=_("resources.person.parser.run_batch_person_operations"),
        batch_description=_(
            "resources.person.parser.delete_multiple_person_records_in_one_command"
        ),
        batch_examples=(
            "lifeos person batch delete --help",
            "lifeos person batch delete --ids <person-id-1> <person-id-2>",
        ),
        batch_notes=(
            _("common.messages.this_namespace_currently_exposes_only_delete_workflow"),
            _("common.messages.use_data_batch_delete_for_file_or_stream_bulk_workflows"),
        ),
        delete_summary=_("resources.person.parser.delete_multiple_person"),
        delete_description=_("resources.person.parser.delete_multiple_person_by_identifier"),
        delete_examples=("lifeos person batch delete --ids <person-id-1> <person-id-2>",),
    )
