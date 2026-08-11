"""Shared validation helpers for domain service modules."""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence


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


def choice_validator(
    allowed: Collection[str],
    *,
    error_cls: type[Exception],
    label: str,
    error_verb: str = "Invalid",
    display_order: Sequence[str] | None = None,
    doc: str | None = None,
) -> Callable[[str], str]:
    """Create a domain validator that normalizes a string choice.

    The returned callable behaves like ``validate_choice`` with the supplied
    allowlist and error configuration, so domain modules can define their
    validators as data instead of repeating wrapper bodies.
    """

    def validate(value: str) -> str:
        return validate_choice(
            value,
            allowed,
            error_cls=error_cls,
            label=label,
            error_verb=error_verb,
            display_order=display_order,
        )

    if doc is not None:
        validate.__doc__ = doc
    return validate
