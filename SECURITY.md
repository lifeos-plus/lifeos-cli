# Security Policy

## Scope

This repository currently ships a Python package skeleton, local validation scripts, dependency audit workflows, and release automation for publishing to PyPI and GitHub Releases.

## Security-Relevant Areas

- release tags and package version derivation
- trusted publishing configuration and GitHub Actions permissions
- dependency locking, export, and vulnerability audit flows
- secret scanning baselines and repository examples

## Reporting a Vulnerability

Please avoid posting secrets, tokens, private package credentials, or sensitive environment details in public issues.

Preferred disclosure order:

1. Use GitHub private vulnerability reporting if it is enabled for this repository.
2. If private reporting is unavailable, contact the repository maintainer directly through GitHub before opening a public issue.
3. Use a normal public issue only for low-risk hardening ideas that do not expose private data.

## Release and Publishing Notes

- Supported Python versions are 3.11 through 3.14; keep `requires-python`, classifiers, CI matrices, and version-support documentation aligned when support changes.
- Treat changes to `.github/workflows/publish.yml`, package versioning, and PyPI publishing configuration as security-sensitive.
- Trusted publishing should be configured only for the intended repository and workflow path.
- Keep `uv.lock`, version metadata, and tag validation logic aligned to reduce release drift.

Routine dependency version updates are intentionally limited to weekly minor updates; patch updates are excluded from routine PRs. Security updates and the weekly frontend audit remain independent of that routine policy. The frontend audit workflow never uses `npm audit fix --force`.

Pull request and `main` validation audits the locked Python project with every optional extra and rejects any known vulnerability reported by `pip-audit`. Frontend validation rejects high- and critical-severity `npm audit` findings. The weekly frontend audit may prepare a non-force lockfile fix, but it still fails when high- or critical-severity findings remain after that attempt.

## Local Web Service Exposure

The local Web API (`lifeos web serve`) has no authentication and holds access to the same personal LifeOS data as the CLI. It defaults to binding `127.0.0.1` (loopback) and prints a warning on stderr when started with a non-loopback `--host` such as `0.0.0.0`. Keep the loopback default for personal use; if you must bind beyond loopback, treat it as an intentional exposure and restrict access at the network layer (for example a firewall or an isolated network). Do not rely on the warning as a security boundary.

Additional request-level boundaries apply by default:

- Only loopback Host headers (`localhost`, `127.0.0.1`, `::1`) are accepted; add trusted hostnames with the `LIFEOS_WEB_ALLOWED_HOSTS` environment variable (comma-separated).
- Requests carrying an `Origin` header must be same-origin or one of the allowlisted Vite development origins; anything else is rejected with `403`.
- Request bodies are limited to 1 MiB by default (override with `LIFEOS_WEB_MAX_BODY_BYTES`), bulk payloads have explicit item caps, and `/api/` requests are rate limited per client (default 300/minute, override with `LIFEOS_WEB_RATE_LIMIT_PER_MINUTE`).
- Swagger UI and the OpenAPI schema are disabled by default; enable them explicitly with `lifeos web serve --docs`.

## Database Credentials

The configured database URL can be stored in `~/.lifeos/config.toml`, which keeps any embedded credentials in plaintext on disk. For PostgreSQL deployments, prefer supplying the URL through the `LIFEOS_DATABASE_URL` environment variable instead of writing it into the config file, and restrict read access to the config file (for example `chmod 600`). Runtime status and `lifeos config show` hide database passwords by default; keep `--show-secrets` for explicit, local-only use.

Local SQLite database files are created with owner-only permissions (`0600`), matching the config file policy, so other local users cannot read personal LifeOS data on shared machines. The database directory is restricted to `0700`, and the resolved database file must be owned by the current user before connecting; symlinks to another user's file are rejected. Interactive `lifeos init` prompts for the database URL with hidden input so embedded passwords are not echoed to the terminal; non-interactive or scripted setups should pass `LIFEOS_DATABASE_URL` or `--database-url`.

## Supported Branches

Security fixes should land on the active `main` branch first.
