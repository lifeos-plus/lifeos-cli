"""Generic weak association model for cross-entity links.

This module is the single source of truth for association entity allowlists.
The same constants drive the ORM check constraints, service validators, and
data import/export adapters so the schema and service layers cannot drift.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from lifeos_cli.db.base import Base, TimestampedMixin, UUIDPrimaryKeyMixin
from lifeos_cli.db.models.event import Event
from lifeos_cli.db.models.habit_action import HabitAction
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.tag import Tag
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.models.timelog_template import TimelogTemplate
from lifeos_cli.db.models.vision import Vision

#: Entity types allowed on the source side of a weak association.
#: ``tag`` and ``timelog_template`` are sources for entity-to-person links.
ASSOCIATION_SOURCE_MODELS = frozenset(
    {
        "event",
        "habit_action",
        "note",
        "person",
        "tag",
        "task",
        "timelog",
        "timelog_template",
        "vision",
    }
)

#: Entity types allowed on the target side of a weak association.
#: ``tag`` is intentionally absent: tag membership is owned by
#: ``tag_associations``, so links cannot be duplicated across tables.
ASSOCIATION_TARGET_MODELS = frozenset(
    {
        "event",
        "habit_action",
        "note",
        "person",
        "task",
        "timelog",
        "vision",
    }
)

VALID_ASSOCIATION_LINK_TYPES = frozenset({"is_about", "relates_to", "captured_from"})

#: Canonical target model and link type for entity-to-person links.
PERSON_TARGET_MODEL = "person"
PERSON_LINK_TYPE = "is_about"

#: Mapping from entity type name to the ORM model used for endpoint checks.
ASSOCIATION_MODEL_MAP: dict[str, Any] = {
    "event": Event,
    "habit_action": HabitAction,
    "note": Note,
    "person": Person,
    "tag": Tag,
    "task": Task,
    "timelog": Timelog,
    "timelog_template": TimelogTemplate,
    "vision": Vision,
}


def _sql_quoted_list(values: frozenset[str]) -> str:
    """Render an allowlist as a deterministic SQL ``IN`` value list."""
    return ", ".join(f"'{value}'" for value in sorted(values))


class Association(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    """Directional weak link between two domain entities."""

    __tablename__ = "associations"
    __table_args__ = (
        CheckConstraint(
            f"source_model IN ({_sql_quoted_list(ASSOCIATION_SOURCE_MODELS)})",
            name="ck_associations_source_model_valid",
        ),
        CheckConstraint(
            f"target_model IN ({_sql_quoted_list(ASSOCIATION_TARGET_MODELS)})",
            name="ck_associations_target_model_valid",
        ),
        CheckConstraint(
            "link_type IN ('captured_from', 'is_about', 'relates_to')",
            name="ck_associations_link_type_valid",
        ),
        UniqueConstraint(
            "source_model",
            "source_id",
            "target_model",
            "target_id",
            "link_type",
            name="uq_associations_source_target_type",
        ),
        Index(
            "ix_associations_source_model_id_type",
            "source_model",
            "source_id",
            "link_type",
        ),
        Index(
            "ix_associations_target_model_id_type",
            "target_model",
            "target_id",
            "link_type",
        ),
    )

    source_model: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    target_model: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    def __repr__(self) -> str:
        return (
            "Association("
            f"id={self.id!s}, "
            f"{self.source_model}:{self.source_id!s} -> "
            f"{self.target_model}:{self.target_id!s}, "
            f"link_type={self.link_type!r})"
        )
