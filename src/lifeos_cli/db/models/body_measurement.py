"""Body weight and composition measurement model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Index, Numeric, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin
from lifeos_cli.db.types import UTCDateTime


class BodyMeasurement(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """One body weight/body-composition measurement with a user-owned timestamp."""

    __tablename__ = "body_measurements"
    __table_args__ = (
        CheckConstraint(
            "weight_kg > 0 AND weight_kg <= 1000",
            name="ck_body_measurements_weight_valid",
        ),
        CheckConstraint(
            "(body_fat_percentage IS NULL OR body_fat_percentage BETWEEN 0 AND 100) AND "
            "(muscle_percentage IS NULL OR muscle_percentage BETWEEN 0 AND 100) AND "
            "(visceral_fat IS NULL OR visceral_fat BETWEEN 0 AND 100)",
            name="ck_body_measurements_percentages_valid",
        ),
        CheckConstraint(
            "(fat_mass_kg IS NULL OR fat_mass_kg BETWEEN 0 AND 1000) AND "
            "(muscle_mass_kg IS NULL OR muscle_mass_kg BETWEEN 0 AND 1000) AND "
            "(body_water_kg IS NULL OR body_water_kg BETWEEN 0 AND 1000) AND "
            "(protein_kg IS NULL OR protein_kg BETWEEN 0 AND 1000) AND "
            "(bone_mass_kg IS NULL OR bone_mass_kg BETWEEN 0 AND 1000) AND "
            "(skeletal_muscle_kg IS NULL OR skeletal_muscle_kg BETWEEN 0 AND 1000)",
            name="ck_body_measurements_masses_valid",
        ),
        Index(
            "uq_body_measurements_measured_at_active",
            "measured_at",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    measured_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    body_fat_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    visceral_fat: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    fat_mass_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    muscle_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    muscle_mass_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    body_water_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    protein_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    bone_mass_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    skeletal_muscle_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"BodyMeasurement(id={self.id!s}, weight_kg={self.weight_kg!r})"
