"""Async CRUD helpers for tags."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.association import Association
from lifeos_cli.db.models.event import Event
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.tag import Tag
from lifeos_cli.db.models.tag_association import tag_associations
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.models.vision import Vision
from lifeos_cli.db.services.batching import BatchDeleteResult, batch_delete_records
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.entity_person import load_person_for_entities, sync_entity_person
from lifeos_cli.db.services.model_utils import (
    load_model_by_id,
    load_view_by_id,
    soft_delete_model_by_id,
)
from lifeos_cli.db.services.read_models import TagView, build_tag_view
from lifeos_cli.db.services.validation_utils import DomainValidationError, choice_validator

VALID_TAG_ENTITY_TYPES = {"note", "person", "task", "vision", "area", "event", "timelog"}
TAGGED_ENTITY_MODELS = {
    "area": Area,
    "event": Event,
    "note": Note,
    "person": Person,
    "task": Task,
    "timelog": Timelog,
    "vision": Vision,
}


class TagNotFoundError(LookupError):
    """Raised when a tag cannot be found."""


class TagAlreadyExistsError(ValueError):
    """Raised when a tag with the same identity already exists."""


class InvalidTagEntityTypeError(DomainValidationError):
    """Raised when an unsupported tag entity type is requested."""


def normalize_tag_name(name: str) -> str:
    """Normalize a tag name."""
    normalized = name.strip().lower()
    if not normalized:
        raise ValueError("Tag name must not be empty")
    return normalized


validate_tag_entity_type = choice_validator(
    VALID_TAG_ENTITY_TYPES,
    error_cls=InvalidTagEntityTypeError,
    label="tag entity type",
    error_verb="Unsupported",
    doc="Validate a tag entity type.",
)


def normalize_tag_category(category: str | None) -> str:
    """Normalize a tag category."""
    normalized = (category or "").strip().lower()
    return normalized or "general"


async def create_tag(
    session: AsyncSession,
    *,
    name: str,
    entity_type: str,
    category: str = "general",
    description: str | None = None,
    color: str | None = None,
    person_ids: list[UUID] | None = None,
) -> TagView:
    """Create a new tag."""
    normalized_name = normalize_tag_name(name)
    normalized_entity_type = validate_tag_entity_type(entity_type)
    normalized_category = normalize_tag_category(category)
    existing = await session.execute(
        select(Tag).where(
            Tag.name == normalized_name,
            Tag.entity_type == normalized_entity_type,
            Tag.category == normalized_category,
            Tag.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise TagAlreadyExistsError(
            "Tag with the same name, entity type, and category already exists"
        )
    tag = Tag(
        name=normalized_name,
        entity_type=normalized_entity_type,
        category=normalized_category,
        description=description,
        color=color,
    )
    session.add(tag)
    await session.flush()
    if person_ids is not None:
        await sync_entity_person(
            session, entity_id=tag.id, entity_type="tag", desired_person_ids=person_ids
        )
    await session.refresh(tag)
    return await _build_tag_view(session, tag)


async def _build_tag_view(session: AsyncSession, tag: Tag) -> TagView:
    person_map = await load_person_for_entities(session, entity_ids=[tag.id], entity_type="tag")
    return build_tag_view(tag, person_records=person_map.get(tag.id, ()))


async def _build_tag_views(session: AsyncSession, tags: list[Tag]) -> list[TagView]:
    if not tags:
        return []
    person_map = await load_person_for_entities(
        session,
        entity_ids=[tag.id for tag in tags],
        entity_type="tag",
    )
    return [build_tag_view(tag, person_records=person_map.get(tag.id, ())) for tag in tags]


async def get_tag(
    session: AsyncSession,
    *,
    tag_id: UUID,
) -> TagView | None:
    """Load a tag by identifier."""
    return await load_view_by_id(
        session,
        model_cls=Tag,
        model_id=tag_id,
        view_builder=_build_tag_view,
    )


async def list_tags(
    session: AsyncSession,
    *,
    entity_type: str | None = None,
    category: str | None = None,
    person_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TagView]:
    """List tags with optional filters."""
    stmt = select(Tag)
    stmt = stmt.where(Tag.deleted_at.is_(None))
    if entity_type is not None:
        stmt = stmt.where(Tag.entity_type == validate_tag_entity_type(entity_type))
    if category is not None:
        stmt = stmt.where(Tag.category == normalize_tag_category(category))
    if person_id is not None:
        stmt = stmt.join(
            Association,
            (Association.source_model == "tag")
            & (Association.source_id == Tag.id)
            & (Association.target_model == "person"),
        ).where(Association.target_id == person_id)
    stmt = stmt.order_by(Tag.name.asc(), Tag.id.asc()).offset(offset).limit(limit)
    tags = list((await session.execute(stmt)).scalars())
    return await _build_tag_views(session, tags)


async def list_tag_categories(
    session: AsyncSession,
    *,
    entity_type: str | None = None,
) -> list[str]:
    """List normalized categories present on tags."""
    stmt = select(Tag.category).distinct()
    stmt = stmt.where(Tag.deleted_at.is_(None))
    if entity_type is not None:
        stmt = stmt.where(Tag.entity_type == validate_tag_entity_type(entity_type))
    rows = (await session.execute(stmt)).scalars()
    categories = {normalize_tag_category(category) for category in rows}
    categories.add("general")
    return sorted(categories)


async def update_tag(
    session: AsyncSession,
    *,
    tag_id: UUID,
    name: str | None = None,
    entity_type: str | None = None,
    category: str | None = None,
    description: str | None = None,
    clear_description: bool = False,
    color: str | None = None,
    clear_color: bool = False,
    person_ids: list[UUID] | None = None,
    clear_person: bool = False,
) -> TagView:
    """Update a tag."""
    tag = await load_model_by_id(
        session,
        model_cls=Tag,
        model_id=tag_id,
    )
    if tag is None:
        raise TagNotFoundError(f"Tag {tag_id} was not found")
    next_name = normalize_tag_name(name) if name is not None else tag.name
    next_entity_type = validate_tag_entity_type(entity_type) if entity_type else tag.entity_type
    next_category = normalize_tag_category(category) if category is not None else tag.category
    conflict = await session.execute(
        select(Tag.id).where(
            Tag.name == next_name,
            Tag.entity_type == next_entity_type,
            Tag.category == next_category,
            Tag.id != tag_id,
            Tag.deleted_at.is_(None),
        )
    )
    if conflict.scalar_one_or_none() is not None:
        raise TagAlreadyExistsError(
            "Tag with the same name, entity type, and category already exists"
        )
    tag.name = next_name
    tag.entity_type = next_entity_type
    tag.category = next_category
    if clear_description:
        tag.description = None
    elif description is not None:
        tag.description = description
    if clear_color:
        tag.color = None
    elif color is not None:
        tag.color = color
    if clear_person:
        await sync_entity_person(
            session, entity_id=tag.id, entity_type="tag", desired_person_ids=[]
        )
    elif person_ids is not None:
        await sync_entity_person(
            session, entity_id=tag.id, entity_type="tag", desired_person_ids=person_ids
        )
    await session.flush()
    await session.refresh(tag)
    return await _build_tag_view(session, tag)


async def rename_tag_category(
    session: AsyncSession,
    *,
    entity_type: str,
    category: str,
    new_category: str,
) -> list[TagView]:
    """Move all active tags in one category to another category."""
    normalized_entity_type = validate_tag_entity_type(entity_type)
    normalized_category = normalize_tag_category(category)
    normalized_new_category = normalize_tag_category(new_category)
    if normalized_category == normalized_new_category:
        return []

    stmt = select(Tag).where(
        Tag.entity_type == normalized_entity_type,
        Tag.category == normalized_category,
        Tag.deleted_at.is_(None),
    )
    tags = list((await session.execute(stmt)).scalars())
    conflict_names: list[str] = []
    for tag in tags:
        conflict = await session.execute(
            select(Tag.id).where(
                Tag.name == tag.name,
                Tag.entity_type == normalized_entity_type,
                Tag.category == normalized_new_category,
                Tag.id != tag.id,
                Tag.deleted_at.is_(None),
            )
        )
        if conflict.scalar_one_or_none() is not None:
            conflict_names.append(tag.name)
    if conflict_names:
        preview = ", ".join(sorted(conflict_names)[:3])
        suffix = "" if len(conflict_names) <= 3 else f", and {len(conflict_names) - 3} more"
        raise TagAlreadyExistsError(
            f"Cannot rename category because matching tags already exist: {preview}{suffix}"
        )
    for tag in tags:
        tag.category = normalized_new_category
    await session.flush()
    return await _build_tag_views(session, tags)


async def bulk_update_tag_categories(
    session: AsyncSession,
    *,
    tag_ids: list[UUID],
    category: str,
) -> tuple[list[TagView], list[UUID], list[str]]:
    """Move selected active tags to another category with per-tag errors."""
    normalized_category = normalize_tag_category(category)
    updated: list[Tag] = []
    failed_ids: list[UUID] = []
    errors: list[str] = []

    for tag_id in deduplicate_preserving_order(tag_ids):
        tag = await load_model_by_id(
            session,
            model_cls=Tag,
            model_id=tag_id,
        )
        if tag is None:
            failed_ids.append(tag_id)
            errors.append(f"Tag {tag_id} was not found")
            continue
        conflict = await session.execute(
            select(Tag.id).where(
                Tag.name == tag.name,
                Tag.entity_type == tag.entity_type,
                Tag.category == normalized_category,
                Tag.id != tag.id,
                Tag.deleted_at.is_(None),
            )
        )
        if conflict.scalar_one_or_none() is not None:
            failed_ids.append(tag_id)
            errors.append("Tag with the same name, entity type, and category already exists")
            continue
        tag.category = normalized_category
        updated.append(tag)

    await session.flush()
    return await _build_tag_views(session, updated), failed_ids, errors


async def count_tag_usage_by_entity_type(
    session: AsyncSession,
    *,
    entity_type: str,
) -> dict[UUID, int]:
    """Count active tagged records by tag for one entity type."""
    normalized_entity_type = validate_tag_entity_type(entity_type)
    entity_model: Any = TAGGED_ENTITY_MODELS[normalized_entity_type]
    stmt = (
        select(tag_associations.c.tag_id, func.count(func.distinct(entity_model.id)))
        .join(Tag, Tag.id == tag_associations.c.tag_id)
        .join(entity_model, entity_model.id == tag_associations.c.entity_id)
        .where(
            tag_associations.c.entity_type == normalized_entity_type,
            Tag.entity_type == normalized_entity_type,
            Tag.deleted_at.is_(None),
            entity_model.deleted_at.is_(None),
        )
        .group_by(tag_associations.c.tag_id)
    )
    rows = await session.execute(stmt)
    return {tag_id: int(count) for tag_id, count in rows.all()}


async def count_tag_usage(session: AsyncSession, *, tag_id: UUID) -> int:
    """Count active tagged records for one tag."""
    tag = await load_model_by_id(
        session,
        model_cls=Tag,
        model_id=tag_id,
    )
    if tag is None:
        raise TagNotFoundError(f"Tag {tag_id} was not found")
    usage_counts = await count_tag_usage_by_entity_type(session, entity_type=tag.entity_type)
    return usage_counts.get(tag_id, 0)


async def delete_tag(session: AsyncSession, *, tag_id: UUID) -> None:
    """Soft-delete a tag."""
    await soft_delete_model_by_id(
        session,
        model_cls=Tag,
        model_id=tag_id,
        not_found_error_factory=lambda missing_id: TagNotFoundError(
            f"Tag {missing_id} was not found"
        ),
    )


async def batch_delete_tags(
    session: AsyncSession,
    *,
    tag_ids: list[UUID],
) -> BatchDeleteResult:
    """Soft-delete multiple tags while preserving per-tag error reporting."""
    return await batch_delete_records(
        identifiers=deduplicate_preserving_order(tag_ids),
        delete_record=lambda tag_id: delete_tag(session, tag_id=tag_id),
        handled_exceptions=(TagNotFoundError,),
    )
