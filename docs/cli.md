# CLI Guide

This document is a secondary overview of the current `lifeos` CLI.

Command-specific facts such as arguments, examples, constraints, and command notes must live in `lifeos --help`, `lifeos <resource> --help`, and `lifeos <resource> <action> --help`.

Use this document for cross-command guidance only. Do not treat it as the source of truth for resource-level command details.

## Command Grammar

The CLI follows one stable grammar:

```text
lifeos <resource> <action> [arguments] [options]
```

The public command tree prefers:

- short resource names
- short action verbs such as `add`, `list`, `show`, `update`, and `delete`
- `list` as the main query entrypoint for structured resources
- grouped namespaces such as `batch` for multi-record writes

## Documentation Model

To avoid duplicate maintenance, the documentation boundary is:

- Help is the primary command reference.
- Repository docs summarize cross-resource concepts and operating rules.
- When command behavior changes, update help first.
- Only update this file when a cross-command model, workflow, or policy changes.

Practical rule:

- If a user needs to know how to run one command correctly, that information belongs in help.

## Output Conventions

The current CLI output stays intentionally simple and scriptable.

- `list` commands print compact summary rows
- `show` commands print labeled fields
- `add` and `update` commands print short confirmation messages
- public `delete` commands report soft-delete results only

`list`, `search`, and `show` read commands accept an opt-in `--json` flag that leaves the default text output untouched:

- JSON output is pretty-printed, preserves non-ASCII characters, and is emitted as one array of record objects for list-style commands
- commands that support `--count` emit `{"items": [...], "total_count": N}` when `--count --json` are combined
- timestamps render as explicit UTC ISO strings (for example `2026-04-10T12:00:00Z`), UUIDs render as strings, and Decimal amounts render as strings so precision is preserved
- JSON payloads expose the full underlying record fields; for example note content is not truncated or whitespace-normalized the way text summaries are

Aggregated read commands (`schedule show/list`, `planning show`) and `config show`
also accept `--json`; `config show --json` keeps database passwords masked unless
`--show-secrets` is passed.

The `--json` shape follows the Web API serialization conventions where the two surfaces overlap, so callers that already consume the API can reuse their field handling.

## Installation and Initialization

Install the published CLI:

```bash
uv tool install lifeos-cli
```

Initialize local configuration:

```bash
lifeos init
```

Inspect the effective runtime configuration:

```bash
lifeos config show
```

Check database connectivity and migrations:

```bash
lifeos db ping
lifeos db upgrade
```

## Runtime Preferences

The CLI persists a small set of runtime preferences:

- `timezone`
- `language`
- `day_starts_at`
- `week_starts_on`
- `vision_experience_rate_per_hour`

Time-oriented behavior follows these rules:

- `event` and `timelog` datetimes are stored in UTC-normalized form
- CLI timestamp rendering uses the configured `timezone`
- date-based queries also use the configured `day_starts_at`
- weekly habit summaries use the configured `week_starts_on`

## Command Families

The current command tree is organized around a few stable families:

- planning resources such as `area`, `vision`, `task`, `planning`, `note`, `person`, and `tag`
- scheduling and tracking resources such as `event`, `schedule`, `timelog`, `habit`, and `habit-action`
- financial reality resources such as `finance`
- system, Web, and portability commands such as `init`, `config`, `db`, `web`, and `data`

`finance` uses nested namespaces (`finance asset`, `finance tree`, `finance node`,
`finance snapshot`, and `finance rate-snapshot`), each with the standard
`add`/`list`/`show`/`update`/`delete` actions. Command names follow the singular
`person` convention and the nested finance namespaces are the only supported
command shape.

`data import --mode upsert --key <field>` supports idempotent natural-key sync for `area.name`, `vision.name`, `person.name`, and `habit.title`: each row is matched against existing active records, updated when one match exists, and inserted otherwise (a fresh id is generated when the row has none). Ambiguous keys and missing key values are reported as row-level failures.

Use `lifeos <resource> --help` to enter one family and then follow the resource-level help into the action or namespace you need.

## Help Review

The CLI help tree is broad enough that manual spot checks are not sufficient for release review. Use the help audit script when reviewing command documentation:

```bash
uv run python scripts/audit_cli_help.py
```

The script walks the parser tree, executes every discovered `--help` invocation, and renders a Markdown report with command output and failures. Use `--path-prefix` for focused reviews such as:

```bash
uv run python scripts/audit_cli_help.py --path-prefix "timelog stats"
```

The same script emits a machine-readable command reference without spawning subprocesses:

```bash
uv run python scripts/audit_cli_help.py --format json
uv run python scripts/audit_cli_help.py --format json --path-prefix "task list"
```

The JSON reference is locale-aware, includes the package version, and describes every command node with its summary, description, usage, examples, notes, and structured arguments (name, kind, metavar, choices, required, nargs, default). It is intended for agents and tooling that need the full command grammar in one fetch instead of walking `--help` one level at a time.

The same script renders a plain-text command tree that is committed as
[docs/cli-tree.md](cli-tree.md) and kept current by a pre-commit check:

```bash
LIFEOS_LANGUAGE=en uv run python scripts/audit_cli_help.py --format tree --output docs/cli-tree.md
```

Regenerate the file whenever a command, argument, or summary changes; the
`cli-tree-sync` pre-commit hook fails when the artifact drifts.

Localized help should be reviewed through the same command surface by setting the runtime language preference or `LIFEOS_LANGUAGE`.

## Safety Model

The public CLI is intentionally conservative.

- public `delete` commands only soft-delete records
- public `delete` commands accept one or more identifiers and only soft-delete records
- hard delete stays outside the public CLI

This boundary should remain stable as more resources are added.

## Agent Guidance

If the caller is an agent or another automation layer:

- start from `list` to discover identifiers
- use `show` before destructive or state-changing operations
- treat help as the only authoritative command-level reference
- run `lifeos config show` before writing human-authored payload fields
- use `Preference language` as the payload language for titles, descriptions, and note content unless the human explicitly asks for another language
- keep flows identifier-driven after discovery
- decide whether the record belongs to the human, the agent, or both before writing data
- prefer resource help and action help over repository docs whenever an operation depends on exact flags, scope rules, or examples
