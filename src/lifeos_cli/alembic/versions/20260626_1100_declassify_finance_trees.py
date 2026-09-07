"""Update finance snapshot, asset precision, and tree shape.

Revision ID: 20260626_1100
Revises: 20260617_1400
Create Date: 2026-06-26 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "20260626_1100"
down_revision: str | Sequence[str] | None = "20260617_1400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema_name() -> str | None:
    context = op.get_context()
    return context.version_table_schema


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _qualified_table_name(table_name: str) -> str:
    schema_name = _schema_name()
    if schema_name is None:
        return _quote_identifier(table_name)
    return f"{_quote_identifier(schema_name)}.{_quote_identifier(table_name)}"


def _assert_active_tree_names_are_unique() -> None:
    bind = op.get_bind()
    finance_trees = _qualified_table_name("finance_trees")
    duplicate_rows = bind.execute(
        text(
            f"""
            SELECT name, COUNT(*) AS tree_count
            FROM {finance_trees}
            WHERE deleted_at IS NULL
            GROUP BY name
            HAVING COUNT(*) > 1
            ORDER BY name
            """
        )
    ).mappings()
    duplicates = [f"{row['name']} ({row['tree_count']})" for row in duplicate_rows]
    if duplicates:
        names = ", ".join(duplicates)
        raise RuntimeError(
            "Active finance tree names must be globally unique before applying "
            f"revision 20260626_1100: {names}"
        )


def _normalize_active_default_tree() -> None:
    bind = op.get_bind()
    finance_trees = _qualified_table_name("finance_trees")
    default_rows = list(
        bind.execute(
            text(
                f"""
                SELECT id
                FROM {finance_trees}
                WHERE deleted_at IS NULL AND is_default = :is_default
                ORDER BY display_order ASC, created_at ASC, id ASC
                """
            ),
            {"is_default": True},
        ).mappings()
    )
    for row in default_rows[1:]:
        bind.execute(
            text(f"UPDATE {finance_trees} SET is_default = :is_default WHERE id = :tree_id"),
            {"is_default": False, "tree_id": row["id"]},
        )


def _finance_tree_columns() -> set[str]:
    bind = op.get_bind()
    return {
        column["name"]
        for column in sa.inspect(bind).get_columns("finance_trees", schema=_schema_name())
    }


def upgrade() -> None:
    schema_name = _schema_name()
    with op.batch_alter_table("finance_snapshots", schema=schema_name) as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=200), nullable=True))
    with op.batch_alter_table("finance_assets", schema=schema_name) as batch_op:
        batch_op.add_column(
            sa.Column(
                "decimal_places",
                sa.Integer(),
                nullable=False,
                server_default="2",
            )
        )
    with op.batch_alter_table("finance_assets", schema=schema_name) as batch_op:
        batch_op.alter_column("decimal_places", server_default=None)

    _assert_active_tree_names_are_unique()
    _normalize_active_default_tree()
    op.drop_index("ix_finance_trees_purpose_default", table_name="finance_trees")
    op.drop_index("uq_finance_trees_purpose_name_active", table_name="finance_trees")
    with op.batch_alter_table("finance_trees", schema=schema_name) as batch_op:
        batch_op.drop_column("time_mode")
        batch_op.drop_column("purpose")
    op.create_index(
        "uq_finance_trees_name_active",
        "finance_trees",
        ["name"],
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
        sqlite_where=text("deleted_at IS NULL"),
    )
    op.create_index("ix_finance_trees_default", "finance_trees", ["is_default"])


def downgrade() -> None:
    schema_name = _schema_name()
    op.drop_index("ix_finance_trees_default", table_name="finance_trees")
    op.drop_index("uq_finance_trees_name_active", table_name="finance_trees")
    existing_columns = _finance_tree_columns()
    with op.batch_alter_table("finance_trees", schema=schema_name) as batch_op:
        if "purpose" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "purpose",
                    sa.String(length=20),
                    nullable=False,
                    server_default="custom",
                ),
            )
        if "time_mode" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "time_mode",
                    sa.String(length=20),
                    nullable=False,
                    server_default="instant",
                ),
            )
    # SQLite batch mode must rebuild the table for these alterations. Keep the
    # add and alter phases separate so Alembic does not derive a circular
    # partial-reordering graph for the two new columns.
    with op.batch_alter_table("finance_trees", schema=schema_name) as batch_op:
        if "purpose" not in existing_columns:
            batch_op.alter_column("purpose", server_default=None)
        if "time_mode" not in existing_columns:
            batch_op.alter_column("time_mode", server_default=None)
    op.create_index(
        "uq_finance_trees_purpose_name_active",
        "finance_trees",
        ["purpose", "name"],
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
        sqlite_where=text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_finance_trees_purpose_default",
        "finance_trees",
        ["purpose", "is_default"],
    )
    with op.batch_alter_table("finance_assets", schema=schema_name) as batch_op:
        batch_op.drop_column("decimal_places")
    with op.batch_alter_table("finance_snapshots", schema=schema_name) as batch_op:
        batch_op.drop_column("title")
