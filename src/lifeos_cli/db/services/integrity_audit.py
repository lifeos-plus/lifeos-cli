"""Referential integrity audit for generic weak associations.

The audit is read-only by default and reports hard-dangling links, invalid
entity types, duplicates, and soft-deleted endpoints as distinct categories.
Repair is an explicit opt-in that deletes only hard-dangling rows; soft-deleted
endpoints are preserved because their links remain restorable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.association import (
    ASSOCIATION_MODEL_MAP,
    ASSOCIATION_SOURCE_MODELS,
    ASSOCIATION_TARGET_MODELS,
    Association,
)
from lifeos_cli.db.models.tag import Tag
from lifeos_cli.db.models.tag_association import tag_associations
from lifeos_cli.db.services.tags import TAGGED_ENTITY_MODELS, VALID_TAG_ENTITY_TYPES
from lifeos_cli.db.session import INCLUDE_SOFT_DELETED_EXECUTION_OPTION

_SOFT_DELETED_EXECUTION_OPTIONS = {INCLUDE_SOFT_DELETED_EXECUTION_OPTION: True}


@dataclass(frozen=True)
class IntegrityIssue:
    """One detected referential-integrity issue."""

    table: str
    kind: str
    message: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    related_type: str | None = None
    related_id: UUID | None = None
    link_type: str | None = None


@dataclass(frozen=True)
class IntegrityAuditReport:
    """Result of an integrity audit, optionally with repaired row counts."""

    issues: tuple[IntegrityIssue, ...]
    repaired_count: int = 0

    @property
    def ok(self) -> bool:
        """Return whether the audited tables are clean."""
        return not self.issues and self.repaired_count == 0


async def _load_endpoint_sets(
    session: AsyncSession,
    model: Any,
) -> tuple[set[UUID], set[UUID]]:
    """Return ``(existing ids incl. soft-deleted, soft-deleted ids)`` for one model."""
    stmt = select(model.id).execution_options(**_SOFT_DELETED_EXECUTION_OPTIONS)
    rows = await session.execute(stmt)
    existing_ids = set(rows.scalars().all())
    if not hasattr(model, "deleted_at"):
        return existing_ids, set()
    deleted_rows = await session.execute(
        select(model.id)
        .where(model.deleted_at.is_not(None))
        .execution_options(**_SOFT_DELETED_EXECUTION_OPTIONS)
    )
    return existing_ids, set(deleted_rows.scalars().all())


async def audit_associations(
    session: AsyncSession,
    *,
    repair: bool = False,
) -> IntegrityAuditReport:
    """Audit the ``associations`` table; optionally repair hard-dangling rows."""
    rows = (
        await session.execute(
            select(
                Association.id,
                Association.source_model,
                Association.source_id,
                Association.target_model,
                Association.target_id,
                Association.link_type,
            )
        )
    ).all()
    issues: list[IntegrityIssue] = []
    repair_ids: list[UUID] = []
    source_rows: dict[str, list[tuple[UUID, UUID]]] = {}
    target_rows: dict[str, list[tuple[UUID, UUID]]] = {}
    duplicate_keys: dict[tuple[str, UUID, str, UUID], set[str]] = {}

    for row in rows:
        (
            association_id,
            source_model,
            source_id,
            target_model,
            target_id,
            link_type,
        ) = row
        source_rows.setdefault(source_model, []).append((association_id, source_id))
        target_rows.setdefault(target_model, []).append((association_id, target_id))
        key = (source_model, source_id, target_model, target_id)
        duplicate_keys.setdefault(key, set()).add(link_type)
        if source_model not in ASSOCIATION_SOURCE_MODELS:
            issues.append(
                IntegrityIssue(
                    table="associations",
                    kind="invalid_source_type",
                    message=(f"Unsupported source model {source_model!r} in associations"),
                    entity_type=source_model,
                    entity_id=source_id,
                    related_type=target_model,
                    related_id=target_id,
                    link_type=link_type,
                )
            )
        if target_model not in ASSOCIATION_TARGET_MODELS:
            issues.append(
                IntegrityIssue(
                    table="associations",
                    kind="invalid_target_type",
                    message=(f"Unsupported target model {target_model!r} in associations"),
                    entity_type=source_model,
                    entity_id=source_id,
                    related_type=target_model,
                    related_id=target_id,
                    link_type=link_type,
                )
            )

    for model_name, rows_for_model in source_rows.items():
        if model_name not in ASSOCIATION_SOURCE_MODELS:
            continue
        existing_ids, deleted_ids = await _load_endpoint_sets(
            session, ASSOCIATION_MODEL_MAP[model_name]
        )
        for association_id, entity_id in rows_for_model:
            if entity_id not in existing_ids:
                issues.append(
                    IntegrityIssue(
                        table="associations",
                        kind="missing_source",
                        message=f"Source {model_name}:{entity_id} does not exist",
                        entity_type=model_name,
                        entity_id=entity_id,
                    )
                )
                repair_ids.append(association_id)
            elif entity_id in deleted_ids:
                issues.append(
                    IntegrityIssue(
                        table="associations",
                        kind="soft_deleted_source",
                        message=f"Source {model_name}:{entity_id} is soft-deleted",
                        entity_type=model_name,
                        entity_id=entity_id,
                    )
                )

    for model_name, rows_for_model in target_rows.items():
        if model_name not in ASSOCIATION_TARGET_MODELS:
            continue
        existing_ids, deleted_ids = await _load_endpoint_sets(
            session, ASSOCIATION_MODEL_MAP[model_name]
        )
        for association_id, entity_id in rows_for_model:
            if entity_id not in existing_ids:
                issues.append(
                    IntegrityIssue(
                        table="associations",
                        kind="missing_target",
                        message=f"Target {model_name}:{entity_id} does not exist",
                        related_type=model_name,
                        related_id=entity_id,
                    )
                )
                repair_ids.append(association_id)
            elif entity_id in deleted_ids:
                issues.append(
                    IntegrityIssue(
                        table="associations",
                        kind="soft_deleted_target",
                        message=f"Target {model_name}:{entity_id} is soft-deleted",
                        related_type=model_name,
                        related_id=entity_id,
                    )
                )

    for key, link_types in duplicate_keys.items():
        if len(link_types) <= 1:
            continue
        source_model, source_id, target_model, target_id = key
        issues.append(
            IntegrityIssue(
                table="associations",
                kind="duplicate",
                message=(
                    f"{source_model}:{source_id} -> {target_model}:{target_id} "
                    f"linked with multiple link types: {', '.join(sorted(link_types))}"
                ),
                entity_type=source_model,
                entity_id=source_id,
                related_type=target_model,
                related_id=target_id,
                link_type=", ".join(sorted(link_types)),
            )
        )

    repaired_count = 0
    if repair and repair_ids:
        unique_repair_ids = list(dict.fromkeys(repair_ids))
        await session.execute(delete(Association).where(Association.id.in_(unique_repair_ids)))
        repaired_count = len(unique_repair_ids)
    return IntegrityAuditReport(tuple(issues), repaired_count)


async def audit_tag_associations(
    session: AsyncSession,
    *,
    repair: bool = False,
) -> IntegrityAuditReport:
    """Audit the ``tag_associations`` table; optionally repair dangling rows."""
    rows = (
        await session.execute(
            select(
                tag_associations.c.entity_type,
                tag_associations.c.entity_id,
                tag_associations.c.tag_id,
            )
        )
    ).all()
    issues: list[IntegrityIssue] = []
    repair_rows: set[tuple[str, UUID, UUID]] = set()
    entity_rows: dict[str, list[tuple[UUID, UUID]]] = {}

    for entity_type, entity_id, tag_id in rows:
        if entity_type not in VALID_TAG_ENTITY_TYPES:
            issues.append(
                IntegrityIssue(
                    table="tag_associations",
                    kind="invalid_entity_type",
                    message=f"Unsupported entity type {entity_type!r} in tag_associations",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    related_type="tag",
                    related_id=tag_id,
                )
            )
            continue
        entity_rows.setdefault(entity_type, []).append((entity_id, tag_id))

    tag_existing_ids, tag_deleted_ids = await _load_endpoint_sets(session, Tag)
    for entity_type, pairs in entity_rows.items():
        existing_ids, deleted_ids = await _load_endpoint_sets(
            session, TAGGED_ENTITY_MODELS[entity_type]
        )
        for entity_id, tag_id in pairs:
            if entity_id not in existing_ids:
                issues.append(
                    IntegrityIssue(
                        table="tag_associations",
                        kind="missing_entity",
                        message=(
                            f"Entity {entity_type}:{entity_id} does not exist in tag_associations"
                        ),
                        entity_type=entity_type,
                        entity_id=entity_id,
                        related_type="tag",
                        related_id=tag_id,
                    )
                )
                repair_rows.add((entity_type, entity_id, tag_id))
            elif entity_id in deleted_ids:
                issues.append(
                    IntegrityIssue(
                        table="tag_associations",
                        kind="soft_deleted_entity",
                        message=(
                            f"Entity {entity_type}:{entity_id} is soft-deleted in tag_associations"
                        ),
                        entity_type=entity_type,
                        entity_id=entity_id,
                        related_type="tag",
                        related_id=tag_id,
                    )
                )
            if tag_id not in tag_existing_ids:
                issues.append(
                    IntegrityIssue(
                        table="tag_associations",
                        kind="missing_tag",
                        message=f"Tag {tag_id} does not exist in tag_associations",
                        entity_type=entity_type,
                        entity_id=entity_id,
                        related_type="tag",
                        related_id=tag_id,
                    )
                )
                repair_rows.add((entity_type, entity_id, tag_id))
            elif tag_id in tag_deleted_ids:
                issues.append(
                    IntegrityIssue(
                        table="tag_associations",
                        kind="soft_deleted_tag",
                        message=f"Tag {tag_id} is soft-deleted in tag_associations",
                        entity_type=entity_type,
                        entity_id=entity_id,
                        related_type="tag",
                        related_id=tag_id,
                    )
                )

    repaired_count = 0
    if repair and repair_rows:
        for entity_type, entity_id, tag_id in repair_rows:
            await session.execute(
                delete(tag_associations).where(
                    tag_associations.c.entity_type == entity_type,
                    tag_associations.c.entity_id == entity_id,
                    tag_associations.c.tag_id == tag_id,
                )
            )
        repaired_count = len(repair_rows)
    return IntegrityAuditReport(tuple(issues), repaired_count)


async def audit_referential_integrity(
    session: AsyncSession,
    *,
    repair: bool = False,
) -> IntegrityAuditReport:
    """Audit all weak association tables; repair only when explicitly requested."""
    associations_report = await audit_associations(session, repair=repair)
    tags_report = await audit_tag_associations(session, repair=repair)
    return IntegrityAuditReport(
        issues=associations_report.issues + tags_report.issues,
        repaired_count=associations_report.repaired_count + tags_report.repaired_count,
    )
