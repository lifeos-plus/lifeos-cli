"""Finance resource parser construction."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.parser_common import (
    add_limit_offset_arguments,
)
from lifeos_cli.cli_support.resources.finance.handlers import (
    handle_finance_asset_add_async,
    handle_finance_asset_delete_async,
    handle_finance_asset_list_async,
    handle_finance_asset_update_async,
    handle_finance_node_add_async,
    handle_finance_node_delete_async,
    handle_finance_node_update_async,
    handle_finance_rate_snapshot_add_async,
    handle_finance_rate_snapshot_list_async,
    handle_finance_rate_snapshot_show_async,
    handle_finance_snapshot_add_async,
    handle_finance_snapshot_list_async,
    handle_finance_snapshot_show_async,
    handle_finance_tree_add_async,
    handle_finance_tree_ensure_default_async,
    handle_finance_tree_list_async,
    handle_finance_tree_show_async,
    parse_rate_snapshot_entry,
    parse_snapshot_entry,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.cli_support.time_args import parse_user_datetime_value
from lifeos_cli.i18n import cli_message as _


def build_finance_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the finance command tree."""
    finance_parser = add_documented_help_parser(
        subparsers,
        "finance",
        help_content=HelpContent(
            summary=_("resources.finance.parser.manage_unified_finance_trees_and_snapshots"),
            description=(_("resources.finance.parser.create_finance_trees_nodes_and_snapshots")),
            examples=(
                "lifeos finance asset-list",
                "lifeos finance tree-add --help",
                "lifeos finance node-add --help",
                "lifeos finance rate-snapshot-add --help",
                "lifeos finance snapshot-add --help",
            ),
            notes=(
                _("resources.finance.parser.instant_snapshots_appear_in_balance_sheet_view"),
                _("resources.finance.parser.period_snapshots_appear_in_cashflow_view"),
            ),
        ),
    )
    finance_subparsers = finance_parser.add_subparsers(
        dest="finance_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    asset_list = add_documented_parser(
        finance_subparsers,
        "asset-list",
        help_content=HelpContent(
            summary=_("resources.finance.parser.list_finance_assets"),
            description=_(
                "resources.finance.parser.list_active_finance_assets_and_their_precision"
            ),
            examples=("lifeos finance asset-list",),
        ),
    )
    add_limit_offset_arguments(asset_list)
    add_json_output_argument(asset_list)
    asset_list.set_defaults(handler=make_sync_handler(handle_finance_asset_list_async))

    asset_add = add_documented_parser(
        finance_subparsers,
        "asset-add",
        help_content=HelpContent(
            summary=_("resources.finance.parser.create_finance_asset"),
            description=(_("resources.finance.parser.create_selectable_asset_code")),
            examples=(
                'lifeos finance asset-add BTC --name "Bitcoin" --decimal-places 8',
                'lifeos finance asset-add CNY --name "Chinese Yuan"',
            ),
        ),
    )
    asset_add.add_argument("code")
    asset_add.add_argument("--name")
    asset_add.add_argument("--decimal-places", type=int, default=2)
    asset_add.add_argument("--display-order", type=int, default=1000)
    asset_add.set_defaults(handler=make_sync_handler(handle_finance_asset_add_async))

    asset_update = add_documented_parser(
        finance_subparsers,
        "asset-update",
        help_content=HelpContent(
            summary=_("resources.finance.parser.update_finance_asset"),
            description=_("resources.finance.parser.update_mutable_finance_asset_fields"),
            examples=("lifeos finance asset-update <asset-id> --decimal-places 8",),
        ),
    )
    asset_update.add_argument("asset_id", type=UUID)
    asset_update.add_argument("--code")
    asset_update.add_argument("--name")
    asset_update.add_argument("--decimal-places", type=int)
    asset_update.add_argument("--display-order", type=int)
    asset_update.set_defaults(handler=make_sync_handler(handle_finance_asset_update_async))

    asset_delete = add_documented_parser(
        finance_subparsers,
        "asset-delete",
        help_content=HelpContent(
            summary=_("resources.finance.parser.delete_finance_asset"),
            description=_("resources.finance.parser.soft_delete_finance_asset"),
            examples=("lifeos finance asset-delete 11111111-1111-1111-1111-111111111111",),
        ),
    )
    asset_delete.add_argument("asset_id", type=UUID)
    asset_delete.set_defaults(handler=make_sync_handler(handle_finance_asset_delete_async))

    tree_add = add_documented_parser(
        finance_subparsers,
        "tree-add",
        help_content=HelpContent(
            summary=_("resources.finance.parser.create_finance_tree"),
            description=_("resources.finance.parser.create_reusable_finance_tree"),
            examples=(
                'lifeos finance tree-add "Personal Finance" --primary-currency USD',
                'lifeos finance tree-add "Investments" --primary-currency BTC --default',
            ),
        ),
    )
    tree_add.add_argument("name")
    tree_add.add_argument("--primary-currency", default="USD")
    tree_add.add_argument("--display-order", type=int, default=0)
    tree_add.add_argument("--default", action="store_true")
    tree_add.set_defaults(handler=make_sync_handler(handle_finance_tree_add_async))

    tree_list = add_documented_parser(
        finance_subparsers,
        "tree-list",
        help_content=HelpContent(
            summary=_("resources.finance.parser.list_finance_trees"),
            description=_("resources.finance.parser.list_active_finance_trees"),
            examples=("lifeos finance tree-list",),
        ),
    )
    add_limit_offset_arguments(tree_list)
    add_json_output_argument(tree_list)
    tree_list.set_defaults(handler=make_sync_handler(handle_finance_tree_list_async))

    tree_show = add_documented_parser(
        finance_subparsers,
        "tree-show",
        help_content=HelpContent(
            summary=_("resources.finance.parser.show_finance_tree"),
            description=_("resources.finance.parser.show_one_finance_tree_and_node_hierarchy"),
            examples=("lifeos finance tree-show 11111111-1111-1111-1111-111111111111",),
        ),
    )
    tree_show.add_argument("tree_id", type=UUID)
    add_json_output_argument(tree_show)
    tree_show.set_defaults(handler=make_sync_handler(handle_finance_tree_show_async))

    ensure_default = add_documented_parser(
        finance_subparsers,
        "tree-ensure-default",
        help_content=HelpContent(
            summary=_("resources.finance.parser.ensure_default_finance_tree_exists"),
            description=_("resources.finance.parser.create_global_default_finance_tree_if_missing"),
            examples=("lifeos finance tree-ensure-default",),
        ),
    )
    ensure_default.add_argument("--primary-currency", default="USD")
    ensure_default.set_defaults(handler=make_sync_handler(handle_finance_tree_ensure_default_async))

    node_add = add_documented_parser(
        finance_subparsers,
        "node-add",
        help_content=HelpContent(
            summary=_("resources.finance.parser.add_finance_tree_node"),
            description=(_("resources.finance.parser.add_node_to_finance_tree")),
            examples=(
                'lifeos finance node-add <tree-id> "Checking" --parent-id <assets-id>',
                'lifeos finance node-add <tree-id> "Cash"',
            ),
        ),
    )
    node_add.add_argument("tree_id", type=UUID)
    node_add.add_argument("name")
    node_add.add_argument("--parent-id", type=UUID)
    node_add.add_argument("--currency-code")
    node_add.add_argument("--display-order", type=int, default=0)
    node_add.set_defaults(handler=make_sync_handler(handle_finance_node_add_async))

    node_update = add_documented_parser(
        finance_subparsers,
        "node-update",
        help_content=HelpContent(
            summary=_("resources.finance.parser.update_finance_node"),
            description=_("resources.finance.parser.update_mutable_node_fields"),
            examples=('lifeos finance node-update <node-id> --name "Brokerage"',),
        ),
    )
    node_update.add_argument("node_id", type=UUID)
    node_update.add_argument("--name")
    node_update.add_argument("--currency-code")
    node_update.add_argument("--display-order", type=int)
    node_update.set_defaults(handler=make_sync_handler(handle_finance_node_update_async))

    node_delete = add_documented_parser(
        finance_subparsers,
        "node-delete",
        help_content=HelpContent(
            summary=_("resources.finance.parser.delete_finance_node"),
            description=_("resources.finance.parser.soft_delete_finance_node"),
            examples=("lifeos finance node-delete 11111111-1111-1111-1111-111111111111",),
        ),
    )
    node_delete.add_argument("node_id", type=UUID)
    node_delete.set_defaults(handler=make_sync_handler(handle_finance_node_delete_async))

    snapshot_add = add_documented_parser(
        finance_subparsers,
        "snapshot-add",
        help_content=HelpContent(
            summary=_("resources.finance.parser.create_finance_snapshot"),
            description=(_("resources.finance.parser.create_instant_or_period_snapshot")),
            examples=(
                'lifeos finance snapshot-add <tree-id> --title "June net worth" '
                "--entry <node-id>:1000:USD",
                "lifeos finance snapshot-add <tree-id> --period-start 2026-06-01T00:00:00 "
                "--period-end 2026-06-30T23:59:59 --entry <node-id>:-120:USD",
            ),
        ),
    )
    snapshot_add.add_argument("tree_id", type=UUID)
    snapshot_add.add_argument("--title")
    snapshot_add.add_argument("--snapshot-ts", type=parse_user_datetime_value)
    snapshot_add.add_argument("--period-start", type=parse_user_datetime_value)
    snapshot_add.add_argument("--period-end", type=parse_user_datetime_value)
    snapshot_add.add_argument("--primary-currency")
    snapshot_add.add_argument("--rate-snapshot-id", type=UUID)
    snapshot_add.add_argument("--note")
    snapshot_add.add_argument(
        "--entry",
        dest="entries",
        action="append",
        type=parse_snapshot_entry,
        required=True,
    )
    snapshot_add.set_defaults(handler=make_sync_handler(handle_finance_snapshot_add_async))

    rate_snapshot_add = add_documented_parser(
        finance_subparsers,
        "rate-snapshot-add",
        help_content=HelpContent(
            summary=_("resources.finance.parser.create_exchange_rate_snapshot"),
            description=(_("resources.finance.parser.capture_point_in_time_exchange_rate_pairs")),
            examples=(
                "lifeos finance rate-snapshot-add --rate BTC:67000:USDT",
                "lifeos finance rate-snapshot-add --rate EUR:1.08:USD --rate CNY:0.14:USD",
            ),
        ),
    )
    rate_snapshot_add.add_argument("--captured-at", type=parse_user_datetime_value)
    rate_snapshot_add.add_argument("--source", default="manual")
    rate_snapshot_add.add_argument("--note")
    rate_snapshot_add.add_argument(
        "--rate",
        dest="rates",
        action="append",
        type=parse_rate_snapshot_entry,
        required=True,
    )
    rate_snapshot_add.set_defaults(
        handler=make_sync_handler(handle_finance_rate_snapshot_add_async)
    )

    rate_snapshot_list = add_documented_parser(
        finance_subparsers,
        "rate-snapshot-list",
        help_content=HelpContent(
            summary=_("resources.finance.parser.list_exchange_rate_snapshots"),
            description=_("resources.finance.parser.list_stored_exchange_rate_snapshots"),
            examples=("lifeos finance rate-snapshot-list",),
        ),
    )
    add_limit_offset_arguments(rate_snapshot_list)
    add_json_output_argument(rate_snapshot_list)
    rate_snapshot_list.set_defaults(
        handler=make_sync_handler(handle_finance_rate_snapshot_list_async)
    )

    rate_snapshot_show = add_documented_parser(
        finance_subparsers,
        "rate-snapshot-show",
        help_content=HelpContent(
            summary=_("resources.finance.parser.show_exchange_rate_snapshot"),
            description=_("resources.finance.parser.show_one_rate_snapshot_and_entries"),
            examples=("lifeos finance rate-snapshot-show 11111111-1111-1111-1111-111111111111",),
        ),
    )
    rate_snapshot_show.add_argument("rate_snapshot_id", type=UUID)
    add_json_output_argument(rate_snapshot_show)
    rate_snapshot_show.set_defaults(
        handler=make_sync_handler(handle_finance_rate_snapshot_show_async)
    )

    snapshot_list = add_documented_parser(
        finance_subparsers,
        "snapshot-list",
        help_content=HelpContent(
            summary=_("resources.finance.parser.list_finance_snapshots"),
            description=_("resources.finance.parser.list_finance_snapshots_across_trees"),
            examples=(
                "lifeos finance snapshot-list",
                "lifeos finance snapshot-list --tree-id <tree-id>",
            ),
        ),
    )
    snapshot_list.add_argument("--tree-id", type=UUID)
    add_limit_offset_arguments(snapshot_list)
    add_json_output_argument(snapshot_list)
    snapshot_list.set_defaults(handler=make_sync_handler(handle_finance_snapshot_list_async))

    snapshot_show = add_documented_parser(
        finance_subparsers,
        "snapshot-show",
        help_content=HelpContent(
            summary=_("resources.finance.parser.show_finance_snapshot"),
            description=_("resources.finance.parser.show_one_finance_snapshot_with_entries"),
            examples=("lifeos finance snapshot-show 11111111-1111-1111-1111-111111111111",),
        ),
    )
    snapshot_show.add_argument("snapshot_id", type=UUID)
    add_json_output_argument(snapshot_show)
    snapshot_show.set_defaults(handler=make_sync_handler(handle_finance_snapshot_show_async))
