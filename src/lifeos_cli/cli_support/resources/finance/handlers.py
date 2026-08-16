"""CLI handlers for the finance resource."""

from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from lifeos_cli.application.time_preferences import to_storage_timezone
from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import format_timestamp, print_summary_rows
from lifeos_cli.db import session as db_session
from lifeos_cli.db.models.finance import (
    FinanceAsset,
    FinanceRateSnapshot,
    FinanceSnapshot,
    FinanceTree,
    FinanceTreeNode,
)
from lifeos_cli.db.services import finance as finance_services

ASSET_SUMMARY_COLUMNS = ("asset_id", "code", "decimal_places", "name")
TREE_SUMMARY_COLUMNS = ("tree_id", "currency", "name")
SNAPSHOT_SUMMARY_COLUMNS = ("snapshot_id", "tree_id", "title", "period", "net_amount", "currency")
RATE_SNAPSHOT_SUMMARY_COLUMNS = ("rate_snapshot_id", "captured_at", "pairs", "source")


def _format_asset_summary(asset: FinanceAsset) -> str:
    return f"{asset.id}\t{asset.code}\t{asset.decimal_places}\t{asset.name or '-'}"


def _format_tree_summary(tree: FinanceTree) -> str:
    return f"{tree.id}\t{tree.primary_currency}\t{tree.name}"


def _format_node_summary(node: FinanceTreeNode) -> str:
    indent = "  " * node.depth
    return f"{node.id}\t{node.parent_id or '-'}\t{node.currency_code or '-'}\t{indent}{node.name}"


def _format_snapshot_period(snapshot: FinanceSnapshot) -> str:
    if snapshot.period_start is not None and snapshot.period_end is not None:
        return f"{format_timestamp(snapshot.period_start)}..{format_timestamp(snapshot.period_end)}"
    return format_timestamp(snapshot.snapshot_ts)


def _format_decimal(
    value: Decimal,
    *,
    currency_code: str,
    decimal_places_by_code: dict[str, int],
) -> str:
    return finance_services.format_asset_amount(
        value,
        currency_code=currency_code,
        decimal_places_by_code=decimal_places_by_code,
    )


def _format_snapshot_summary(
    snapshot: FinanceSnapshot,
    *,
    decimal_places_by_code: dict[str, int],
) -> str:
    net_amount = _format_decimal(
        snapshot.net_amount,
        currency_code=snapshot.primary_currency,
        decimal_places_by_code=decimal_places_by_code,
    )
    return (
        f"{snapshot.id}\t{snapshot.tree_id}\t{snapshot.title or '-'}\t"
        f"{_format_snapshot_period(snapshot)}\t{net_amount}\t{snapshot.primary_currency}"
    )


def _format_rate_snapshot_summary(rate_snapshot: FinanceRateSnapshot) -> str:
    pairs = ",".join(
        f"{entry.base_currency}/{entry.quote_currency}" for entry in rate_snapshot.entries[:3]
    )
    return (
        f"{rate_snapshot.id}\t{format_timestamp(rate_snapshot.captured_at)}\t"
        f"{pairs or '-'}\t{rate_snapshot.source}"
    )


def _format_tree_detail(tree: FinanceTree, nodes: list[FinanceTreeNode]) -> str:
    node_lines = [_format_node_summary(node) for node in nodes]
    return "\n".join(
        (
            f"id: {tree.id}",
            f"name: {tree.name}",
            f"primary_currency: {tree.primary_currency}",
            f"is_default: {tree.is_default}",
            f"display_order: {tree.display_order}",
            "nodes:",
            *(node_lines or ["-"]),
        )
    )


def _format_snapshot_detail(
    snapshot: FinanceSnapshot,
    *,
    decimal_places_by_code: dict[str, int],
) -> str:
    entry_lines = []
    for entry in snapshot.entries:
        amount = _format_decimal(
            entry.amount,
            currency_code=entry.currency_code,
            decimal_places_by_code=decimal_places_by_code,
        )
        amount_converted = _format_decimal(
            entry.amount_converted,
            currency_code=snapshot.primary_currency,
            decimal_places_by_code=decimal_places_by_code,
        )
        entry_lines.append(
            f"  {entry.node_id}\t{entry.node.name if entry.node else '-'}\t"
            f"{amount}\t{entry.currency_code}\t{amount_converted}\t"
            f"{'auto' if entry.is_auto_generated else 'manual'}"
        )
    total_positive = _format_decimal(
        snapshot.total_positive,
        currency_code=snapshot.primary_currency,
        decimal_places_by_code=decimal_places_by_code,
    )
    total_negative = _format_decimal(
        snapshot.total_negative,
        currency_code=snapshot.primary_currency,
        decimal_places_by_code=decimal_places_by_code,
    )
    net_amount = _format_decimal(
        snapshot.net_amount,
        currency_code=snapshot.primary_currency,
        decimal_places_by_code=decimal_places_by_code,
    )
    return "\n".join(
        (
            f"id: {snapshot.id}",
            f"tree_id: {snapshot.tree_id}",
            f"title: {snapshot.title or '-'}",
            f"snapshot_ts: {format_timestamp(snapshot.snapshot_ts)}",
            f"period_start: {format_timestamp(snapshot.period_start)}",
            f"period_end: {format_timestamp(snapshot.period_end)}",
            f"primary_currency: {snapshot.primary_currency}",
            f"rate_snapshot_id: {snapshot.rate_snapshot_id or '-'}",
            f"rate_snapshot_policy: {snapshot.rate_snapshot_policy}",
            f"total_positive: {total_positive}",
            f"total_negative: {total_negative}",
            f"net_amount: {net_amount}",
            f"note: {snapshot.note or '-'}",
            "entries:",
            "  node_id\tname\tamount\tcurrency\tconverted\tsource",
            *(entry_lines or ["  -"]),
        )
    )


