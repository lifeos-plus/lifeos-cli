"""Helpers for executing and reviewing CLI help output."""

from __future__ import annotations

import argparse
import shlex
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


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
