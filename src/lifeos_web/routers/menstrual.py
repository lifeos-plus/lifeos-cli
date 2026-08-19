"""Menstrual cycle endpoints for the local Web API."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.datetime_utils import format_utc_iso
from lifeos_cli.db.models.menstrual import MenstrualDay, MenstrualFactor
from lifeos_cli.db.services import menstrual as menstrual_services
from lifeos_cli.db.services.validation_utils import DomainValidationError
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.common import EmptyMeta
from lifeos_web.response_schemas.menstrual import (
    MenstrualDayResponse,
    MenstrualFactorResponse,
)
from lifeos_web.router_utils import page_envelope, soft_delete
from lifeos_web.schemas import (
    ListResponse,
    MenstrualDayCreate,
    MenstrualDayUpdate,
    MenstrualFactorCreate,
)

router = APIRouter(prefix="/menstrual-days", tags=["menstrual-days"])
factor_router = APIRouter(prefix="/menstrual-factors", tags=["menstrual-factors"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _factor_payload(factor: MenstrualFactor) -> dict[str, object]:
    return {"id": str(factor.id), "name": factor.name}


def _day_payload(day: MenstrualDay) -> dict[str, object]:
    return {
        "id": str(day.id),
        "log_date": day.log_date.isoformat(),
        "in_period": day.in_period,
        "flow_amount": day.flow_amount,
        "symptoms": day.symptoms or [],
        "factors": [_factor_payload(factor) for factor in day.factors],
        "mood_changes": day.mood_changes,
        "protection_used": day.protection_used,
        "spotting": day.spotting,
        "notes": day.notes,
        "created_at": format_utc_iso(day.created_at),
        "updated_at": format_utc_iso(day.updated_at),
    }


@router.get(
    "/",
    response_model=ListResponse[MenstrualDayResponse, EmptyMeta],
    response_model_exclude_unset=True,
)
async def list_menstrual_days(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    start_date: date | None = None,
    end_date: date | None = None,
) -> ListResponse:
    """List menstrual day records for the local Web UI."""
    if (start_date is None) != (end_date is None):
        raise HTTPException(
            status_code=400,
            detail="start_date and end_date must be provided together.",
        )
    days = await menstrual_services.list_menstrual_days(
        session,
        start_date=start_date,
        end_date=end_date,
        limit=size,
        offset=(page - 1) * size,
    )
    total = await menstrual_services.count_menstrual_days(
        session,
        start_date=start_date,
        end_date=end_date,
    )
    return page_envelope(
        items=[_day_payload(day) for day in days],
        page=page,
        size=size,
        total=total,
    )


@router.post(
    "/",
    response_model=MenstrualDayResponse,
    response_model_exclude_unset=True,
)
async def create_menstrual_day(
    payload: MenstrualDayCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Create one daily menstrual cycle record."""
    try:
        day = await menstrual_services.create_menstrual_day(
            session,
            log_date=payload.log_date,
            in_period=payload.in_period,
            flow_amount=payload.flow_amount,
            symptoms=payload.symptoms,
            mood_changes=payload.mood_changes,
            protection_used=payload.protection_used,
            spotting=payload.spotting,
            factor_names=payload.factor_names,
            notes=payload.notes,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _day_payload(day)


@router.get(
    "/{day_id}",
    response_model=MenstrualDayResponse,
    response_model_exclude_unset=True,
)
async def get_menstrual_day(day_id: UUID, session: SessionDep) -> dict[str, object]:
    """Return one active menstrual day record."""
    day = await menstrual_services.get_menstrual_day(session, day_id=day_id)
    if day is None:
        raise HTTPException(status_code=404, detail=f"Menstrual day {day_id} was not found")
    return _day_payload(day)


@router.patch(
    "/{day_id}",
    response_model=MenstrualDayResponse,
    response_model_exclude_unset=True,
)
async def update_menstrual_day(
    day_id: UUID,
    payload: MenstrualDayUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update one daily menstrual cycle record."""
    try:
        day = await menstrual_services.update_menstrual_day(
            session,
            day_id=day_id,
            log_date=payload.log_date,
            in_period=payload.in_period,
            flow_amount=payload.flow_amount,
            symptoms=payload.symptoms,
            mood_changes=payload.mood_changes,
            protection_used=payload.protection_used,
            spotting=payload.spotting,
            factor_names=payload.factor_names,
            notes=payload.notes,
            clear_flow=payload.clear_flow,
            clear_symptoms=payload.clear_symptoms,
            clear_notes=payload.clear_notes,
            clear_factors=payload.clear_factors,
        )
    except menstrual_services.MenstrualDayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _day_payload(day)


@router.delete("/{day_id}", status_code=204)
async def delete_menstrual_day(day_id: UUID, session: SessionDep) -> None:
    """Soft-delete one menstrual day record."""
    await soft_delete(menstrual_services.delete_menstrual_day, session=session, day_id=day_id)


@factor_router.get(
    "/",
    response_model=ListResponse[MenstrualFactorResponse, EmptyMeta],
    response_model_exclude_unset=True,
)
async def list_menstrual_factors(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
) -> ListResponse:
    """List custom menstrual factors."""
    factors = await menstrual_services.list_menstrual_factors(
        session,
        limit=size,
        offset=(page - 1) * size,
    )
    total = await menstrual_services.count_menstrual_factors(session)
    return page_envelope(
        items=[_factor_payload(factor) for factor in factors],
        page=page,
        size=size,
        total=total,
    )


@factor_router.post(
    "/",
    response_model=MenstrualFactorResponse,
    response_model_exclude_unset=True,
)
async def create_menstrual_factor(
    payload: MenstrualFactorCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Create one custom menstrual factor."""
    try:
        factor = await menstrual_services.create_menstrual_factor(
            session,
            name=payload.name,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _factor_payload(factor)


@factor_router.delete("/{factor_id}", status_code=204)
async def delete_menstrual_factor(factor_id: UUID, session: SessionDep) -> None:
    """Soft-delete one custom menstrual factor."""
    await soft_delete(
        menstrual_services.delete_menstrual_factor,
        session=session,
        factor_id=factor_id,
    )
