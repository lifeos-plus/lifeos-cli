from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from lifeos_cli.db.models.association import (
    ASSOCIATION_SOURCE_MODELS,
    PERSON_LINK_TYPE,
    PERSON_TARGET_MODEL,
    Association,
)
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.services import entity_associations, entity_person
from tests.support import sqlite_session_factory, utc_datetime


def test_association_reads_ignore_soft_deleted_endpoints() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                active_note = Note(content="active")
                deleted_note = Note(content="deleted")
                timelog = Timelog(
                    title="Deep work",
                    start_time=utc_datetime(2026, 6, 30, 13, 0),
                    end_time=utc_datetime(2026, 6, 30, 14, 0),
                )
                session.add_all([active_note, deleted_note, timelog])
                await session.flush()
                deleted_note.soft_delete()
                session.add_all(
                    [
                        Association(
                            source_model="note",
                            source_id=active_note.id,
                            target_model="timelog",
                            target_id=timelog.id,
                            link_type="captured_from",
                        ),
                        Association(
                            source_model="note",
                            source_id=deleted_note.id,
                            target_model="timelog",
                            target_id=timelog.id,
                            link_type="captured_from",
                        ),
                    ]
                )
                await session.flush()

                target_ids = await entity_associations.get_target_ids_for_sources(
                    session,
                    source_model="note",
                    source_ids=[active_note.id, deleted_note.id],
                    target_model="timelog",
                    link_type="captured_from",
                )
                counts = await entity_associations.count_sources_for_targets(
                    session,
                    source_model="note",
                    target_model="timelog",
                    target_ids=[timelog.id],
                    link_type="captured_from",
                )

                assert target_ids == {active_note.id: [timelog.id]}
                assert counts == {timelog.id: 1}

    asyncio.run(scenario())


def test_invalid_association_model_raises_validation_error() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                with pytest.raises(
                    entity_associations.AssociationValidationError,
                    match="Unsupported association model 'bogus'. Expected one of: ",
                ):
                    await entity_associations.set_association_links(
                        session,
                        source_model="bogus",
                        source_id=uuid4(),
                        target_model="note",
                        target_ids=[uuid4()],
                        link_type="is_about",
                    )

    asyncio.run(scenario())


def test_invalid_association_link_type_raises_validation_error() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                with pytest.raises(
                    entity_associations.AssociationValidationError,
                    match="Unsupported association link type 'bogus'. Expected one of: ",
                ):
                    await entity_associations.get_target_ids_for_sources(
                        session,
                        source_model="note",
                        source_ids=[uuid4()],
                        target_model="timelog",
                        link_type="bogus",
                    )

    asyncio.run(scenario())


def test_entity_person_links_are_stored_in_associations() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                person = Person(name="Alice")
                note = Note(content="Review integrity plan")
                session.add_all([person, note])
                await session.flush()

                await entity_person.sync_entity_person(
                    session,
                    entity_id=note.id,
                    entity_type="note",
                    desired_person_ids=[person.id],
                )
                await session.flush()

                links = list((await session.execute(select(Association))).scalars())
                assert len(links) == 1
                link = links[0]
                assert (
                    link.source_model,
                    link.source_id,
                    link.target_model,
                    link.target_id,
                    link.link_type,
                ) == ("note", note.id, PERSON_TARGET_MODEL, person.id, PERSON_LINK_TYPE)

                loaded_person_map = await entity_person.load_person_for_entities(
                    session,
                    entity_ids=[note.id],
                    entity_type="note",
                )
                assert loaded_person_map == {note.id: [person]}

    asyncio.run(scenario())


def test_sync_entity_person_replaces_links() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                first_person = Person(name="Alice")
                second_person = Person(name="Bob")
                note = Note(content="Replacement semantics")
                session.add_all([first_person, second_person, note])
                await session.flush()

                await entity_person.sync_entity_person(
                    session,
                    entity_id=note.id,
                    entity_type="note",
                    desired_person_ids=[first_person.id, second_person.id],
                )
                await session.flush()
                await entity_person.sync_entity_person(
                    session,
                    entity_id=note.id,
                    entity_type="note",
                    desired_person_ids=[second_person.id],
                )
                await session.flush()

                person = await entity_person.load_person_for_entities(
                    session,
                    entity_ids=[note.id],
                    entity_type="note",
                )
                assert [person.id for person in person[note.id]] == [second_person.id]

    asyncio.run(scenario())


def test_sync_entity_person_replaces_person_links_across_link_types() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                person = Person(name="Alice")
                note = Note(content="Canonical replacement")
                session.add_all([person, note])
                await session.flush()
                await entity_associations.set_association_links(
                    session,
                    source_model="note",
                    source_id=note.id,
                    target_model="person",
                    target_ids=[person.id],
                    link_type="relates_to",
                )
                await session.flush()

                await entity_person.sync_entity_person(
                    session,
                    entity_id=note.id,
                    entity_type="note",
                    desired_person_ids=[person.id],
                )
                await session.flush()

                links = list((await session.execute(select(Association))).scalars())
                assert len(links) == 1
                assert links[0].link_type == PERSON_LINK_TYPE
                loaded_person_map = await entity_person.load_person_for_entities(
                    session,
                    entity_ids=[note.id],
                    entity_type="note",
                )
                assert loaded_person_map == {note.id: [person]}

    asyncio.run(scenario())


def test_load_person_for_entities_returns_person_links_with_any_link_type() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                person = Person(name="Alice")
                note = Note(content="Non-canonical person link")
                session.add_all([person, note])
                await session.flush()
                await entity_associations.set_association_links(
                    session,
                    source_model="note",
                    source_id=note.id,
                    target_model="person",
                    target_ids=[person.id],
                    link_type="relates_to",
                )
                await session.flush()

                loaded_person_map = await entity_person.load_person_for_entities(
                    session,
                    entity_ids=[note.id],
                    entity_type="note",
                )
                assert loaded_person_map == {note.id: [person]}

    asyncio.run(scenario())


def test_load_person_for_entities_hides_soft_deleted_person() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                person = Person(name="Alice")
                note = Note(content="Soft delete scope")
                session.add_all([person, note])
                await session.flush()

                await entity_person.sync_entity_person(
                    session,
                    entity_id=note.id,
                    entity_type="note",
                    desired_person_ids=[person.id],
                )
                await session.flush()
                person.soft_delete()

                loaded_person_map = await entity_person.load_person_for_entities(
                    session,
                    entity_ids=[note.id],
                    entity_type="note",
                )
                assert loaded_person_map == {}

    asyncio.run(scenario())


def test_sync_entity_person_validates_source_model() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                with pytest.raises(
                    entity_associations.AssociationValidationError,
                    match="Unsupported association model 'bogus'. Expected one of: ",
                ):
                    await entity_person.sync_entity_person(
                        session,
                        entity_id=uuid4(),
                        entity_type="bogus",
                        desired_person_ids=[],
                    )

    asyncio.run(scenario())


def test_data_ops_entity_types_stay_within_allowlists() -> None:
    from lifeos_cli.db.services import data_ops
    from lifeos_cli.db.services import tags as tags_service

    for spec in data_ops.RESOURCE_SPECS.values():
        if spec.person_entity_type is not None:
            assert spec.person_entity_type in ASSOCIATION_SOURCE_MODELS
        if spec.tag_entity_type is not None:
            assert spec.tag_entity_type in tags_service.VALID_TAG_ENTITY_TYPES
