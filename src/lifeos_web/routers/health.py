"""Health endpoints for the local Web API."""

from __future__ import annotations

from fastapi import APIRouter

from lifeos_cli.db.base import utc_now
from lifeos_web.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/healthy", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return a lightweight service health response."""
    return HealthResponse(status="ok", timestamp=utc_now())
