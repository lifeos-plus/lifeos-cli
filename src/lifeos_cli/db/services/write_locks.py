"""Transaction-scoped coordination for persisted planning aggregates."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lock_planning_writes(session: AsyncSession) -> None:
    """Serialize planning writes within a PostgreSQL application schema.

    Task trees, vision experience, and daily/monthly/yearly timelog aggregates
    overlap, so they share one transaction lock. Other resource families and
    readers remain independent. SQLite already serializes writers; conflicting
    read-to-write upgrades fail and must roll back instead of overwriting data.
    """
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    schema = (bind.get_execution_options().get("schema_translate_map") or {}).get(None)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": f"lifeos:{schema or 'public'}:planning-writes"},
    )
