"""Add menstrual cycle, body measurement, and sleep segment tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260819_1200"
down_revision = "20260812_1200"
branch_labels = None
depends_on = None


def _schema_name() -> str | None:
    context = op.get_context()
    return context.version_table_schema


def _qualified_column(schema_name: str | None, table_name: str, column_name: str) -> str:
    if schema_name is None:
        return f"{table_name}.{column_name}"
    return f"{schema_name}.{table_name}.{column_name}"


def _create_menstrual_tables(schema_name: str | None) -> None:
    op.create_table(
        "menstrual_factors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menstrual_factors")),
        schema=schema_name,
    )
    op.create_index(
        "uq_menstrual_factors_name_active",
        "menstrual_factors",
        ["name"],
        unique=True,
        schema=schema_name,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "menstrual_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("in_period", sa.Boolean(), nullable=False),
        sa.Column("flow_amount", sa.String(length=16), nullable=True),
        sa.Column("symptoms", sa.JSON(), nullable=True),
        sa.Column("personality_behavior", sa.Boolean(), nullable=True),
        sa.Column("protection_used", sa.Boolean(), nullable=True),
        sa.Column("spotting", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menstrual_days")),
        schema=schema_name,
    )
    op.create_index(
        "ix_menstrual_days_log_date",
        "menstrual_days",
        ["log_date"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        "uq_menstrual_days_log_date_active",
        "menstrual_days",
        ["log_date"],
        unique=True,
        schema=schema_name,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "menstrual_day_factors",
        sa.Column("menstrual_day_id", sa.Uuid(), nullable=False),
        sa.Column("factor_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["menstrual_day_id"],
            [_qualified_column(schema_name, "menstrual_days", "id")],
            name=op.f("fk_menstrual_day_factors_menstrual_day_id_menstrual_days"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["factor_id"],
            [_qualified_column(schema_name, "menstrual_factors", "id")],
            name=op.f("fk_menstrual_day_factors_factor_id_menstrual_factors"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "menstrual_day_id",
            "factor_id",
            name=op.f("pk_menstrual_day_factors"),
        ),
        schema=schema_name,
    )
    op.create_index(
        "ix_menstrual_day_factors_factor_id",
        "menstrual_day_factors",
        ["factor_id"],
        unique=False,
        schema=schema_name,
    )


def _create_body_measurement_table(schema_name: str | None) -> None:
    op.create_table(
        "body_measurements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("weight_kg", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("body_fat_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("visceral_fat", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("fat_mass_kg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("muscle_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("muscle_mass_kg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("body_water_kg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("protein_kg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("bone_mass_kg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("skeletal_muscle_kg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_body_measurements")),
        schema=schema_name,
    )
    op.create_index(
        "ix_body_measurements_measured_at",
        "body_measurements",
        ["measured_at"],
        unique=False,
        schema=schema_name,
    )


def _create_sleep_segment_table(schema_name: str | None) -> None:
    op.create_table(
        "sleep_segments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sleep_date", sa.Date(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sleep_segments")),
        schema=schema_name,
    )
    op.create_index(
        "ix_sleep_segments_sleep_date",
        "sleep_segments",
        ["sleep_date"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        "ix_sleep_segments_start_at",
        "sleep_segments",
        ["start_at"],
        unique=False,
        schema=schema_name,
    )


def upgrade() -> None:
    schema_name = _schema_name()
    _create_menstrual_tables(schema_name)
    _create_body_measurement_table(schema_name)
    _create_sleep_segment_table(schema_name)


def downgrade() -> None:
    schema_name = _schema_name()
    op.drop_table("menstrual_day_factors", schema=schema_name)
    op.drop_table("sleep_segments", schema=schema_name)
    op.drop_table("body_measurements", schema=schema_name)
    op.drop_table("menstrual_days", schema=schema_name)
    op.drop_table("menstrual_factors", schema=schema_name)
