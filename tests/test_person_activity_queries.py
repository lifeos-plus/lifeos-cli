"""Unit tests for person activity timeline queries."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.services import person_activity_queries


def test_list_person_activities_paginates_and_calculates_timelog_metadata(
    monkeypatch,
) -> None:
    timestamp = datetime(2026, 7, 2, 9, 0, tzinfo=timezone.utc)
    activities = [
        person_activity_queries.PersonActivity(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            activity_type="timelog",
            title="Deep work",
            description=None,
            activity_date=timestamp,
            start_time=timestamp,
            end_time=datetime(2026, 7, 2, 9, 30, tzinfo=timezone.utc),
        ),
        person_activity_queries.PersonActivity(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            activity_type="timelog",
            title="Review",
            description=None,
            activity_date=timestamp,
            start_time=timestamp,
            end_time=datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc),
        ),
    ]

    async def fake_load_activity_items(
        _session: object,
        **_kwargs: object,
    ) -> list[person_activity_queries.PersonActivity]:
        return activities

    monkeypatch.setattr(person_activity_queries, "_load_activity_items", fake_load_activity_items)

    result = asyncio.run(
        person_activity_queries.list_person_activities(
            cast(AsyncSession, object()),
            person_id=UUID("33333333-3333-3333-3333-333333333333"),
            activity_filter="timelog",
            limit=1,
            offset=1,
        )
    )

    assert result.items == (activities[1],)
    assert result.total == 2
    assert result.timelog_count == 2
    assert result.timelog_total_minutes == 90
