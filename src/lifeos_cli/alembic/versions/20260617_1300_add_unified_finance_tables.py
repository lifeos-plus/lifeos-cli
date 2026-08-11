"""Add unified finance tree, snapshot, rate, and asset tables."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "20260617_1300"
down_revision = "20260617_1200"
branch_labels = None
depends_on = None


DEFAULT_ASSETS = (
    ("USD", "US Dollar", 10),
    ("USDT", "Tether USD", 20),
    ("CNY", "Chinese Yuan", 30),
    ("BTC", "Bitcoin", 40),
    ("ETH", "Ethereum", 50),
    ("EUR", "Euro", 60),
)


def _schema_name() -> str | None:
    context = op.get_context()
    return context.version_table_schema


def _qualified_column(schema_name: str | None, table_name: str, column_name: str) -> str:
    if schema_name is None:
        return f"{table_name}.{column_name}"
    return f"{schema_name}.{table_name}.{column_name}"


def upgrade() -> None:
    schema_name = _schema_name()
    op.create_table(
        "finance_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finance_assets")),
        schema=schema_name,
    )
    op.create_index(
        "uq_finance_assets_code_active",
        "finance_assets",
        ["code"],
        unique=True,
        schema=schema_name,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_finance_assets_display_order",
        "finance_assets",
        ["display_order", "code"],
        schema=schema_name,
    )

    assets_table = sa.table(
        "finance_assets",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("display_order", sa.Integer()),
        sa.column("is_default", sa.Boolean()),
        sa.column("metadata", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
        schema=schema_name,
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        assets_table,
        [
            {
                "id": uuid4(),
                "code": code,
                "name": name,
                "display_order": display_order,
                "is_default": True,
                "metadata": None,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
            for code, name, display_order in DEFAULT_ASSETS
        ],
    )

    op.create_table(
        "finance_trees",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("time_mode", sa.String(length=20), nullable=False),
        sa.Column("primary_currency", sa.String(length=16), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finance_trees")),
        schema=schema_name,
    )
    op.create_index(
        "uq_finance_trees_purpose_name_active",
        "finance_trees",
        ["purpose", "name"],
        unique=True,
        schema=schema_name,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_finance_trees_purpose_default",
        "finance_trees",
        ["purpose", "is_default"],
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_trees_display_order",
        "finance_trees",
        ["display_order"],
        schema=schema_name,
    )

    op.create_table(
        "finance_tree_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("currency_code", sa.String(length=16), nullable=True),
        sa.Column("path", sa.String(length=1200), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("children_count", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            [_qualified_column(schema_name, "finance_trees", "id")],
            name=op.f("fk_finance_tree_nodes_tree_id_finance_trees"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            [_qualified_column(schema_name, "finance_tree_nodes", "id")],
            name=op.f("fk_finance_tree_nodes_parent_id_finance_tree_nodes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finance_tree_nodes")),
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_tree_nodes_tree_id",
        "finance_tree_nodes",
        ["tree_id"],
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_tree_nodes_parent",
        "finance_tree_nodes",
        ["parent_id"],
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_tree_nodes_tree_path",
        "finance_tree_nodes",
        ["tree_id", "path"],
        unique=True,
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_tree_nodes_tree_order",
        "finance_tree_nodes",
        ["tree_id", "display_order", "created_at"],
        schema=schema_name,
    )

    op.create_table(
        "finance_rate_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finance_rate_snapshots")),
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_rate_snapshots_captured",
        "finance_rate_snapshots",
        ["captured_at"],
        schema=schema_name,
    )

    op.create_table(
        "finance_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("rate_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("rate_snapshot_policy", sa.String(length=32), nullable=False),
        sa.Column("snapshot_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("primary_currency", sa.String(length=16), nullable=False),
        sa.Column("total_positive", sa.Numeric(20, 8), nullable=False),
        sa.Column("total_negative", sa.Numeric(20, 8), nullable=False),
        sa.Column("net_amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("exchange_rates", sa.JSON(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            [_qualified_column(schema_name, "finance_trees", "id")],
            name=op.f("fk_finance_snapshots_tree_id_finance_trees"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rate_snapshot_id"],
            [_qualified_column(schema_name, "finance_rate_snapshots", "id")],
            name=op.f("fk_finance_snapshots_rate_snapshot_id_finance_rate_snapshots"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finance_snapshots")),
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_snapshots_tree_id",
        "finance_snapshots",
        ["tree_id"],
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_snapshots_tree_ts",
        "finance_snapshots",
        ["tree_id", "snapshot_ts"],
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_snapshots_tree_period",
        "finance_snapshots",
        ["tree_id", "period_start", "period_end"],
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_snapshots_rate_snapshot",
        "finance_snapshots",
        ["rate_snapshot_id"],
        schema=schema_name,
    )

    op.create_table(
        "finance_snapshot_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency_code", sa.String(length=16), nullable=False),
        sa.Column("amount_converted", sa.Numeric(20, 8), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_auto_generated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            [_qualified_column(schema_name, "finance_snapshots", "id")],
            name=op.f("fk_finance_snapshot_entries_snapshot_id_finance_snapshots"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            [_qualified_column(schema_name, "finance_tree_nodes", "id")],
            name=op.f("fk_finance_snapshot_entries_node_id_finance_tree_nodes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finance_snapshot_entries")),
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_snapshot_entries_snapshot_id",
        "finance_snapshot_entries",
        ["snapshot_id"],
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_snapshot_entries_node",
        "finance_snapshot_entries",
        ["node_id"],
        schema=schema_name,
    )
    op.create_index(
        "uq_finance_snapshot_entries_snapshot_node_active",
        "finance_snapshot_entries",
        ["snapshot_id", "node_id"],
        unique=True,
        schema=schema_name,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "finance_rate_snapshot_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rate_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("base_currency", sa.String(length=16), nullable=False),
        sa.Column("quote_currency", sa.String(length=16), nullable=False),
        sa.Column("rate", sa.Numeric(28, 12), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_derived", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["rate_snapshot_id"],
            [_qualified_column(schema_name, "finance_rate_snapshots", "id")],
            name=op.f("fk_finance_rate_snapshot_entries_rate_snapshot_id_finance_rate_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finance_rate_snapshot_entries")),
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_rate_snapshot_entries_rate_snapshot_id",
        "finance_rate_snapshot_entries",
        ["rate_snapshot_id"],
        schema=schema_name,
    )
    op.create_index(
        "ix_finance_rate_snapshot_entries_base",
        "finance_rate_snapshot_entries",
        ["base_currency"],
        schema=schema_name,
    )
    op.create_index(
        "uq_finance_rate_snapshot_entries_pair_active",
        "finance_rate_snapshot_entries",
        ["rate_snapshot_id", "base_currency", "quote_currency"],
        unique=True,
        schema=schema_name,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    schema_name = _schema_name()
    op.drop_index(
        "uq_finance_rate_snapshot_entries_pair_active",
        table_name="finance_rate_snapshot_entries",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_rate_snapshot_entries_base",
        table_name="finance_rate_snapshot_entries",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_rate_snapshot_entries_rate_snapshot_id",
        table_name="finance_rate_snapshot_entries",
        schema=schema_name,
    )
    op.drop_table("finance_rate_snapshot_entries", schema=schema_name)
    op.drop_index(
        "uq_finance_snapshot_entries_snapshot_node_active",
        table_name="finance_snapshot_entries",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_snapshot_entries_node",
        table_name="finance_snapshot_entries",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_snapshot_entries_snapshot_id",
        table_name="finance_snapshot_entries",
        schema=schema_name,
    )
    op.drop_table("finance_snapshot_entries", schema=schema_name)
    op.drop_index(
        "ix_finance_snapshots_rate_snapshot",
        table_name="finance_snapshots",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_snapshots_tree_period",
        table_name="finance_snapshots",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_snapshots_tree_ts",
        table_name="finance_snapshots",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_snapshots_tree_id",
        table_name="finance_snapshots",
        schema=schema_name,
    )
    op.drop_table("finance_snapshots", schema=schema_name)
    op.drop_index(
        "ix_finance_rate_snapshots_captured",
        table_name="finance_rate_snapshots",
        schema=schema_name,
    )
    op.drop_table("finance_rate_snapshots", schema=schema_name)
    op.drop_index(
        "ix_finance_tree_nodes_tree_order",
        table_name="finance_tree_nodes",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_tree_nodes_tree_path",
        table_name="finance_tree_nodes",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_tree_nodes_parent",
        table_name="finance_tree_nodes",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_tree_nodes_tree_id",
        table_name="finance_tree_nodes",
        schema=schema_name,
    )
    op.drop_table("finance_tree_nodes", schema=schema_name)
    op.drop_index(
        "ix_finance_trees_display_order",
        table_name="finance_trees",
        schema=schema_name,
    )
    op.drop_index(
        "ix_finance_trees_purpose_default",
        table_name="finance_trees",
        schema=schema_name,
    )
    op.drop_index(
        "uq_finance_trees_purpose_name_active",
        table_name="finance_trees",
        schema=schema_name,
    )
    op.drop_table("finance_trees", schema=schema_name)
    op.drop_index(
        "ix_finance_assets_display_order",
        table_name="finance_assets",
        schema=schema_name,
    )
    op.drop_index(
        "uq_finance_assets_code_active",
        table_name="finance_assets",
        schema=schema_name,
    )
    op.drop_table("finance_assets", schema=schema_name)
