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


def test_tag_services_can_skip_person_enrichment(monkeypatch) -> None:
    """Web consumers can opt out of the person read-back used by CLI output."""

    async def run() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:

                async def fail_load(*args, **kwargs) -> dict:
                    raise AssertionError("person enrichment must be skipped")

                monkeypatch.setattr(tags, "load_person_for_entities", fail_load)

                first = await tags.create_tag(
                    session,
                    name="Alpha",
                    entity_type="note",
                    category="topic",
                    include_person=False,
                )
                second = await tags.create_tag(
                    session,
                    name="Beta",
                    entity_type="note",
                    category="topic",
                    include_person=False,
                )
                assert first.person == ()
                assert second.person == ()

                loaded = await tags.get_tag(session, tag_id=first.id, include_person=False)
                assert loaded is not None
                assert loaded.person == ()

                listed = await tags.list_tags(session, include_person=False)
                assert len(listed) == 2
                assert all(item.person == () for item in listed)

                updated = await tags.update_tag(
                    session,
                    tag_id=first.id,
                    color="#111111",
                    include_person=False,
                )
                assert updated.person == ()

                renamed = await tags.rename_tag_category(
                    session,
                    entity_type="note",
                    category="topic",
                    new_category="work",
                    include_person=False,
                )
                assert all(item.person == () for item in renamed)

                bulk, _, _ = await tags.bulk_update_tag_categories(
                    session,
                    tag_ids=[second.id],
                    category="work",
                    include_person=False,
                )
                assert all(item.person == () for item in bulk)

    asyncio.run(run())
