"""Enforce one active body measurement per measured-at time."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260827_1200"
down_revision = "20260819_1200"
branch_labels = None
depends_on = None


def _schema_name() -> str | None:
    context = op.get_context()
    return context.version_table_schema


def _dedupe_active_measurements(schema_name: str | None) -> None:
    """Soft-delete older duplicate measurements sharing one measured-at time.

    The unique active index below requires at most one active row per
    measured-at value. Keep the most recently updated row and soft-delete
    the rest so existing duplicate records from the pre-index CLI remain
    readable history instead of blocking the migration.
    """
    table = sa.table(
        "body_measurements",
        sa.column("id", sa.Uuid()),
        sa.column("measured_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
        schema=schema_name,
    )
    rows = op.get_bind().execute(
        sa.select(table.c.id, table.c.measured_at, table.c.updated_at)
        .where(table.c.deleted_at.is_(None))
        .order_by(table.c.measured_at.asc(), table.c.updated_at.desc(), table.c.id.desc())
    )
    seen_measured_at: set[object] = set()
    duplicate_ids: list[object] = []
    for row_id, measured_at, updated_at in rows:
        if measured_at in seen_measured_at:
            duplicate_ids.append(row_id)
        else:
            seen_measured_at.add(measured_at)
    for row_id in duplicate_ids:
        op.get_bind().execute(
            sa.update(table)
            .where(table.c.id == row_id)
            .values(deleted_at=table.c.updated_at)
        )


def upgrade() -> None:
    schema_name = _schema_name()
    _dedupe_active_measurements(schema_name)
    op.create_index(
        "uq_body_measurements_measured_at_active",
        "body_measurements",
        ["measured_at"],
        unique=True,
        schema=schema_name,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    schema_name = _schema_name()
    op.drop_index(
        "uq_body_measurements_measured_at_active",
        table_name="body_measurements",
        schema=schema_name,
    )
