"""Shared validation helpers for domain service modules."""

from __future__ import annotations

from collections.abc import Collection, Sequence


class DomainValidationError(ValueError):
    """Base class for domain-service validation errors."""


def validate_choice(
    value: str,
    allowed: Collection[str],
    *,
    error_cls: type[Exception],
    label: str,
    error_verb: str = "Invalid",
    display_order: Sequence[str] | None = None,
) -> str:
    """Validate and normalize a string choice against an allowlist.

    The normalized value is the input with surrounding whitespace stripped and
    lowercased. When it is not part of ``allowed``, ``error_cls`` is raised
    with a message listing every supported choice.

    ``display_order`` optionally overrides how the allowlist is rendered in
    error messages; it defaults to sorted ``allowed``.
    """
    normalized = value.strip().lower()
    if normalized not in allowed:
        display = display_order if display_order is not None else sorted(allowed)
        allowed_text = ", ".join(display)
        raise error_cls(f"{error_verb} {label} {normalized!r}. Expected one of: {allowed_text}")
    return normalized
