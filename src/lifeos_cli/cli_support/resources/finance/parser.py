"""Finance resource parser construction."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Coroutine
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.parser_common import add_limit_offset_arguments
from lifeos_cli.cli_support.resources.finance.handlers import (
    handle_finance_asset_add_async,
    handle_finance_asset_delete_async,
    handle_finance_asset_list_async,
    handle_finance_asset_show_async,
    handle_finance_asset_update_async,
    handle_finance_node_add_async,
    handle_finance_node_delete_async,
    handle_finance_node_list_async,
    handle_finance_node_show_async,
    handle_finance_node_update_async,
    handle_finance_rate_snapshot_add_async,
    handle_finance_rate_snapshot_delete_async,
    handle_finance_rate_snapshot_list_async,
    handle_finance_rate_snapshot_show_async,
    handle_finance_rate_snapshot_update_async,
    handle_finance_snapshot_add_async,
    handle_finance_snapshot_delete_async,
    handle_finance_snapshot_list_async,
    handle_finance_snapshot_show_async,
    handle_finance_snapshot_update_async,
    handle_finance_tree_add_async,
    handle_finance_tree_delete_async,
    handle_finance_tree_ensure_default_async,
    handle_finance_tree_list_async,
    handle_finance_tree_show_async,
    handle_finance_tree_update_async,
    parse_rate_snapshot_entry,
    parse_snapshot_entry,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.cli_support.time_args import parse_user_datetime_value
from lifeos_cli.i18n import cli_message as _

_ASSET_ACTIONS = ("add", "list", "show", "update", "delete")
_TREE_ACTIONS = ("add", "list", "show", "update", "delete", "ensure-default")
_NODE_ACTIONS = ("add", "list", "show", "update", "delete")
_SNAPSHOT_ACTIONS = ("add", "list", "show", "update", "delete")
_RATE_SNAPSHOT_ACTIONS = ("add", "list", "show", "update", "delete")

_ASSET_HANDLERS = {
    "add": handle_finance_asset_add_async,
    "list": handle_finance_asset_list_async,
    "show": handle_finance_asset_show_async,
    "update": handle_finance_asset_update_async,
    "delete": handle_finance_asset_delete_async,
}
_TREE_HANDLERS = {
    "add": handle_finance_tree_add_async,
    "list": handle_finance_tree_list_async,
    "show": handle_finance_tree_show_async,
    "update": handle_finance_tree_update_async,
    "delete": handle_finance_tree_delete_async,
    "ensure-default": handle_finance_tree_ensure_default_async,
}
_NODE_HANDLERS = {
    "add": handle_finance_node_add_async,
    "list": handle_finance_node_list_async,
    "show": handle_finance_node_show_async,
    "update": handle_finance_node_update_async,
    "delete": handle_finance_node_delete_async,
}
_SNAPSHOT_HANDLERS = {
    "add": handle_finance_snapshot_add_async,
    "list": handle_finance_snapshot_list_async,
    "show": handle_finance_snapshot_show_async,
    "update": handle_finance_snapshot_update_async,
    "delete": handle_finance_snapshot_delete_async,
}
_RATE_SNAPSHOT_HANDLERS = {
    "add": handle_finance_rate_snapshot_add_async,
    "list": handle_finance_rate_snapshot_list_async,
    "show": handle_finance_rate_snapshot_show_async,
    "update": handle_finance_rate_snapshot_update_async,
    "delete": handle_finance_rate_snapshot_delete_async,
}


def _add_asset_arguments(parser: argparse.ArgumentParser, action: str) -> None:
    if action == "list":
        add_limit_offset_arguments(parser)
        add_json_output_argument(parser)
    elif action == "add":
        parser.add_argument("code")
        parser.add_argument("--name")
        parser.add_argument("--decimal-places", type=int, default=2)
        parser.add_argument("--display-order", type=int, default=1000)
    elif action == "show":
        parser.add_argument("asset_id", type=UUID)
        add_json_output_argument(parser)
    elif action == "update":
        parser.add_argument("asset_id", type=UUID)
        parser.add_argument("--code")
        parser.add_argument("--name")
        parser.add_argument("--decimal-places", type=int)
        parser.add_argument("--display-order", type=int)
    elif action == "delete":
        parser.add_argument("asset_id", type=UUID)


def _add_tree_arguments(parser: argparse.ArgumentParser, action: str) -> None:
    if action == "list":
        add_limit_offset_arguments(parser)
        add_json_output_argument(parser)
    elif action == "add":
        parser.add_argument("name")
        parser.add_argument("--primary-currency", default="USD")
        parser.add_argument("--display-order", type=int, default=0)
        parser.add_argument("--default", action="store_true")
    elif action == "show":
        parser.add_argument("tree_id", type=UUID)
        add_json_output_argument(parser)
    elif action == "update":
        parser.add_argument("tree_id", type=UUID)
        parser.add_argument("--name")
        parser.add_argument("--primary-currency")
        parser.add_argument("--display-order", type=int)
        parser.add_argument("--default", action="store_true", default=None)
    elif action == "delete":
        parser.add_argument("tree_id", type=UUID)
    elif action == "ensure-default":
        parser.add_argument("--primary-currency", default="USD")


def _add_node_arguments(parser: argparse.ArgumentParser, action: str) -> None:
    if action == "list":
        parser.add_argument("--tree-id", type=UUID, required=True)
        add_json_output_argument(parser)
    elif action == "add":
        parser.add_argument("tree_id", type=UUID)
        parser.add_argument("name")
        parser.add_argument("--parent-id", type=UUID)
        parser.add_argument("--currency-code")
        parser.add_argument("--display-order", type=int, default=0)
    elif action == "show":
        parser.add_argument("node_id", type=UUID)
        add_json_output_argument(parser)
    elif action == "update":
        parser.add_argument("node_id", type=UUID)
        parser.add_argument("--name")
        parser.add_argument("--currency-code")
        parser.add_argument("--display-order", type=int)
    elif action == "delete":
        parser.add_argument("node_id", type=UUID)


def _add_snapshot_arguments(parser: argparse.ArgumentParser, action: str) -> None:
    if action == "list":
        parser.add_argument("--tree-id", type=UUID)
        add_limit_offset_arguments(parser)
        add_json_output_argument(parser)
    elif action == "add":
        parser.add_argument("tree_id", type=UUID)
        parser.add_argument("--title")
        parser.add_argument("--snapshot-ts", type=parse_user_datetime_value)
        parser.add_argument("--period-start", type=parse_user_datetime_value)
        parser.add_argument("--period-end", type=parse_user_datetime_value)
        parser.add_argument("--primary-currency")
        parser.add_argument("--rate-snapshot-id", type=UUID)
        parser.add_argument("--note")
        parser.add_argument(
            "--entry",
            dest="entries",
            action="append",
            type=parse_snapshot_entry,
            required=True,
        )
    elif action == "show":
        parser.add_argument("snapshot_id", type=UUID)
        add_json_output_argument(parser)
    elif action == "update":
        parser.add_argument("snapshot_id", type=UUID)
        parser.add_argument("--title")
        parser.add_argument("--snapshot-ts", type=parse_user_datetime_value)
        parser.add_argument("--period-start", type=parse_user_datetime_value)
        parser.add_argument("--period-end", type=parse_user_datetime_value)
        parser.add_argument("--primary-currency")
        parser.add_argument("--rate-snapshot-id", type=UUID)
        parser.add_argument("--note")
        parser.add_argument(
            "--entry",
            dest="entries",
            action="append",
            type=parse_snapshot_entry,
        )
    elif action == "delete":
        parser.add_argument("snapshot_id", type=UUID)


def _add_rate_snapshot_arguments(parser: argparse.ArgumentParser, action: str) -> None:
    if action == "list":
        add_limit_offset_arguments(parser)
        add_json_output_argument(parser)
    elif action == "add":
        parser.add_argument("--captured-at", type=parse_user_datetime_value)
        parser.add_argument("--source", default="manual")
        parser.add_argument("--note")
        parser.add_argument(
            "--rate",
            dest="rates",
            action="append",
            type=parse_rate_snapshot_entry,
            required=True,
        )
    elif action == "show":
        parser.add_argument("rate_snapshot_id", type=UUID)
        add_json_output_argument(parser)
    elif action == "update":
        parser.add_argument("rate_snapshot_id", type=UUID)
        parser.add_argument("--captured-at", type=parse_user_datetime_value)
        parser.add_argument("--source")
        parser.add_argument("--note")
        parser.add_argument(
            "--rate",
            dest="rates",
            action="append",
            type=parse_rate_snapshot_entry,
        )
    elif action == "delete":
        parser.add_argument("rate_snapshot_id", type=UUID)


def _asset_help(action: str) -> HelpContent:
    if action == "add":
        return HelpContent(
            summary=_("resources.finance.parser.create_finance_asset"),
            description=_("resources.finance.parser.create_selectable_asset_code"),
            examples=(
                'lifeos finance asset add BTC --name "Bitcoin" --decimal-places 8',
                'lifeos finance asset add CNY --name "Chinese Yuan"',
            ),
        )
    if action == "list":
        return HelpContent(
            summary=_("resources.finance.parser.list_finance_assets"),
            description=_(
                "resources.finance.parser.list_active_finance_assets_and_their_precision"
            ),
            examples=("lifeos finance asset list",),
        )
    if action == "show":
        return HelpContent(
            summary=_("resources.finance.parser.show_finance_asset"),
            description=_("resources.finance.parser.show_one_finance_asset_and_precision"),
            examples=("lifeos finance asset show 11111111-1111-1111-1111-111111111111",),
        )
    if action == "update":
        return HelpContent(
            summary=_("resources.finance.parser.update_finance_asset"),
            description=_("resources.finance.parser.update_mutable_finance_asset_fields"),
            examples=(
                "lifeos finance asset update 11111111-1111-1111-1111-111111111111 "
                "--decimal-places 8",
            ),
        )
    return HelpContent(
        summary=_("resources.finance.parser.delete_finance_asset"),
        description=_("resources.finance.parser.soft_delete_finance_asset"),
        examples=("lifeos finance asset delete 11111111-1111-1111-1111-111111111111",),
    )


def _tree_help(action: str) -> HelpContent:
    if action == "add":
        return HelpContent(
            summary=_("resources.finance.parser.create_finance_tree"),
            description=_("resources.finance.parser.create_reusable_finance_tree"),
            examples=(
                'lifeos finance tree add "Personal Finance" --primary-currency USD',
                'lifeos finance tree add "Investments" --primary-currency BTC --default',
            ),
        )
    if action == "list":
        return HelpContent(
            summary=_("resources.finance.parser.list_finance_trees"),
            description=_("resources.finance.parser.list_active_finance_trees"),
            examples=("lifeos finance tree list",),
        )
    if action == "show":
        return HelpContent(
            summary=_("resources.finance.parser.show_finance_tree"),
            description=_("resources.finance.parser.show_one_finance_tree_and_node_hierarchy"),
            examples=("lifeos finance tree show 11111111-1111-1111-1111-111111111111",),
        )
    if action == "update":
        return HelpContent(
            summary=_("resources.finance.parser.update_finance_tree"),
            description=_("resources.finance.parser.update_mutable_finance_tree_fields"),
            examples=(
                "lifeos finance tree update 11111111-1111-1111-1111-111111111111 "
                '--name "Personal Finance" --primary-currency CNY',
            ),
        )
    if action == "delete":
        return HelpContent(
            summary=_("resources.finance.parser.delete_finance_tree"),
            description=_(
                "resources.finance.parser.soft_delete_finance_tree_when_no_snapshots_exist"
            ),
            examples=("lifeos finance tree delete 11111111-1111-1111-1111-111111111111",),
        )
    return HelpContent(
        summary=_("resources.finance.parser.ensure_default_finance_tree_exists"),
        description=_("resources.finance.parser.create_global_default_finance_tree_if_missing"),
        examples=("lifeos finance tree ensure-default",),
        notes=(_("resources.finance.parser.ensure_default_tree_is_idempotent"),),
    )


def _node_help(action: str) -> HelpContent:
    if action == "add":
        return HelpContent(
            summary=_("resources.finance.parser.add_finance_tree_node"),
            description=_("resources.finance.parser.add_node_to_finance_tree"),
            examples=(
                'lifeos finance node add <tree-id> "Checking" --parent-id <assets-id>',
                'lifeos finance node add <tree-id> "Cash"',
            ),
        )
    if action == "list":
        return HelpContent(
            summary=_("resources.finance.parser.list_finance_tree_nodes"),
            description=_("resources.finance.parser.list_nodes_for_one_finance_tree_in_tree_order"),
            examples=("lifeos finance node list --tree-id <tree-id>",),
        )
    if action == "show":
        return HelpContent(
            summary=_("resources.finance.parser.show_finance_tree_node"),
            description=_("resources.finance.parser.show_one_finance_tree_node_with_tree_context"),
            examples=("lifeos finance node show 11111111-1111-1111-1111-111111111111",),
        )
    if action == "update":
        return HelpContent(
            summary=_("resources.finance.parser.update_finance_node"),
            description=_("resources.finance.parser.update_mutable_node_fields"),
            examples=(
                "lifeos finance node update 11111111-1111-1111-1111-111111111111 "
                '--name "Brokerage"',
            ),
        )
    return HelpContent(
        summary=_("resources.finance.parser.delete_finance_node"),
        description=_("resources.finance.parser.soft_delete_finance_node"),
        examples=("lifeos finance node delete 11111111-1111-1111-1111-111111111111",),
    )


def _snapshot_help(action: str) -> HelpContent:
    if action == "add":
        return HelpContent(
            summary=_("resources.finance.parser.create_finance_snapshot"),
            description=_("resources.finance.parser.create_instant_or_period_snapshot"),
            examples=(
                'lifeos finance snapshot add <tree-id> --title "June net worth" '
                "--entry <node-id>:1000:USD",
                "lifeos finance snapshot add <tree-id> --period-start 2026-06-01T00:00:00 "
                "--period-end 2026-06-30T23:59:59 --entry <node-id>:-120:USD",
            ),
        )
    if action == "list":
        return HelpContent(
            summary=_("resources.finance.parser.list_finance_snapshots"),
            description=_("resources.finance.parser.list_finance_snapshots_across_trees"),
            examples=(
                "lifeos finance snapshot list",
                "lifeos finance snapshot list --tree-id <tree-id>",
            ),
        )
    if action == "show":
        return HelpContent(
            summary=_("resources.finance.parser.show_finance_snapshot"),
            description=_("resources.finance.parser.show_one_finance_snapshot_with_entries"),
            examples=("lifeos finance snapshot show 11111111-1111-1111-1111-111111111111",),
        )
    if action == "update":
        return HelpContent(
            summary=_("resources.finance.parser.update_finance_snapshot"),
            description=_("resources.finance.parser.update_finance_snapshot_fields_and_entries"),
            examples=(
                "lifeos finance snapshot update 11111111-1111-1111-1111-111111111111 "
                '--title "June net worth revised"',
            ),
        )
    return HelpContent(
        summary=_("resources.finance.parser.delete_finance_snapshot"),
        description=_("resources.finance.parser.soft_delete_finance_snapshot_and_entries"),
        examples=("lifeos finance snapshot delete 11111111-1111-1111-1111-111111111111",),
    )


def _rate_snapshot_help(action: str) -> HelpContent:
    if action == "add":
        return HelpContent(
            summary=_("resources.finance.parser.create_exchange_rate_snapshot"),
            description=_("resources.finance.parser.capture_point_in_time_exchange_rate_pairs"),
            examples=(
                "lifeos finance rate-snapshot add --rate BTC:67000:USDT",
                "lifeos finance rate-snapshot add --rate EUR:1.08:USD --rate CNY:0.14:USD",
            ),
        )
    if action == "list":
        return HelpContent(
            summary=_("resources.finance.parser.list_exchange_rate_snapshots"),
            description=_("resources.finance.parser.list_stored_exchange_rate_snapshots"),
            examples=("lifeos finance rate-snapshot list",),
        )
    if action == "show":
        return HelpContent(
            summary=_("resources.finance.parser.show_exchange_rate_snapshot"),
            description=_("resources.finance.parser.show_one_rate_snapshot_and_entries"),
            examples=("lifeos finance rate-snapshot show 11111111-1111-1111-1111-111111111111",),
        )
    if action == "update":
        return HelpContent(
            summary=_("resources.finance.parser.update_finance_rate_snapshot"),
            description=_(
                "resources.finance.parser.update_finance_rate_snapshot_fields_and_entries"
            ),
            examples=(
                "lifeos finance rate-snapshot update 11111111-1111-1111-1111-111111111111 "
                '--note "July rates" --rate EUR:1.07:USD',
            ),
        )
    return HelpContent(
        summary=_("resources.finance.parser.delete_finance_rate_snapshot"),
        description=_("resources.finance.parser.soft_delete_finance_rate_snapshot_and_entries"),
        examples=("lifeos finance rate-snapshot delete 11111111-1111-1111-1111-111111111111",),
    )


def _register_command(
    container: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    name: str,
    help_content: HelpContent,
    add_arguments: Callable[[argparse.ArgumentParser, str], None],
    action: str,
    handler: Callable[[argparse.Namespace], Coroutine[object, object, int]],
) -> None:
    """Register one finance action inside its nested group."""
    parser = add_documented_parser(container, name, help_content=help_content)
    add_arguments(parser, action)
    parser.set_defaults(handler=make_sync_handler(handler))


def _build_asset_group(
    finance_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the nested `finance asset` command group."""
    asset_parser = add_documented_help_parser(
        finance_subparsers,
        "asset",
        help_content=HelpContent(
            summary=_("resources.finance.parser.manage_finance_assets"),
            description=_("resources.finance.parser.manage_finance_asset_codes_and_precision"),
            examples=("lifeos finance asset --help",),
        ),
    )
    asset_subparsers = asset_parser.add_subparsers(
        dest="finance_asset_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )
    for action in _ASSET_ACTIONS:
        _register_command(
            asset_subparsers,
            name=action,
            help_content=_asset_help(action),
            add_arguments=_add_asset_arguments,
            action=action,
            handler=_ASSET_HANDLERS[action],
        )


def _build_tree_group(
    finance_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the nested `finance tree` command group."""
    tree_parser = add_documented_help_parser(
        finance_subparsers,
        "tree",
        help_content=HelpContent(
            summary=_("resources.finance.parser.manage_finance_trees"),
            description=_("resources.finance.parser.manage_finance_trees_and_default_tree"),
            examples=("lifeos finance tree --help",),
        ),
    )
    tree_subparsers = tree_parser.add_subparsers(
        dest="finance_tree_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )
    for action in _TREE_ACTIONS:
        _register_command(
            tree_subparsers,
            name=action,
            help_content=_tree_help(action),
            add_arguments=_add_tree_arguments,
            action=action,
            handler=_TREE_HANDLERS[action],
        )


def _build_node_group(
    finance_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the nested `finance node` command group."""
    node_parser = add_documented_help_parser(
        finance_subparsers,
        "node",
        help_content=HelpContent(
            summary=_("resources.finance.parser.manage_finance_tree_nodes"),
            description=_("resources.finance.parser.manage_nodes_inside_one_finance_tree"),
            examples=("lifeos finance node --help",),
        ),
    )
    node_subparsers = node_parser.add_subparsers(
        dest="finance_node_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )
    for action in _NODE_ACTIONS:
        _register_command(
            node_subparsers,
            name=action,
            help_content=_node_help(action),
            add_arguments=_add_node_arguments,
            action=action,
            handler=_NODE_HANDLERS[action],
        )


def _build_snapshot_group(
    finance_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the nested `finance snapshot` command group."""
    snapshot_parser = add_documented_help_parser(
        finance_subparsers,
        "snapshot",
        help_content=HelpContent(
            summary=_("resources.finance.parser.manage_finance_snapshots"),
            description=_("resources.finance.parser.manage_instant_and_period_finance_snapshots"),
            examples=("lifeos finance snapshot --help",),
        ),
    )
    snapshot_subparsers = snapshot_parser.add_subparsers(
        dest="finance_snapshot_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )
    for action in _SNAPSHOT_ACTIONS:
        _register_command(
            snapshot_subparsers,
            name=action,
            help_content=_snapshot_help(action),
            add_arguments=_add_snapshot_arguments,
            action=action,
            handler=_SNAPSHOT_HANDLERS[action],
        )


def _build_rate_snapshot_group(
    finance_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the nested `finance rate-snapshot` command group."""
    rate_snapshot_parser = add_documented_help_parser(
        finance_subparsers,
        "rate-snapshot",
        help_content=HelpContent(
            summary=_("resources.finance.parser.manage_finance_rate_snapshots"),
            description=_("resources.finance.parser.manage_exchange_rate_snapshot_records"),
            examples=("lifeos finance rate-snapshot --help",),
        ),
    )
    rate_snapshot_subparsers = rate_snapshot_parser.add_subparsers(
        dest="finance_rate_snapshot_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )
    for action in _RATE_SNAPSHOT_ACTIONS:
        _register_command(
            rate_snapshot_subparsers,
            name=action,
            help_content=_rate_snapshot_help(action),
            add_arguments=_add_rate_snapshot_arguments,
            action=action,
            handler=_RATE_SNAPSHOT_HANDLERS[action],
        )


def build_finance_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the finance command tree."""
    finance_parser = add_documented_help_parser(
        subparsers,
        "finance",
        help_content=HelpContent(
            summary=_("resources.finance.parser.manage_unified_finance_trees_and_snapshots"),
            description=_("resources.finance.parser.create_finance_trees_nodes_and_snapshots"),
            examples=(
                "lifeos finance asset list",
                "lifeos finance tree --help",
                "lifeos finance node --help",
                "lifeos finance rate-snapshot --help",
                "lifeos finance snapshot --help",
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
    _build_asset_group(finance_subparsers)
    _build_tree_group(finance_subparsers)
    _build_node_group(finance_subparsers)
    _build_snapshot_group(finance_subparsers)
    _build_rate_snapshot_group(finance_subparsers)
