"""Shared classification of recoverable database lock contention."""

import sqlite3

from sqlalchemy.exc import OperationalError


def is_lock_contention_error(exc: OperationalError) -> bool:
    """Prefer driver error codes; never classify using SQL text or parameters."""
    original = exc.orig
    code = getattr(original, "sqlite_errorcode", None)
    if isinstance(code, int):
        return code & 0xFF in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    if sqlstate is not None:
        return sqlstate in {"40001", "40P01", "55P03"}
    return any(
        marker in str(original).lower()
        for marker in (
            "database is locked",
            "database schema is locked",
            "database table is locked",
            "lock timeout",
            "deadlock detected",
            "could not serialize access",
            "could not obtain lock",
        )
    )
