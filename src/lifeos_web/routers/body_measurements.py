"""Body measurement endpoints for the local Web API."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.datetime_utils import format_utc_iso
from lifeos_cli.application.time_preferences import to_storage_timezone
from lifeos_cli.config import get_preferences_settings
from lifeos_cli.db.models.body_measurement import BodyMeasurement
from lifeos_cli.db.services import body_measurements as body_services
from lifeos_cli.db.services.validation_utils import DomainValidationError
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.body_measurements import BodyMeasurementResponse
from lifeos_web.response_schemas.common import EmptyMeta
from lifeos_web.router_utils import page_envelope, soft_delete
from lifeos_web.schemas import (
    BodyMeasurementCreate,
    BodyMeasurementUpdate,
    ListResponse,
)

router = APIRouter(prefix="/body-measurements", tags=["body-measurements"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _measurement_payload(measurement: BodyMeasurement) -> dict[str, object]:
    height_cm = get_preferences_settings().body_height_cm
    payload: dict[str, object] = {
        "id": str(measurement.id),
        "measured_at": format_utc_iso(measurement.measured_at),
        "weight_kg": float(measurement.weight_kg),
        "display_unit": get_preferences_settings().weight_unit,
        "bmi": (
            float(body_services.compute_bmi(measurement.weight_kg, height_cm))
            if height_cm is not None
            else None
        ),
        "notes": measurement.notes,
        "created_at": format_utc_iso(measurement.created_at),
        "updated_at": format_utc_iso(measurement.updated_at),
    }
    for field in (
        "body_fat_percentage",
        "visceral_fat",
        "fat_mass_kg",
        "muscle_percentage",
        "muscle_mass_kg",
        "body_water_kg",
        "protein_kg",
        "bone_mass_kg",
        "skeletal_muscle_kg",
    ):
        value = getattr(measurement, field)
        payload[field] = float(value) if value is not None else None
    return payload


def _service_update(
    payload: BodyMeasurementUpdate,
) -> body_services.BodyMeasurementUpdate:
    return body_services.BodyMeasurementUpdate(
        measured_at=(to_storage_timezone(payload.measured_at) if payload.measured_at else None),
        weight=payload.weight,
        unit=payload.unit,
        body_fat_percentage=payload.body_fat_percentage,
        visceral_fat=payload.visceral_fat,
        fat_mass_kg=payload.fat_mass_kg,
        muscle_percentage=payload.muscle_percentage,
        muscle_mass_kg=payload.muscle_mass_kg,
        body_water_kg=payload.body_water_kg,
        protein_kg=payload.protein_kg,
        bone_mass_kg=payload.bone_mass_kg,
        skeletal_muscle_kg=payload.skeletal_muscle_kg,
        notes=payload.notes,
        clear_fields=frozenset(payload.clear_fields or ()),
    )


@router.get(
    "/",
    response_model=ListResponse[BodyMeasurementResponse, EmptyMeta],
    response_model_exclude_unset=True,
)
async def list_body_measurements(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    start_date: date | None = None,
    end_date: date | None = None,
) -> ListResponse:
    """List body measurements for the local Web UI."""
    if (start_date is None) != (end_date is None):
        raise HTTPException(
            status_code=400,
            detail="start_date and end_date must be provided together.",
        )
    measurements = await body_services.list_body_measurements(
        session,
        start_date=start_date,
        end_date=end_date,
        limit=size,
        offset=(page - 1) * size,
    )
    total = await body_services.count_body_measurements(
        session,
        start_date=start_date,
        end_date=end_date,
    )
    return page_envelope(
        items=[_measurement_payload(measurement) for measurement in measurements],
        page=page,
        size=size,
        total=total,
    )


@router.post(
    "/",
    response_model=BodyMeasurementResponse,
    response_model_exclude_unset=True,
)
async def create_body_measurement(
    payload: BodyMeasurementCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Create one body measurement record."""
    service_payload = body_services.BodyMeasurementCreate(
        measured_at=to_storage_timezone(payload.measured_at),
        weight=payload.weight,
        unit=payload.unit,
        body_fat_percentage=payload.body_fat_percentage,
        visceral_fat=payload.visceral_fat,
        fat_mass_kg=payload.fat_mass_kg,
        muscle_percentage=payload.muscle_percentage,
        muscle_mass_kg=payload.muscle_mass_kg,
        body_water_kg=payload.body_water_kg,
        protein_kg=payload.protein_kg,
        bone_mass_kg=payload.bone_mass_kg,
        skeletal_muscle_kg=payload.skeletal_muscle_kg,
        notes=payload.notes,
    )
    try:
        measurement = await body_services.create_body_measurement(
            session,
            payload=service_payload,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _measurement_payload(measurement)


@router.get(
    "/{measurement_id}",
    response_model=BodyMeasurementResponse,
    response_model_exclude_unset=True,
)
async def get_body_measurement(
    measurement_id: UUID,
    session: SessionDep,
) -> dict[str, object]:
    """Return one active body measurement."""
    measurement = await body_services.get_body_measurement(
        session,
        measurement_id=measurement_id,
    )
    if measurement is None:
        raise HTTPException(
            status_code=404,
            detail=f"Body measurement {measurement_id} was not found",
        )
    return _measurement_payload(measurement)


@router.patch(
    "/{measurement_id}",
    response_model=BodyMeasurementResponse,
    response_model_exclude_unset=True,
)
async def update_body_measurement(
    measurement_id: UUID,
    payload: BodyMeasurementUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update one body measurement record."""
    try:
        measurement = await body_services.update_body_measurement(
            session,
            measurement_id=measurement_id,
            payload=_service_update(payload),
        )
    except body_services.BodyMeasurementNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _measurement_payload(measurement)


@router.delete("/{measurement_id}", status_code=204)
async def delete_body_measurement(measurement_id: UUID, session: SessionDep) -> None:
    """Soft-delete one body measurement."""
    await soft_delete(
        body_services.delete_body_measurement,
        session=session,
        measurement_id=measurement_id,
    )
