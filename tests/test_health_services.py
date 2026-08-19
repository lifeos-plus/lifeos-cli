"""Service-level tests for menstrual, body, and sleep health domains."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from lifeos_cli.db.services import body_measurements as body_services
from lifeos_cli.db.services import menstrual as menstrual_services
from lifeos_cli.db.services import sleep as sleep_services
from tests.support import sqlite_session_factory


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_menstrual_factor_and_day_lifecycle() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                factor = await menstrual_services.create_menstrual_factor(
                    session,
                    name="travel",
                )
                assert factor.name == "travel"
                with pytest.raises(menstrual_services.MenstrualValidationError):
                    await menstrual_services.create_menstrual_factor(session, name="travel")

                day = await menstrual_services.create_menstrual_day(
                    session,
                    log_date=date(2026, 8, 19),
                    in_period=True,
                    flow_amount="medium",
                    symptoms=["headache", "hot_flash", "headache"],
                    factor_names=["travel", "travel"],
                    spotting=True,
                    notes="  evening notes  ",
                )
                assert day.flow_amount == "medium"
                assert day.symptoms == ["headache", "hot_flash"]
                assert sorted(f.name for f in day.factors) == ["travel"]
                assert day.notes == "evening notes"

                with pytest.raises(menstrual_services.MenstrualValidationError):
                    await menstrual_services.create_menstrual_day(
                        session,
                        log_date=date(2026, 8, 19),
                    )
                with pytest.raises(menstrual_services.MenstrualValidationError):
                    await menstrual_services.create_menstrual_day(
                        session,
                        log_date=date(2026, 8, 20),
                        flow_amount="high",
                    )

                listed = await menstrual_services.list_menstrual_days(session)
                assert len(listed) == 1
                assert await menstrual_services.count_menstrual_days(session) == 1

                updated = await menstrual_services.update_menstrual_day(
                    session,
                    day_id=day.id,
                    flow_amount="low",
                    clear_symptoms=True,
                    clear_notes=True,
                )
                assert updated.flow_amount == "low"
                assert updated.symptoms is None
                assert updated.notes is None

                await menstrual_services.delete_menstrual_day(session, day_id=day.id)
                assert await menstrual_services.get_menstrual_day(session, day_id=day.id) is None

                await menstrual_services.delete_menstrual_factor(
                    session,
                    factor_id=factor.id,
                )
                with pytest.raises(menstrual_services.MenstrualFactorNotFoundError):
                    await menstrual_services.delete_menstrual_factor(
                        session,
                        factor_id=factor.id,
                    )

    asyncio.run(scenario())


def test_body_measurement_unit_conversion_and_update() -> None:
    assert body_services.to_kg(140, "jin") == Decimal("70.00")
    assert body_services.from_kg(Decimal("70.00"), "jin") == Decimal("140.00")
    assert body_services.compute_bmi(70, 175) == Decimal("22.9")
    assert body_services.compute_bmi(70, None) is None
    with pytest.raises(body_services.BodyMeasurementValidationError):
        body_services.to_kg(2000, "kg")

    async def scenario() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                measurement = await body_services.create_body_measurement(
                    session,
                    payload=body_services.BodyMeasurementCreate(
                        measured_at=_utc(2026, 8, 19, 8),
                        weight=127,
                        unit="jin",
                        body_fat_percentage=22.5,
                        notes="morning",
                    ),
                )
                assert measurement.weight_kg == Decimal("63.50")
                assert measurement.body_fat_percentage == Decimal("22.50")

                listed = await body_services.list_body_measurements(session)
                assert len(listed) == 1
                assert await body_services.count_body_measurements(session) == 1

                updated = await body_services.update_body_measurement(
                    session,
                    measurement_id=measurement.id,
                    payload=body_services.BodyMeasurementUpdate(
                        weight=65,
                        clear_fields=frozenset({"body_fat_percentage"}),
                    ),
                )
                assert updated.weight_kg == Decimal("65.00")
                assert updated.body_fat_percentage is None

                await body_services.delete_body_measurement(
                    session,
                    measurement_id=measurement.id,
                )
                assert (
                    await body_services.get_body_measurement(
                        session,
                        measurement_id=measurement.id,
                    )
                    is None
                )

    asyncio.run(scenario())


def test_menstrual_flow_cleared_when_period_ends_and_date_filter_applies() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                day = await menstrual_services.create_menstrual_day(
                    session,
                    log_date=date(2026, 8, 19),
                    in_period=True,
                    flow_amount="medium",
                )
                updated = await menstrual_services.update_menstrual_day(
                    session,
                    day_id=day.id,
                    in_period=False,
                )
                assert updated.in_period is False
                assert updated.flow_amount is None

                await menstrual_services.create_menstrual_day(
                    session,
                    log_date=date(2026, 8, 20),
                )
                listed = await menstrual_services.list_menstrual_days(
                    session,
                    dates=(date(2026, 8, 19),),
                )
                assert [item.id for item in listed] == [day.id]
                assert (
                    await menstrual_services.count_menstrual_days(
                        session,
                        dates=(date(2026, 8, 19),),
                    )
                    == 1
                )

    asyncio.run(scenario())


def test_body_and_sleep_lists_filter_by_dates() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                first = await body_services.create_body_measurement(
                    session,
                    payload=body_services.BodyMeasurementCreate(
                        measured_at=_utc(2026, 8, 19, 8),
                        weight=63.5,
                    ),
                )
                await body_services.create_body_measurement(
                    session,
                    payload=body_services.BodyMeasurementCreate(
                        measured_at=_utc(2026, 8, 20, 8),
                        weight=64,
                    ),
                )
                body_listed = await body_services.list_body_measurements(
                    session,
                    dates=(date(2026, 8, 19),),
                )
                assert [item.id for item in body_listed] == [first.id]

                sleep_first = await sleep_services.create_sleep_segment(
                    session,
                    start_at=_utc(2026, 8, 18, 22),
                    end_at=_utc(2026, 8, 19, 6),
                )
                await sleep_services.create_sleep_segment(
                    session,
                    start_at=_utc(2026, 8, 20, 22),
                    end_at=_utc(2026, 8, 21, 6),
                )
                sleep_listed = await sleep_services.list_sleep_segments(
                    session,
                    dates=(date(2026, 8, 18),),
                )
                assert [item.id for item in sleep_listed] == [sleep_first.id]
                summaries = await sleep_services.get_sleep_daily_summaries(
                    session,
                    dates=(date(2026, 8, 20),),
                )
                assert [item.sleep_date for item in summaries] == [date(2026, 8, 20)]

    asyncio.run(scenario())


def test_sleep_segment_attribution_summary_and_update() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as factory:
            async with factory() as session:
                segment = await sleep_services.create_sleep_segment(
                    session,
                    start_at=_utc(2026, 8, 18, 22, 30),
                    end_at=_utc(2026, 8, 19, 6, 30),
                )
                assert segment.sleep_date == date(2026, 8, 18)
                assert segment.duration_minutes == 480

                second = await sleep_services.create_sleep_segment(
                    session,
                    start_at=_utc(2026, 8, 18, 13, 0),
                    end_at=_utc(2026, 8, 18, 14, 0),
                )
                assert second.sleep_date == date(2026, 8, 18)

                with pytest.raises(sleep_services.SleepValidationError):
                    await sleep_services.create_sleep_segment(
                        session,
                        start_at=_utc(2026, 8, 18, 22),
                        end_at=_utc(2026, 8, 18, 21),
                    )

                summaries = await sleep_services.get_sleep_daily_summaries(session)
                assert len(summaries) == 1
                summary = summaries[0]
                assert summary.sleep_date == date(2026, 8, 18)
                assert summary.total_minutes == 540
                assert summary.segment_count == 2

                updated = await sleep_services.update_sleep_segment(
                    session,
                    segment_id=second.id,
                    end_at=_utc(2026, 8, 18, 14, 30),
                )
                assert updated.duration_minutes == 90

                await sleep_services.delete_sleep_segment(session, segment_id=segment.id)
                remaining = await sleep_services.list_sleep_segments(session)
                assert [item.id for item in remaining] == [second.id]

    asyncio.run(scenario())
