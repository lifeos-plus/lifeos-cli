"""Cross-backend SQL expression helpers."""

from __future__ import annotations

from sqlalchemy import Date, Integer
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression


class AddDaysToDate(expression.FunctionElement):
    """Add one integer day offset to one date expression."""

    type = Date()
    inherit_cache = True


@compiles(AddDaysToDate)
def _compile_add_days_default(element, compiler, **kwargs) -> str:
    start_sql, offset_sql = (
        compiler.process(clause, **kwargs) for clause in element.clauses.clauses
    )
    return f"({start_sql} + {offset_sql})"


@compiles(AddDaysToDate, "sqlite")
def _compile_add_days_sqlite(element, compiler, **kwargs) -> str:
    start_sql, offset_sql = (
        compiler.process(clause, **kwargs) for clause in element.clauses.clauses
    )
    return f"date({start_sql}, printf('%+d days', {offset_sql}))"


class SecondsBetween(expression.FunctionElement):
    """Return the whole-second distance between two datetime expressions.

    The value is rounded to the nearest whole second so callers can compare
    against exact integer bounds instead of relying on float tolerance.
    """

    type = Integer()
    inherit_cache = True


@compiles(SecondsBetween)
def _compile_seconds_between_default(element, compiler, **kwargs) -> str:
    start_sql, end_sql = (compiler.process(clause, **kwargs) for clause in element.clauses.clauses)
    return f"CAST(ROUND(EXTRACT(EPOCH FROM ({end_sql} - {start_sql}))) AS INTEGER)"


@compiles(SecondsBetween, "sqlite")
def _compile_seconds_between_sqlite(element, compiler, **kwargs) -> str:
    start_sql, end_sql = (compiler.process(clause, **kwargs) for clause in element.clauses.clauses)
    return f"CAST(ROUND((julianday({end_sql}) - julianday({start_sql})) * 86400) AS INTEGER)"
