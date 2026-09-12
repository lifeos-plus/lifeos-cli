"""Event occurrence exception model for recurring event series."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin
from lifeos_cli.db.types import UTCDateTime

EVENT_OCCURRENCE_ACTIONS = frozenset({"skip"})


class EventOccurrenceException(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """Exception row describing a skipped recurring event instance."""

    __tablename__ = "event_occurrence_exceptions"
    __table_args__ = (
        CheckConstraint("action IN ('skip')", name="action_valid"),
        Index("ix_event_occurrence_exceptions_master_event_id", "master_event_id"),
        Index("ix_event_occurrence_exceptions_instance_start", "instance_start"),
        Index(
            "uq_evt_occur_exc_master_id_start_active",
            "master_event_id",
            "instance_start",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    master_event_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False, default="skip")
    instance_start: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    master_event = relationship("Event", foreign_keys=[master_event_id])

    def __repr__(self) -> str:
        return (
            "EventOccurrenceException("
            f"id={self.id!s}, master_event_id={self.master_event_id!s}, action={self.action!r})"
        )
