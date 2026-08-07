# Contributing

Thanks for contributing to `lifeos-cli`.

This repository ships the `lifeos-cli` distribution and the `lifeos` command-line entrypoint. Changes should keep package metadata, CLI behavior, CI, security expectations, and release workflows aligned.

## Before You Start

- Read [README.md](README.md) for project scope and local development commands.
- Read [SECURITY.md](SECURITY.md) before changing publishing, credentials, or dependency handling.
- Read [AGENTS.md](AGENTS.md) if you are contributing through an automated coding workflow.

## Development Setup

Requirements:

- Python 3.10, 3.11, 3.12, or 3.13
- `uv`

Install dependencies:

```bash
uv sync --all-extras
```

## Validation

Run the default validation baseline before opening a PR:

```bash
bash ./scripts/doctor.sh
```

The default validation baseline includes dead-code scanning through `vulture`. It validates locked dependency resolution, runs lint plus the default non-integration test suite, exports the project and all optional extras for `pip-audit`, builds package artifacts, and then calls `bash ./scripts/integration_tests.sh` as the explicit PostgreSQL-backed integration entrypoint. When `LIFEOS_TEST_DATABASE_URL` is unset, the integration script reports an explicit skip and `doctor.sh` finishes with a warning that PostgreSQL CLI coverage did not run.

The React Web UI lives in the separate
[`lifeos-web`](https://github.com/lifeos-plus/lifeos-web) repository. Frontend
changes, including npm dependency updates, are validated there with
`bash ./scripts/validate.sh`. This repository keeps the Web API and the
`lifeos web serve` command; the split boundary is documented in
[issue 251](https://github.com/lifeos-plus/lifeos-cli/issues/251).

If you change CI, packaging metadata, or compatibility declarations, also validate the relevant interpreter targets explicitly. Examples:

```bash
rm -rf .venv && uv sync --all-extras --python 3.10 --frozen && .venv/bin/python -m pytest
rm -rf .venv && uv sync --all-extras --python 3.11 --frozen && .venv/bin/python -m pytest
rm -rf .venv && uv sync --all-extras --python 3.12 --frozen && .venv/bin/python -m pytest
rm -rf .venv && uv sync --all-extras --python 3.13 --frozen && bash ./scripts/doctor.sh
```

To run the real CLI integration suite locally:

```bash
LIFEOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:<password>@127.0.0.1:5432/lifeos_test \
bash ./scripts/integration_tests.sh
```

Integration tests normalize `LIFEOS_TEST_DATABASE_URL` to a database name that contains `test`. If you point the variable at `.../lifeos`, the test support layer rewrites it to `.../lifeos_test` before any CLI setup or cleanup runs.

For local convenience, `scripts/doctor.sh` and `scripts/integration_tests.sh` also load a project-root `.env` file when present. Keep `.env` untracked and use it only for machine-local development settings such as `LIFEOS_TEST_DATABASE_URL`.

If you change dependency or release workflows, also run:

```bash
bash ./scripts/dependency_health.sh
```

Dependency maintenance policy:

- `.github/dependabot.yml` checks the root `uv` backend workspace weekly.
- Backend dependency updates use the `backend` and `dependencies` labels.
- Routine Dependabot version updates allow only semver minor updates. Patch updates are intentionally excluded from routine PRs, and major version migrations are explicit tasks with focused validation coverage.
- Dependabot security updates remain eligible independently of the routine version-update policy.
- `bash ./scripts/dependency_health.sh` remains the explicit maintainer audit flow for Python outdated packages and dependency-related health checks.
- `bash ./scripts/doctor.sh` rejects known vulnerabilities in the locked project and every optional Python extra during PR and `main` validation.
- Frontend dependency maintenance and validation are handled by the `lifeos-web` repository.
- The `open-pull-requests-limit` setting limits concurrent Dependabot version-update PRs; it is not a dependency version ceiling.

Static-analysis governance:

- Treat framework-driven symbols as intentional API surface when they are required by the toolchain. Examples in this repository include Alembic revision metadata, pytest fixtures and `pytestmark`, SQLAlchemy declarative hooks, and argparse translation hooks.
- Do not delete those symbols just to satisfy a generic dead-code scanner.
- `scripts/dead_code_check.sh` keeps the name-based ignore list for Alembic revision metadata and module-level `pytestmark`; use `scripts/vulture_whitelist.py` for importable framework symbols that must stay intentionally reachable.
- Keep intentional false positives documented in `scripts/vulture_whitelist.py`.
- If you add a new framework-driven symbol that `vulture` cannot resolve, update the whitelist in the same change.

## Change Expectations

- Keep code, comments, commit messages, and canonical repository docs in English.
- Localized Markdown companions are allowed when the English source stays canonical, the documents are cross-linked, and the localized copy is updated together with the source.
- Keep issue and PR collaboration in Simplified Chinese for this repository.
- Prefer explicit, additive changes over hidden behavioral shifts.
- Keep Python compatibility declarations, CI matrices, and packaging metadata consistent with each other.
- Treat release and trusted publishing changes as security-sensitive infrastructure work.

## Git and PR Workflow

- Branch from the latest `main`.
- Use `git fetch` and `git merge --ff-only` to sync from `main`.
- Do not push directly to protected branches.
- Create or link a tracking issue for substantive development work.
- Use English commit-message style for PR titles.
- Link relevant issues in the PR description using `Closes #xx` or `Related #xx`.

## Documentation

Update docs together with code whenever you change:

- supported Python versions
- validation or dependency workflows
- release or publishing behavior
- security or disclosure guidance

Documentation language policy:

- Keep `README.md` as the canonical English entry document.
- Localized entry documents such as `README.zh-Hans.md` are allowed when they clearly link to the canonical English version and the English version links back to them.
- Avoid duplicating command-level facts in repository docs across languages. CLI help remains the primary command reference.

For CLI-facing changes:

- Treat CLI help as the primary command reference.
- Update `lifeos --help`, `lifeos <resource> --help`, or `lifeos <resource> <action> --help` when command behavior, examples, arguments, or constraints change.
- Use `uv run python scripts/audit_cli_help.py --output /tmp/cli-help-audit.md` to execute the current help surface and review the rendered report.
- Use `--path-prefix "note"` or another parser subtree when you want to audit one resource family at a time.
- Keep resource help focused on resource identity, primary entrypoints, and cross-command boundaries.
- Put detailed output contracts, flag semantics, and action-specific behavior in the relevant action help instead of duplicating them at the resource level.
- Keep repository CLI docs focused on cross-command guidance rather than duplicating command-level facts.
- Review and update the related CLI tests so help text and user-visible behavior stay covered together.
