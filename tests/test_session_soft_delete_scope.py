from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.timelog import Timelog
from tests.support import sqlite_session_factory, utc_datetime


def test_session_queries_exclude_soft_deleted_models_by_default() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                active_area = Area(name="Active")
                deleted_area = Area(name="Deleted")
                session.add_all([active_area, deleted_area])
                await session.flush()
                deleted_area.soft_delete()
                await session.commit()

            async with session_factory() as session:
                areas = list((await session.execute(select(Area))).scalars())

                assert [area.name for area in areas] == ["Active"]

    asyncio.run(scenario())


def test_session_relationship_loads_exclude_soft_deleted_models_by_default() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                area = Area(name="Deleted area")
                session.add(area)
                await session.flush()
                timelog = Timelog(
                    title="Deep work",
                    start_time=utc_datetime(2026, 6, 30, 13, 0),
                    end_time=utc_datetime(2026, 6, 30, 14, 0),
                    area_id=area.id,
                )
                session.add(timelog)
                await session.flush()
                area.soft_delete()
                await session.commit()

            async with session_factory() as session:
                loaded = (
                    await session.execute(select(Timelog).options(selectinload(Timelog.area)))
                ).scalar_one()

                assert loaded.area_id == area.id
                assert loaded.area is None

    asyncio.run(scenario())
