"""Harden persisted domain invariants and finance default uniqueness."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260907_1200"
down_revision = "20260906_1200"
branch_labels = None
depends_on = None


CONSTRAINTS: dict[str, tuple[tuple[str, str], ...]] = {
    "body_measurements": (
        ("ck_body_measurements_weight_valid", "weight_kg > 0 AND weight_kg <= 1000"),
        (
            "ck_body_measurements_percentages_valid",
            "(body_fat_percentage IS NULL OR body_fat_percentage BETWEEN 0 AND 100) AND "
            "(muscle_percentage IS NULL OR muscle_percentage BETWEEN 0 AND 100) AND "
            "(visceral_fat IS NULL OR visceral_fat BETWEEN 0 AND 100)",
        ),
        (
            "ck_body_measurements_masses_valid",
            "(fat_mass_kg IS NULL OR fat_mass_kg BETWEEN 0 AND 1000) AND "
            "(muscle_mass_kg IS NULL OR muscle_mass_kg BETWEEN 0 AND 1000) AND "
            "(body_water_kg IS NULL OR body_water_kg BETWEEN 0 AND 1000) AND "
            "(protein_kg IS NULL OR protein_kg BETWEEN 0 AND 1000) AND "
            "(bone_mass_kg IS NULL OR bone_mass_kg BETWEEN 0 AND 1000) AND "
            "(skeletal_muscle_kg IS NULL OR skeletal_muscle_kg BETWEEN 0 AND 1000)",
        ),
    ),
    "events": (
        ("ck_events_status_valid", "status IN ('planned', 'cancelled', 'completed')"),
        ("ck_events_priority_valid", "priority BETWEEN 0 AND 5"),
        ("ck_events_time_range_valid", "end_time IS NULL OR end_time >= start_time"),
        (
            "ck_events_recurrence_frequency_valid",
            "recurrence_frequency IS NULL OR recurrence_frequency IN "
            "('daily', 'weekly', 'monthly', 'yearly')",
        ),
        (
            "ck_events_recurrence_numbers_positive",
            "(recurrence_interval IS NULL OR recurrence_interval > 0) AND "
            "(recurrence_count IS NULL OR recurrence_count > 0)",
        ),
    ),
    "finance_assets": (
        ("ck_finance_assets_decimal_places_valid", "decimal_places BETWEEN 0 AND 8"),
    ),
    "finance_rate_snapshot_entries": (
        ("ck_finance_rate_snapshot_entries_rate_positive", "rate > 0"),
    ),
    "finance_tree_nodes": (
        (
            "ck_finance_tree_nodes_counts_nonnegative",
            "depth >= 0 AND children_count >= 0",
        ),
    ),
    "habit_actions": (
        ("ck_habit_actions_status_valid", "status IN ('pending', 'done', 'skip', 'miss')"),
    ),
    "habits": (
        ("ck_habits_duration_days_valid", "duration_days BETWEEN 1 AND 10000"),
        ("ck_habits_target_per_cycle_positive", "target_per_cycle > 0"),
        (
            "ck_habits_cadence_frequency_valid",
            "cadence_frequency IN ('daily', 'weekly', 'monthly', 'yearly')",
        ),
        (
            "ck_habits_status_valid",
            "status IN ('active', 'completed', 'paused', 'expired')",
        ),
    ),
    "sleep_segments": (
        ("ck_sleep_segments_time_range_valid", "end_at > start_at"),
        ("ck_sleep_segments_duration_valid", "duration_minutes BETWEEN 1 AND 2880"),
    ),
    "tasks": (
        (
            "ck_tasks_status_valid",
            "status IN ('todo', 'in_progress', 'done', 'cancelled', 'paused')",
        ),
        (
            "ck_tasks_planning_cycle_type_valid",
            "planning_cycle_type IS NULL OR planning_cycle_type IN "
            "('day', 'week', 'month', 'year', '7years')",
        ),
        (
            "ck_tasks_planning_cycle_complete",
            "(planning_cycle_type IS NULL AND planning_cycle_days IS NULL AND "
            "planning_cycle_start_date IS NULL) OR "
            "(planning_cycle_type IS NOT NULL AND planning_cycle_days > 0 AND "
            "planning_cycle_start_date IS NOT NULL)",
        ),
        (
            "ck_tasks_effort_nonnegative",
            "actual_effort_self >= 0 AND actual_effort_total >= 0 AND "
            "(estimated_effort IS NULL OR estimated_effort >= 0)",
        ),
    ),
    "timelog_templates": (
        (
            "ck_timelog_templates_duration_valid",
            "default_duration_minutes IS NULL OR default_duration_minutes BETWEEN 1 AND 1440",
        ),
        (
            "ck_timelog_templates_counters_nonnegative",
            "position >= 0 AND usage_count >= 0",
        ),
    ),
    "timelogs": (
        ("ck_timelogs_time_range_valid", "end_time >= start_time"),
        (
            "ck_timelogs_tracking_method_valid",
            "tracking_method IN ('manual', 'automatic', 'imported')",
        ),
        (
            "ck_timelogs_energy_level_valid",
            "energy_level IS NULL OR energy_level BETWEEN 1 AND 5",
        ),
    ),
    "visions": (
        ("ck_visions_status_valid", "status IN ('active', 'archived', 'fruit')"),
        (
            "ck_visions_progress_nonnegative",
            "stage >= 0 AND experience_points >= 0",
        ),
        (
            "ck_visions_experience_rate_positive",
            "experience_rate_per_hour IS NULL OR experience_rate_per_hour > 0",
        ),
    ),
}

REDUNDANT_INDEXES: tuple[tuple[str, str], ...] = (
    ("body_measurements", "ix_body_measurements_measured_at"),
    ("finance_trees", "ix_finance_trees_default"),
    ("menstrual_days", "ix_menstrual_days_log_date"),
    ("tags", "ix_tags_name_entity_type_category"),
)


def _schema_name() -> str | None:
    return op.get_context().version_table_schema


def _assert_existing_rows_valid(schema_name: str | None) -> None:
    if op.get_context().as_sql:
        return
    connection = op.get_bind()
    for table_name, constraints in CONSTRAINTS.items():
        qualified_table = f'"{schema_name}"."{table_name}"' if schema_name else f'"{table_name}"'
        for constraint_name, condition in constraints:
            invalid_count = connection.execute(
                sa.text(f"SELECT COUNT(*) FROM {qualified_table} WHERE NOT ({condition})")
            ).scalar_one()
            if invalid_count:
                raise RuntimeError(
                    f"Cannot add {constraint_name}: {invalid_count} existing row(s) violate "
                    "the new invariant. Repair the rows and rerun `lifeos db upgrade`."
                )
    finance_trees = f'"{schema_name}"."finance_trees"' if schema_name else '"finance_trees"'
    default_count = connection.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {finance_trees} WHERE is_default IS TRUE AND deleted_at IS NULL"
        )
    ).scalar_one()
    if default_count > 1:
        raise RuntimeError(
            "Cannot add uq_finance_trees_single_active_default: multiple active default "
            "finance trees exist. Select one default and rerun `lifeos db upgrade`."
        )


def upgrade() -> None:
    schema_name = _schema_name()
    _assert_existing_rows_valid(schema_name)
    for table_name, index_name in REDUNDANT_INDEXES:
        op.drop_index(index_name, table_name=table_name, schema=schema_name)
    for table_name, constraints in CONSTRAINTS.items():
        with op.batch_alter_table(table_name, schema=schema_name) as batch_op:
            for constraint_name, condition in constraints:
                batch_op.create_check_constraint(constraint_name, condition)
    op.create_index(
        "uq_finance_trees_single_active_default",
        "finance_trees",
        ["is_default"],
        unique=True,
        schema=schema_name,
        postgresql_where=sa.text("is_default IS TRUE AND deleted_at IS NULL"),
        sqlite_where=sa.text("is_default = 1 AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    schema_name = _schema_name()
    op.drop_index(
        "uq_finance_trees_single_active_default",
        table_name="finance_trees",
        schema=schema_name,
    )
    for table_name, constraints in reversed(CONSTRAINTS.items()):
        with op.batch_alter_table(table_name, schema=schema_name) as batch_op:
            for constraint_name, _ in reversed(constraints):
                batch_op.drop_constraint(constraint_name, type_="check")
    for table_name, index_name in REDUNDANT_INDEXES:
        if table_name == "tags":
            columns = ["name", "entity_type", "category"]
        elif table_name == "finance_trees":
            columns = ["is_default"]
        elif table_name == "menstrual_days":
            columns = ["log_date"]
        else:
            columns = ["measured_at"]
        op.create_index(index_name, table_name, columns, schema=schema_name)
