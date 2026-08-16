from __future__ import annotations

import asyncio

from lifeos_cli.db.services import person, tags
from tests.support import sqlite_session_factory


def test_count_person_tag_usage_counts_active_tagged_person() -> None:
    async def run() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                tag = await tags.create_tag(
                    session,
                    name="Mentor",
                    entity_type="person",
                    category="relationship",
                )
                active_person = await person.create_person(
                    session,
                    name="Alice",
                    tag_ids=[tag.id],
                )
                deleted_person = await person.create_person(
                    session,
                    name="Bob",
                    tag_ids=[tag.id],
                )
                await person.delete_person(session, person_id=deleted_person.id)

                counts = await tags.count_tag_usage_by_entity_type(
                    session,
                    entity_type="person",
                )

                assert counts == {tag.id: 1}
                assert await tags.count_tag_usage(session, tag_id=tag.id) == 1
                assert active_person.tags[0].id == tag.id

    asyncio.run(run())
