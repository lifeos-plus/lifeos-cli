from __future__ import annotations

from tests.cli_integration_support import (
    INTEGRATION_PYTESTMARK,
    IntegrationContext,
    assert_ok,
    init_context,
    run_alembic,
    run_lifeos,
)

pytestmark = INTEGRATION_PYTESTMARK


def test_real_cli_init_and_db_commands(integration_context: IntegrationContext) -> None:
    init_context(integration_context)

    assert integration_context.config_path.exists()
    assert integration_context.schema in integration_context.config_path.read_text(encoding="utf-8")

    ping_result = run_lifeos(integration_context, "db", "ping")
    assert_ok(ping_result)
    assert "Database connection succeeded." in ping_result.stdout

    upgrade_result = run_lifeos(integration_context, "db", "upgrade")
    assert_ok(upgrade_result)
    assert "Database migrations are up to date." in upgrade_result.stdout

    schema_check_result = run_alembic(integration_context, "check")
    assert_ok(schema_check_result)
    assert "No new upgrade operations detected." in schema_check_result.stdout

    check_result = run_lifeos(integration_context, "db", "check")
    assert_ok(check_result)
    assert "Database checks passed." in check_result.stdout

    config_result = run_lifeos(integration_context, "config", "show")
    assert_ok(config_result)
    assert integration_context.schema in config_result.stdout
