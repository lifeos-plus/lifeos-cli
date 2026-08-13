# AGENTS.md

The following rules apply to coding agent collaboration in this repository. These complement the general [CONTRIBUTING.md](CONTRIBUTING.md) workflow.

## 1. Core Principles

- Keep repository governance, release safety, and Python compatibility aligned.
- Prefer small, traceable changes that preserve a releasable `main` branch.

## 2. Collaboration Workflow

- Follow the Git, Issue, and PR workflow defined in [CONTRIBUTING.md](CONTRIBUTING.md).
- Use `gh` CLI for all issue and PR operations. Do not edit through the web UI.
- Never use the Codex GitHub connector or any connector-backed GitHub mutation workflow. At any time, issue and PR operations must go through `gh` CLI only.
- If GitHub permissions, authentication, policy, or environment constraints block a required `gh` operation, stop and ask the human collaborator to perform or authorize the needed step. Do not switch to the Codex GitHub connector as a fallback.
- Create a tracking issue for non-trivial development tasks that do not already have one; very small changes do not require a new issue.
- Link the relevant issue in the PR description with `Closes #xx` or `Related #xx` as appropriate.
- Keep issue and PR status synchronized when work scope changes.
- Begin every issue and PR description with a `TL;DR` section that states the intent and expected outcome in plain language, so human readers can grasp the point at a glance before reading the full description.

## 3. Text and Language Conventions

- Use Simplified Chinese for issue and PR descriptions, comments, and review notes; keep technical terms in English.
- Always use English commit-message style for PR titles.
- Use English for code, comments, commit messages, and canonical repository documents.
- Localized Markdown companions are allowed when they are explicitly scoped, linked from the canonical English document, and kept aligned with it.
- Keep the root `README.md` in English as the canonical repository entrypoint. Localized companions such as `README.zh-Hans.md` must link back to `README.md`, and `README.md` should link to the available localized companion documents.
- Do not hard-wrap text in repository documents; keep each paragraph on a single line and let the editor soft-wrap long lines. Markdown tables, code blocks, and ASCII art are exempt because their line layout is meaningful.
- For multi-line PR bodies or comments, write to a temporary file first and pass it through `gh`.

## 4. Validation and Release Safety

- Use the primary validation entrypoint for code changes:
  ```bash
  bash ./scripts/doctor.sh
  ```
- Treat the dead-code scan as part of the primary validation gate. Do not delete framework-driven symbols only to satisfy generic static analysis; update `scripts/vulture_whitelist.py` when a tool-required symbol must remain intentionally reachable.
- If changes affect compatibility claims, packaging metadata, or CI, validate the impacted Python versions explicitly.
- Keep release-related changes aligned with:
  - [pyproject.toml](pyproject.toml)
  - [.github/workflows/validate.yml](.github/workflows/validate.yml)
  - [.github/workflows/publish.yml](.github/workflows/publish.yml)
- Do not weaken checks that protect trusted publishing, locked dependency resolution, or tag/version consistency without explicit justification.

## 5. Security and Documentation

- Never commit secrets, tokens, private keys, or `.env` contents.
- Ensure logs and examples do not expose credentials or sensitive local paths unintentionally.
- Update [SECURITY.md](SECURITY.md), [README.md](README.md), localized README companions, and release-related docs when changing publishing, dependency, or security-sensitive behavior.

## 6. CLI Help and Tests

- Treat CLI help as the primary command reference:
  - `lifeos --help`
  - `lifeos <resource> --help`
  - `lifeos <resource> <action> --help`
- Command-specific facts such as examples, argument constraints, behavioral notes, and scope rules must be updated in help when CLI behavior changes.
- Repository-level CLI docs should summarize cross-command concepts and must not become a second source of truth for command-level details.
- For CLI feature work, review the related help text and tests before considering the task complete.
- Do not ship CLI behavior changes with source-only updates; update the relevant help text and add or adjust tests that cover the user-visible command shape and behavior.
