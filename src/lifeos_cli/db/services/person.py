"""Async CRUD helpers for person."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.tag_association import tag_associations
from lifeos_cli.db.services.batching import BatchDeleteResult, batch_delete_records
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.entity_tags import load_tags_for_entities, sync_entity_tags
from lifeos_cli.db.services.model_utils import (
    load_model_by_id,
    load_view_by_id,
    soft_delete_model_by_id,
)
from lifeos_cli.db.services.read_models import PersonView, build_person_view


class PersonNotFoundError(LookupError):
    """Raised when a person cannot be found."""


class PersonAlreadyExistsError(ValueError):
    """Raised when a person with the same name already exists."""


async def _build_person_view(session: AsyncSession, person: Person) -> PersonView:
    tags_map = await load_tags_for_entities(
        session,
        entity_ids=[person.id],
        entity_type="person",
    )
    return build_person_view(person, tags=tags_map.get(person.id, ()))


async def _build_person_views(
    session: AsyncSession,
    person_records: list[Person],
) -> list[PersonView]:
    if not person_records:
        return []
    tags_map = await load_tags_for_entities(
        session,
        entity_ids=[person.id for person in person_records],
        entity_type="person",
    )
    return [
        build_person_view(person, tags=tags_map.get(person.id, ())) for person in person_records
    ]


async def create_person(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    nicknames: list[str] | None = None,
    birth_date: date | None = None,
    location: str | None = None,
    tag_ids: list[UUID] | None = None,
) -> PersonView:
    """Create a new person."""
    normalized_name = name.strip()
    existing = await session.execute(
        select(Person).where(Person.name == normalized_name, Person.deleted_at.is_(None)).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        raise PersonAlreadyExistsError(f"Person with name {normalized_name!r} already exists")
    person = Person(
        name=normalized_name,
        description=description,
        nicknames=nicknames or None,
        birth_date=birth_date,
        location=location,
    )
    session.add(person)
    await session.flush()
    if tag_ids:
        await sync_entity_tags(
            session,
            entity_id=person.id,
            entity_type="person",
            desired_tag_ids=tag_ids,
        )
    await session.refresh(person)
    return await _build_person_view(session, person)


async def get_person(
    session: AsyncSession,
    *,
    person_id: UUID,
) -> PersonView | None:
    """Load a person by identifier."""
    return await load_view_by_id(
        session,
        model_cls=Person,
        model_id=person_id,
        view_builder=_build_person_view,
    )


async def list_person(
    session: AsyncSession,
    *,
    search: str | None = None,
    tag_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[PersonView]:
    """List people, optionally filtered by search or tag."""
    stmt = select(Person)
    stmt = stmt.where(Person.deleted_at.is_(None))
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Person.name.ilike(pattern),
                cast(Person.nicknames, Text).ilike(pattern),
                Person.location.ilike(pattern),
            )
        )
    if tag_id is not None:
        stmt = stmt.join(
            tag_associations,
            (tag_associations.c.entity_id == Person.id)
            & (tag_associations.c.entity_type == "person"),
        ).where(tag_associations.c.tag_id == tag_id)
    stmt = stmt.order_by(Person.created_at.desc(), Person.id.desc()).offset(offset).limit(limit)
    person_records = list((await session.execute(stmt)).scalars())
    return await _build_person_views(session, person_records)


async def update_person(
    session: AsyncSession,
    *,
    person_id: UUID,
    name: str | None = None,
    description: str | None = None,
    clear_description: bool = False,
    nicknames: list[str] | None = None,
    clear_nicknames: bool = False,
    birth_date: date | None = None,
    clear_birth_date: bool = False,
    location: str | None = None,
    clear_location: bool = False,
    tag_ids: list[UUID] | None = None,
    clear_tags: bool = False,
) -> PersonView:
    """Update a person."""
    person = await load_model_by_id(
        session,
        model_cls=Person,
        model_id=person_id,
    )
    if person is None:
        raise PersonNotFoundError(f"Person {person_id} was not found")
    if name is not None:
        normalized_name = name.strip()
        if normalized_name != person.name:
            conflict = await session.execute(
                select(Person.id).where(
                    Person.name == normalized_name,
                    Person.id != person_id,
                    Person.deleted_at.is_(None),
                )
            )
            if conflict.scalar_one_or_none() is not None:
                raise PersonAlreadyExistsError(
                    f"Person with name {normalized_name!r} already exists"
                )
        person.name = normalized_name
    if clear_description:
        person.description = None
    elif description is not None:
        person.description = description
    if clear_nicknames:
        person.nicknames = None
    elif nicknames is not None:
        person.nicknames = nicknames
    if clear_birth_date:
        person.birth_date = None
    elif birth_date is not None:
        person.birth_date = birth_date
    if clear_location:
        person.location = None
    elif location is not None:
        person.location = location
    if clear_tags:
        await sync_entity_tags(
            session,
            entity_id=person.id,
            entity_type="person",
            desired_tag_ids=[],
        )
    elif tag_ids is not None:
        await sync_entity_tags(
            session,
            entity_id=person.id,
            entity_type="person",
            desired_tag_ids=tag_ids,
        )
    await session.flush()
    await session.refresh(person)
    return await _build_person_view(session, person)


async def delete_person(
    session: AsyncSession,
    *,
    person_id: UUID,
) -> None:
    """Soft-delete a person."""
    await soft_delete_model_by_id(
        session,
        model_cls=Person,
        model_id=person_id,
        not_found_error_factory=lambda missing_id: PersonNotFoundError(
            f"Person {missing_id} was not found"
        ),
    )


async def batch_delete_person(
    session: AsyncSession,
    *,
    person_ids: list[UUID],
) -> BatchDeleteResult:
    """Soft-delete multiple people while preserving per-person error reporting."""
    return await batch_delete_records(
        identifiers=deduplicate_preserving_order(person_ids),
        delete_record=lambda person_id: delete_person(session, person_id=person_id),
        handled_exceptions=(PersonNotFoundError,),
    )
