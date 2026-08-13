"""PostgreSQL integration coverage for the integrity audit."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import insert

from lifeos_cli.config import clear_config_cache
from lifeos_cli.db.models.association import Association
from lifeos_cli.db.services.integrity_audit import audit_referential_integrity
from lifeos_cli.db.session import clear_session_cache, get_async_session_factory
from tests.cli_integration_support import (
    INTEGRATION_PYTESTMARK,
    IntegrationContext,
    init_context,
)

pytestmark = INTEGRATION_PYTESTMARK


def test_postgres_audit_detects_and_repairs_dangling_links(
    integration_context: IntegrationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_context(integration_context)
    monkeypatch.setenv("LIFEOS_DATABASE_URL", integration_context.database_url)
    monkeypatch.setenv("LIFEOS_DATABASE_SCHEMA", integration_context.schema)
    clear_config_cache()
    clear_session_cache()

    async def scenario() -> None:
        factory = get_async_session_factory()
        async with factory() as session:
            now = datetime.now(UTC)
            await session.execute(
                insert(Association),
                [
                    {
                        "id": uuid4(),
                        "source_model": "note",
                        "source_id": uuid4(),
                        "target_model": "person",
                        "target_id": uuid4(),
                        "link_type": "is_about",
                        "created_at": now,
                        "updated_at": now,
                    }
                ],
            )
            await session.commit()

            report = await audit_referential_integrity(session)
            assert {"missing_source", "missing_target"} <= {issue.kind for issue in report.issues}

            repaired = await audit_referential_integrity(session, repair=True)
            assert repaired.repaired_count == 1
            assert (await audit_referential_integrity(session)).ok

    try:
        asyncio.run(scenario())
    finally:
        clear_session_cache()
        clear_config_cache()
