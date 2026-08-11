from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lifeos_cli.db.base import Base
from lifeos_cli.db.models.association import Association
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.services import entity_associations
from lifeos_cli.db.session import configure_async_engine
from tests.support import utc_datetime


async def _create_sqlite_session_factory() -> tuple[
    AsyncEngine,
    async_sessionmaker[AsyncSession],
]:
    engine = configure_async_engine(
        create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, future=True)


def test_association_reads_ignore_soft_deleted_endpoints() -> None:
    async def scenario() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
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
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_invalid_association_model_raises_validation_error() -> None:
    async def scenario() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
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
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_invalid_association_link_type_raises_validation_error() -> None:
    async def scenario() -> None:
        engine, session_factory = await _create_sqlite_session_factory()
        try:
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
        finally:
            await engine.dispose()

    asyncio.run(scenario())
