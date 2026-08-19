"""Async CRUD helpers for body weight and composition measurements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.time_preferences import (
    get_utc_half_open_window_for_local_date_range,
)
from lifeos_cli.config import get_preferences_settings
from lifeos_cli.db.models.body_measurement import BodyMeasurement
from lifeos_cli.db.services.validation_utils import DomainValidationError, validate_choice

WEIGHT_UNIT_FACTORS: dict[str, Decimal] = {
    "kg": Decimal("1"),
    "jin": Decimal("0.5"),
    "lb": Decimal("0.45359237"),
}
MAX_WEIGHT_KG = Decimal("1000")
PERCENTAGE_FIELDS = frozenset({"body_fat_percentage", "muscle_percentage"})
MASS_FIELDS = frozenset(
    {
        "fat_mass_kg",
        "muscle_mass_kg",
        "body_water_kg",
        "protein_kg",
        "bone_mass_kg",
        "skeletal_muscle_kg",
    }
)


class BodyMeasurementNotFoundError(LookupError):
    """Raised when a body measurement cannot be found."""


class BodyMeasurementValidationError(DomainValidationError):
    """Raised when body measurement input cannot be applied."""


def validate_unit(unit: str) -> str:
    """Validate and normalize a weight input unit."""
    return validate_choice(
        unit,
        WEIGHT_UNIT_FACTORS,
        error_cls=BodyMeasurementValidationError,
        label="weight unit",
        display_order=("kg", "jin", "lb"),
    )


def to_kg(value: Decimal | float | int, unit: str) -> Decimal:
    """Convert one weight value in the given unit to canonical kilograms."""
    normalized_unit = validate_unit(unit)
    try:
        decimal_value = Decimal(str(value))
    except (TypeError, ValueError) as exc:
        raise BodyMeasurementValidationError("Weight must be a number.") from exc
    if decimal_value <= 0 or decimal_value > MAX_WEIGHT_KG * 4:
        raise BodyMeasurementValidationError(
            "Weight must be positive and within a plausible range."
        )
    return (decimal_value * WEIGHT_UNIT_FACTORS[normalized_unit]).quantize(Decimal("0.01"))


def from_kg(weight_kg: Decimal | float | int, unit: str) -> Decimal:
    """Convert canonical kilograms to the requested display unit."""
    normalized_unit = validate_unit(unit)
    return (Decimal(str(weight_kg)) / WEIGHT_UNIT_FACTORS[normalized_unit]).quantize(
        Decimal("0.01")
    )


def compute_bmi(weight_kg: Decimal | float | int, height_cm: float | None) -> Decimal | None:
    """Compute BMI from canonical weight and optional height."""
    if height_cm is None or height_cm <= 0:
        return None
    height_m = Decimal(str(height_cm)) / Decimal("100")
    bmi = Decimal(str(weight_kg)) / (height_m * height_m)
    return bmi.quantize(Decimal("0.1"))


def _validate_percentage(value: Decimal | float | int, *, field: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (TypeError, ValueError) as exc:
        raise BodyMeasurementValidationError(f"{field} must be a number.") from exc
    if decimal_value < 0 or decimal_value > 100:
        raise BodyMeasurementValidationError(f"{field} must be between 0 and 100.")
    return decimal_value.quantize(Decimal("0.01"))


def _validate_visceral_fat(value: Decimal | float | int) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (TypeError, ValueError) as exc:
        raise BodyMeasurementValidationError("visceral_fat must be a number.") from exc
    if decimal_value < 0 or decimal_value > 100:
        raise BodyMeasurementValidationError("visceral_fat must be between 0 and 100.")
    return decimal_value.quantize(Decimal("0.01"))


def _validate_mass(value: Decimal | float | int, *, field: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (TypeError, ValueError) as exc:
        raise BodyMeasurementValidationError(f"{field} must be a number.") from exc
    if decimal_value < 0 or decimal_value > MAX_WEIGHT_KG:
        raise BodyMeasurementValidationError(f"{field} must be between 0 and {MAX_WEIGHT_KG}.")
    return decimal_value.quantize(Decimal("0.01"))


def validate_notes(notes: str | None) -> str | None:
    """Normalize optional measurement notes."""
    if notes is None:
        return None
    normalized = notes.strip()
    return normalized or None


@dataclass(frozen=True)
class BodyMeasurementCreate:
    """Validated body measurement creation payload."""

    measured_at: datetime
    weight: Decimal | float | int
    unit: str = "kg"
    body_fat_percentage: Decimal | float | None = None
    visceral_fat: Decimal | float | None = None
    fat_mass_kg: Decimal | float | None = None
    muscle_percentage: Decimal | float | None = None
    muscle_mass_kg: Decimal | float | None = None
    body_water_kg: Decimal | float | None = None
    protein_kg: Decimal | float | None = None
    bone_mass_kg: Decimal | float | None = None
    skeletal_muscle_kg: Decimal | float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class BodyMeasurementUpdate:
    """Validated body measurement update payload; None values stay unchanged."""

    measured_at: datetime | None = None
    weight: Decimal | float | int | None = None
    unit: str = "kg"
    body_fat_percentage: Decimal | float | None = None
    visceral_fat: Decimal | float | None = None
    fat_mass_kg: Decimal | float | None = None
    muscle_percentage: Decimal | float | None = None
    muscle_mass_kg: Decimal | float | None = None
    body_water_kg: Decimal | float | None = None
    protein_kg: Decimal | float | None = None
    bone_mass_kg: Decimal | float | None = None
    skeletal_muscle_kg: Decimal | float | None = None
    notes: str | None = None
    clear_fields: frozenset[str] = frozenset()


def _normalize_create(payload: BodyMeasurementCreate) -> dict[str, object]:
    normalized: dict[str, object] = {
        "measured_at": payload.measured_at,
        "weight_kg": to_kg(payload.weight, payload.unit),
    }
    if payload.body_fat_percentage is not None:
        normalized["body_fat_percentage"] = _validate_percentage(
            payload.body_fat_percentage,
            field="body_fat_percentage",
        )
    if payload.visceral_fat is not None:
        normalized["visceral_fat"] = _validate_visceral_fat(payload.visceral_fat)
    for field in MASS_FIELDS:
        value = getattr(payload, field)
        if value is not None:
            normalized[field] = _validate_mass(value, field=field)
    if payload.muscle_percentage is not None:
        normalized["muscle_percentage"] = _validate_percentage(
            payload.muscle_percentage,
            field="muscle_percentage",
        )
    normalized["notes"] = validate_notes(payload.notes)
    return normalized


async def _get_measurement_model(
    session: AsyncSession,
    measurement_id: UUID,
) -> BodyMeasurement | None:
    stmt = (
        select(BodyMeasurement)
        .where(
            BodyMeasurement.id == measurement_id,
            BodyMeasurement.deleted_at.is_(None),
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_body_measurement(
    session: AsyncSession,
    *,
    payload: BodyMeasurementCreate,
) -> BodyMeasurement:
    """Create one body measurement record."""
    values = _normalize_create(payload)
    measurement = BodyMeasurement(**values)
    session.add(measurement)
    await session.flush()
    return measurement


async def get_body_measurement(
    session: AsyncSession,
    *,
    measurement_id: UUID,
) -> BodyMeasurement | None:
    """Return one active body measurement."""
    return await _get_measurement_model(session, measurement_id)


async def list_body_measurements(
    session: AsyncSession,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[BodyMeasurement]:
    """List active body measurements with optional local-date range filtering."""
    stmt = (
        select(BodyMeasurement)
        .where(BodyMeasurement.deleted_at.is_(None))
        .order_by(BodyMeasurement.measured_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if start_date is not None and end_date is not None:
        window_start, window_end = get_utc_half_open_window_for_local_date_range(
            start_date=start_date,
            end_date=end_date,
        )
        stmt = stmt.where(
            BodyMeasurement.measured_at >= window_start,
            BodyMeasurement.measured_at < window_end,
        )
    return list((await session.execute(stmt)).scalars().all())


async def count_body_measurements(
    session: AsyncSession,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """Count active body measurements for pagination metadata."""
    stmt = select(func.count(BodyMeasurement.id)).where(BodyMeasurement.deleted_at.is_(None))
    if start_date is not None and end_date is not None:
        window_start, window_end = get_utc_half_open_window_for_local_date_range(
            start_date=start_date,
            end_date=end_date,
        )
        stmt = stmt.where(
            BodyMeasurement.measured_at >= window_start,
            BodyMeasurement.measured_at < window_end,
        )
    return int((await session.execute(stmt)).scalar_one())


async def update_body_measurement(
    session: AsyncSession,
    *,
    measurement_id: UUID,
    payload: BodyMeasurementUpdate,
) -> BodyMeasurement:
    """Update mutable body measurement fields; omitted values stay unchanged."""
    measurement = await _get_measurement_model(session, measurement_id)
    if measurement is None:
        raise BodyMeasurementNotFoundError(f"Body measurement {measurement_id} was not found")
    if payload.measured_at is not None:
        measurement.measured_at = payload.measured_at
    if payload.weight is not None:
        measurement.weight_kg = to_kg(payload.weight, payload.unit)
    for field in PERCENTAGE_FIELDS | MASS_FIELDS | {"visceral_fat"}:
        if field in payload.clear_fields:
            setattr(measurement, field, None)
            continue
        value = getattr(payload, field)
        if value is None:
            continue
        if field in PERCENTAGE_FIELDS:
            setattr(measurement, field, _validate_percentage(value, field=field))
        elif field == "visceral_fat":
            setattr(measurement, field, _validate_visceral_fat(value))
        else:
            setattr(measurement, field, _validate_mass(value, field=field))
    if "notes" in payload.clear_fields:
        measurement.notes = None
    elif payload.notes is not None:
        measurement.notes = validate_notes(payload.notes)
    await session.flush()
    return measurement


async def delete_body_measurement(
    session: AsyncSession,
    *,
    measurement_id: UUID,
) -> None:
    """Soft-delete one body measurement."""
    measurement = await _get_measurement_model(session, measurement_id)
    if measurement is None:
        raise BodyMeasurementNotFoundError(f"Body measurement {measurement_id} was not found")
    measurement.soft_delete()
    await session.flush()


def preferred_weight_unit() -> str:
    """Return the configured display unit for body weight."""
    return get_preferences_settings().weight_unit
