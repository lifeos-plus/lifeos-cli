"""Unified finance tree and snapshot models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin
from lifeos_cli.db.types import UTCDateTime


class FinanceTree(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """Reusable finance tree for any finance snapshot view."""

    __tablename__ = "finance_trees"
    __table_args__ = (
        Index(
            "uq_finance_trees_name_active",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_finance_trees_display_order", "display_order"),
        Index(
            "uq_finance_trees_single_active_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default IS TRUE AND deleted_at IS NULL"),
            sqlite_where=text("is_default = 1 AND deleted_at IS NULL"),
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    primary_currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    nodes = relationship(
        "FinanceTreeNode",
        back_populates="tree",
        cascade="all, delete-orphan",
        order_by="FinanceTreeNode.path",
    )
    snapshots = relationship(
        "FinanceSnapshot",
        back_populates="tree",
        cascade="all, delete-orphan",
        order_by="FinanceSnapshot.snapshot_ts.desc()",
    )

    def __repr__(self) -> str:
        return f"FinanceTree(id={self.id!s}, name={self.name!r})"


class FinanceAsset(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """Asset code usable by finance trees, snapshots, and exchange rates."""

    __tablename__ = "finance_assets"
    __table_args__ = (
        CheckConstraint(
            "decimal_places BETWEEN 0 AND 8",
            name="ck_finance_assets_decimal_places_valid",
        ),
        Index(
            "uq_finance_assets_code_active",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_finance_assets_display_order", "display_order", "code"),
    )

    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decimal_places: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    def __repr__(self) -> str:
        return f"FinanceAsset(id={self.id!s}, code={self.code!r})"


class FinanceTreeNode(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """Hierarchical finance node shared by balance and cashflow presets."""

    __tablename__ = "finance_tree_nodes"
    __table_args__ = (
        CheckConstraint(
            "depth >= 0 AND children_count >= 0",
            name="ck_finance_tree_nodes_counts_nonnegative",
        ),
        Index("ix_finance_tree_nodes_tree_path", "tree_id", "path", unique=True),
        Index("ix_finance_tree_nodes_parent", "parent_id"),
        Index("ix_finance_tree_nodes_tree_order", "tree_id", "display_order", "created_at"),
    )

    tree_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("finance_trees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("finance_tree_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    path: Mapped[str] = mapped_column(String(1200), nullable=False, default="")
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    children_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    tree = relationship("FinanceTree", back_populates="nodes")
    parent = relationship(
        "FinanceTreeNode",
        remote_side="FinanceTreeNode.id",
        back_populates="children",
    )
    children = relationship(
        "FinanceTreeNode",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="FinanceTreeNode.display_order",
    )
    snapshot_entries = relationship(
        "FinanceSnapshotEntry",
        back_populates="node",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"FinanceTreeNode(id={self.id!s}, tree_id={self.tree_id!s}, name={self.name!r})"


class FinanceSnapshot(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """Snapshot for one finance tree at an instant or over a period."""

    __tablename__ = "finance_snapshots"
    __table_args__ = (
        Index("ix_finance_snapshots_tree_ts", "tree_id", "snapshot_ts"),
        Index("ix_finance_snapshots_tree_period", "tree_id", "period_start", "period_end"),
        Index("ix_finance_snapshots_rate_snapshot", "rate_snapshot_id"),
    )

    tree_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("finance_trees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rate_snapshot_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("finance_rate_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    snapshot_ts: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    primary_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    rate_snapshot_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    total_positive: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    total_negative: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    exchange_rates: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    tree = relationship("FinanceTree", back_populates="snapshots")
    rate_snapshot = relationship("FinanceRateSnapshot", back_populates="snapshots")
    entries = relationship(
        "FinanceSnapshotEntry",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="FinanceSnapshotEntry.created_at",
    )

    def __repr__(self) -> str:
        return f"FinanceSnapshot(id={self.id!s}, tree_id={self.tree_id!s})"


class FinanceSnapshotEntry(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """One node amount captured inside a finance snapshot."""

    __tablename__ = "finance_snapshot_entries"
    __table_args__ = (
        Index(
            "uq_finance_snapshot_entries_snapshot_node_currency_auto_active",
            "snapshot_id",
            "node_id",
            "currency_code",
            "is_auto_generated",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_finance_snapshot_entries_node", "node_id"),
    )

    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("finance_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("finance_tree_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_converted: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    snapshot = relationship("FinanceSnapshot", back_populates="entries")
    node = relationship("FinanceTreeNode", back_populates="snapshot_entries")

    def __repr__(self) -> str:
        return f"FinanceSnapshotEntry(id={self.id!s}, node_id={self.node_id!s})"


class FinanceRateSnapshot(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """Exchange-rate set captured at one time."""

    __tablename__ = "finance_rate_snapshots"
    __table_args__ = (Index("ix_finance_rate_snapshots_captured", "captured_at"),)

    captured_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    entries = relationship(
        "FinanceRateSnapshotEntry",
        back_populates="rate_snapshot",
        cascade="all, delete-orphan",
        order_by="FinanceRateSnapshotEntry.base_currency",
    )
    snapshots = relationship("FinanceSnapshot", back_populates="rate_snapshot")

    def __repr__(self) -> str:
        return f"FinanceRateSnapshot(id={self.id!s}, captured_at={self.captured_at!r})"


class FinanceRateSnapshotEntry(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """One exchange-rate pair inside a rate snapshot."""

    __tablename__ = "finance_rate_snapshot_entries"
    __table_args__ = (
        CheckConstraint(
            "rate > 0",
            name="ck_finance_rate_snapshot_entries_rate_positive",
        ),
        Index(
            "uq_finance_rate_snapshot_entries_pair_active",
            "rate_snapshot_id",
            "base_currency",
            "quote_currency",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_finance_rate_snapshot_entries_base", "base_currency"),
    )

    rate_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("finance_rate_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    is_derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    rate_snapshot = relationship("FinanceRateSnapshot", back_populates="entries")

    def __repr__(self) -> str:
        return (
            "FinanceRateSnapshotEntry("
            f"id={self.id!s}, pair={self.base_currency}/{self.quote_currency})"
        )


__all__ = [
    "FinanceAsset",
    "FinanceRateSnapshot",
    "FinanceRateSnapshotEntry",
    "FinanceSnapshot",
    "FinanceSnapshotEntry",
    "FinanceTree",
    "FinanceTreeNode",
]
