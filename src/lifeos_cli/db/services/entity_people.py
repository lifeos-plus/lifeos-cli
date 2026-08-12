"""Helpers for generic entity-to-person links.

Entity-to-person links live in the ``associations`` table with
``target_model='person'``. Writes canonicalize to ``link_type='is_about'``,
while reads treat every person-targeted association as a person link. The
service API mirrors the historical ``person_associations`` helpers so call
sites are unchanged while the storage is unified.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.association import (
    PERSON_LINK_TYPE,
    PERSON_TARGET_MODEL,
    Association,
)
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.services.entity_associations import (
    load_people_for_sources,
    set_association_links,
)


async def sync_entity_people(
    session: AsyncSession,
    *,
    entity_id: UUID,
    entity_type: str,
    desired_person_ids: list[UUID],
) -> None:
    """Replace an entity's linked people with the provided identifiers.

    All existing person-targeted associations for the entity are removed so
    links written with a non-canonical link type cannot survive a replace.
    """
    await session.execute(
        delete(Association).where(
            Association.source_model == entity_type,
            Association.source_id == entity_id,
            Association.target_model == PERSON_TARGET_MODEL,
        )
    )
    await set_association_links(
        session,
        source_model=entity_type,
        source_id=entity_id,
        target_model=PERSON_TARGET_MODEL,
        target_ids=desired_person_ids,
        link_type=PERSON_LINK_TYPE,
        replace=True,
    )


async def load_people_for_entities(
    session: AsyncSession,
    *,
    entity_ids: list[UUID],
    entity_type: str,
) -> dict[UUID, list[Person]]:
    """Return people grouped by entity identifier."""
    return await load_people_for_sources(
        session,
        source_model=entity_type,
        source_ids=entity_ids,
    )
