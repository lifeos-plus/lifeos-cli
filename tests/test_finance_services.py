from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lifeos_cli.config import clear_config_cache
from lifeos_cli.db.base import Base
from lifeos_cli.db.services import finance
from tests.config_support import install_test_config


async def _create_sqlite_session_factory() -> tuple[
    AsyncEngine,
    async_sessionmaker[AsyncSession],
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, future=True)


def test_finance_default_tree_and_snapshot_rollups() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                nodes = await finance.list_finance_nodes(session, tree_id=tree.id)
                assert {node.name for node in nodes} == {"Assets", "Liabilities"}
                assets = next(node for node in nodes if node.name == "Assets")
                checking = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Checking",
                    currency_code="USD",
                )
                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=checking.id,
                            amount=Decimal("1250.50"),
                            currency_code="USD",
                        )
                    ],
                )

                assert snapshot.total_positive == Decimal("1250.50000000")
                assert snapshot.total_negative == Decimal("0E-8")
                assert snapshot.net_amount == Decimal("1250.50000000")
                assert any(
                    entry.node_id == assets.id
                    and entry.is_auto_generated
                    and entry.amount_converted == Decimal("1250.50000000")
                    for entry in snapshot.entries
                )
                await session.commit()

            async with session_factory() as session:
                trees = await finance.list_finance_trees(session)
                assert len(trees) == 1
                assert trees[0].id == tree.id
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_services_apply_configured_timezone_to_naive_timestamps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_test_config(monkeypatch=monkeypatch, tmp_path=tmp_path, include_preferences=True)

    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                assets = next(
                    node
                    for node in await finance.list_finance_nodes(session, tree_id=tree.id)
                    if node.name == "Assets"
                )
                account = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Checking",
                    currency_code="USD",
                )
                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    snapshot_ts=datetime(2026, 4, 10, 9, 0),
                    period_start=datetime(2026, 4, 1, 0, 0),
                    period_end=datetime(2026, 4, 30, 23, 59, 59),
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=account.id,
                            amount=Decimal("1"),
                            currency_code="USD",
                        )
                    ],
                )
                rate_snapshot = await finance.create_finance_rate_snapshot(
                    session,
                    captured_at=datetime(2026, 4, 10, 9, 0),
                    entries=[
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="USD",
                            quote_currency="CNY",
                            rate=Decimal("7"),
                            captured_at=datetime(2026, 4, 10, 9, 30),
                        )
                    ],
                )

                assert snapshot.snapshot_ts is not None
                assert snapshot.period_start is not None
                assert snapshot.period_end is not None
                assert snapshot.snapshot_ts.isoformat() == "2026-04-10T13:00:00+00:00"
                assert snapshot.period_start.isoformat() == "2026-04-01T04:00:00+00:00"
                assert snapshot.period_end.isoformat() == "2026-05-01T03:59:59+00:00"
                assert rate_snapshot.captured_at.isoformat() == "2026-04-10T13:00:00+00:00"
                assert rate_snapshot.entries[0].captured_at is not None
                assert (
                    rate_snapshot.entries[0].captured_at.isoformat() == "2026-04-10T13:30:00+00:00"
                )
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
    finally:
        clear_config_cache()


