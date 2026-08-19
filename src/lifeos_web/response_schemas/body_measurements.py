"""Body measurement response contracts."""

from __future__ import annotations

from lifeos_web.response_schemas.common import ResponseModel


class BodyMeasurementResponse(ResponseModel):
    """One body weight/composition measurement."""

    id: str
    measured_at: str
    weight_kg: float
    display_unit: str
    bmi: float | None
    body_fat_percentage: float | None
    visceral_fat: float | None
    fat_mass_kg: float | None
    muscle_percentage: float | None
    muscle_mass_kg: float | None
    body_water_kg: float | None
    protein_kg: float | None
    bone_mass_kg: float | None
    skeletal_muscle_kg: float | None
    notes: str | None
    created_at: str
    updated_at: str
