# LifeOS Web UI

This frontend is the first-party human Web UI for LifeOS. It is a Vite/React workspace for browser workflows over the same database configured by the terminal-native `lifeos` CLI. The frontend is not Python package payload; published PyPI installs do not build or bundle this workspace automatically.

The UI currently focuses on dense personal operating-system workflows rather than a marketing shell. It exposes the implemented LifeOS surfaces for planning, execution, reflection, finance, people, and settings.

## Current Scope

Default navigation keeps LifeOS-backed surfaces visible:

- Visions
- Habits
- Planning
- Timelog
- Finance
- Insights / Stats
- Schedule / Calendar
- Notes
- People
- Settings / Config

The Web API backing these surfaces lives in `src/lifeos_web`. New frontend features should land with the corresponding API surface and tests when they need server-backed data.

Unsupported reference-product modules such as food diary, cloud auth, invitations, agent sessions, cardbox, notifications, export APIs, and sage maxims are intentionally absent until LifeOS exposes matching local capabilities.

## Run With Built Assets

From the repository root:

```bash
uv run --extra web --extra postgres lifeos web serve --host 127.0.0.1 --port 8765 --static-dir web/dist
```

Use `--extra postgres` when the configured LifeOS database URL uses `postgresql+psycopg://`. For SQLite-only local setups, `--extra web` is enough.

## Development

Run the API:

```bash
uv run --extra web --extra postgres lifeos web serve --host 127.0.0.1 --port 8765
```

Run the Vite frontend:

```bash
cd web
npm ci
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8765`.

## Build

```bash
cd web
npm ci
npm run build
```

## Generated API Types

The FastAPI OpenAPI document is the source of truth for transport request and response types in
`src/services/api/`. Regenerate the committed schema and TypeScript definitions after changing an
API route, request model, or response model:

```bash
cd web
npm run api:generate
```

Generation imports the local FastAPI app directly. It does not require a running server, a database,
or developer-specific configuration. Commit `src/services/api/generated/schema.ts`; do not edit
`openapi.json` or `schema.ts` manually. `web/openapi.json` is a generated intermediate artifact and
is not tracked in version control — run `npm run api:generate` locally to refresh it for inspection.

`npm run api:check` regenerates the contract and fails if the committed `schema.ts` was stale.
`bash ./scripts/web_validate.sh` runs this drift check before the frontend build, lint, and tests.

Frontend-only query filters, form drafts, cache projections, and aggregate view models may be
derived with `Pick`, `Omit`, intersections, or explicit adapters. Types passed to and returned from
the HTTP boundary must come from the generated OpenAPI contract.
