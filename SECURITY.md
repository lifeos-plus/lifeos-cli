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

## Supported Branches

Security fixes should land on the active `main` branch first.
