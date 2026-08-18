"""Tag endpoints for the local Web UI."""

from __future__ import annotations

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.services import tags as tag_services
from lifeos_cli.db.services.tags import VALID_TAG_ENTITY_TYPES
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.tags import (
    TagBulkUpdateResponse,
    TagCategoryResponse,
    TagListMeta,
    TagResponse,
    TagSelectorResponse,
    TagUsageResponse,
)
from lifeos_web.router_utils import soft_delete
from lifeos_web.schemas import (
    ListResponse,
    Pagination,
    TagBulkCategoryUpdate,
    TagCategoryCreate,
    TagCategoryUpdate,
    TagCreate,
    TagUpdate,
)
from lifeos_web.serialization import to_jsonable_dict

router = APIRouter(prefix="/tags", tags=["tags"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

DEFAULT_TAG_CATEGORIES: dict[str, tuple[str, ...]] = {
    "note": ("general", "topic"),
    "person": ("general", "location", "relation", "profession", "team"),
}
TAG_LIST_FIELD_MODES = {"selector", "full"}
TAG_SELECTOR_FIELDS = ("id", "name", "entity_type", "category")


def _tag_payload(row: object, *, fields: str) -> dict[str, object]:
    payload = to_jsonable_dict(row)
    payload.pop("deleted_at", None)
    payload.pop("person", None)
    if fields == "selector":
        return {field: payload[field] for field in TAG_SELECTOR_FIELDS}
    return payload


def _category_label(value: str) -> str:
    """Return the fallback label for a category value."""
    return value.replace("_", " ").title() if value else "General"


def _category_option(value: str, entity_type: str | None) -> dict[str, object]:
    normalized = tag_services.normalize_tag_category(value)
    return {
        "value": normalized,
        "label": _category_label(normalized),
        "entity_type": entity_type,
    }


def _normalize_category_value(payload: TagCategoryCreate | TagCategoryUpdate) -> str:
    raw = getattr(payload, "value", None) or payload.label
    return tag_services.normalize_tag_category(raw.replace(" ", "_"))


@router.get(
    "/",
    response_model=ListResponse[TagSelectorResponse | TagResponse, TagListMeta],
    response_model_exclude_unset=True,
)
async def list_tags(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=1000)] = 100,
    entity_type: str | None = None,
    category: str | None = None,
    fields: Annotated[str, Query(pattern="^(selector|full)$")] = "full",
) -> ListResponse:
    """List LifeOS tags for selectors and tag management."""
    if fields not in TAG_LIST_FIELD_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported tag fields mode: {fields}")
    offset = (page - 1) * size
    try:
        rows = await tag_services.list_tags(
            session,
            entity_type=entity_type,
            category=category,
            limit=size,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items = [_tag_payload(row, fields=fields) for row in rows]
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=size,
            total=len(items),
            pages=math.ceil(len(items) / size) if size else 0,
        ),
        meta={"entity_type": entity_type, "category": category, "fields": fields},
    )


@router.get("/entity-types/", response_model=list[str])
async def list_tag_entity_types() -> list[str]:
    """Return supported LifeOS tag entity types."""
    return sorted(VALID_TAG_ENTITY_TYPES)


@router.get("/categories/", response_model=list[TagCategoryResponse])
async def list_tag_categories(
    session: SessionDep,
    entity_type: str | None = None,
) -> list[dict[str, object]]:
    """Return built-in and persisted tag categories."""
    try:
        normalized_entity_type = (
            tag_services.validate_tag_entity_type(entity_type) if entity_type else None
        )
        categories = set(
            await tag_services.list_tag_categories(
                session,
                entity_type=normalized_entity_type,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    categories.update(DEFAULT_TAG_CATEGORIES.get(normalized_entity_type or "", ("general",)))
    return [_category_option(category, normalized_entity_type) for category in sorted(categories)]


@router.post("/categories/", response_model=TagCategoryResponse)
async def create_tag_category(
    payload: TagCategoryCreate,
    entity_type: str | None = None,
) -> dict[str, object]:
    """Return a normalized tag category option for the scoped entity type."""
    try:
        normalized_entity_type = (
            tag_services.validate_tag_entity_type(entity_type) if entity_type else None
        )
        return _category_option(_normalize_category_value(payload), normalized_entity_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/categories/{category}", response_model=TagCategoryResponse)
async def rename_tag_category(
    category: str,
    payload: TagCategoryUpdate,
    session: SessionDep,
    entity_type: str | None = None,
) -> dict[str, object]:
    """Rename a tag category by moving its active tags."""
    if not entity_type:
        raise HTTPException(status_code=400, detail="Tag category rename requires entity_type")
    try:
        normalized_entity_type = tag_services.validate_tag_entity_type(entity_type)
        next_category = _normalize_category_value(payload)
        await tag_services.rename_tag_category(
            session,
            entity_type=normalized_entity_type,
            category=category,
            new_category=next_category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _category_option(next_category, normalized_entity_type)


@router.patch("/batch-update", response_model=TagBulkUpdateResponse)
async def bulk_update_tag_categories(
    payload: TagBulkCategoryUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Move selected tags to another category."""
    try:
        updated_tags, failed_ids, errors = await tag_services.bulk_update_tag_categories(
            session,
            tag_ids=payload.ids,
            category=payload.category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "updated_count": len(updated_tags),
        "failed_ids": [str(tag_id) for tag_id in failed_ids],
        "errors": errors,
        "updated_tags": [_tag_payload(tag, fields="full") for tag in updated_tags],
    }


@router.post("/", response_model=TagResponse)
async def create_tag(payload: TagCreate, session: SessionDep) -> dict[str, object]:
    """Create a LifeOS tag."""
    try:
        tag = await tag_services.create_tag(
            session,
            name=payload.name,
            entity_type=payload.entity_type,
            category=payload.category,
            description=payload.description,
            color=payload.color,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _tag_payload(tag, fields="full")


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(tag_id: UUID, session: SessionDep) -> dict[str, object]:
    """Return one LifeOS tag."""
    tag = await tag_services.get_tag(session, tag_id=tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} was not found")
    return _tag_payload(tag, fields="full")


@router.get("/{tag_id}/usage", response_model=TagUsageResponse)
async def get_tag_usage(tag_id: UUID, session: SessionDep) -> dict[str, object]:
    """Return active tagged-record count for one tag."""
    tag = await tag_services.get_tag(session, tag_id=tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} was not found")
    usage_count = await tag_services.count_tag_usage(session, tag_id=tag_id)
    return {
        "tag_id": str(tag.id),
        "tag_name": tag.name,
        "entity_type": tag.entity_type,
        "category": tag.category,
        "usage_by_entity_type": {tag.entity_type: usage_count},
        "total_usage": usage_count,
    }


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: UUID,
    payload: TagUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update one LifeOS tag."""
    fields = payload.model_fields_set
    try:
        tag = await tag_services.update_tag(
            session,
            tag_id=tag_id,
            name=payload.name,
            entity_type=payload.entity_type,
            category=payload.category,
            description=payload.description,
            clear_description="description" in fields and payload.description is None,
            color=payload.color,
            clear_color="color" in fields and payload.color is None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _tag_payload(tag, fields="full")


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(tag_id: UUID, session: SessionDep) -> None:
    """Soft-delete a LifeOS tag."""
    await soft_delete(tag_services.delete_tag, session=session, tag_id=tag_id)
