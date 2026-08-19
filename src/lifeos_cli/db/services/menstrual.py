"""Async CRUD helpers for menstrual cycle records and custom factors."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lifeos_cli.db.models.menstrual import MenstrualDay, MenstrualFactor
from lifeos_cli.db.services.validation_utils import DomainValidationError, validate_choice

MENSTRUAL_FLOW_AMOUNTS = ("low", "medium", "high")
MAX_SYMPTOMS_PER_DAY = 20
MAX_SYMPTOM_LENGTH = 50
MAX_FACTOR_NAME_LENGTH = 100


class MenstrualDayNotFoundError(LookupError):
    """Raised when a menstrual day record cannot be found."""


class MenstrualFactorNotFoundError(LookupError):
    """Raised when a menstrual factor cannot be found."""


class MenstrualValidationError(DomainValidationError):
    """Raised when menstrual cycle input cannot be applied."""


def validate_factor_name(name: str) -> str:
    """Validate and normalize a custom menstrual factor name."""
    normalized = name.strip()
    if not normalized:
        raise MenstrualValidationError("Menstrual factor name must not be empty.")
    if len(normalized) > MAX_FACTOR_NAME_LENGTH:
        raise MenstrualValidationError(
            f"Menstrual factor name must be at most {MAX_FACTOR_NAME_LENGTH} characters."
        )
    return normalized


def validate_flow_amount(value: str | None, *, in_period: bool) -> str | None:
    """Validate flow amount, which is only meaningful for in-period days."""
    if value is None:
        return None
    normalized = validate_choice(
        value,
        MENSTRUAL_FLOW_AMOUNTS,
        error_cls=MenstrualValidationError,
        label="flow amount",
        display_order=("low", "medium", "high"),
    )
    if not in_period:
        raise MenstrualValidationError(
            "Flow amount is only allowed when the day is marked as in-period."
        )
    return normalized


def validate_symptoms(symptoms: list[str] | None) -> list[str] | None:
    """Validate and deduplicate daily symptom values."""
    if not symptoms:
        return None
    deduplicated = list(dict.fromkeys(symptom.strip() for symptom in symptoms if symptom.strip()))
    if len(deduplicated) > MAX_SYMPTOMS_PER_DAY:
        raise MenstrualValidationError(
            f"A menstrual day can record at most {MAX_SYMPTOMS_PER_DAY} symptoms."
        )
    for symptom in deduplicated:
        if len(symptom) > MAX_SYMPTOM_LENGTH:
            raise MenstrualValidationError(
                f"Symptom {symptom!r} must be at most {MAX_SYMPTOM_LENGTH} characters."
            )
    return deduplicated


def validate_notes(notes: str | None) -> str | None:
    """Normalize optional menstrual day notes."""
    if notes is None:
        return None
    normalized = notes.strip()
    return normalized or None


async def _get_active_factor_by_name(
    session: AsyncSession,
    name: str,
) -> MenstrualFactor | None:
    stmt = (
        select(MenstrualFactor)
        .where(
            MenstrualFactor.name == name,
            MenstrualFactor.deleted_at.is_(None),
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _resolve_factors_by_name(
    session: AsyncSession,
    names: list[str] | None,
) -> list[MenstrualFactor]:
    if not names:
        return []
    resolved: list[MenstrualFactor] = []
    seen: set[UUID] = set()
    for raw_name in names:
        name = validate_factor_name(raw_name)
        factor = await _get_active_factor_by_name(session, name)
        if factor is None:
            factor = MenstrualFactor(name=name)
            session.add(factor)
            await session.flush()
        if factor.id not in seen:
            resolved.append(factor)
            seen.add(factor.id)
    return resolved


async def _get_day_model(session: AsyncSession, day_id: UUID) -> MenstrualDay | None:
    stmt = (
        select(MenstrualDay)
        .options(selectinload(MenstrualDay.factors))
        .where(MenstrualDay.id == day_id, MenstrualDay.deleted_at.is_(None))
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _ensure_log_date_available(
    session: AsyncSession,
    log_date: date,
    *,
    exclude_day_id: UUID | None = None,
) -> None:
    stmt = (
        select(MenstrualDay.id)
        .where(MenstrualDay.log_date == log_date, MenstrualDay.deleted_at.is_(None))
        .limit(1)
    )
    existing_id = (await session.execute(stmt)).scalar_one_or_none()
    if existing_id is not None and existing_id != exclude_day_id:
        raise MenstrualValidationError(
            f"A menstrual day record already exists for {log_date.isoformat()}."
        )


async def create_menstrual_factor(
    session: AsyncSession,
    *,
    name: str,
) -> MenstrualFactor:
    """Create one custom menstrual factor."""
    normalized = validate_factor_name(name)
    existing = await _get_active_factor_by_name(session, normalized)
    if existing is not None:
        raise MenstrualValidationError(f"Menstrual factor {normalized!r} already exists.")
    factor = MenstrualFactor(name=normalized)
    session.add(factor)
    await session.flush()
    return factor


async def list_menstrual_factors(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[MenstrualFactor]:
    """List active custom menstrual factors ordered by name."""
    stmt = (
        select(MenstrualFactor)
        .where(MenstrualFactor.deleted_at.is_(None))
        .order_by(MenstrualFactor.name)
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


async def count_menstrual_factors(session: AsyncSession) -> int:
    """Count active custom menstrual factors for pagination metadata."""
    stmt = select(func.count(MenstrualFactor.id)).where(MenstrualFactor.deleted_at.is_(None))
    return int((await session.execute(stmt)).scalar_one())


async def delete_menstrual_factor(
    session: AsyncSession,
    *,
    factor_id: UUID,
) -> None:
    """Soft-delete one custom menstrual factor."""
    stmt = (
        select(MenstrualFactor)
        .where(MenstrualFactor.id == factor_id, MenstrualFactor.deleted_at.is_(None))
        .limit(1)
    )
    factor = (await session.execute(stmt)).scalar_one_or_none()
    if factor is None:
        raise MenstrualFactorNotFoundError(f"Menstrual factor {factor_id} was not found")
    factor.soft_delete()
    await session.flush()


async def get_menstrual_day(
    session: AsyncSession,
    *,
    day_id: UUID,
) -> MenstrualDay | None:
    """Return one active menstrual day record with its factors."""
    return await _get_day_model(session, day_id)


async def list_menstrual_days(
    session: AsyncSession,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[MenstrualDay]:
    """List active menstrual day records with optional local-date range filtering."""
    stmt = (
        select(MenstrualDay)
        .options(selectinload(MenstrualDay.factors))
        .where(MenstrualDay.deleted_at.is_(None))
        .order_by(MenstrualDay.log_date.desc())
        .limit(limit)
        .offset(offset)
    )
    if start_date is not None:
        stmt = stmt.where(MenstrualDay.log_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(MenstrualDay.log_date <= end_date)
    return list((await session.execute(stmt)).scalars().all())


async def count_menstrual_days(
    session: AsyncSession,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """Count active menstrual day records for pagination metadata."""
    stmt = select(func.count(MenstrualDay.id)).where(MenstrualDay.deleted_at.is_(None))
    if start_date is not None:
        stmt = stmt.where(MenstrualDay.log_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(MenstrualDay.log_date <= end_date)
    return int((await session.execute(stmt)).scalar_one())


async def create_menstrual_day(
    session: AsyncSession,
    *,
    log_date: date,
    in_period: bool = False,
    flow_amount: str | None = None,
    symptoms: list[str] | None = None,
    personality_behavior: bool | None = None,
    protection_used: bool | None = None,
    spotting: bool | None = None,
    factor_names: list[str] | None = None,
    notes: str | None = None,
) -> MenstrualDay:
    """Create one daily menstrual cycle record."""
    await _ensure_log_date_available(session, log_date)
    normalized_flow = validate_flow_amount(flow_amount, in_period=in_period)
    normalized_symptoms = validate_symptoms(symptoms)
    normalized_notes = validate_notes(notes)
    factors = await _resolve_factors_by_name(session, factor_names)
    day = MenstrualDay(
        log_date=log_date,
        in_period=in_period,
        flow_amount=normalized_flow,
        symptoms=normalized_symptoms,
        personality_behavior=personality_behavior,
        protection_used=protection_used,
        spotting=spotting,
        notes=normalized_notes,
        factors=factors,
    )
    session.add(day)
    await session.flush()
    return day


async def update_menstrual_day(
    session: AsyncSession,
    *,
    day_id: UUID,
    log_date: date | None = None,
    in_period: bool | None = None,
    flow_amount: str | None = None,
    symptoms: list[str] | None = None,
    personality_behavior: bool | None = None,
    protection_used: bool | None = None,
    spotting: bool | None = None,
    factor_names: list[str] | None = None,
    notes: str | None = None,
    clear_flow: bool = False,
    clear_symptoms: bool = False,
    clear_notes: bool = False,
    clear_factors: bool = False,
) -> MenstrualDay:
    """Update mutable menstrual day fields; omitted values stay unchanged."""
    day = await _get_day_model(session, day_id)
    if day is None:
        raise MenstrualDayNotFoundError(f"Menstrual day {day_id} was not found")

    if log_date is not None and log_date != day.log_date:
        await _ensure_log_date_available(session, log_date, exclude_day_id=day.id)
        day.log_date = log_date
    if in_period is not None and in_period != day.in_period:
        day.in_period = in_period

    if clear_flow:
        day.flow_amount = None
    elif flow_amount is not None:
        day.flow_amount = validate_flow_amount(flow_amount, in_period=day.in_period)

    if clear_symptoms:
        day.symptoms = None
    elif symptoms is not None:
        day.symptoms = validate_symptoms(symptoms)

    if personality_behavior is not None:
        day.personality_behavior = personality_behavior
    if protection_used is not None:
        day.protection_used = protection_used
    if spotting is not None:
        day.spotting = spotting

    if clear_notes:
        day.notes = None
    elif notes is not None:
        day.notes = validate_notes(notes)

    if clear_factors:
        day.factors = []
    elif factor_names is not None:
        day.factors = await _resolve_factors_by_name(session, factor_names)

    await session.flush()
    return day


async def delete_menstrual_day(
    session: AsyncSession,
    *,
    day_id: UUID,
) -> None:
    """Soft-delete one menstrual day record."""
    day = await _get_day_model(session, day_id)
    if day is None:
        raise MenstrualDayNotFoundError(f"Menstrual day {day_id} was not found")
    day.soft_delete()
    await session.flush()
