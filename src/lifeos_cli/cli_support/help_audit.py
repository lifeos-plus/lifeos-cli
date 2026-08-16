"""Helpers for executing and reviewing CLI help output."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lifeos_cli.application.package_metadata import get_installed_package_version
from lifeos_cli.i18n import resolve_locale


@dataclass(frozen=True)
class HelpInvocation:
    """One CLI help invocation target."""

    path: tuple[str, ...]

    @property
    def argv(self) -> tuple[str, ...]:
        """Return CLI arguments needed to query this parser's help."""
        return (*self.path, "--help")


@dataclass(frozen=True)
class HelpAuditResult:
    """Captured result for one help invocation."""

    invocation: HelpInvocation
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        """Return whether the help command exited successfully."""
        return self.returncode == 0


def _get_subparsers_action(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction[argparse.ArgumentParser] | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def collect_help_invocations(
    parser: argparse.ArgumentParser,
    *,
    path: Sequence[str] = (),
) -> list[HelpInvocation]:
    """Collect help invocations for the parser tree in declaration order."""
    normalized_path = tuple(path)
    invocations = [HelpInvocation(path=normalized_path)]
    subparsers_action = _get_subparsers_action(parser)
    if subparsers_action is None:
        return invocations
    for name, child_parser in subparsers_action.choices.items():
        invocations.extend(
            collect_help_invocations(
                child_parser,
                path=(*normalized_path, name),
            )
        )
    return invocations


def filter_help_invocations(
    invocations: Iterable[HelpInvocation],
    *,
    path_prefix: Sequence[str] = (),
) -> list[HelpInvocation]:
    """Return help invocations under one parser subtree."""
    normalized_prefix = tuple(path_prefix)
    return [
        invocation
        for invocation in invocations
        if invocation.path[: len(normalized_prefix)] == normalized_prefix
    ]


def run_help_audit(
    invocations: Iterable[HelpInvocation],
    *,
    command_prefix: Sequence[str],
    cwd: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[HelpAuditResult]:
    """Execute the selected help commands and capture their outputs."""
    results: list[HelpAuditResult] = []
    for invocation in invocations:
        command = (*command_prefix, *invocation.argv)
        completed = runner(
            list(command),
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
        results.append(
            HelpAuditResult(
                invocation=invocation,
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        )
    return results


def render_help_audit_report(results: Sequence[HelpAuditResult]) -> str:
    """Render one Markdown report for the executed help audit."""
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    lines = [
        "# CLI Help Audit",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Commands executed: `{len(results)}`",
        f"- Failures: `{sum(not result.ok for result in results)}`",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"## `{shlex.join(result.command)}`",
                "",
                f"- Exit code: `{result.returncode}`",
                "",
                "```text",
                result.stdout.rstrip("\n"),
                "```",
                "",
            ]
        )
        if result.stderr:
            lines.extend(
                [
                    "stderr:",
                    "",
                    "```text",
                    result.stderr.rstrip("\n"),
                    "```",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _describe_parser_argument(action: argparse.Action) -> dict[str, Any] | None:
    """Describe one argparse action as a JSON-safe reference entry."""
    if isinstance(action, argparse._SubParsersAction):
        return None
    option_strings = getattr(action, "option_strings", None)
    if option_strings and any(flag in ("-h", "--help") for flag in option_strings):
        return None
    is_positional = not option_strings
    name = option_strings[0] if option_strings else action.dest
    default = action.default
    if default is not None and not isinstance(default, (str, int, float, bool)):
        default = str(default)
    required = bool(action.required) or (is_positional and action.nargs not in ("*", "?"))
    return {
        "name": name,
        "kind": "positional" if is_positional else "option",
        "metavar": action.metavar,
        "help": action.help,
        "choices": list(action.choices) if action.choices is not None else None,
        "required": required,
        "nargs": action.nargs,
        "default": default,
    }


def _describe_parser_node(
    parser: argparse.ArgumentParser,
    path: tuple[str, ...],
) -> dict[str, Any]:
    """Describe one parser node as a JSON-safe command reference entry."""
    help_content = getattr(parser, "_lifeos_help_content", None)
    description = help_content.description if help_content is not None else parser.description
    arguments: list[dict[str, Any]] = []
    for action in parser._actions:
        entry = _describe_parser_argument(action)
        if entry is not None:
            arguments.append(entry)
    return {
        "path": list(path),
        "summary": (help_content.summary if help_content is not None else parser.description),
        "description": description,
        "usage": parser.format_usage().strip(),
        "examples": list(help_content.examples) if help_content is not None else [],
        "notes": list(help_content.notes) if help_content is not None else [],
        "arguments": arguments,
    }


def _walk_parser(
    parser: argparse.ArgumentParser,
    path: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Collect reference nodes for every subcommand in declaration order."""
    nodes: list[dict[str, Any]] = []
    subparsers_action = _get_subparsers_action(parser)
    if subparsers_action is None:
        return nodes
    for name, child in subparsers_action.choices.items():
        child_path = (*path, name)
        nodes.append(_describe_parser_node(child, child_path))
        nodes.extend(_walk_parser(child, child_path))
    return nodes


def build_machine_readable_reference(
    parser: argparse.ArgumentParser,
) -> dict[str, Any]:
    """Build a JSON-safe reference for the full CLI parser tree.

    The reference mirrors the current locale and package version, so callers
    can pin both when consuming it.
    """
    return {
        "version": get_installed_package_version(),
        "locale": resolve_locale(),
        "command_shape": "lifeos <resource> <action> [arguments] [options]",
        "commands": _walk_parser(parser, ()),
    }


def filter_reference_commands(
    reference: dict[str, Any],
    *,
    path_prefix: Sequence[str],
) -> dict[str, Any]:
    """Restrict a machine-readable reference to one command subtree."""
    prefix = tuple(path_prefix)
    commands = [
        command
        for command in reference["commands"]
        if tuple(command["path"])[: len(prefix)] == prefix
    ]
    return {**reference, "commands": commands}


def render_machine_readable_reference(
    reference: dict[str, Any],
    *,
    indent: int = 2,
) -> str:
    """Render a machine-readable command reference as JSON text."""
    return json.dumps(reference, ensure_ascii=False, indent=indent) + "\n"


def lint_help_summary_conventions(reference: dict[str, Any]) -> list[str]:
    """Return command-summary convention violations for every parser node.

    Summaries are the short command names shown in subcommand listings. The
    repository convention is an imperative phrase without a trailing period
    (for example ``List areas``, never ``List areas.``).
    """
    violations: list[str] = []
    for command in reference["commands"]:
        path = "/".join(command["path"])
        summary = command.get("summary") or ""
        if not summary.strip():
            violations.append(f"{path}: summary is empty")
        elif summary.rstrip().endswith((".", "。")):
            violations.append(f"{path}: summary ends with a period")
    return violations
