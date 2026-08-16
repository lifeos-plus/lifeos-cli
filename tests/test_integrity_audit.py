"""Unit tests for the weak-association referential integrity audit."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from lifeos_cli.db.base import Base
from lifeos_cli.db.models.association import Association
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.tag import Tag
from lifeos_cli.db.models.tag_association import tag_associations
from lifeos_cli.db.services import entity_person, entity_tags
from lifeos_cli.db.services.integrity_audit import (
    IntegrityAuditReport,
    audit_referential_integrity,
)
from tests.support import sqlite_session_factory


@asynccontextmanager
async def _fk_disabled_session_factory():
    """Yield a session factory whose SQLite engine has foreign keys disabled."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, future=True)
    try:
        yield factory
    finally:
        await engine.dispose()


def _issue_kinds(report: IntegrityAuditReport) -> set[str]:
    return {issue.kind for issue in report.issues}


def test_audit_flags_and_repairs_dangling_association_endpoints() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                missing_source = uuid4()
                missing_target = uuid4()
                session.add(
                    Association(
                        source_model="note",
                        source_id=missing_source,
                        target_model="person",
                        target_id=missing_target,
                        link_type="is_about",
                    )
                )
                await session.flush()

                report = await audit_referential_integrity(session)
                assert {"missing_source", "missing_target"} <= _issue_kinds(report)

                repaired = await audit_referential_integrity(session, repair=True)
                assert repaired.repaired_count == 1

                clean = await audit_referential_integrity(session)
                assert clean.ok

    asyncio.run(scenario())


def test_audit_preserves_soft_deleted_endpoint_links() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                person = Person(name="Alice")
                note = Note(content="Restorable link")
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
                await session.flush()

                report = await audit_referential_integrity(session)
                assert "soft_deleted_target" in _issue_kinds(report)
                assert "missing_target" not in _issue_kinds(report)

                repaired = await audit_referential_integrity(session, repair=True)
                assert repaired.repaired_count == 0
                remaining = await audit_referential_integrity(session)
                assert "soft_deleted_target" in _issue_kinds(remaining)

    asyncio.run(scenario())


def test_audit_flags_duplicate_person_links_across_link_types() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                person = Person(name="Alice")
                note = Note(content="Duplicate link")
                session.add_all([person, note])
                await session.flush()
                session.add_all(
                    [
                        Association(
                            source_model="note",
                            source_id=note.id,
                            target_model="person",
                            target_id=person.id,
                            link_type="is_about",
                        ),
                        Association(
                            source_model="note",
                            source_id=note.id,
                            target_model="person",
                            target_id=person.id,
                            link_type="relates_to",
                        ),
                    ]
                )
                await session.flush()

                report = await audit_referential_integrity(session)
                assert "duplicate" in _issue_kinds(report)

    asyncio.run(scenario())


def test_audit_detects_and_repairs_dangling_tag_associations() -> None:
    async def scenario() -> None:
        async with _fk_disabled_session_factory() as session_factory:
            async with session_factory() as session:
                missing_entity = uuid4()
                missing_tag = uuid4()
                await session.execute(
                    tag_associations.insert().values(
                        entity_type="note",
                        entity_id=missing_entity,
                        tag_id=missing_tag,
                    )
                )
                await session.flush()

                report = await audit_referential_integrity(session)
                assert {"missing_entity", "missing_tag"} <= _issue_kinds(report)

                repaired = await audit_referential_integrity(session, repair=True)
                assert repaired.repaired_count == 1
                assert (await audit_referential_integrity(session)).ok

    asyncio.run(scenario())


def test_audit_flags_invalid_tag_entity_type() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                tag = Tag(name="review", entity_type="note")
                session.add(tag)
                await session.flush()
                await session.execute(
                    tag_associations.insert().values(
                        entity_type="bogus",
                        entity_id=uuid4(),
                        tag_id=tag.id,
                    )
                )
                await session.flush()

                report = await audit_referential_integrity(session)
                assert "invalid_entity_type" in _issue_kinds(report)
                assert report.repaired_count == 0

    asyncio.run(scenario())


def test_audit_reports_clean_for_valid_links() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                person = Person(name="Alice")
                note = Note(content="Clean link")
                tag = Tag(name="review", entity_type="note")
                session.add_all([person, note, tag])
                await session.flush()
                await entity_person.sync_entity_person(
                    session,
                    entity_id=note.id,
                    entity_type="note",
                    desired_person_ids=[person.id],
                )
                await entity_tags.sync_entity_tags(
                    session,
                    entity_id=note.id,
                    entity_type="note",
                    desired_tag_ids=[tag.id],
                )
                await session.flush()

                report = await audit_referential_integrity(session)
                assert report.ok

    asyncio.run(scenario())
