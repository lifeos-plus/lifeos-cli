from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lifeos_cli.cli import build_parser
from lifeos_cli.cli_support.help_audit import (
    build_machine_readable_reference,
    collect_help_invocations,
    filter_help_invocations,
    filter_reference_commands,
    lint_help_summary_conventions,
    render_command_tree,
    render_help_audit_report,
    render_machine_readable_reference,
    run_help_audit,
)


def test_collect_help_invocations_covers_nested_parser_paths() -> None:
    invocations = collect_help_invocations(build_parser())
    paths = {invocation.argv for invocation in invocations}

    assert ("--help",) in paths
    assert ("note", "--help") in paths
    assert ("note", "add", "--help") in paths
    assert ("note", "batch", "update-content", "--help") in paths
    assert ("timelog", "search", "--help") in paths
    assert ("timelog", "stats", "day", "--help") in paths
    assert ("config", "update", "--help") in paths


def test_filter_help_invocations_limits_results_to_one_subtree() -> None:
    invocations = collect_help_invocations(build_parser())

    filtered = filter_help_invocations(invocations, path_prefix=("note",))

    assert filtered
    assert all(invocation.path[:1] == ("note",) for invocation in filtered)
    assert ("note", "--help") in {invocation.argv for invocation in filtered}
    assert ("note", "add", "--help") in {invocation.argv for invocation in filtered}
    assert ("task", "--help") not in {invocation.argv for invocation in filtered}


def test_run_help_audit_executes_requested_commands_and_renders_markdown() -> None:
    invocations = filter_help_invocations(
        collect_help_invocations(build_parser()),
        path_prefix=("note",),
    )[:2]
    captured_commands: list[list[str]] = []

    def fake_runner(
        command: list[str],
        *,
        cwd: str,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        captured_commands.append(command)
        assert cwd == str(Path.cwd())
        assert check is False
        assert capture_output is True
        assert text is True
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"help for {' '.join(command[3:-1]) or 'root'}\n",
            stderr="",
        )

    results = run_help_audit(
        invocations,
        command_prefix=("uv", "run", "lifeos"),
        cwd=Path.cwd(),
        runner=fake_runner,
    )
    report = render_help_audit_report(results)

    assert captured_commands == [
        ["uv", "run", "lifeos", "note", "--help"],
        ["uv", "run", "lifeos", "note", "add", "--help"],
    ]
    assert "## `uv run lifeos note --help`" in report
    assert "help for note add" in report
    assert "- Failures: `0`" in report


def test_machine_readable_reference_covers_nested_commands() -> None:
    reference = build_machine_readable_reference(build_parser())
    paths = {tuple(command["path"]) for command in reference["commands"]}

    assert ("task", "list") in paths
    assert ("note", "add") in paths
    assert ("timelog", "stats", "day") in paths


def test_machine_readable_reference_describes_arguments_and_content() -> None:
    reference = build_machine_readable_reference(build_parser())
    task_list = next(
        command for command in reference["commands"] if command["path"] == ["task", "list"]
    )
    note_add = next(
        command for command in reference["commands"] if command["path"] == ["note", "add"]
    )
    note_search = next(
        command for command in reference["commands"] if command["path"] == ["note", "search"]
    )

    task_argument_names = [argument["name"] for argument in task_list["arguments"]]
    assert "--json" in task_argument_names
    assert "--limit" in task_argument_names
    assert task_list["usage"].startswith("usage: lifeos task list")
    assert task_list["examples"]

    note_positional = [
        argument for argument in note_add["arguments"] if argument["kind"] == "positional"
    ]
    assert [argument["name"] for argument in note_positional] == ["content"]
    assert note_positional[0]["nargs"] == "?"

    search_positional = [
        argument for argument in note_search["arguments"] if argument["kind"] == "positional"
    ]
    assert [argument["name"] for argument in search_positional] == ["query"]
    assert search_positional[0]["required"] is True


def test_lint_help_summary_conventions_flags_trailing_periods_and_empty_summaries() -> None:
    reference = {
        "commands": [
            {"path": ["area", "list"], "summary": "List areas."},
            {"path": ["note", "add"], "summary": "Add a note"},
            {"path": ["config", "show"], "summary": ""},
        ]
    }

    violations = lint_help_summary_conventions(reference)

    assert any("area/list" in violation for violation in violations)
    assert any("config/show" in violation for violation in violations)
    assert not any("note/add" in violation for violation in violations)


def test_built_parser_passes_summary_convention_lint() -> None:
    reference = build_machine_readable_reference(build_parser())

    assert lint_help_summary_conventions(reference) == []


def test_render_command_tree_draws_explicit_connectors_and_leaf_arguments() -> None:
    reference = {
        "commands": [
            {
                "path": ["area", "list"],
                "summary": "List areas",
                "arguments": [
                    {
                        "name": "--limit",
                        "kind": "option",
                        "required": False,
                        "nargs": None,
                    }
                ],
            },
            {"path": ["area"], "summary": "Manage life areas", "arguments": []},
            {"path": ["note"], "summary": "Manage notes", "arguments": []},
            {
                "path": ["note", "add"],
                "summary": "Add a note",
                "arguments": [
                    {
                        "name": "content",
                        "kind": "positional",
                        "required": False,
                        "nargs": "?",
                    }
                ],
            },
        ]
    }

    rendered = render_command_tree(reference)

    assert "├── area  —  Manage life areas" in rendered
    assert "└── note  —  Manage notes" in rendered
    assert "└── list  —  List areas" in rendered
    assert "        args: --limit" in rendered
    assert "content [nargs=?]" in rendered


def test_machine_readable_reference_renders_valid_json_with_metadata() -> None:
    reference = build_machine_readable_reference(build_parser())
    rendered = render_machine_readable_reference(reference)

    payload = json.loads(rendered)
    assert payload["version"]
    assert payload["locale"]
    assert payload["command_shape"] == "lifeos <resource> <action> [arguments] [options]"
    assert payload["commands"]


def test_filter_reference_commands_limits_results_to_one_subtree() -> None:
    reference = build_machine_readable_reference(build_parser())

    filtered = filter_reference_commands(reference, path_prefix=("note",))

    assert filtered["commands"]
    assert all(command["path"][0] == "note" for command in filtered["commands"])
    assert ["note", "add"] in [command["path"] for command in filtered["commands"]]
