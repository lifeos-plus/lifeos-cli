"""Async CRUD helpers for timelog quick templates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lifeos_cli.db.base import utc_now
from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.timelog_template import TimelogTemplate
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.entity_person import load_person_for_entities, sync_entity_person
from lifeos_cli.db.services.model_utils import (
    ensure_optional_reference_exists,
)
from lifeos_cli.db.services.read_models import TimelogTemplateView, build_timelog_template_view
from lifeos_cli.db.services.validation_utils import DomainValidationError

MAX_TEMPLATE_DURATION_MINUTES = 24 * 60
VALID_TEMPLATE_ORDERINGS = {"position", "usage", "recent"}


class TimelogTemplateNotFoundError(LookupError):
    """Raised when a timelog template cannot be found."""


class TimelogTemplateAlreadyExistsError(ValueError):
    """Raised when another active timelog template has the same title."""


class TimelogTemplateAreaReferenceNotFoundError(LookupError):
    """Raised when a referenced area cannot be found."""


class TimelogTemplateValidationError(DomainValidationError):
    """Raised when timelog template data is invalid."""


@dataclass(frozen=True)
class TimelogTemplateCreateInput:
    """Writable fields for creating a timelog quick template."""

    title: str
    area_id: UUID | None = None
    person_ids: list[UUID] | None = None
    default_duration_minutes: int | None = None
    position: int | None = None
    usage_count: int = 0
    last_used_at: datetime | None = None


@dataclass(frozen=True)
class TimelogTemplateUpdateInput:
    """Mutable fields for updating a timelog quick template."""

    title: str | None = None
    title_provided: bool = False
    area_id: UUID | None = None
    area_provided: bool = False
    person_ids: list[UUID] | None = None
    person_ids_provided: bool = False
    default_duration_minutes: int | None = None
    default_duration_minutes_provided: bool = False
    position: int | None = None
    position_provided: bool = False
    usage_count: int | None = None
    usage_count_provided: bool = False
    last_used_at: datetime | None = None
    last_used_at_provided: bool = False


@dataclass(frozen=True)
class TimelogTemplateListInput:
    """List intent for timelog quick templates."""

    limit: int = 50
    offset: int = 0
    order_by: str = "position"


def validate_template_title(title: str) -> str:
    """Validate and normalize a template title."""
    normalized = title.strip()
    if not normalized:
        raise TimelogTemplateValidationError("Timelog template title must not be empty")
    if len(normalized) > 200:
        raise TimelogTemplateValidationError(
            "Timelog template title must be 200 characters or fewer"
        )
    return normalized


def validate_template_duration(minutes: int | None) -> int | None:
    """Validate an optional template duration in minutes."""
    if minutes is None:
        return None
    if minutes < 1 or minutes > MAX_TEMPLATE_DURATION_MINUTES:
        raise TimelogTemplateValidationError(
            "Timelog template duration must be between 1 and 1440 minutes"
        )
    return minutes


def validate_template_position(position: int | None) -> int | None:
    """Validate an optional template display position."""
    if position is None:
        return None
    if position < 0:
        raise TimelogTemplateValidationError("Timelog template position must be 0 or greater")
    return position


def validate_template_usage_count(usage_count: int | None) -> int | None:
    """Validate an optional template usage counter."""
    if usage_count is None:
        return None
    if usage_count < 0:
        raise TimelogTemplateValidationError("Timelog template usage count must be 0 or greater")
    return usage_count


async def ensure_template_area_exists(session: AsyncSession, area_id: UUID | None) -> None:
    """Ensure an optional template area reference exists."""
    await ensure_optional_reference_exists(
        session,
        model_cls=Area,
        model_id=area_id,
        not_found_error_factory=lambda missing_id: TimelogTemplateAreaReferenceNotFoundError(
            f"Area {missing_id} was not found"
        ),
    )


async def _get_next_position(session: AsyncSession) -> int:
    stmt = select(func.max(TimelogTemplate.position)).where(TimelogTemplate.deleted_at.is_(None))
    current_max = (await session.execute(stmt)).scalar_one_or_none()
    return (current_max if current_max is not None else -1) + 1


async def _ensure_title_available(
    session: AsyncSession,
    *,
    title_normalized: str,
    excluding_template_id: UUID | None = None,
) -> None:
    stmt = select(TimelogTemplate.id).where(
        TimelogTemplate.title_normalized == title_normalized,
        TimelogTemplate.deleted_at.is_(None),
    )
    if excluding_template_id is not None:
        stmt = stmt.where(TimelogTemplate.id != excluding_template_id)
    existing_id = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if existing_id is not None:
        raise TimelogTemplateAlreadyExistsError("Timelog template title already exists")


async def _get_template_model(
    session: AsyncSession,
    *,
    template_id: UUID,
) -> TimelogTemplate | None:
    stmt = (
        select(TimelogTemplate)
        .options(selectinload(TimelogTemplate.area.and_(Area.deleted_at.is_(None))))
        .where(TimelogTemplate.id == template_id)
        .limit(1)
    )
    stmt = stmt.where(TimelogTemplate.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def _build_template_views(
    session: AsyncSession,
    templates: list[TimelogTemplate],
) -> list[TimelogTemplateView]:
    if not templates:
        return []
    template_ids = [template.id for template in templates]
    person_map = await load_person_for_entities(
        session,
        entity_ids=template_ids,
        entity_type="timelog_template",
    )
    return [
        build_timelog_template_view(
            template,
            person_records=person_map.get(template.id, ()),
        )
        for template in templates
    ]


async def _build_template_view(
    session: AsyncSession,
    template: TimelogTemplate,
) -> TimelogTemplateView:
    refreshed = await _get_template_model(
        session,
        template_id=template.id,
    )
    if refreshed is not None:
        template = refreshed
    views = await _build_template_views(session, [template])
    return views[0]


def _order_by(order_by: str) -> tuple[Any, ...]:
    if order_by not in VALID_TEMPLATE_ORDERINGS:
        raise TimelogTemplateValidationError(
            "Timelog template ordering must be one of: position, usage, recent"
        )
    if order_by == "usage":
        return (
            TimelogTemplate.usage_count.desc(),
            TimelogTemplate.last_used_at.desc(),
            TimelogTemplate.position.asc(),
            TimelogTemplate.title.asc(),
        )
    if order_by == "recent":
        return (
            TimelogTemplate.last_used_at.desc(),
            TimelogTemplate.updated_at.desc(),
            TimelogTemplate.position.asc(),
        )
    return (TimelogTemplate.position.asc(), TimelogTemplate.title.asc())


async def list_templates(
    session: AsyncSession,
    *,
    query: TimelogTemplateListInput | None = None,
) -> list[TimelogTemplateView]:
    """List active timelog quick templates."""
    resolved_query = query or TimelogTemplateListInput()
    stmt = (
        select(TimelogTemplate)
        .options(selectinload(TimelogTemplate.area.and_(Area.deleted_at.is_(None))))
        .where(TimelogTemplate.deleted_at.is_(None))
        .order_by(*_order_by(resolved_query.order_by))
        .offset(resolved_query.offset)
        .limit(resolved_query.limit)
    )
    templates = list((await session.execute(stmt)).scalars())
    return await _build_template_views(session, templates)


async def count_templates(session: AsyncSession) -> int:
    """Count active timelog quick templates."""
    stmt = select(func.count()).select_from(
        select(TimelogTemplate.id).where(TimelogTemplate.deleted_at.is_(None)).subquery()
    )
    return int((await session.execute(stmt)).scalar_one())


async def create_template(
    session: AsyncSession,
    *,
    payload: TimelogTemplateCreateInput,
) -> TimelogTemplateView:
    """Create a timelog quick template."""
    title = validate_template_title(payload.title)
    title_normalized = title.lower()
    await _ensure_title_available(session, title_normalized=title_normalized)
    await ensure_template_area_exists(session, payload.area_id)
    position = validate_template_position(payload.position)
    if position is None:
        position = await _get_next_position(session)
    template = TimelogTemplate(
        title=title,
        title_normalized=title_normalized,
        area_id=payload.area_id,
        default_duration_minutes=validate_template_duration(payload.default_duration_minutes),
        position=position,
        usage_count=validate_template_usage_count(payload.usage_count) or 0,
        last_used_at=payload.last_used_at,
    )
    session.add(template)
    await session.flush()
    if payload.person_ids is not None:
        await sync_entity_person(
            session,
            entity_id=template.id,
            entity_type="timelog_template",
            desired_person_ids=payload.person_ids,
        )
    await session.flush()
    await session.refresh(template)
    return await _build_template_view(session, template)


async def update_template(
    session: AsyncSession,
    *,
    template_id: UUID,
    changes: TimelogTemplateUpdateInput,
) -> TimelogTemplateView:
    """Update one active timelog quick template."""
    template = await _get_template_model(
        session,
        template_id=template_id,
    )
    if template is None:
        raise TimelogTemplateNotFoundError(f"Timelog template {template_id} was not found")

    if changes.title_provided:
        if changes.title is None:
            raise TimelogTemplateValidationError("Timelog template title must not be null")
        title = validate_template_title(changes.title)
        title_normalized = title.lower()
        await _ensure_title_available(
            session,
            title_normalized=title_normalized,
            excluding_template_id=template.id,
        )
        template.title = title
        template.title_normalized = title_normalized

    if changes.area_provided:
        await ensure_template_area_exists(session, changes.area_id)
        template.area_id = changes.area_id

    if changes.default_duration_minutes_provided:
        template.default_duration_minutes = validate_template_duration(
            changes.default_duration_minutes
        )

    if changes.position_provided:
        if changes.position is None:
            raise TimelogTemplateValidationError("Timelog template position must not be null")
        template.position = validate_template_position(changes.position) or 0

    if changes.usage_count_provided:
        if changes.usage_count is None:
            raise TimelogTemplateValidationError("Timelog template usage count must not be null")
        template.usage_count = validate_template_usage_count(changes.usage_count) or 0

    if changes.last_used_at_provided:
        template.last_used_at = changes.last_used_at

    if changes.person_ids_provided:
        await sync_entity_person(
            session,
            entity_id=template.id,
            entity_type="timelog_template",
            desired_person_ids=changes.person_ids or [],
        )

    await session.flush()
    await session.refresh(template)
    return await _build_template_view(session, template)


async def delete_template(session: AsyncSession, *, template_id: UUID) -> None:
    """Soft-delete one timelog quick template."""
    template = await _get_template_model(
        session,
        template_id=template_id,
    )
    if template is None:
        raise TimelogTemplateNotFoundError(f"Timelog template {template_id} was not found")
    template.soft_delete()
    await session.flush()


async def reorder_templates(
    session: AsyncSession,
    *,
    positions: list[tuple[UUID, int]],
) -> None:
    """Update display positions for multiple templates."""
    if not positions:
        return
    unique_pairs = [
        (template_id, validate_template_position(position) or 0)
        for template_id, position in deduplicate_preserving_order(positions)
    ]
    template_ids = [template_id for template_id, _ in unique_pairs]
    rows = await session.execute(
        select(TimelogTemplate).where(
            TimelogTemplate.id.in_(template_ids),
            TimelogTemplate.deleted_at.is_(None),
        )
    )
    templates_by_id = {template.id: template for template in rows.scalars()}
    missing = [template_id for template_id in template_ids if template_id not in templates_by_id]
    if missing:
        missing_text = ", ".join(str(template_id) for template_id in missing)
        raise TimelogTemplateNotFoundError(f"Timelog templates not found: {missing_text}")
    for template_id, position in unique_pairs:
        templates_by_id[template_id].position = position
    await session.flush()


async def bump_template_usage(
    session: AsyncSession,
    *,
    template_id: UUID,
    when: datetime | None = None,
) -> TimelogTemplateView:
    """Increment one template's usage metadata."""
    template = await _get_template_model(
        session,
        template_id=template_id,
    )
    if template is None:
        raise TimelogTemplateNotFoundError(f"Timelog template {template_id} was not found")
    template.touch_usage(when=when or utc_now())
    await session.flush()
    await session.refresh(template)
    return await _build_template_view(session, template)
