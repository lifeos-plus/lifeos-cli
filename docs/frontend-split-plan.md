# Frontend Split Plan

This document defines how `lifeos-cli` splits its first-party React Web UI
into a separate repository while keeping the Web API, CLI, and release
workflows stable. It implements the planning deliverables tracked by
[issue 251](https://github.com/lifeos-plus/lifeos-cli/issues/251).

## Repository Boundary

- The LifeOS Web API (`src/lifeos_web`, FastAPI routers, response schemas,
  `scripts/export_web_openapi.py`) stays in `lifeos-cli`.
- The React/Vite frontend moves to `lifeos-plus/lifeos-web`. The former
  `web/` subtree becomes the repository root so it is a standard npm
  workspace, and its git history is preserved through a `git subtree split`.
- The `lifeos-cli[web]` optional extra remains the Web API runtime extra
  (FastAPI, uvicorn). Removing the frontend workspace does not change the
  API server behavior.

## Cross-Repo Schema Publish and Pin

The FastAPI OpenAPI document is the single transport contract.

### Publishing (lifeos-cli)

- `scripts/export_web_openapi.py` is the only export path and does not require
  a running server or database.
- `.github/workflows/publish.yml` exports `openapi.json` and uploads it as a
  release asset for every `v*` tag and for repair dispatches.

### Pinning (lifeos-web)

- `openapi.json` is committed as the pinned contract baseline.
- `scripts/fetch-schema.mjs` downloads the pinned release asset from
  `lifeos-plus/lifeos-cli` (`LIFEOS_CLI_SCHEMA_VERSION`, default `latest`).
- `npm run api:refresh` fetches and regenerates
  `src/services/api/generated/schema.ts`; `npm run api:check` fails on drift
  and runs in CI.
- Before the first pinned release exists, contributors refresh the baseline
  manually from a `lifeos-cli` checkout.

## API Compatibility Policy

- Response and request models are the transport contract
  ([#223](https://github.com/lifeos-plus/lifeos-cli/issues/223) closed) and
  generated TypeScript types are the only HTTP boundary type source
  ([#226](https://github.com/lifeos-plus/lifeos-cli/issues/226) closed,
  merged in PR #256).
- Additive contract changes are safe and do not require a coordinated release.
- Breaking contract changes require a coordinated `lifeos-cli` release and
  `lifeos-web` `api:refresh` in the same change set, or an explicitly versioned
  API path.
- UI catalogs that mirror backend enums (for example theme options) must be
  exposed through the API contract so cross-repo sync checks run at the
  contract boundary instead of on duplicated local files.

## Artifact Delivery

- `lifeos-web` builds a static `dist/` with `npm run build`.
- The LifeOS Web API keeps serving built assets through
  `lifeos web serve --static-dir <path>`; `--static-dir` remains the
  integration point for locally built or release-downloaded frontend assets.
- No npm package publishing is planned initially. GitHub Releases can carry
  the `dist/` artifact if deployed hosting needs it later.

## Dual-Repo CI

### lifeos-cli

- `validate.yml` keeps backend quality gate, runtime matrix, and PostgreSQL
  integration jobs; the frontend job is removed.
- `frontend-dependency-audit.yml` is removed; npm dependency auditing moves to
  `lifeos-web`.
- `dependency-review.yml` keeps only the Python dependency health job.
- `.github/dependabot.yml` keeps only the `uv` update entry.
- `publish.yml` uploads `openapi.json` to every release.

### lifeos-web

- `validate.yml` runs `npm ci`, high-severity audit enforcement, `api:check`,
  `i18n:check`, build, lint, and the Vitest suite.
- `dependency-audit.yml` runs the weekly non-force `npm audit fix` workflow.
- `dependency-review.yml` runs the monthly outdated/audit health job.
- `.github/dependabot.yml` checks the root npm workspace weekly.

## Rollout Checklist

- [x] Migrate the repository to `lifeos-plus` (issue 251 prerequisite)
- [x] Update `origin` to the organization address
- [x] Merge repository metadata and CLI help canonical-URL updates (PR #254)
- [x] Close the response-contract issue (#223) and OpenAPI type generation
      issue (#226)
- [x] Create `lifeos-plus/lifeos-web` with the migrated `web/` history
- [x] Add pinned OpenAPI baseline, npm CI, dependency audit, and governance
      documents to `lifeos-web`
- [x] Strip the frontend workspace from `lifeos-cli` on a feature branch
- [ ] Publish `openapi.json` as a release asset and pin the first schema
      version in `lifeos-web`
- [ ] Move theme-option sync to the API contract boundary
- [ ] (human) Rebind the PyPI Trusted Publisher to
      `lifeos-plus/lifeos-cli` before the next formal release

## Follow-Ups

- End-to-end browser tests do not exist yet; the frontend CI currently covers
  unit and integration-style component tests only.
- The API compatibility policy needs a versioned-path decision before any
  breaking API change lands.
- `lifeos-cli` remote branches that are closed but unmerged
  (`issue-227-query-boundary`, `refactor/228-split-finance-services`,
  `chore/web-npm-audit-fix`) should be cleaned up on the remote once confirmed
  obsolete.