def test_finance_snapshot_title_can_be_created_updated_and_cleared() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                assets = next(
                    node
                    for node in await finance.list_finance_nodes(session, tree_id=tree.id)
                    if node.name == "Assets"
                )
                checking = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Checking",
                    currency_code="USD",
                )

                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    title="June net worth",
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=checking.id,
                            amount=Decimal("100"),
                            currency_code="USD",
                        )
                    ],
                )
                assert snapshot.title == "June net worth"

                updated = await finance.update_finance_snapshot(
                    session,
                    snapshot_id=snapshot.id,
                    title="Updated net worth",
                    update_title=True,
                )
                assert updated.title == "Updated net worth"

                cleared = await finance.update_finance_snapshot(
                    session,
                    snapshot_id=snapshot.id,
                    title=" ",
                    update_title=True,
                )
                assert cleared.title is None
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_default_finance_tree_is_global() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                nodes = await finance.list_finance_nodes(session, tree_id=tree.id)

                assert tree.name == "Finance"
                assert {node.name for node in nodes} == {"Assets", "Liabilities"}

                same_tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="CNY",
                )
                assert same_tree.id == tree.id
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_tree_update_delete_and_report_snapshot_listing() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                first_tree = await finance.create_finance_tree(
                    session,
                    name="Primary balance",
                    primary_currency="USD",
                )
                second_tree = await finance.create_finance_tree(
                    session,
                    name="Secondary balance",
                    primary_currency="CNY",
                )
                updated_tree = await finance.update_finance_tree(
                    session,
                    tree_id=second_tree.id,
                    name="Brokerage balance",
                    primary_currency="USD",
                    is_default=True,
                )
                assert updated_tree.name == "Brokerage balance"
                assert updated_tree.primary_currency == "USD"
                assert updated_tree.is_default is True

                reloaded_first = await finance.get_finance_tree(session, tree_id=first_tree.id)
                assert reloaded_first is not None
                assert reloaded_first.is_default is False

                assets = await finance.create_finance_node(
                    session,
                    tree_id=updated_tree.id,
                    parent_id=None,
                    name="Assets",
                    currency_code="USD",
                )
                wallet = await finance.create_finance_node(
                    session,
                    tree_id=updated_tree.id,
                    parent_id=assets.id,
                    name="Wallet",
                    currency_code="USD",
                )
                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=updated_tree.id,
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=wallet.id,
                            amount=Decimal("10"),
                            currency_code="USD",
                        )
                    ],
                )
                period_snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=updated_tree.id,
                    period_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
                    period_end=datetime(2026, 6, 30, tzinfo=timezone.utc),
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=wallet.id,
                            amount=Decimal("20"),
                            currency_code="USD",
                        )
                    ],
                )

                snapshots = await finance.list_finance_snapshots(session)
                assert {item.id for item in snapshots} == {snapshot.id, period_snapshot.id}

                with pytest.raises(finance.FinanceValidationError):
                    await finance.delete_finance_tree(session, tree_id=updated_tree.id)

                disposable_tree = await finance.create_finance_tree(
                    session,
                    name="Disposable cashflow",
                    primary_currency="USD",
                )
                await finance.delete_finance_tree(session, tree_id=disposable_tree.id)
                assert (await finance.get_finance_tree(session, tree_id=disposable_tree.id)) is None
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_assets_include_defaults_and_custom_assets() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                assets = await finance.list_finance_assets(session)
                assert {"USD", "USDT", "CNY", "BTC"}.issubset({asset.code for asset in assets})
                assert all(asset.decimal_places == 2 for asset in assets)

                custom = await finance.create_finance_asset(
                    session,
                    code="sol",
                    name="Solana",
                    decimal_places=8,
                )
                assert custom.code == "SOL"
                assert custom.decimal_places == 8

                updated = await finance.update_finance_asset(
                    session,
                    asset_id=custom.id,
                    name="Solana token",
                    decimal_places=4,
                )
                assert updated.name == "Solana token"
                assert updated.decimal_places == 4

                await finance.delete_finance_asset(session, asset_id=custom.id)
                assert all(
                    asset.code != "SOL" for asset in await finance.list_finance_assets(session)
                )

                usd = next(
                    asset
                    for asset in await finance.list_finance_assets(session)
                    if asset.code == "USD"
                )
                await finance.delete_finance_asset(session, asset_id=usd.id)
                active_assets = await finance.list_finance_assets(session)
                assert all(asset.deleted_at is None for asset in active_assets)
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_snapshot_amount_precision_follows_asset() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="BTC",
                )
                btc = next(
                    asset
                    for asset in await finance.list_finance_assets(session)
                    if asset.code == "BTC"
                )
                await finance.update_finance_asset(
                    session,
                    asset_id=btc.id,
                    decimal_places=8,
                )
                nodes = await finance.list_finance_nodes(session, tree_id=tree.id)
                assets = next(node for node in nodes if node.name == "Assets")
                wallet = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Wallet",
                    currency_code="BTC",
                )

                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=wallet.id,
                            amount=Decimal("0.12345678"),
                            currency_code="BTC",
                        )
                    ],
                )
                assert snapshot.net_amount == Decimal("0.12345678")

                with pytest.raises(finance.FinanceValidationError):
                    await finance.create_finance_snapshot(
                        session,
                        tree_id=tree.id,
                        entries=[
                            finance.FinanceSnapshotEntryInput(
                                node_id=wallet.id,
                                amount=Decimal("0.123456789"),
                                currency_code="BTC",
                            )
                        ],
                    )
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_snapshot_supports_multiple_assets_under_one_account() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                nodes = await finance.list_finance_nodes(session, tree_id=tree.id)
                assets = next(node for node in nodes if node.name == "Assets")
                exin = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="EXIN savings",
                    currency_code="CNY",
                )

                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=exin.id,
                            amount=Decimal("1000"),
                            currency_code="CNY",
                        ),
                        finance.FinanceSnapshotEntryInput(
                            node_id=exin.id,
                            amount=Decimal("50"),
                            currency_code="USDT",
                        ),
                    ],
                )

                manual_entries = [
                    entry for entry in snapshot.entries if not entry.is_auto_generated
                ]
                assert {(entry.node_id, entry.currency_code) for entry in manual_entries} == {
                    (exin.id, "CNY"),
                    (exin.id, "USDT"),
                }
                asset_rollups = [
                    entry
                    for entry in snapshot.entries
                    if entry.node_id == assets.id and entry.is_auto_generated
                ]
                assert {(entry.currency_code, entry.amount) for entry in asset_rollups} == {
                    ("CNY", Decimal("1000.00000000")),
                    ("USDT", Decimal("50.00000000")),
                }
                assert snapshot.summary is not None
                assert snapshot.summary["amounts_by_currency"]["CNY"]["net_amount"] == (
                    "1000.00000000"
                )
                assert snapshot.summary["amounts_by_currency"]["USDT"]["net_amount"] == (
                    "50.00000000"
                )
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_snapshot_rejects_duplicate_asset_entries_for_one_account() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                assets = next(
                    node
                    for node in await finance.list_finance_nodes(session, tree_id=tree.id)
                    if node.name == "Assets"
                )
                account = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Brokerage",
                    currency_code="USD",
                )

                with pytest.raises(finance.FinanceValidationError):
                    await finance.create_finance_snapshot(
                        session,
                        tree_id=tree.id,
                        entries=[
                            finance.FinanceSnapshotEntryInput(
                                node_id=account.id,
                                amount=Decimal("10"),
                                currency_code="USD",
                            ),
                            finance.FinanceSnapshotEntryInput(
                                node_id=account.id,
                                amount=Decimal("20"),
                                currency_code="usd",
                            ),
                        ],
                    )
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_snapshot_without_rate_snapshot_keeps_native_currency_totals() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                assets = next(
                    node
                    for node in await finance.list_finance_nodes(session, tree_id=tree.id)
                    if node.name == "Assets"
                )
                account = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Euro account",
                    currency_code="EUR",
                )
                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    snapshot_ts=datetime(2026, 6, 2, tzinfo=timezone.utc),
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=account.id,
                            amount=Decimal("10"),
                            currency_code="EUR",
                        )
                    ],
                )

                assert snapshot.rate_snapshot_id is None
                assert snapshot.rate_snapshot_policy == "none"
                assert snapshot.net_amount == Decimal("0E-8")
                assert snapshot.exchange_rates is None
                assert snapshot.summary is not None
                assert snapshot.summary["aggregation_mode"] == "native_by_currency"
                assert snapshot.summary["amounts_by_currency"]["EUR"]["net_amount"] == "10.00000000"
                assert any(
                    entry.node_id == assets.id
                    and entry.currency_code == "EUR"
                    and entry.amount == Decimal("10.00000000")
                    for entry in snapshot.entries
                )
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_snapshot_supports_explicit_inverse_rate_snapshot() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                assets = next(
                    node
                    for node in await finance.list_finance_nodes(session, tree_id=tree.id)
                    if node.name == "Assets"
                )
                account = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Euro account",
                    currency_code="EUR",
                )
                rate_snapshot = await finance.create_finance_rate_snapshot(
                    session,
                    captured_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                    entries=[
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="USD",
                            quote_currency="EUR",
                            rate=Decimal("0.8"),
                        )
                    ],
                )

                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    rate_snapshot_id=rate_snapshot.id,
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=account.id,
                            amount=Decimal("8"),
                            currency_code="EUR",
                        )
                    ],
                )

                assert snapshot.rate_snapshot_policy == "selected"
                assert snapshot.net_amount == Decimal("10.00000000")
                assert snapshot.exchange_rates is not None
                assert snapshot.exchange_rates["rates"]["EUR"]["derived"] is True
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_snapshot_uses_chained_rates_and_follows_rate_snapshot_updates() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                assets = next(
                    node
                    for node in await finance.list_finance_nodes(session, tree_id=tree.id)
                    if node.name == "Assets"
                )
                btc = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="BTC",
                    currency_code="BTC",
                )
                cny = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="CNY",
                    currency_code="CNY",
                )
                usdt = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="USDT",
                    currency_code="USDT",
                )
                rate_snapshot = await finance.create_finance_rate_snapshot(
                    session,
                    captured_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                    entries=[
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="BTC",
                            quote_currency="USDT",
                            rate=Decimal("64123.56"),
                        ),
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="USDT",
                            quote_currency="CNY",
                            rate=Decimal("6.6"),
                        ),
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="USDT",
                            quote_currency="USD",
                            rate=Decimal("0.98"),
                        ),
                    ],
                )

                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    rate_snapshot_id=rate_snapshot.id,
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=btc.id,
                            amount=Decimal("0.1"),
                            currency_code="BTC",
                        ),
                        finance.FinanceSnapshotEntryInput(
                            node_id=cny.id,
                            amount=Decimal("660"),
                            currency_code="CNY",
                        ),
                        finance.FinanceSnapshotEntryInput(
                            node_id=usdt.id,
                            amount=Decimal("100"),
                            currency_code="USDT",
                        ),
                    ],
                )

                assert snapshot.summary is not None
                assert snapshot.summary["aggregation_mode"] == "converted"
                assert snapshot.summary["missing_rate_currencies"] == []
                assert snapshot.net_amount == Decimal("6480.10888000")
                assert snapshot.exchange_rates is not None
                assert snapshot.exchange_rates["rates"]["BTC"]["path"] == [
                    "BTC",
                    "USDT",
                    "USD",
                ]
                assert snapshot.exchange_rates["rates"]["BTC"]["derived"] is True
                assert snapshot.exchange_rates["rates"]["CNY"]["path"] == [
                    "CNY",
                    "USDT",
                    "USD",
                ]
                assert snapshot.exchange_rates["rates"]["CNY"]["derived"] is True
                assert snapshot.exchange_rates["rates"]["USDT"]["path"] == ["USDT", "USD"]
                assert snapshot.exchange_rates["rates"]["USDT"]["derived"] is False

                await finance.update_finance_rate_snapshot(
                    session,
                    rate_snapshot_id=rate_snapshot.id,
                    entries=[
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="BTC",
                            quote_currency="USDT",
                            rate=Decimal("1000"),
                        ),
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="USDT",
                            quote_currency="CNY",
                            rate=Decimal("10"),
                        ),
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="USDT",
                            quote_currency="USD",
                            rate=Decimal("2"),
                        ),
                    ],
                    update_entries=True,
                )
                recalculated = await finance.get_finance_snapshot(
                    session,
                    snapshot_id=snapshot.id,
                )
                assert recalculated is not None
                assert recalculated.net_amount == Decimal("532.00000000")
                assert recalculated.summary is not None
                assert recalculated.summary["aggregation_mode"] == "converted"

                await finance.delete_finance_rate_snapshot(
                    session,
                    rate_snapshot_id=rate_snapshot.id,
                )
                cleared = await finance.get_finance_snapshot(
                    session,
                    snapshot_id=snapshot.id,
                )
                assert cleared is not None
                assert cleared.rate_snapshot_id is None
                assert cleared.rate_snapshot_policy == "none"
                assert cleared.net_amount == Decimal("0E-8")
                assert cleared.exchange_rates is None
                assert cleared.summary is not None
                assert cleared.summary["aggregation_mode"] == "native_by_currency"
                assert cleared.summary["amounts_by_currency"]["BTC"]["net_amount"] == "0.10000000"
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_snapshot_with_incomplete_rate_snapshot_keeps_native_totals() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                assets = next(
                    node
                    for node in await finance.list_finance_nodes(session, tree_id=tree.id)
                    if node.name == "Assets"
                )
                account = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Euro account",
                    currency_code="EUR",
                )
                rate_snapshot = await finance.create_finance_rate_snapshot(
                    session,
                    captured_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                    entries=[
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="BTC",
                            quote_currency="USD",
                            rate=Decimal("67000"),
                        )
                    ],
                )

                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    rate_snapshot_id=rate_snapshot.id,
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=account.id,
                            amount=Decimal("8"),
                            currency_code="EUR",
                        )
                    ],
                )

                assert snapshot.rate_snapshot_id == rate_snapshot.id
                assert snapshot.rate_snapshot_policy == "selected"
                assert snapshot.net_amount == Decimal("0E-8")
                assert snapshot.exchange_rates is None
                assert snapshot.summary is not None
                assert snapshot.summary["aggregation_mode"] == "native_by_currency"
                assert snapshot.summary["net_amount"] == "0E-8"
                assert snapshot.summary["missing_rate_currencies"] == ["EUR"]
                assert snapshot.summary["amounts_by_currency"]["EUR"]["net_amount"] == "8.00000000"
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_rate_snapshot_can_be_updated_and_deleted() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                rate_snapshot = await finance.create_finance_rate_snapshot(
                    session,
                    captured_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                    source="manual",
                    note="Initial rates",
                    entries=[
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="BTC",
                            quote_currency="USD",
                            rate=Decimal("67000"),
                        )
                    ],
                )

                updated = await finance.update_finance_rate_snapshot(
                    session,
                    rate_snapshot_id=rate_snapshot.id,
                    captured_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
                    source="import",
                    note="Updated rates",
                    entries=[
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="ETH",
                            quote_currency="USD",
                            rate=Decimal("3500"),
                        )
                    ],
                    update_captured_at=True,
                    update_source=True,
                    update_note=True,
                    update_entries=True,
                )

                assert updated.source == "import"
                assert updated.note == "Updated rates"
                assert len(updated.entries) == 1
                assert updated.entries[0].base_currency == "ETH"
                assert updated.entries[0].quote_currency == "USD"
                assert updated.entries[0].rate == Decimal("3500.000000000000")

                await finance.delete_finance_rate_snapshot(
                    session,
                    rate_snapshot_id=rate_snapshot.id,
                )

                assert (
                    await finance.get_finance_rate_snapshot(
                        session,
                        rate_snapshot_id=rate_snapshot.id,
                    )
                    is None
                )
                assert await finance.count_finance_rate_snapshots(session) == 0
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_snapshot_rate_snapshot_can_be_cleared() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                assets = next(
                    node
                    for node in await finance.list_finance_nodes(session, tree_id=tree.id)
                    if node.name == "Assets"
                )
                account = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Euro account",
                    currency_code="EUR",
                )
                rate_snapshot = await finance.create_finance_rate_snapshot(
                    session,
                    captured_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                    entries=[
                        finance.FinanceRateSnapshotEntryInput(
                            base_currency="EUR",
                            quote_currency="USD",
                            rate=Decimal("2"),
                        )
                    ],
                )
                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    rate_snapshot_id=rate_snapshot.id,
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=account.id,
                            amount=Decimal("10"),
                            currency_code="EUR",
                        )
                    ],
                )
                assert snapshot.net_amount == Decimal("20.00000000")

                updated = await finance.update_finance_snapshot(
                    session,
                    snapshot_id=snapshot.id,
                    rate_snapshot_id=None,
                    update_rate_snapshot=True,
                )

                assert updated.rate_snapshot_id is None
                assert updated.rate_snapshot_policy == "none"
                assert updated.net_amount == Decimal("0E-8")
                assert updated.summary is not None
                assert updated.summary["amounts_by_currency"]["EUR"]["net_amount"] == "10.00000000"
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_snapshot_can_be_updated_and_deleted() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                assets = next(
                    node
                    for node in await finance.list_finance_nodes(session, tree_id=tree.id)
                    if node.name == "Assets"
                )
                salary = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Salary",
                    currency_code="USD",
                )
                snapshot = await finance.create_finance_snapshot(
                    session,
                    tree_id=tree.id,
                    period_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
                    period_end=datetime(2026, 6, 30, tzinfo=timezone.utc),
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=salary.id,
                            amount=Decimal("100"),
                            currency_code="USD",
                        )
                    ],
                )

                updated = await finance.update_finance_snapshot(
                    session,
                    snapshot_id=snapshot.id,
                    period_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
                    period_end=datetime(2026, 7, 31, tzinfo=timezone.utc),
                    note="July cashflow",
                    entries=[
                        finance.FinanceSnapshotEntryInput(
                            node_id=salary.id,
                            amount=Decimal("125"),
                            currency_code="USD",
                            note="Updated salary",
                        )
                    ],
                    update_time_fields=True,
                    update_note=True,
                )

                assert updated.period_start == datetime(2026, 7, 1, tzinfo=timezone.utc)
                assert updated.period_end == datetime(2026, 7, 31, tzinfo=timezone.utc)
                assert updated.note == "July cashflow"
                assert updated.net_amount == Decimal("125.00000000")
                manual_entries = [entry for entry in updated.entries if not entry.is_auto_generated]
                assert len(manual_entries) == 1
                assert manual_entries[0].note == "Updated salary"

                await finance.delete_finance_snapshot(session, snapshot_id=snapshot.id)

                assert await finance.get_finance_snapshot(session, snapshot_id=snapshot.id) is None
                assert await finance.count_finance_snapshots(session, tree_id=tree.id) == 0
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_tree_count_respects_deleted_scope() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                custom_tree = await finance.create_finance_tree(
                    session,
                    name="Planning",
                    primary_currency="USD",
                )
                custom_tree.soft_delete()

                assert await finance.count_finance_trees(session) == 1
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_finance_node_delete_soft_deletes_descendants() -> None:
    async def run() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
            async with session_factory() as session:
                tree = await finance.ensure_default_finance_tree(
                    session,
                    primary_currency="USD",
                )
                nodes = await finance.list_finance_nodes(session, tree_id=tree.id)
                assets = next(node for node in nodes if node.name == "Assets")
                bank = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=assets.id,
                    name="Bank",
                )
                checking = await finance.create_finance_node(
                    session,
                    tree_id=tree.id,
                    parent_id=bank.id,
                    name="Checking",
                )

                await finance.delete_finance_node(session, node_id=bank.id)
                remaining = await finance.list_finance_nodes(session, tree_id=tree.id)

                assert {node.id for node in remaining}.isdisjoint({bank.id, checking.id})
                assert next(node for node in remaining if node.id == assets.id).children_count == 0
        finally:
            await engine.dispose()

    asyncio.run(run())
