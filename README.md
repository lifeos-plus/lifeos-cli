# lifeos-cli

[简体中文版](README.zh-Hans.md)

```text
██╗     ██╗███████╗███████╗ ██████╗ ███████╗
██║     ██║██╔════╝██╔════╝██╔═══██╗██╔════╝
██║     ██║█████╗  █████╗  ██║   ██║███████╗
██║     ██║██╔══╝  ██╔══╝  ██║   ██║╚════██║
███████╗██║██║     ███████╗╚██████╔╝███████║
╚══════╝╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚══════╝
```

`lifeos-cli` is a terminal-native, local-first LifeOS for quantified-self workflows. It gives one structured system for intentions, plans, execution, relationships, money, reflection, and measured reality.

The product surface is already broad and deep: a typed Python CLI as the primary interface, SQLite and PostgreSQL backends, Alembic migrations, a local FastAPI service, and a first-party React Web UI (in the separate `lifeos-web` repository) for human browser workflows over the same configured LifeOS database. The CLI is designed to be both human-usable and agent-friendly, with stable command grammar, help-first documentation, identifier-driven flows, and predictable text output.

## Why It Exists

Most personal systems fragment life into disconnected tools. Tasks live in one place, calendars in another, notes somewhere else, and actual time spent disappears into scattered logs. That makes it hard to answer practical questions:

- What did I intend to do?
- What actually happened?
- What did I spend time on?
- Which routines are real versus aspirational?
- Which people, projects, and priorities am I actually serving?
- How do my plans, time, habits, notes, relationships, and finances connect?

`lifeos-cli` treats a personal operating system as both a planning graph and an evidence ledger:

- intention: areas, visions, tasks, habits, planned events, and finance structures
- reality: timelogs, habit actions, notes, relationship records, finance snapshots, and aggregate stats

The goal is not just storage. The goal is a coherent command and API surface that humans and agents can use to capture life as it happens, inspect it later, and automate repeatable self-management workflows.

## Current Capability Map

The implemented system covers the main quantified-self loop from planning to evidence to review.

| Area | Current support |
| --- | --- |
| Life structure | `area` records for durable life domains, with display ordering, color/icon metadata, active state, and soft deletion. |
| Direction | `vision` records with status, area ownership, task trees, stats, experience points, task-effort synchronization, and harvest flow. |
| Execution | Hierarchical `task` records with parent/child structure, planning-cycle fields, status updates, subtree and hierarchy views, reorder/move support, and aggregate stats. |
| Calendar intent | Planned `event` records with appointment/timeblock/deadline types, all-day support, recurrence rules, instance-scoped recurring updates/deletes, task/area/person/tag links, and bounded expansion. |
| Daily schedule | `schedule` day and range views that aggregate planned events, planning-cycle tasks, and habit actions, including overdue unfinished task and habit-action roll-forward behavior. |
| Routines | `habit` records with daily/weekly/monthly/yearly cadence, weekday/weekend controls, task links, stats, and on-demand `habit-action` materialization. |
| Time reality | `timelog` records with date and datetime entry modes, quick batch entry, list/search filters, relationship links, batch update/delete, templates, and area-based stats. |
| Notes and reflection | `note` records with inline/stdin/file capture, search, full-content display, bulk content replacement, soft delete, and associations to tasks, visions, events, people, timelogs, and tags. |
| Relationships | `people` records with relationship metadata, birthday/anniversary dates, tags, related activities, anniversaries, and links from events, notes, and timelogs. |
| Taxonomy | `tag` records with category/entity-type metadata and association counts across supported resources. |
| Finance | Assets, reusable finance trees, nodes, instant and period snapshots, exchange-rate snapshots, default tree bootstrapping, and balance-sheet/cashflow style data modeling. |
| Data portability | Canonical JSON/JSONL export/import, full bundle backup/restore, dry-run validation, row-level errors, and machine-oriented batch update/delete. |
| Configuration | Persistent database and preference configuration, including timezone, language, day boundary, week boundary, theme, and default vision experience rate. |
| Local Web API | FastAPI routers for health, tasks, visions, habits, notes, timelogs, timelog templates, people, areas, finance, planned events, stats, tags, and preferences. |
| Web UI | A first-party Vite/React workspace in `lifeos-plus/lifeos-web` for visions, habits, planning, timelog, finance, insights/stats, schedule/calendar, notes, people, and settings. |

## Interfaces

The terminal-native CLI is the primary product interface and command reference:

```bash
lifeos --help
lifeos <resource> --help
lifeos <resource> <action> --help
```

The command shape is intentionally stable:

```text
lifeos <resource> <action> [arguments] [options]
```

This shape is intentionally friendly to both humans and agents. Humans get explicit, discoverable commands; agents get deterministic help, stable identifiers, compact tabular list output, and labeled detail output.

The local Web UI is the human browser interface for the same LifeOS data. It is first-party and intentionally local; it lives in the separate `lifeos-web` repository and talks to the Web API over the generated OpenAPI contract.

## Getting Started

`lifeos-cli` requires Python 3.11 or newer; Python 3.11 through 3.14 are tested in CI.

Install or upgrade from PyPI:

