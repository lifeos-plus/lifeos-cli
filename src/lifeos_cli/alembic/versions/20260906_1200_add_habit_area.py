"""Associate habits with optional life areas."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260906_1200"
down_revision = "20260827_1200"
branch_labels = None
depends_on = None


def _schema_name() -> str | None:
    context = op.get_context()
    return context.version_table_schema


def upgrade() -> None:
    schema_name = _schema_name()

    with op.batch_alter_table("habits", schema=schema_name) as batch_op:
        batch_op.add_column(sa.Column("area_id", sa.Uuid(), nullable=True))
        batch_op.create_index("ix_habits_area_id", ["area_id"], unique=False)
        batch_op.create_foreign_key(
            op.f("fk_habits_area_id_areas"),
            "areas",
            ["area_id"],
            ["id"],
            referent_schema=schema_name,
            ondelete="SET NULL",
        )


def downgrade() -> None:
    schema_name = _schema_name()

    with op.batch_alter_table("habits", schema=schema_name) as batch_op:
        batch_op.drop_constraint(
            op.f("fk_habits_area_id_areas"),
            type_="foreignkey",
        )
        batch_op.drop_index("ix_habits_area_id")
        batch_op.drop_column("area_id")
