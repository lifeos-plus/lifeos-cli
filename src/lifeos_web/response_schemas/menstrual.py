"""Menstrual cycle response contracts."""

from __future__ import annotations

from lifeos_web.response_schemas.common import ResponseModel


class MenstrualFactorResponse(ResponseModel):
    """One custom menstrual factor."""

    id: str
    name: str


class MenstrualDayResponse(ResponseModel):
    """One daily menstrual cycle record."""

    id: str
    log_date: str
    in_period: bool
    flow_amount: str | None
    symptoms: list[str]
    factors: list[MenstrualFactorResponse]
    personality_behavior: bool | None
    protection_used: bool | None
    spotting: bool | None
    notes: str | None
    created_at: str
    updated_at: str
