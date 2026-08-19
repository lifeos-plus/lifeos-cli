"""Menstrual cycle models: daily records, custom factors, and their link table."""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin

menstrual_day_factors = Table(
    "menstrual_day_factors",
    Base.metadata,
    Column(
        "menstrual_day_id",
        Uuid,
        ForeignKey("menstrual_days.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "factor_id",
        Uuid,
        ForeignKey("menstrual_factors.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Index("ix_menstrual_day_factors_factor_id", "factor_id"),
)


class MenstrualFactor(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """User-defined factor that can be attached to menstrual day records."""

    __tablename__ = "menstrual_factors"
    __table_args__ = (
        Index(
            "uq_menstrual_factors_name_active",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    days = relationship(
        "MenstrualDay",
        secondary=menstrual_day_factors,
        back_populates="factors",
    )

    def __repr__(self) -> str:
        return f"MenstrualFactor(id={self.id!s}, name={self.name!r})"


class MenstrualDay(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """One daily menstrual-cycle record for a local calendar date."""

    __tablename__ = "menstrual_days"
    __table_args__ = (
        Index("ix_menstrual_days_log_date", "log_date"),
        Index(
            "uq_menstrual_days_log_date_active",
            "log_date",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    in_period: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flow_amount: Mapped[str | None] = mapped_column(String(16), nullable=True)
    symptoms: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    personality_behavior: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    protection_used: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    spotting: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    factors: Mapped[list[MenstrualFactor]] = relationship(
        "MenstrualFactor",
        secondary=menstrual_day_factors,
        back_populates="days",
    )

    def __repr__(self) -> str:
        return (
            f"MenstrualDay(id={self.id!s}, log_date={self.log_date!s}, "
            f"in_period={self.in_period!r})"
        )
