# LifeOS CLI Architecture

This document describes how the `lifeos-cli` repository is organized and why. It is written for maintainers and contributors; command-level facts belong in CLI help (`lifeos <resource> <action> --help`) and in [`docs/cli.md`](cli.md), not in this file.

## 1. Repository Layout

- `src/lifeos_cli` — the Python package: CLI parsing and handlers, database services, ORM models, configuration, Alembic migrations, and locale catalogs.
- `src/lifeos_web` — the local FastAPI Web API that shares the same database services as the CLI.
- `scripts` — validation and maintenance entrypoints (`doctor.sh`, `export_web_openapi.py`, `check_locale_catalog.py`, and others).
- `tests` — pytest suite. Integration-marked tests run against a configured PostgreSQL database; everything else runs against SQLite by default.
- `docs` — repository-level documentation. `cli.md` is the CLI command reference; this file is the architecture reference.

The first-party React frontend lives in the separate [`lifeos-plus/lifeos-web`](https://github.com/lifeos-plus/lifeos-web) repository and is not part of this repository.

## 2. Layering and Call Direction

Both the CLI and the Web API are thin transport layers over shared domain services:

```text
CLI:   cli_support/resources/<resource>/parser_*.py
         -> async handler (make_sync_handler)
         -> db/services/<domain>_*.py
         -> ORM models (db/models)
         -> SQLite / PostgreSQL

Web:   uvicorn (lifeos web serve)
         -> lifeos_web.app.create_app()
         -> lifeos_web/routers/<domain>.py
         -> lifeos_web.deps.get_db_session (session_scope)
         -> db/services/<domain>_*.py
         -> ORM models (db/models)
         -> SQLite / PostgreSQL
```

Rules that keep this architecture stable:

- `db/services` is the only place that owns domain logic and ORM access. Routers and CLI handlers orchestrate services and format results; they do not build their own business layer.
- The Web API keeps an explicit response boundary: routers return serialized payloads declared by `lifeos_web/response_schemas`, and the OpenAPI contract is the transport contract consumed by `lifeos-web`.
- The CLI renders text from the same domain read models; command-specific output facts are documented in CLI help, not duplicated in repository docs.

## 3. Domain Model Overview

Core entities (see `src/lifeos_cli/db/models`):

- `vision`, `task`, `event` (+ `event_occurrence_exception`), `habit`, `habit_action`, `timelog`, `timelog_template`, `note`, `person`, `tag`, `area`, and `finance` models (assets, trees, snapshots, rate snapshots).
- Aggregated statistics models for timelog insights.

Generic weak associations connect entities across domain boundaries:

- `Association` — polymorphic `source_model/source_id -> target_model/target_id`;
  entity-to-person links use `target_model='person'`; writes canonicalize to
  `link_type='is_about'`, while reads treat every person-targeted association
  as a person link.
- `TagAssociation` — `entity_type/entity_id -> tag_id`.

These associations cannot use ordinary foreign keys for the polymorphic side; referential-integrity guarantees are enforced by services and integrity audit tools rather than the database alone.

`db/services/integrity_audit.py` provides a read-only audit across both
association tables and an explicit repair mode that only removes hard-dangling
rows. Entity type allowlists for `associations` are defined once in
`db/models/association.py` and drive the ORM check constraints, service
validators, and data import/export adapters.

The migration that unified person links renames the legacy
`person_associations` table to `person_associations_legacy_20260812` instead of
dropping it, so no existing row is lost during an upgrade; operators can drop
the archive after verifying the new layout.

## 4. Configuration, Transactions, and Soft Deletes

### Configuration

`lifeos_cli.config` loads `~/.lifeos/config.toml` (or `LIFEOS_CONFIG_FILE`), with environment variables overriding file values at runtime. `clear_config_cache` resets cached settings when the configuration changes in-process.

### Transactions

`db/session.session_scope()` is the single transaction boundary used by both the CLI and Web routers. It opens one async session, commits on success, and rolls back on failure. The async engine and session factory are cached at the process level (`get_async_engine`, `get_async_session_factory`); use `clear_session_cache()` to dispose the engine after configuration changes.

### Soft Deletes

Models opt into `SoftDeleteMixin`, which adds `deleted_at`. A global ORM listener excludes soft-deleted rows from every default SELECT; code that needs the deleted rows explicitly passes the `INCLUDE_SOFT_DELETED_EXECUTION_OPTION` execution option. Soft-deleted records are kept so restores can recover the original relationships.

## 5. Database Backends and Migrations

### Supported backends

- SQLite (`sqlite+aiosqlite`) — local file storage, no schema concept; foreign keys are enabled per connection (`PRAGMA foreign_keys=ON`).
- PostgreSQL (`postgresql+psycopg`) — schema-capable; configured schema names are applied through SQLAlchemy `schema_translate_map`.

`db/backend_policy.py` centralizes backend capabilities (schema support, local file storage, foreign-key enforcement, replace-existing strategy) so services do not branch on driver strings.

### Alembic strategy

- Migrations live in `src/lifeos_cli/alembic` and use an async environment (`env.py`) that resolves the database URL from configuration.
- When a schema is configured (PostgreSQL), the migration context applies `schema_translate_map` and sets `version_table_schema` so the Alembic version table follows the data schema.
- `Base.metadata` uses an explicit naming convention so generated constraint names are stable and safe for PostgreSQL's 63-byte identifier limit.
- Always audit and migrate existing data before adding constraints; do not assume a production database is clean.

## 6. Web API Surface

- `lifeos web serve` starts uvicorn against `create_app()`. The API binds `127.0.0.1` by default and warns on stderr when bound beyond loopback, because the Web API has no authentication.
- Routers are grouped by domain under `lifeos_web/routers` and mounted under `/api/v1`. Every router depends on `get_db_session`, which yields one `session_scope()` transaction per request.
- `lifeos_web/serialization` converts ORM read models to JSON-safe payloads; `lifeos_web/response_schemas` declares the explicit success contracts.
- The OpenAPI document is served at `/api/v1/openapi.json` and exported by `scripts/export_web_openapi.py`; release workflows upload it as an asset so `lifeos-web` can pin a schema version (`npm run api:check` prevents drift).

## 7. Frontend Architecture Summary

The React UI is maintained in `lifeos-plus/lifeos-web`; this repository only keeps the Web API. The frontend follows a routes/pages/features/hooks/contexts layering, uses generated TypeScript types from the pinned `openapi.json`, and keeps its English/Chinese locale catalogs in sync with `npm run i18n:check`. See the `lifeos-web` README for the detailed frontend architecture.

## 8. Runtime and Process Model

### Current model (short-lived CLI processes)

Every CLI command runs its own event loop: `make_sync_handler` adapts each async handler with `asyncio.run`, and the process-level `AsyncEngine` cache is shared across commands within one process. For a short-lived CLI process this is correct and cheap: one command, one event loop, one engine, then exit.

### Long-running scenarios (design direction)

If a long-running process shape appears (interactive REPL, watch/daemon mode, or an event-driven agent service), the per-command `asyncio.run` model cannot reuse connections or event loops. The planned reusable runtime is:

- one shared event loop and engine/session-factory lifecycle owned by the long-running runtime, not per command;
- configuration changes dispose the engine through the existing `clear_session_cache()` path before reconnecting;
- individual commands keep their current sync/async handler contracts and borrow the shared session factory instead of creating a new event loop.

The first real long-running use case should implement this runtime and cover it with tests; until then, the short-lived model is the supported behavior.

## 9. Maintenance Conventions

- **Help-first documentation**: CLI help is the primary command reference. Update `lifeos <resource> --help` and its locale keys whenever command behavior changes; repository-level docs summarize, they do not duplicate.
- **i18n dual-track**: CLI user-facing text comes from `src/lifeos_cli/locales/{en,zh_Hans}` JSON catalogs. `scripts/check_locale_catalog.py` (hooked as `locale-catalog-sync`) enforces identical key sets across locales and verifies that every referenced key exists, scanning both `cli_support` and `lifeos_web`. Web UI copy is managed in `lifeos-web`.
- **New resource checklist**: ORM model -> Alembic revision -> domain service -> CLI parser with help and locale keys -> Web router with response schema -> OpenAPI export verification -> tests covering CLI shape, Web payloads, and HTTP round-trips -> `bash ./scripts/doctor.sh`.
- **Validation**: `bash ./scripts/doctor.sh` is the primary gate: dependency sync, lint, dead-code, mypy, locale sync, the full non-integration test suite, dependency audit, and package build. PostgreSQL CLI integration tests run when `LIFEOS_TEST_DATABASE_URL` is configured.