```bash
uv tool install --upgrade lifeos-cli
```

Install PostgreSQL support only when you need it:

```bash
uv tool install --upgrade "lifeos-cli[postgres]"
```

Install the optional local Web API runtime dependencies when you want browser or HTTP access backed by the same configured LifeOS database:

```bash
uv tool install --upgrade "lifeos-cli[web]"
```

`lifeos-cli` supports SQLite and PostgreSQL.

- SQLite is the low-friction option for local, single-user setups.
- PostgreSQL remains the schema-capable backend for managed deployments.

Initialize your local setup:

```bash
lifeos init
```

For local-first use, `lifeos init` can bootstrap SQLite without requiring a separate database service. Use `lifeos init --help` for backend-specific defaults and examples.

Inspect and adjust runtime preferences:

```bash
lifeos config show
lifeos config set preferences.timezone America/Toronto
lifeos config set preferences.language zh-Hans
lifeos config set preferences.day_starts_at 04:00
lifeos config set preferences.week_starts_on monday
```

## Common CLI Workflows

```bash
lifeos area add "Health" --color "#16A34A" --icon heart
lifeos vision add "Build a stronger health baseline" --area-id <area-id>
lifeos task add "Train three times this week" --vision-id <vision-id> --planning-cycle-type week --planning-cycle-days 7 --planning-cycle-start-date 2026-04-13
lifeos event add "Strength training" --start-time 2026-04-13T18:00:00 --end-time 2026-04-13T19:00:00 --task-id <task-id>
lifeos schedule show --date 2026-04-13
lifeos timelog add "Workout" --start-time 2026-04-13T18:00:00 --end-time 2026-04-13T19:00:00 --task-id <task-id>
lifeos habit add "Morning mobility" --start-date 2026-04-01 --duration-days 100 --cadence-frequency daily
lifeos habit-action log --habit-id <habit-id> --date 2026-04-13 --status done
lifeos note add "Energy was higher after sleeping earlier." --task-id <task-id>
lifeos finance tree-ensure-default
lifeos data export all --output lifeos-bundle.zip
```

For complete CLI usage, workflows, and output conventions, see [docs/cli.md](docs/cli.md). Command-specific facts belong in CLI help, not in repository-level docs. For maintainer-oriented architecture guidance, see [docs/architecture.md](docs/architecture.md).

## Local Web UI

The first-party React Web UI lives in the separate [`lifeos-web`](https://github.com/lifeos-plus/lifeos-web) repository and talks to this project's Web API over the generated OpenAPI contract. This repository keeps the Web API and the `web serve` command.

Start the local Web API server for browser or HTTP access:

```bash
lifeos web serve
```

`lifeos web serve` does not install, build, or bundle the frontend from PyPI. Build the frontend from `lifeos-web` and pass its output directory explicitly:

```bash
lifeos web serve --static-dir <path-to>/lifeos-web/dist
```

If your configured database URL uses PostgreSQL, install or run with both optional extras:

```bash
uv tool install --upgrade "lifeos-cli[web,postgres]"
uv run --extra web --extra postgres lifeos web serve
```

The Web API has no authentication and defaults to binding `127.0.0.1`. Starting it with a non-loopback `--host` (for example `0.0.0.0`) exposes your personal data to the network; `lifeos web serve` prints a warning in that case. Keep the loopback default or restrict access at the network layer.

During frontend development, run the Vite app in `lifeos-web` and proxy API requests to the local Web API:

```bash
git clone https://github.com/lifeos-plus/lifeos-web
cd lifeos-web
npm ci
npm run dev
```

See the [`lifeos-web` README](https://github.com/lifeos-plus/lifeos-web) for the frontend workspace and cross-repo contract policy.

## Agent Use

Any agent runtime that can execute terminal commands and inspect command output can operate the same CLI. That includes Codex, OpenCode, Swival, Claude Code, Cursor, Gemini CLI, OpenClaw, or your own setup.

- stable grammar: `lifeos <resource> <action> [arguments] [options]`
- help-first command model, with `--help` as the primary command reference
- identifier-driven discovery flows built around `list` and `show`
- compact summary output for lists and labeled output for record detail views
- entity-specific primary-key headers such as `task_id`, `vision_id`, and `event_id`
- persisted language preference so agents can match human-authored payload language
- data import/export commands for machine-generated cleanup, migration, and backup flows

## Development Validation

For repository changes, run the primary validation entrypoint:

```bash
bash ./scripts/doctor.sh
```

For CLI documentation review, the help audit script executes the parser tree and renders a Markdown report:

```bash
uv run python scripts/audit_cli_help.py
```

## Dependency Maintenance

Routine backend dependency version updates are checked weekly. Only semver minor version updates are included in routine automation; patch updates are intentionally excluded and major migrations remain explicit maintenance tasks. Security updates are handled independently. Pull request validation audits every locked Python extra and rejects known vulnerabilities. Frontend dependency maintenance moved to the `lifeos-web` repository.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the dependency maintenance commands and workflow boundaries.

## Project Policies

- Contribution workflow: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security disclosure: [SECURITY.md](SECURITY.md)
- Community expectations: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
