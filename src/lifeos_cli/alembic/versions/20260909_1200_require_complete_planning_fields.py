"""Close SQL NULL loopholes in optional planning and recurrence groups."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260909_1200"
down_revision = "20260907_1200"
branch_labels = None
depends_on = None

CONSTRAINTS = (
    (
        "tasks",
        "planning_cycle_days_required",
        "planning_cycle_type IS NULL OR planning_cycle_days IS NOT NULL",
    ),
    (
        "events",
        "recurrence_interval_required",
        "recurrence_frequency IS NULL OR recurrence_interval IS NOT NULL",
    ),
)


def upgrade() -> None:
    schema = op.get_context().version_table_schema
    connection = op.get_bind()
    for table_name, name, condition in CONSTRAINTS:
        if not op.get_context().as_sql:
            qualified = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
            count = connection.execute(
                sa.text(f"SELECT COUNT(*) FROM {qualified} WHERE NOT ({condition})")
            ).scalar_one()
            if count:
                raise RuntimeError(
                    f"Cannot add ck_{table_name}_{name}: {count} incomplete row(s). "
                    "Repair the rows and rerun `lifeos db upgrade`."
                )
        with op.batch_alter_table(table_name, schema=schema) as batch_op:
            batch_op.create_check_constraint(name, condition)


def downgrade() -> None:
    schema = op.get_context().version_table_schema
    for table_name, name, _ in reversed(CONSTRAINTS):
        with op.batch_alter_table(table_name, schema=schema) as batch_op:
            batch_op.drop_constraint(name, type_="check")
