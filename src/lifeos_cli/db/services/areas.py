"""Async CRUD helpers for areas."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.area import Area
from lifeos_cli.db.services.batching import BatchDeleteResult, batch_delete_records
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.model_utils import load_model_by_id
from lifeos_cli.db.session import INCLUDE_SOFT_DELETED_EXECUTION_OPTION


class AreaNotFoundError(LookupError):
    """Raised when an area cannot be found."""


class AreaAlreadyExistsError(ValueError):
    """Raised when an area with the same name already exists."""


async def create_area(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    color: str = "#3B82F6",
    icon: str | None = None,
    is_active: bool = True,
    display_order: int = 0,
) -> Area:
    """Create a new area, restoring a hidden area with the same name."""
    normalized_name = name.strip()
    existing = await session.execute(
        select(Area).where(Area.name == normalized_name, Area.deleted_at.is_(None)).limit(1)
    )
    existing_area = existing.scalar_one_or_none()
    if existing_area is not None and existing_area.is_active:
        raise AreaAlreadyExistsError(f"Area with name {normalized_name!r} already exists")
    if existing_area is not None:
        existing_area.description = description
        existing_area.color = color
        existing_area.icon = icon
        existing_area.is_active = is_active
        existing_area.display_order = display_order
        await session.flush()
        await session.refresh(existing_area)
        return existing_area
    deleted = await session.execute(
        select(Area)
        .where(Area.name == normalized_name, Area.deleted_at.is_not(None))
        .order_by(Area.deleted_at.desc(), Area.updated_at.desc())
        .limit(1)
        .execution_options(**{INCLUDE_SOFT_DELETED_EXECUTION_OPTION: True})
    )
    restored_area = deleted.scalar_one_or_none()
    if restored_area is not None:
        restored_area.deleted_at = None
        restored_area.description = description
        restored_area.color = color
        restored_area.icon = icon
        restored_area.is_active = is_active
        restored_area.display_order = display_order
        await session.flush()
        await session.refresh(restored_area)
        return restored_area
    area = Area(
        name=normalized_name,
        description=description,
        color=color,
        icon=icon,
        is_active=is_active,
        display_order=display_order,
    )
    session.add(area)
    await session.flush()
    await session.refresh(area)
    return area


async def get_area(
    session: AsyncSession,
    *,
    area_id: UUID,
) -> Area | None:
    """Load an area by identifier."""
    return await load_model_by_id(
        session,
        model_cls=Area,
        model_id=area_id,
    )


async def list_areas(
    session: AsyncSession,
    *,
    include_inactive: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[Area]:
    """List areas in display order."""
    stmt = select(Area)
    stmt = stmt.where(Area.deleted_at.is_(None))
    if not include_inactive:
        stmt = stmt.where(Area.is_active.is_(True))
    stmt = stmt.order_by(Area.display_order.asc(), Area.name.asc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars())


async def update_area(
    session: AsyncSession,
    *,
    area_id: UUID,
    name: str | None = None,
    description: str | None = None,
    clear_description: bool = False,
    color: str | None = None,
    icon: str | None = None,
    clear_icon: bool = False,
    is_active: bool | None = None,
    display_order: int | None = None,
) -> Area:
    """Update an area's mutable fields."""
    area = await get_area(session, area_id=area_id)
    if area is None:
        raise AreaNotFoundError(f"Area {area_id} was not found")
    if name is not None:
        normalized_name = name.strip()
        conflict = await session.execute(
            select(Area.id).where(
                Area.name == normalized_name,
                Area.id != area_id,
                Area.deleted_at.is_(None),
            )
        )
        if conflict.scalar_one_or_none() is not None:
            raise AreaAlreadyExistsError(f"Area with name {normalized_name!r} already exists")
        area.name = normalized_name
    if clear_description:
        area.description = None
    elif description is not None:
        area.description = description
    if color is not None:
        area.color = color
    if clear_icon:
        area.icon = None
    elif icon is not None:
        area.icon = icon
    if is_active is not None:
        area.is_active = is_active
    if display_order is not None:
        area.display_order = display_order
    await session.flush()
    await session.refresh(area)
    return area


async def delete_area(session: AsyncSession, *, area_id: UUID) -> None:
    area = await get_area(session, area_id=area_id)
    if area is None:
        raise AreaNotFoundError(f"Area {area_id} was not found")
    area.soft_delete()
    area.is_active = False
    await session.flush()


async def batch_delete_areas(
    session: AsyncSession,
    *,
    area_ids: list[UUID],
) -> BatchDeleteResult:
    """Soft-delete multiple areas while preserving per-area error reporting."""
    return await batch_delete_records(
        identifiers=deduplicate_preserving_order(area_ids),
        delete_record=lambda area_id: delete_area(session, area_id=area_id),
        handled_exceptions=(AreaNotFoundError,),
    )
