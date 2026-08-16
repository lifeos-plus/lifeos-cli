from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.timelog_template import TimelogTemplate
from lifeos_cli.db.services import timelog_templates
from tests.support import sqlite_session_factory


def test_create_template_hydrates_area_and_person() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                area = Area(name="Work", color="#123456", display_order=1)
                person = Person(name="Alice")
                session.add_all([area, person])
                await session.flush()

                template = await timelog_templates.create_template(
                    session,
                    payload=timelog_templates.TimelogTemplateCreateInput(
                        title="Deep Work",
                        area_id=area.id,
                        person_ids=[person.id],
                        default_duration_minutes=90,
                    ),
                )

                assert template.title == "Deep Work"
                assert template.area_id == area.id
                assert template.area_name == "Work"
                assert template.area_color == "#123456"
                assert template.person_ids == (person.id,)
                assert [summary.name for summary in template.person] == ["Alice"]
                assert template.default_duration_minutes == 90
                assert template.position == 0

    asyncio.run(scenario())


def test_list_templates_does_not_hydrate_soft_deleted_area() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                area = Area(name="Archived area", color="#123456", display_order=1)
                session.add(area)
                await session.flush()
                template = TimelogTemplate(
                    title="Archived area template",
                    title_normalized="archived area template",
                    area_id=area.id,
                )
                session.add(template)
                await session.flush()
                area.soft_delete()
                await session.commit()

            async with session_factory() as session:
                templates = await timelog_templates.list_templates(session)

                assert len(templates) == 1
                assert templates[0].area_id == area.id
                assert templates[0].area_name is None
                assert templates[0].area_color is None

    asyncio.run(scenario())


def test_create_template_rejects_duplicate_active_title() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await timelog_templates.create_template(
                    session,
                    payload=timelog_templates.TimelogTemplateCreateInput(title="Focus Block"),
                )

                with pytest.raises(timelog_templates.TimelogTemplateAlreadyExistsError):
                    await timelog_templates.create_template(
                        session,
                        payload=timelog_templates.TimelogTemplateCreateInput(title=" focus block "),
                    )

    asyncio.run(scenario())


def test_update_template_can_clear_optional_fields() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                area = Area(name="Health", color="#00AA00", display_order=1)
                person = Person(name="Coach")
                session.add_all([area, person])
                await session.flush()
                template = await timelog_templates.create_template(
                    session,
                    payload=timelog_templates.TimelogTemplateCreateInput(
                        title="Run",
                        area_id=area.id,
                        person_ids=[person.id],
                        default_duration_minutes=30,
                    ),
                )

                updated = await timelog_templates.update_template(
                    session,
                    template_id=template.id,
                    changes=timelog_templates.TimelogTemplateUpdateInput(
                        area_provided=True,
                        area_id=None,
                        person_ids_provided=True,
                        person_ids=[],
                        default_duration_minutes_provided=True,
                        default_duration_minutes=None,
                    ),
                )

                assert updated.area_id is None
                assert updated.area_name is None
                assert updated.person_ids == ()
                assert updated.person == ()
                assert updated.default_duration_minutes is None

    asyncio.run(scenario())


def test_reorder_and_bump_usage_update_templates() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                first = await timelog_templates.create_template(
                    session,
                    payload=timelog_templates.TimelogTemplateCreateInput(title="First"),
                )
                second = await timelog_templates.create_template(
                    session,
                    payload=timelog_templates.TimelogTemplateCreateInput(title="Second"),
                )

                await timelog_templates.reorder_templates(
                    session,
                    positions=[(first.id, 2), (second.id, 0)],
                )
                fixed_now = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
                used = await timelog_templates.bump_template_usage(
                    session,
                    template_id=first.id,
                    when=fixed_now,
                )
                listed = await timelog_templates.list_templates(
                    session,
                    query=timelog_templates.TimelogTemplateListInput(order_by="position"),
                )

                assert used.usage_count == 1
                assert used.last_used_at == fixed_now
                assert [(item.title, item.position) for item in listed] == [
                    ("Second", 0),
                    ("First", 2),
                ]

    asyncio.run(scenario())