def _format_rate_snapshot_detail(rate_snapshot: FinanceRateSnapshot) -> str:
    entry_lines = [
        (
            f"  {entry.base_currency}\t{entry.quote_currency}\t{entry.rate}\t"
            f"{entry.source or '-'}\t{format_timestamp(entry.captured_at)}"
        )
        for entry in rate_snapshot.entries
    ]
    return "\n".join(
        (
            f"id: {rate_snapshot.id}",
            f"captured_at: {format_timestamp(rate_snapshot.captured_at)}",
            f"source: {rate_snapshot.source}",
            f"note: {rate_snapshot.note or '-'}",
            "entries:",
            "  base_currency\tquote_currency\trate\tsource\tcaptured_at",
            *(entry_lines or ["  -"]),
        )
    )


def parse_snapshot_entry(value: str) -> finance_services.FinanceSnapshotEntryInput:
    """Parse node_id:amount[:currency] CLI entry syntax."""
    parts = value.split(":")
    if len(parts) not in {2, 3}:
        raise argparse.ArgumentTypeError("Entry must use node-id:amount[:currency]")
    node_id_text, amount_text = parts[0], parts[1]
    currency_code = parts[2] if len(parts) >= 3 and parts[2] else None
    try:
        return finance_services.FinanceSnapshotEntryInput(
            node_id=UUID(node_id_text),
            amount=Decimal(amount_text),
            currency_code=currency_code,
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_rate_snapshot_entry(value: str) -> finance_services.FinanceRateSnapshotEntryInput:
    """Parse base-currency:rate:quote-currency CLI rate syntax."""
    parts = value.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("Rate must use base-currency:rate:quote-currency")
    base_currency, rate_text = parts[0], parts[1]
    quote_currency = parts[2]
    try:
        return finance_services.FinanceRateSnapshotEntryInput(
            base_currency=base_currency,
            rate=Decimal(rate_text),
            quote_currency=quote_currency,
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _storage_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return to_storage_timezone(value)


async def handle_finance_asset_list_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        assets = await finance_services.list_finance_assets(
            session,
            limit=args.limit,
            offset=args.offset,
        )
    if args.json:
        print_json_items(assets)
        return 0
    print_summary_rows(
        items=assets,
        columns=ASSET_SUMMARY_COLUMNS,
        row_formatter=_format_asset_summary,
        empty_message="No finance assets found.",
    )
    return 0


async def handle_finance_asset_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            asset = await finance_services.create_finance_asset(
                session,
                code=args.code,
                name=args.name,
                decimal_places=args.decimal_places,
                display_order=args.display_order,
            )
        except ValueError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created finance asset {asset.id}")
    return 0


async def handle_finance_asset_update_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            asset = await finance_services.update_finance_asset(
                session,
                asset_id=args.asset_id,
                code=args.code,
                name=args.name,
                decimal_places=args.decimal_places,
                display_order=args.display_order,
            )
        except (LookupError, ValueError) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated finance asset {asset.id}")
    return 0


async def handle_finance_asset_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            await finance_services.delete_finance_asset(session, asset_id=args.asset_id)
        except LookupError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted finance asset {args.asset_id}")
    return 0


async def handle_finance_tree_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            tree = await finance_services.create_finance_tree(
                session,
                name=args.name,
                primary_currency=args.primary_currency,
                display_order=args.display_order,
                is_default=args.default,
            )
        except ValueError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created finance tree {tree.id}")
    return 0


async def handle_finance_tree_list_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            trees = await finance_services.list_finance_trees(
                session,
                limit=args.limit,
                offset=args.offset,
            )
        except ValueError as exc:
            return cli_handler_utils.print_cli_error(exc)
    if args.json:
        print_json_items(trees)
        return 0
    print_summary_rows(
        items=trees,
        columns=TREE_SUMMARY_COLUMNS,
        row_formatter=_format_tree_summary,
        empty_message="No finance trees found.",
    )
    return 0


async def handle_finance_tree_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        tree = await finance_services.get_finance_tree_with_nodes(
            session,
            tree_id=args.tree_id,
        )
    if tree is None:
        return cli_handler_utils.print_missing_record_error("Finance tree", args.tree_id)
    if args.json:
        print_json_payload(tree)
        return 0
    print(_format_tree_detail(tree, list(tree.nodes)))
    return 0


async def handle_finance_tree_ensure_default_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            tree = await finance_services.ensure_default_finance_tree(
                session,
                primary_currency=args.primary_currency,
            )
        except ValueError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Default finance tree {tree.id}")
    return 0


async def handle_finance_node_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            node = await finance_services.create_finance_node(
                session,
                tree_id=args.tree_id,
                parent_id=args.parent_id,
                name=args.name,
                currency_code=args.currency_code,
                display_order=args.display_order,
            )
        except (LookupError, ValueError) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created finance node {node.id}")
    return 0


async def handle_finance_node_update_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            node = await finance_services.update_finance_node(
                session,
                node_id=args.node_id,
                name=args.name,
                currency_code=args.currency_code,
                display_order=args.display_order,
            )
        except (LookupError, ValueError) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated finance node {node.id}")
    return 0


async def handle_finance_node_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            await finance_services.delete_finance_node(session, node_id=args.node_id)
        except LookupError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted finance node {args.node_id}")
    return 0


async def handle_finance_snapshot_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            snapshot = await finance_services.create_finance_snapshot(
                session,
                tree_id=args.tree_id,
                title=args.title,
                snapshot_ts=_storage_datetime(args.snapshot_ts),
                period_start=_storage_datetime(args.period_start),
                period_end=_storage_datetime(args.period_end),
                primary_currency=args.primary_currency,
                rate_snapshot_id=args.rate_snapshot_id,
                note=args.note,
                entries=list(args.entries),
            )
        except (LookupError, ValueError) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created finance snapshot {snapshot.id}")
    return 0


async def handle_finance_rate_snapshot_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            rate_snapshot = await finance_services.create_finance_rate_snapshot(
                session,
                captured_at=_storage_datetime(args.captured_at),
                source=args.source,
                note=args.note,
                entries=list(args.rates),
            )
        except ValueError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created finance rate snapshot {rate_snapshot.id}")
    return 0


async def handle_finance_rate_snapshot_list_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            rate_snapshots = await finance_services.list_finance_rate_snapshots(
                session,
                limit=args.limit,
                offset=args.offset,
            )
        except ValueError as exc:
            return cli_handler_utils.print_cli_error(exc)
    if args.json:
        print_json_items(rate_snapshots)
        return 0
    print_summary_rows(
        items=rate_snapshots,
        columns=RATE_SNAPSHOT_SUMMARY_COLUMNS,
        row_formatter=_format_rate_snapshot_summary,
        empty_message="No finance rate snapshots found.",
    )
    return 0


async def handle_finance_rate_snapshot_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        rate_snapshot = await finance_services.get_finance_rate_snapshot(
            session,
            rate_snapshot_id=args.rate_snapshot_id,
        )
    if rate_snapshot is None:
        return cli_handler_utils.print_missing_record_error(
            "Finance rate snapshot",
            args.rate_snapshot_id,
        )
    if args.json:
        print_json_payload(rate_snapshot)
        return 0
    print(_format_rate_snapshot_detail(rate_snapshot))
    return 0


async def handle_finance_snapshot_list_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            snapshots = await finance_services.list_finance_snapshots(
                session,
                tree_id=args.tree_id,
                limit=args.limit,
                offset=args.offset,
            )
        except ValueError as exc:
            return cli_handler_utils.print_cli_error(exc)
        assets = await finance_services.list_finance_assets(session)
    decimal_places_by_code = {asset.code: asset.decimal_places for asset in assets}
    if args.json:
        print_json_items(snapshots)
        return 0
    print_summary_rows(
        items=snapshots,
        columns=SNAPSHOT_SUMMARY_COLUMNS,
        row_formatter=lambda snapshot: _format_snapshot_summary(
            snapshot,
            decimal_places_by_code=decimal_places_by_code,
        ),
        empty_message="No finance snapshots found.",
    )
    return 0


async def handle_finance_snapshot_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        snapshot = await finance_services.get_finance_snapshot(
            session,
            snapshot_id=args.snapshot_id,
        )
        assets = await finance_services.list_finance_assets(session)
    if snapshot is None:
        return cli_handler_utils.print_missing_record_error("Finance snapshot", args.snapshot_id)
    if args.json:
        print_json_payload(snapshot)
        return 0
    decimal_places_by_code = {asset.code: asset.decimal_places for asset in assets}
    print(
        _format_snapshot_detail(
            snapshot,
            decimal_places_by_code=decimal_places_by_code,
        )
    )
    return 0
