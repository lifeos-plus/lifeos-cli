"""Body weight and composition measurement model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Index, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin
from lifeos_cli.db.types import UTCDateTime


class BodyMeasurement(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """One body weight/body-composition measurement with a user-owned timestamp."""

    __tablename__ = "body_measurements"
    __table_args__ = (Index("ix_body_measurements_measured_at", "measured_at"),)

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
