"""Unified finance tree and snapshot services."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lifeos_cli.application.time_preferences import to_storage_timezone
from lifeos_cli.db.base import utc_now
from lifeos_cli.db.models.finance import (
    FinanceAsset,
    FinanceRateSnapshot,
    FinanceRateSnapshotEntry,
    FinanceSnapshot,
    FinanceSnapshotEntry,
    FinanceTree,
    FinanceTreeNode,
)

DEFAULT_FINANCE_CURRENCY = "USD"
DEFAULT_FINANCE_ASSET_DECIMAL_PLACES = 2
MAX_FINANCE_ASSET_DECIMAL_PLACES = 8
DEFAULT_FINANCE_ASSETS: tuple[tuple[str, str, int], ...] = (
    ("USD", "US Dollar", 10),
    ("USDT", "Tether USD", 20),
    ("CNY", "Chinese Yuan", 30),
    ("BTC", "Bitcoin", 40),
    ("ETH", "Ethereum", 50),
    ("EUR", "Euro", 60),
)
FINANCE_AMOUNT_QUANT = Decimal("0.00000001")
FINANCE_RATE_QUANT = Decimal("0.000000000001")


def _finance_tree_nodes_loader() -> Any:
    return selectinload(FinanceTree.nodes.and_(FinanceTreeNode.deleted_at.is_(None)))


def _finance_node_tree_loader() -> Any:
    return selectinload(FinanceTreeNode.tree.and_(FinanceTree.deleted_at.is_(None)))


def _finance_node_children_loader() -> Any:
    return selectinload(FinanceTreeNode.children.and_(FinanceTreeNode.deleted_at.is_(None)))


def _finance_rate_entries_loader() -> Any:
    return selectinload(
        FinanceRateSnapshot.entries.and_(FinanceRateSnapshotEntry.deleted_at.is_(None))
    )


def _finance_snapshot_tree_loader() -> Any:
    return selectinload(FinanceSnapshot.tree.and_(FinanceTree.deleted_at.is_(None)))


def _finance_snapshot_rate_loader() -> Any:
    return selectinload(
        FinanceSnapshot.rate_snapshot.and_(FinanceRateSnapshot.deleted_at.is_(None))
    )


def _finance_snapshot_entries_loader() -> Any:
    entries = selectinload(FinanceSnapshot.entries.and_(FinanceSnapshotEntry.deleted_at.is_(None)))
    return entries.selectinload(
        FinanceSnapshotEntry.node.and_(FinanceTreeNode.deleted_at.is_(None))
    )


class FinanceValidationError(ValueError):
    """Raised when finance input is invalid."""


class FinanceTreeNotFoundError(LookupError):
    """Raised when a finance tree cannot be found."""


class FinanceTreeAlreadyExistsError(ValueError):
    """Raised when a finance tree name is already used."""


class FinanceTreeNodeNotFoundError(LookupError):
    """Raised when a finance tree node cannot be found."""


class FinanceTreeNodeAlreadyExistsError(ValueError):
    """Raised when a sibling finance node has the same name."""


class FinanceRateSnapshotNotFoundError(LookupError):
    """Raised when a finance rate snapshot cannot be found."""


class FinanceAssetNotFoundError(LookupError):
    """Raised when a finance asset cannot be found."""


class FinanceAssetAlreadyExistsError(ValueError):
    """Raised when a finance asset code is already active."""


@dataclass(frozen=True)
class FinanceSnapshotEntryInput:
    """Writable fields for a finance snapshot entry."""

    node_id: UUID
    amount: Decimal
    currency_code: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class FinanceRateSnapshotEntryInput:
    """Writable fields for one exchange-rate snapshot entry."""

    base_currency: str
    quote_currency: str
    rate: Decimal
    source: str | None = None
    captured_at: datetime | None = None
    is_derived: bool = False
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class RateResolution:
    """Resolved conversion rate with auditable source path metadata."""

    rate: Decimal
    derived: bool
    source_entries: tuple[FinanceRateSnapshotEntry, ...]
    path: tuple[str, ...]
    source_pairs: tuple[str, ...]


def normalize_currency_code(currency_code: str | None, *, fallback: str | None = None) -> str:
    """Normalize a currency or asset code."""
    candidate = currency_code if currency_code is not None else fallback
    if candidate is None:
        candidate = DEFAULT_FINANCE_CURRENCY
    normalized = candidate.strip().upper()
    if not normalized:
        raise FinanceValidationError("Currency code must not be empty")
    if len(normalized) > 16:
        raise FinanceValidationError("Currency code must be 16 characters or fewer")
    return normalized


def validate_asset_name(name: str | None) -> str | None:
    """Validate and normalize an optional finance asset display name."""
    if name is None:
        return None
    normalized = name.strip()
    if not normalized:
        return None
    if len(normalized) > 200:
        raise FinanceValidationError("Finance asset name must be 200 characters or fewer")
    return normalized


def validate_asset_decimal_places(decimal_places: int | None = None) -> int:
    """Validate asset display and input precision."""
    resolved = DEFAULT_FINANCE_ASSET_DECIMAL_PLACES if decimal_places is None else decimal_places
    if resolved < 0 or resolved > MAX_FINANCE_ASSET_DECIMAL_PLACES:
        raise FinanceValidationError("Finance asset decimal places must be between 0 and 8")
    return resolved


def decimal_quant_for_places(decimal_places: int) -> Decimal:
    """Return the Decimal quantum for a given number of fractional places."""
    if decimal_places <= 0:
        return Decimal("1")
    return Decimal("1").scaleb(-decimal_places)


def format_decimal_places(value: Decimal, decimal_places: int) -> str:
    """Format a decimal with fixed places and no scientific notation."""
    return format(value.quantize(decimal_quant_for_places(decimal_places)), "f")


def format_asset_amount(
    value: Decimal,
    *,
    currency_code: str | None,
    decimal_places_by_code: dict[str, int] | None = None,
) -> str:
    """Format an amount using the precision configured for its asset."""
    normalized = normalize_currency_code(currency_code)
    decimal_places = (decimal_places_by_code or {}).get(
        normalized,
        DEFAULT_FINANCE_ASSET_DECIMAL_PLACES,
    )
    return format_decimal_places(value, decimal_places)


async def ensure_default_finance_assets(session: AsyncSession) -> None:
    """Create built-in assets only when the code has never existed."""
    existing_codes = set((await session.execute(select(FinanceAsset.code))).scalars().all())
    for code, name, display_order in DEFAULT_FINANCE_ASSETS:
        if code in existing_codes:
            continue
        session.add(
            FinanceAsset(
                code=code,
                name=name,
                decimal_places=DEFAULT_FINANCE_ASSET_DECIMAL_PLACES,
                display_order=display_order,
                is_default=True,
            )
        )
    await session.flush()


async def list_finance_assets(
    session: AsyncSession,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[FinanceAsset]:
    """List finance assets."""
    await ensure_default_finance_assets(session)
    stmt = select(FinanceAsset)
    stmt = stmt.where(FinanceAsset.deleted_at.is_(None))
    stmt = stmt.order_by(FinanceAsset.display_order.asc(), FinanceAsset.code.asc())
    stmt = stmt.offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars())


async def count_finance_assets(
    session: AsyncSession,
) -> int:
    """Count finance assets."""
    await ensure_default_finance_assets(session)
    stmt = select(func.count()).select_from(FinanceAsset)
    stmt = stmt.where(FinanceAsset.deleted_at.is_(None))
    return int((await session.execute(stmt)).scalar_one())


async def create_finance_asset(
    session: AsyncSession,
    *,
    code: str,
    name: str | None = None,
    decimal_places: int | None = None,
    display_order: int = 1000,
    is_default: bool = False,
    metadata: dict[str, Any] | None = None,
) -> FinanceAsset:
    """Create a selectable finance asset."""
    resolved_code = normalize_currency_code(code)
    existing = (
        await session.execute(
            select(FinanceAsset.id).where(
                FinanceAsset.code == resolved_code,
                FinanceAsset.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise FinanceAssetAlreadyExistsError(f"Finance asset {resolved_code!r} already exists")
    asset = FinanceAsset(
        code=resolved_code,
        name=validate_asset_name(name),
        decimal_places=validate_asset_decimal_places(decimal_places),
        display_order=display_order,
        is_default=is_default,
        metadata_json=metadata,
    )
    session.add(asset)
    await session.flush()
    await session.refresh(asset)
    return asset


async def update_finance_asset(
    session: AsyncSession,
    *,
    asset_id: UUID,
    code: str | None = None,
    name: str | None = None,
    decimal_places: int | None = None,
    display_order: int | None = None,
) -> FinanceAsset:
    """Update a finance asset."""
    asset = (
        await session.execute(
            select(FinanceAsset).where(
                FinanceAsset.id == asset_id,
                FinanceAsset.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if asset is None:
        raise FinanceAssetNotFoundError(f"Finance asset {asset_id} was not found")
    if code is not None:
        resolved_code = normalize_currency_code(code)
        existing = (
            await session.execute(
                select(FinanceAsset.id).where(
                    FinanceAsset.code == resolved_code,
                    FinanceAsset.deleted_at.is_(None),
                    FinanceAsset.id != asset.id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise FinanceAssetAlreadyExistsError(f"Finance asset {resolved_code!r} already exists")
        asset.code = resolved_code
    if name is not None:
        asset.name = validate_asset_name(name)
    if decimal_places is not None:
        asset.decimal_places = validate_asset_decimal_places(decimal_places)
    if display_order is not None:
        asset.display_order = display_order
    await session.flush()
    await session.refresh(asset)
    return asset


async def delete_finance_asset(session: AsyncSession, *, asset_id: UUID) -> None:
    """Soft-delete one finance asset."""
    asset = (
        await session.execute(
            select(FinanceAsset).where(
                FinanceAsset.id == asset_id,
                FinanceAsset.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if asset is None:
        raise FinanceAssetNotFoundError(f"Finance asset {asset_id} was not found")
    asset.soft_delete()


def validate_tree_name(name: str) -> str:
    """Validate and normalize a finance tree name."""
    normalized = name.strip()
    if not normalized:
        raise FinanceValidationError("Finance tree name must not be empty")
    if len(normalized) > 200:
        raise FinanceValidationError("Finance tree name must be 200 characters or fewer")
    return normalized


def validate_node_name(name: str) -> str:
    """Validate and normalize a finance node name."""
    normalized = name.strip()
    if not normalized:
        raise FinanceValidationError("Finance node name must not be empty")
    if len(normalized) > 200:
        raise FinanceValidationError("Finance node name must be 200 characters or fewer")
    return normalized


def validate_snapshot_title(title: str | None) -> str | None:
    """Validate and normalize an optional finance snapshot display title."""
    if title is None:
        return None
    normalized = title.strip()
    if not normalized:
        return None
    if len(normalized) > 200:
        raise FinanceValidationError("Finance snapshot title must be 200 characters or fewer")
    return normalized


async def _ensure_tree_name_available(
    session: AsyncSession,
    *,
    name: str,
    excluding_tree_id: UUID | None = None,
) -> None:
    stmt = select(FinanceTree.id).where(
        FinanceTree.name == name,
        FinanceTree.deleted_at.is_(None),
    )
    if excluding_tree_id is not None:
        stmt = stmt.where(FinanceTree.id != excluding_tree_id)
    existing_id = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if existing_id is not None:
        raise FinanceTreeAlreadyExistsError(f"Finance tree named {name!r} already exists")


async def _ensure_node_name_available(
    session: AsyncSession,
    *,
    tree_id: UUID,
    parent_id: UUID | None,
    name: str,
    excluding_node_id: UUID | None = None,
) -> None:
    stmt = select(FinanceTreeNode.id).where(
        FinanceTreeNode.tree_id == tree_id,
        FinanceTreeNode.name == name,
        FinanceTreeNode.deleted_at.is_(None),
    )
    stmt = stmt.where(
        FinanceTreeNode.parent_id.is_(None)
        if parent_id is None
        else FinanceTreeNode.parent_id == parent_id
    )
    if excluding_node_id is not None:
        stmt = stmt.where(FinanceTreeNode.id != excluding_node_id)
    existing_id = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if existing_id is not None:
        raise FinanceTreeNodeAlreadyExistsError(
            f"Finance node named {name!r} already exists under this parent"
        )


async def get_finance_tree(
    session: AsyncSession,
    *,
    tree_id: UUID,
) -> FinanceTree | None:
    """Load one finance tree."""
    stmt = select(FinanceTree).where(FinanceTree.id == tree_id).limit(1)
    stmt = stmt.where(FinanceTree.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_finance_tree_with_nodes(
    session: AsyncSession,
    *,
    tree_id: UUID,
) -> FinanceTree | None:
    """Load one finance tree with all nodes."""
    stmt = (
        select(FinanceTree)
        .options(_finance_tree_nodes_loader())
        .where(FinanceTree.id == tree_id)
        .limit(1)
    )
    stmt = stmt.where(FinanceTree.deleted_at.is_(None))
    tree = (await session.execute(stmt)).scalar_one_or_none()
    if tree is None:
        return None
    return tree


async def list_finance_trees(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[FinanceTree]:
    """List finance trees."""
    stmt = select(FinanceTree)
    stmt = stmt.where(FinanceTree.deleted_at.is_(None))
    stmt = (
        stmt.order_by(
            FinanceTree.display_order.asc(),
            FinanceTree.name.asc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())


async def count_finance_trees(
    session: AsyncSession,
) -> int:
    """Count finance trees."""
    stmt = select(func.count()).select_from(FinanceTree)
    stmt = stmt.where(FinanceTree.deleted_at.is_(None))
    return int((await session.execute(stmt)).scalar_one())


async def _clear_other_defaults(
    session: AsyncSession,
    *,
    default_tree: FinanceTree,
) -> None:
    stmt = select(FinanceTree).where(
        FinanceTree.deleted_at.is_(None),
        FinanceTree.is_default.is_(True),
    )
    for tree in (await session.execute(stmt)).scalars():
        if tree is not default_tree:
            tree.is_default = False


async def create_finance_tree(
    session: AsyncSession,
    *,
    name: str,
    primary_currency: str | None = None,
    display_order: int = 0,
    is_default: bool = False,
    metadata: dict[str, Any] | None = None,
) -> FinanceTree:
    """Create a finance tree."""
    resolved_name = validate_tree_name(name)
    await _ensure_tree_name_available(session, name=resolved_name)
    tree = FinanceTree(
        name=resolved_name,
        primary_currency=normalize_currency_code(primary_currency),
        display_order=display_order,
        is_default=is_default,
        metadata_json=metadata,
    )
    session.add(tree)
    if is_default:
        await _clear_other_defaults(session, default_tree=tree)
    await session.flush()
    await session.refresh(tree)
    return tree


async def update_finance_tree(
    session: AsyncSession,
    *,
    tree_id: UUID,
    name: str | None = None,
    primary_currency: str | None = None,
    display_order: int | None = None,
    is_default: bool | None = None,
    metadata: dict[str, Any] | None = None,
    update_metadata: bool = False,
) -> FinanceTree:
    """Update mutable finance tree fields."""
    tree = await get_finance_tree(session, tree_id=tree_id)
    if tree is None:
        raise FinanceTreeNotFoundError(f"Finance tree {tree_id} was not found")

    if name is not None:
        resolved_name = validate_tree_name(name)
        if resolved_name != tree.name:
            await _ensure_tree_name_available(
                session,
                name=resolved_name,
                excluding_tree_id=tree.id,
            )
            tree.name = resolved_name
    if primary_currency is not None:
        tree.primary_currency = normalize_currency_code(primary_currency)
    if display_order is not None:
        tree.display_order = display_order
    if is_default is not None:
        tree.is_default = is_default
        if is_default:
            await _clear_other_defaults(session, default_tree=tree)
    if update_metadata:
        tree.metadata_json = metadata

    await session.flush()
    await session.refresh(tree)
    return tree


async def delete_finance_tree(
    session: AsyncSession,
    *,
    tree_id: UUID,
) -> None:
    """Soft-delete a finance tree that has no active snapshots."""
    tree = await get_finance_tree_with_nodes(session, tree_id=tree_id)
    if tree is None:
        raise FinanceTreeNotFoundError(f"Finance tree {tree_id} was not found")
    if await count_finance_snapshots(session, tree_id=tree.id):
        raise FinanceValidationError("Finance tree cannot be deleted while it has snapshots")
    for node in tree.nodes:
        node.soft_delete()
    tree.soft_delete()
    await session.flush()


async def _get_node_model(
    session: AsyncSession,
    *,
    node_id: UUID,
) -> FinanceTreeNode | None:
    stmt = (
        select(FinanceTreeNode)
        .options(
            _finance_node_tree_loader(),
            _finance_node_children_loader(),
        )
        .where(FinanceTreeNode.id == node_id)
        .limit(1)
    )
    stmt = stmt.where(FinanceTreeNode.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_finance_nodes(
    session: AsyncSession,
    *,
    tree_id: UUID,
) -> list[FinanceTreeNode]:
    """List finance nodes for one tree in tree order."""
    stmt = select(FinanceTreeNode).where(FinanceTreeNode.tree_id == tree_id)
    stmt = stmt.where(FinanceTreeNode.deleted_at.is_(None))
    stmt = stmt.order_by(FinanceTreeNode.path.asc(), FinanceTreeNode.display_order.asc())
    return list((await session.execute(stmt)).scalars())


async def create_finance_node(
    session: AsyncSession,
    *,
    tree_id: UUID,
    name: str,
    parent_id: UUID | None = None,
    currency_code: str | None = None,
    display_order: int = 0,
    metadata: dict[str, Any] | None = None,
) -> FinanceTreeNode:
    """Create a finance tree node."""
    tree = await get_finance_tree(session, tree_id=tree_id)
    if tree is None:
        raise FinanceTreeNotFoundError(f"Finance tree {tree_id} was not found")
    parent: FinanceTreeNode | None = None
    if parent_id is not None:
        parent = await _get_node_model(session, node_id=parent_id)
        if parent is None or parent.tree_id != tree_id:
            raise FinanceTreeNodeNotFoundError(f"Finance parent node {parent_id} was not found")
    resolved_name = validate_node_name(name)
    await _ensure_node_name_available(
        session,
        tree_id=tree_id,
        parent_id=parent_id,
        name=resolved_name,
    )
    node = FinanceTreeNode(
        tree_id=tree_id,
        parent_id=parent_id,
        name=resolved_name,
        currency_code=normalize_currency_code(currency_code, fallback=tree.primary_currency),
        depth=0 if parent is None else parent.depth + 1,
        display_order=display_order,
        metadata_json=metadata,
        path="pending",
    )
    session.add(node)
    await session.flush()
    node.path = str(node.id) if parent is None else f"{parent.path}/{node.id}"
    if parent is not None:
        parent.children_count += 1
    await session.flush()
    await session.refresh(node)
    return node


async def update_finance_node(
    session: AsyncSession,
    *,
    node_id: UUID,
    name: str | None = None,
    currency_code: str | None = None,
    display_order: int | None = None,
) -> FinanceTreeNode:
    """Update mutable finance node fields."""
    node = await _get_node_model(session, node_id=node_id)
    if node is None:
        raise FinanceTreeNodeNotFoundError(f"Finance node {node_id} was not found")
    if name is not None:
        resolved_name = validate_node_name(name)
        await _ensure_node_name_available(
            session,
            tree_id=node.tree_id,
            parent_id=node.parent_id,
            name=resolved_name,
            excluding_node_id=node.id,
        )
        node.name = resolved_name
    if currency_code is not None:
        node.currency_code = normalize_currency_code(currency_code)
    if display_order is not None:
        node.display_order = display_order
    await session.flush()
    await session.refresh(node)
    return node


async def delete_finance_node(session: AsyncSession, *, node_id: UUID) -> None:
    """Soft-delete a finance node and its descendants."""
    node = await _get_node_model(session, node_id=node_id)
    if node is None:
        raise FinanceTreeNodeNotFoundError(f"Finance node {node_id} was not found")
    descendant_stmt = select(FinanceTreeNode).where(
        FinanceTreeNode.tree_id == node.tree_id,
        FinanceTreeNode.path.startswith(f"{node.path}/"),
        FinanceTreeNode.deleted_at.is_(None),
    )
    descendants = list((await session.scalars(descendant_stmt)).all())
    for descendant in descendants:
        descendant.soft_delete()
    node.soft_delete()
    if node.parent_id is not None:
        parent = await _get_node_model(session, node_id=node.parent_id)
        if parent is not None and parent.children_count > 0:
            parent.children_count -= 1


def _validate_snapshot_time_fields(
    *,
    snapshot_ts: datetime | None,
    period_start: datetime | None,
    period_end: datetime | None,
) -> tuple[datetime | None, datetime | None, datetime | None]:
    normalized_snapshot_ts = to_storage_timezone(snapshot_ts) if snapshot_ts is not None else None
    normalized_period_start = (
        to_storage_timezone(period_start) if period_start is not None else None
    )
    normalized_period_end = to_storage_timezone(period_end) if period_end is not None else None
    has_period_start = normalized_period_start is not None
    has_period_end = normalized_period_end is not None
    if has_period_start or has_period_end:
        if normalized_period_start is None or normalized_period_end is None:
            raise FinanceValidationError(
                "Period finance snapshots require period_start and period_end"
            )
        if normalized_period_end < normalized_period_start:
            raise FinanceValidationError("Finance snapshot period_end must be after period_start")
        return (
            normalized_snapshot_ts or utc_now(),
            normalized_period_start,
            normalized_period_end,
        )
    return normalized_snapshot_ts or utc_now(), None, None


async def _load_entry_nodes(
    session: AsyncSession,
    *,
    tree_id: UUID,
    entries: list[FinanceSnapshotEntryInput],
) -> dict[UUID, FinanceTreeNode]:
    if not entries:
        raise FinanceValidationError("Finance snapshot requires at least one entry")
    node_ids = [entry.node_id for entry in entries]
    stmt = select(FinanceTreeNode).where(
        FinanceTreeNode.id.in_(set(node_ids)),
        FinanceTreeNode.tree_id == tree_id,
        FinanceTreeNode.deleted_at.is_(None),
    )
    nodes = {node.id: node for node in (await session.execute(stmt)).scalars()}
    missing = sorted(str(node_id) for node_id in set(node_ids) - set(nodes))
    if missing:
        raise FinanceTreeNodeNotFoundError(f"Finance nodes were not found: {', '.join(missing)}")
    return nodes


async def _load_rollup_nodes(
    session: AsyncSession,
    *,
    tree_id: UUID,
) -> list[FinanceTreeNode]:
    stmt = (
        select(FinanceTreeNode)
        .where(
            FinanceTreeNode.tree_id == tree_id,
            FinanceTreeNode.children_count > 0,
            FinanceTreeNode.deleted_at.is_(None),
        )
        .order_by(FinanceTreeNode.depth.desc())
    )
    return list((await session.execute(stmt)).scalars())


def _decimal(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _quantize_amount(value: Decimal) -> Decimal:
    return value.quantize(FINANCE_AMOUNT_QUANT, rounding=ROUND_HALF_UP)


def _validate_amount_precision(
    value: Decimal,
    *,
    currency_code: str,
    decimal_places: int,
) -> Decimal:
    quantum = decimal_quant_for_places(decimal_places)
    quantized = value.quantize(quantum, rounding=ROUND_HALF_UP)
    if value != quantized:
        raise FinanceValidationError(
            f"Finance amount for {currency_code} supports at most {decimal_places} decimal places"
        )
    return quantized


async def _load_asset_decimal_places(
    session: AsyncSession,
    *,
    currency_codes: set[str],
) -> dict[str, int]:
    if not currency_codes:
        return {}
    stmt = select(FinanceAsset).where(
        FinanceAsset.code.in_(currency_codes),
        FinanceAsset.deleted_at.is_(None),
    )
    return {
        asset.code: validate_asset_decimal_places(asset.decimal_places)
        for asset in (await session.execute(stmt)).scalars()
    }


def _format_rate(value: Decimal) -> str:
    return str(value.quantize(FINANCE_RATE_QUANT, rounding=ROUND_HALF_UP))


def _validate_rate(value: Decimal | int | str) -> Decimal:
    rate = _decimal(value)
    if rate <= 0:
        raise FinanceValidationError("Exchange rate must be greater than zero")
    return rate


def _rate_snapshot_source(source: str | None) -> str:
    resolved = (source or "manual").strip().lower()
    if not resolved:
        raise FinanceValidationError("Finance rate snapshot source must not be empty")
    if len(resolved) > 64:
        raise FinanceValidationError("Finance rate snapshot source must be 64 characters or fewer")
    return resolved


async def create_finance_rate_snapshot(
    session: AsyncSession,
    *,
    captured_at: datetime | None = None,
    source: str | None = None,
    note: str | None = None,
    entries: list[FinanceRateSnapshotEntryInput],
    metadata: dict[str, Any] | None = None,
) -> FinanceRateSnapshot:
    """Create one exchange-rate snapshot."""
    if not entries:
        raise FinanceValidationError("Finance rate snapshot requires at least one rate entry")
    resolved_captured_at = (
        to_storage_timezone(captured_at) if captured_at is not None else utc_now()
    )
    rate_snapshot = FinanceRateSnapshot(
        captured_at=resolved_captured_at,
        source=_rate_snapshot_source(source),
        note=note,
        metadata_json=metadata,
    )
    session.add(rate_snapshot)
    await session.flush()

    await _create_finance_rate_snapshot_entries(
        session,
        rate_snapshot=rate_snapshot,
        entries=entries,
    )

    await session.flush()
    await session.refresh(rate_snapshot)
    reloaded = await get_finance_rate_snapshot(session, rate_snapshot_id=rate_snapshot.id)
    return reloaded or rate_snapshot


async def _create_finance_rate_snapshot_entries(
    session: AsyncSession,
    *,
    rate_snapshot: FinanceRateSnapshot,
    entries: list[FinanceRateSnapshotEntryInput],
) -> None:
    """Add validated rate entries to one exchange-rate snapshot."""
    seen_pairs: set[tuple[str, str]] = set()
    for entry_input in entries:
        base_currency = normalize_currency_code(entry_input.base_currency)
        quote_currency = normalize_currency_code(entry_input.quote_currency)
        if base_currency == quote_currency:
            raise FinanceValidationError("Exchange-rate pair assets must be different")
        pair = (base_currency, quote_currency)
        if pair in seen_pairs:
            raise FinanceValidationError(
                f"Duplicate exchange-rate pair: {base_currency}/{quote_currency}"
            )
        seen_pairs.add(pair)
        rate_entry = FinanceRateSnapshotEntry(
            rate_snapshot_id=rate_snapshot.id,
            base_currency=base_currency,
            quote_currency=quote_currency,
            rate=_validate_rate(entry_input.rate),
            source=entry_input.source,
            captured_at=(
                to_storage_timezone(entry_input.captured_at)
                if entry_input.captured_at is not None
                else None
            ),
            is_derived=entry_input.is_derived,
            metadata_json=entry_input.metadata,
        )
        session.add(rate_entry)


async def get_finance_rate_snapshot(
    session: AsyncSession,
    *,
    rate_snapshot_id: UUID,
) -> FinanceRateSnapshot | None:
    """Load one finance rate snapshot with entries."""
    stmt = (
        select(FinanceRateSnapshot)
        .options(_finance_rate_entries_loader())
        .where(FinanceRateSnapshot.id == rate_snapshot_id)
        .limit(1)
    )
    stmt = stmt.where(FinanceRateSnapshot.deleted_at.is_(None))
    rate_snapshot = (await session.execute(stmt)).scalar_one_or_none()
    if rate_snapshot is None:
        return None
    return rate_snapshot


async def list_finance_rate_snapshots(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[FinanceRateSnapshot]:
    """List exchange-rate snapshots."""
    stmt = select(FinanceRateSnapshot).options(_finance_rate_entries_loader())
    stmt = stmt.where(FinanceRateSnapshot.deleted_at.is_(None))
    stmt = (
        stmt.order_by(
            FinanceRateSnapshot.captured_at.desc(),
            FinanceRateSnapshot.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())


async def count_finance_rate_snapshots(
    session: AsyncSession,
) -> int:
    """Count exchange-rate snapshots."""
    stmt = select(func.count()).select_from(FinanceRateSnapshot)
    stmt = stmt.where(FinanceRateSnapshot.deleted_at.is_(None))
    return int((await session.execute(stmt)).scalar_one())


async def update_finance_rate_snapshot(
    session: AsyncSession,
    *,
    rate_snapshot_id: UUID,
    captured_at: datetime | None = None,
    source: str | None = None,
    note: str | None = None,
    entries: list[FinanceRateSnapshotEntryInput] | None = None,
    metadata: dict[str, Any] | None = None,
    update_captured_at: bool = False,
    update_source: bool = False,
    update_note: bool = False,
    update_entries: bool = False,
    update_metadata: bool = False,
) -> FinanceRateSnapshot:
    """Update one exchange-rate snapshot and optionally replace its entries."""
    rate_snapshot = await get_finance_rate_snapshot(
        session,
        rate_snapshot_id=rate_snapshot_id,
    )
    if rate_snapshot is None:
        raise FinanceRateSnapshotNotFoundError(
            f"Finance rate snapshot {rate_snapshot_id} was not found"
        )

    if update_captured_at:
        rate_snapshot.captured_at = (
            to_storage_timezone(captured_at) if captured_at is not None else utc_now()
        )
    if update_source:
        rate_snapshot.source = _rate_snapshot_source(source)
    if update_note:
        rate_snapshot.note = note
    if update_metadata:
        rate_snapshot.metadata_json = metadata

    if update_entries:
        if entries is None or not entries:
            raise FinanceValidationError("Finance rate snapshot requires at least one rate entry")
        for entry in rate_snapshot.entries:
            if entry.deleted_at is None:
                entry.soft_delete()
        await session.flush()
        await _create_finance_rate_snapshot_entries(
            session,
            rate_snapshot=rate_snapshot,
            entries=entries,
        )

    await session.flush()
    session.expire(rate_snapshot, ["entries"])
    reloaded = await get_finance_rate_snapshot(session, rate_snapshot_id=rate_snapshot.id)
    resolved_rate_snapshot = reloaded or rate_snapshot
    await _recalculate_finance_snapshots_for_rate_snapshot(
        session,
        rate_snapshot=resolved_rate_snapshot,
    )
    refreshed = await get_finance_rate_snapshot(session, rate_snapshot_id=rate_snapshot.id)
    return refreshed or resolved_rate_snapshot


async def delete_finance_rate_snapshot(
    session: AsyncSession,
    *,
    rate_snapshot_id: UUID,
) -> None:
    """Soft-delete an exchange-rate snapshot and its entries."""
    rate_snapshot = await get_finance_rate_snapshot(
        session,
        rate_snapshot_id=rate_snapshot_id,
    )
    if rate_snapshot is None:
        raise FinanceRateSnapshotNotFoundError(
            f"Finance rate snapshot {rate_snapshot_id} was not found"
        )
    await _recalculate_finance_snapshots_for_rate_snapshot(
        session,
        rate_snapshot=rate_snapshot,
        clear_rate_snapshot=True,
    )
    for entry in rate_snapshot.entries:
        if entry.deleted_at is None:
            entry.soft_delete()
    rate_snapshot.soft_delete()
    await session.flush()


def _manual_snapshot_entry_inputs(snapshot: FinanceSnapshot) -> list[FinanceSnapshotEntryInput]:
    return [
        FinanceSnapshotEntryInput(
            node_id=entry.node_id,
            amount=entry.amount,
            currency_code=entry.currency_code,
            note=entry.note,
        )
        for entry in sorted(snapshot.entries, key=lambda item: item.created_at)
        if entry.deleted_at is None and not entry.is_auto_generated
    ]


async def _recalculate_finance_snapshots_for_rate_snapshot(
    session: AsyncSession,
    *,
    rate_snapshot: FinanceRateSnapshot,
    clear_rate_snapshot: bool = False,
) -> None:
    """Recompute snapshots that are linked to a changed exchange-rate snapshot."""
    stmt = (
        select(FinanceSnapshot)
        .options(
            _finance_snapshot_entries_loader(),
            _finance_snapshot_tree_loader(),
        )
        .where(
            FinanceSnapshot.rate_snapshot_id == rate_snapshot.id,
            FinanceSnapshot.deleted_at.is_(None),
        )
        .order_by(FinanceSnapshot.created_at.asc())
    )
    snapshots = list((await session.execute(stmt)).scalars())
    for snapshot in snapshots:
        tree = snapshot.tree or await get_finance_tree(session, tree_id=snapshot.tree_id)
        if tree is None:
            raise FinanceTreeNotFoundError(f"Finance tree {snapshot.tree_id} was not found")
        if clear_rate_snapshot:
            snapshot.rate_snapshot_id = None
            snapshot.rate_snapshot_policy = "none"
            selected_rate_snapshot = None
        else:
            snapshot.rate_snapshot_id = rate_snapshot.id
            snapshot.rate_snapshot_policy = "selected"
            selected_rate_snapshot = rate_snapshot
        await _rebuild_finance_snapshot_entries(
            session,
            snapshot=snapshot,
            tree=tree,
            entries=_manual_snapshot_entry_inputs(snapshot),
            rate_snapshot=selected_rate_snapshot,
        )


def _active_rate_entries(rate_snapshot: FinanceRateSnapshot) -> list[FinanceRateSnapshotEntry]:
    return sorted(
        (entry for entry in rate_snapshot.entries if entry.deleted_at is None),
        key=lambda entry: (
            entry.base_currency,
            entry.quote_currency,
            entry.created_at,
            str(entry.id),
        ),
    )


def _resolve_rate(
    rate_snapshot: FinanceRateSnapshot | None,
    *,
    base_currency: str,
    quote_currency: str,
) -> RateResolution:
    base = normalize_currency_code(base_currency)
    quote = normalize_currency_code(quote_currency)
    if base == quote:
        return RateResolution(
            rate=Decimal("1"),
            derived=False,
            source_entries=(),
            path=(base,),
            source_pairs=(),
        )
    if rate_snapshot is None:
        raise FinanceValidationError(
            f"Finance snapshot requires a rate snapshot for {base}/{quote}"
        )

    graph: dict[
        str,
        list[tuple[str, Decimal, bool, FinanceRateSnapshotEntry, str]],
    ] = {}
    for entry in _active_rate_entries(rate_snapshot):
        rate = _validate_rate(entry.rate)
        entry_base = normalize_currency_code(entry.base_currency)
        entry_quote = normalize_currency_code(entry.quote_currency)
        graph.setdefault(entry_base, []).append(
            (entry_quote, rate, False, entry, f"{entry_base}/{entry_quote}")
        )
        graph.setdefault(entry_quote, []).append(
            (entry_base, Decimal("1") / rate, True, entry, f"{entry_quote}/{entry_base}")
        )

    queue: deque[
        tuple[
            str,
            Decimal,
            tuple[FinanceRateSnapshotEntry, ...],
            tuple[str, ...],
            tuple[str, ...],
            bool,
        ]
    ] = deque([(base, Decimal("1"), (), (), (base,), False)])
    visited = {base}

    while queue:
        currency, rate, source_entries, source_pairs, path, uses_inverse = queue.popleft()
        for next_currency, edge_rate, edge_inverse, source_entry, source_pair in sorted(
            graph.get(currency, []),
            key=lambda edge: (edge[2], edge[0], edge[4]),
        ):
            if next_currency in visited:
                continue
            next_rate = rate * edge_rate
            next_source_entries = source_entries + (source_entry,)
            next_source_pairs = source_pairs + (source_pair,)
            next_path = path + (next_currency,)
            next_uses_inverse = uses_inverse or edge_inverse
            if next_currency == quote:
                return RateResolution(
                    rate=next_rate,
                    derived=next_uses_inverse or len(next_source_entries) > 1,
                    source_entries=next_source_entries,
                    path=next_path,
                    source_pairs=next_source_pairs,
                )
            visited.add(next_currency)
            queue.append(
                (
                    next_currency,
                    next_rate,
                    next_source_entries,
                    next_source_pairs,
                    next_path,
                    next_uses_inverse,
                )
            )

    raise FinanceValidationError(
        f"Rate snapshot {rate_snapshot.id} does not include a path for {base}/{quote}"
    )


def _find_rate(
    rate_snapshot: FinanceRateSnapshot,
    *,
    base_currency: str,
    quote_currency: str,
) -> RateResolution | None:
    try:
        return _resolve_rate(
            rate_snapshot,
            base_currency=base_currency,
            quote_currency=quote_currency,
        )
    except FinanceValidationError:
        return None


async def _select_rate_snapshot_for_entries(
    session: AsyncSession,
    *,
    explicit_rate_snapshot_id: UUID | None,
) -> tuple[FinanceRateSnapshot | None, str]:
    if explicit_rate_snapshot_id is not None:
        rate_snapshot = await get_finance_rate_snapshot(
            session,
            rate_snapshot_id=explicit_rate_snapshot_id,
        )
        if rate_snapshot is None:
            raise FinanceRateSnapshotNotFoundError(
                f"Finance rate snapshot {explicit_rate_snapshot_id} was not found"
            )
        return rate_snapshot, "selected"
    return None, "none"


def _rate_usage_payload(
    *,
    primary_currency: str,
    rate_snapshot: FinanceRateSnapshot | None,
    used_rates: dict[str, RateResolution],
) -> dict[str, Any] | None:
    if not used_rates:
        return None
    return {
        "primary_currency": primary_currency,
        "rate_snapshot_id": str(rate_snapshot.id) if rate_snapshot is not None else None,
        "captured_at": rate_snapshot.captured_at.isoformat() if rate_snapshot is not None else None,
        "rates": {
            currency: {
                "base_currency": currency,
                "quote_currency": primary_currency,
                "rate": _format_rate(resolution.rate),
                "derived": resolution.derived,
                "source_rate_entry_id": (
                    str(resolution.source_entries[0].id)
                    if len(resolution.source_entries) == 1
                    else None
                ),
                "source_pair": " -> ".join(resolution.source_pairs)
                if resolution.source_pairs
                else f"{currency}/{primary_currency}",
                "source_rate_entry_ids": [
                    str(source_entry.id) for source_entry in resolution.source_entries
                ],
                "source_pairs": list(resolution.source_pairs),
                "path": list(resolution.path),
            }
            for currency, resolution in sorted(used_rates.items())
        },
    }


def _build_currency_totals(entries: list[FinanceSnapshotEntry]) -> dict[str, dict[str, Decimal]]:
    totals: dict[str, dict[str, Decimal]] = {}
    for entry in entries:
        if entry.is_auto_generated:
            continue
        currency_totals = totals.setdefault(
            entry.currency_code,
            {
                "total_positive": Decimal("0"),
                "total_negative": Decimal("0"),
                "net_amount": Decimal("0"),
            },
        )
        if entry.amount > 0:
            currency_totals["total_positive"] += entry.amount
        if entry.amount < 0:
            currency_totals["total_negative"] += entry.amount
        currency_totals["net_amount"] += entry.amount
    return totals


def _build_summary(
    entries: list[FinanceSnapshotEntry],
    *,
    primary_currency: str,
    rate_snapshot: FinanceRateSnapshot | None,
    aggregation_mode: str,
    missing_rate_currencies: set[str],
) -> dict[str, Any]:
    manual_entries = [entry for entry in entries if not entry.is_auto_generated]
    totals_by_currency = _build_currency_totals(manual_entries)
    total_source_entries = (
        manual_entries
        if aggregation_mode == "converted"
        else [entry for entry in manual_entries if entry.currency_code == primary_currency]
    )
    total_positive = sum(
        (entry.amount_converted for entry in total_source_entries if entry.amount_converted > 0),
        Decimal("0"),
    )
    total_negative = sum(
        (entry.amount_converted for entry in total_source_entries if entry.amount_converted < 0),
        Decimal("0"),
    )
    total_positive = _quantize_amount(total_positive)
    total_negative = _quantize_amount(total_negative)
    net_amount = _quantize_amount(total_positive + total_negative)
    return {
        "manual_entry_count": str(len(manual_entries)),
        "entry_count": str(len(entries)),
        "total_positive": str(total_positive),
        "total_negative": str(total_negative),
        "net_amount": str(net_amount),
        "primary_currency": primary_currency,
        "rate_snapshot_id": str(rate_snapshot.id) if rate_snapshot is not None else None,
        "aggregation_mode": aggregation_mode,
        "missing_rate_currencies": sorted(missing_rate_currencies),
        "amounts_by_currency": {
            currency: {
                key: str(_quantize_amount(value)) for key, value in sorted(currency_totals.items())
            }
            for currency, currency_totals in sorted(totals_by_currency.items())
        },
    }


async def _rebuild_finance_snapshot_entries(
    session: AsyncSession,
    *,
    snapshot: FinanceSnapshot,
    tree: FinanceTree,
    entries: list[FinanceSnapshotEntryInput],
    rate_snapshot: FinanceRateSnapshot | None,
) -> FinanceSnapshot:
    """Replace snapshot entries and recompute derived snapshot totals."""
    existing_entries = list(
        (
            await session.execute(
                select(FinanceSnapshotEntry).where(
                    FinanceSnapshotEntry.snapshot_id == snapshot.id,
                    FinanceSnapshotEntry.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for existing_entry in existing_entries:
        await session.delete(existing_entry)
    await session.flush()

    entry_nodes = await _load_entry_nodes(session, tree_id=tree.id, entries=entries)
    normalized_inputs: list[tuple[FinanceSnapshotEntryInput, FinanceTreeNode, Decimal, str]] = []
    entry_currency_codes: set[str] = {snapshot.primary_currency}
    for entry_input in entries:
        node = entry_nodes[entry_input.node_id]
        currency_code = normalize_currency_code(
            entry_input.currency_code,
            fallback=node.currency_code or snapshot.primary_currency,
        )
        amount = _decimal(entry_input.amount)
        normalized_inputs.append((entry_input, node, amount, currency_code))
        entry_currency_codes.add(currency_code)
    seen_entry_keys: set[tuple[UUID, str]] = set()
    for _, node, _, currency_code in normalized_inputs:
        entry_key = (node.id, currency_code)
        if entry_key in seen_entry_keys:
            raise FinanceValidationError(
                f"Finance snapshot entries must reference unique assets per node: "
                f"{node.name} {currency_code}"
            )
        seen_entry_keys.add(entry_key)
    decimal_places_by_code = await _load_asset_decimal_places(
        session,
        currency_codes=entry_currency_codes,
    )
    snapshot_entries: list[FinanceSnapshotEntry] = []
    manual_entries_by_node_id: dict[UUID, list[FinanceSnapshotEntry]] = {}
    used_rates: dict[str, RateResolution] = {}
    missing_rate_currencies: set[str] = set()
    for entry_input, node, amount, currency_code in normalized_inputs:
        amount = _validate_amount_precision(
            amount,
            currency_code=currency_code,
            decimal_places=decimal_places_by_code.get(
                currency_code,
                DEFAULT_FINANCE_ASSET_DECIMAL_PLACES,
            ),
        )
        if rate_snapshot is not None:
            rate_match = _find_rate(
                rate_snapshot,
                base_currency=currency_code,
                quote_currency=snapshot.primary_currency,
            )
            if rate_match is None:
                rate = Decimal("1")
                if currency_code != snapshot.primary_currency:
                    missing_rate_currencies.add(currency_code)
            else:
                rate = rate_match.rate
                if currency_code != snapshot.primary_currency:
                    used_rates[currency_code] = rate_match
        else:
            rate = Decimal("1")
        amount_converted = _quantize_amount(amount * rate)
        entry = FinanceSnapshotEntry(
            snapshot_id=snapshot.id,
            node_id=node.id,
            amount=amount,
            currency_code=currency_code,
            amount_converted=amount_converted,
            note=entry_input.note,
            is_auto_generated=False,
        )
        session.add(entry)
        snapshot_entries.append(entry)
        manual_entries_by_node_id.setdefault(node.id, []).append(entry)

    rollup_nodes = await _load_rollup_nodes(session, tree_id=tree.id)
    all_nodes = {node.id: node for node in await list_finance_nodes(session, tree_id=tree.id)}
    for rollup_node in rollup_nodes:
        descendant_entries = [
            entry
            for node_id, node_entries in manual_entries_by_node_id.items()
            for entry in node_entries
            if all_nodes.get(node_id) is not None
            and (
                all_nodes[node_id].id == rollup_node.id
                or all_nodes[node_id].path.startswith(f"{rollup_node.path}/")
            )
        ]
        if not descendant_entries:
            continue
        use_converted_rollups = rate_snapshot is not None and not missing_rate_currencies
        if not use_converted_rollups:
            entries_by_currency: dict[str, list[FinanceSnapshotEntry]] = {}
            for descendant_entry in descendant_entries:
                entries_by_currency.setdefault(
                    descendant_entry.currency_code,
                    [],
                ).append(descendant_entry)
            for rollup_currency, currency_entries in sorted(entries_by_currency.items()):
                amount = _quantize_amount(
                    sum((entry.amount for entry in currency_entries), Decimal("0"))
                )
                entry = FinanceSnapshotEntry(
                    snapshot_id=snapshot.id,
                    node_id=rollup_node.id,
                    amount=amount,
                    currency_code=rollup_currency,
                    amount_converted=amount,
                    is_auto_generated=True,
                )
                session.add(entry)
                snapshot_entries.append(entry)
            continue
        amount_converted = _quantize_amount(
            sum((entry.amount_converted for entry in descendant_entries), Decimal("0"))
        )
        entry = FinanceSnapshotEntry(
            snapshot_id=snapshot.id,
            node_id=rollup_node.id,
            amount=amount_converted,
            currency_code=snapshot.primary_currency,
            amount_converted=amount_converted,
            is_auto_generated=True,
        )
        session.add(entry)
        snapshot_entries.append(entry)

    manual_entries = [entry for entry in snapshot_entries if not entry.is_auto_generated]
    aggregation_mode = (
        "converted"
        if rate_snapshot is not None and not missing_rate_currencies
        else "native_by_currency"
    )
    total_source_entries = (
        manual_entries
        if aggregation_mode == "converted"
        else [entry for entry in manual_entries if entry.currency_code == snapshot.primary_currency]
    )
    snapshot.total_positive = _quantize_amount(
        sum(
            (
                entry.amount_converted
                for entry in total_source_entries
                if entry.amount_converted > 0
            ),
            Decimal("0"),
        )
    )
    snapshot.total_negative = _quantize_amount(
        sum(
            (
                entry.amount_converted
                for entry in total_source_entries
                if entry.amount_converted < 0
            ),
            Decimal("0"),
        )
    )
    snapshot.net_amount = _quantize_amount(snapshot.total_positive + snapshot.total_negative)
    snapshot.exchange_rates = _rate_usage_payload(
        primary_currency=snapshot.primary_currency,
        rate_snapshot=rate_snapshot,
        used_rates=used_rates,
    )
    snapshot.summary = _build_summary(
        snapshot_entries,
        primary_currency=snapshot.primary_currency,
        rate_snapshot=rate_snapshot,
        aggregation_mode=aggregation_mode,
        missing_rate_currencies=missing_rate_currencies,
    )
    await session.flush()
    await session.refresh(snapshot)
    return await get_finance_snapshot(session, snapshot_id=snapshot.id) or snapshot


async def create_finance_snapshot(
    session: AsyncSession,
    *,
    tree_id: UUID,
    entries: list[FinanceSnapshotEntryInput],
    title: str | None = None,
    snapshot_ts: datetime | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    primary_currency: str | None = None,
    rate_snapshot_id: UUID | None = None,
    note: str | None = None,
) -> FinanceSnapshot:
    """Create a finance snapshot and roll up aggregate nodes."""
    tree = await get_finance_tree(session, tree_id=tree_id)
    if tree is None:
        raise FinanceTreeNotFoundError(f"Finance tree {tree_id} was not found")
    resolved_snapshot_ts, resolved_period_start, resolved_period_end = (
        _validate_snapshot_time_fields(
            snapshot_ts=snapshot_ts,
            period_start=period_start,
            period_end=period_end,
        )
    )
    resolved_currency = normalize_currency_code(primary_currency, fallback=tree.primary_currency)
    rate_snapshot, rate_snapshot_policy = await _select_rate_snapshot_for_entries(
        session,
        explicit_rate_snapshot_id=rate_snapshot_id,
    )
    snapshot = FinanceSnapshot(
        tree_id=tree_id,
        rate_snapshot_id=rate_snapshot.id if rate_snapshot is not None else None,
        title=validate_snapshot_title(title),
        snapshot_ts=resolved_snapshot_ts,
        period_start=resolved_period_start,
        period_end=resolved_period_end,
        primary_currency=resolved_currency,
        rate_snapshot_policy=rate_snapshot_policy,
        total_positive=Decimal("0"),
        total_negative=Decimal("0"),
        net_amount=Decimal("0"),
        exchange_rates=None,
        summary={},
        note=note,
    )
    session.add(snapshot)
    await session.flush()
    return await _rebuild_finance_snapshot_entries(
        session,
        snapshot=snapshot,
        tree=tree,
        entries=entries,
        rate_snapshot=rate_snapshot,
    )


async def list_finance_snapshots(
    session: AsyncSession,
    *,
    tree_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FinanceSnapshot]:
    """List finance snapshots."""
    stmt = (
        select(FinanceSnapshot)
        .options(_finance_snapshot_tree_loader())
        .where(FinanceSnapshot.deleted_at.is_(None))
    )
    if tree_id is not None:
        stmt = stmt.where(FinanceSnapshot.tree_id == tree_id)
    stmt = (
        stmt.order_by(
            FinanceSnapshot.snapshot_ts.desc().nullslast(),
            FinanceSnapshot.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())


async def update_finance_snapshot(
    session: AsyncSession,
    *,
    snapshot_id: UUID,
    entries: list[FinanceSnapshotEntryInput] | None = None,
    title: str | None = None,
    snapshot_ts: datetime | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    primary_currency: str | None = None,
    rate_snapshot_id: UUID | None = None,
    note: str | None = None,
    update_title: bool = False,
    update_time_fields: bool = False,
    update_primary_currency: bool = False,
    update_rate_snapshot: bool = False,
    update_note: bool = False,
) -> FinanceSnapshot:
    """Update a finance snapshot and recompute derived amounts when needed."""
    snapshot = await get_finance_snapshot(session, snapshot_id=snapshot_id)
    if snapshot is None:
        raise FinanceTreeNotFoundError(f"Finance snapshot {snapshot_id} was not found")
    tree = snapshot.tree or await get_finance_tree(session, tree_id=snapshot.tree_id)
    if tree is None:
        raise FinanceTreeNotFoundError(f"Finance tree {snapshot.tree_id} was not found")

    if update_title:
        snapshot.title = validate_snapshot_title(title)

    if update_time_fields:
        resolved_snapshot_ts, resolved_period_start, resolved_period_end = (
            _validate_snapshot_time_fields(
                snapshot_ts=snapshot_ts,
                period_start=period_start,
                period_end=period_end,
            )
        )
        snapshot.snapshot_ts = resolved_snapshot_ts
        snapshot.period_start = resolved_period_start
        snapshot.period_end = resolved_period_end

    if update_primary_currency:
        snapshot.primary_currency = normalize_currency_code(
            primary_currency,
            fallback=tree.primary_currency,
        )

    if update_note:
        snapshot.note = note

    resolved_rate_snapshot_id = (
        rate_snapshot_id if update_rate_snapshot else snapshot.rate_snapshot_id
    )
    rate_snapshot, rate_snapshot_policy = await _select_rate_snapshot_for_entries(
        session,
        explicit_rate_snapshot_id=resolved_rate_snapshot_id,
    )
    snapshot.rate_snapshot_id = rate_snapshot.id if rate_snapshot is not None else None
    snapshot.rate_snapshot_policy = rate_snapshot_policy

    rebuild_entries = entries
    if rebuild_entries is None:
        rebuild_entries = [
            FinanceSnapshotEntryInput(
                node_id=entry.node_id,
                amount=entry.amount,
                currency_code=entry.currency_code,
                note=entry.note,
            )
            for entry in snapshot.entries
            if not entry.is_auto_generated
        ]
    return await _rebuild_finance_snapshot_entries(
        session,
        snapshot=snapshot,
        tree=tree,
        entries=rebuild_entries,
        rate_snapshot=rate_snapshot,
    )


async def delete_finance_snapshot(
    session: AsyncSession,
    *,
    snapshot_id: UUID,
) -> None:
    """Soft-delete a finance snapshot and its entries."""
    snapshot = await get_finance_snapshot(session, snapshot_id=snapshot_id)
    if snapshot is None:
        raise FinanceTreeNotFoundError(f"Finance snapshot {snapshot_id} was not found")
    for entry in snapshot.entries:
        entry.soft_delete()
    snapshot.soft_delete()
    await session.flush()


async def get_finance_snapshot(
    session: AsyncSession,
    *,
    snapshot_id: UUID,
) -> FinanceSnapshot | None:
    """Load one finance snapshot with entries and node metadata."""
    stmt = (
        select(FinanceSnapshot)
        .options(
            _finance_snapshot_tree_loader(),
            _finance_snapshot_rate_loader(),
            _finance_snapshot_entries_loader(),
        )
        .where(FinanceSnapshot.id == snapshot_id)
        .limit(1)
    )
    stmt = stmt.where(FinanceSnapshot.deleted_at.is_(None))
    snapshot = (await session.execute(stmt)).scalar_one_or_none()
    if snapshot is None:
        return None
    return snapshot


async def count_finance_snapshots(
    session: AsyncSession,
    *,
    tree_id: UUID | None = None,
) -> int:
    """Count finance snapshots."""
    stmt = (
        select(func.count())
        .select_from(FinanceSnapshot)
        .where(FinanceSnapshot.deleted_at.is_(None))
    )
    if tree_id is not None:
        stmt = stmt.where(FinanceSnapshot.tree_id == tree_id)
    return int((await session.execute(stmt)).scalar_one())


async def ensure_default_finance_tree(
    session: AsyncSession,
    *,
    primary_currency: str | None = None,
) -> FinanceTree:
    """Ensure one global default finance tree exists."""
    stmt = (
        select(FinanceTree)
        .where(
            FinanceTree.is_default.is_(True),
            FinanceTree.deleted_at.is_(None),
        )
        .limit(1)
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing
    tree = await create_finance_tree(
        session,
        name="Finance",
        primary_currency=primary_currency,
        is_default=True,
    )
    await create_finance_node(
        session,
        tree_id=tree.id,
        name="Assets",
        display_order=0,
    )
    await create_finance_node(
        session,
        tree_id=tree.id,
        name="Liabilities",
        display_order=1,
    )
    return tree
