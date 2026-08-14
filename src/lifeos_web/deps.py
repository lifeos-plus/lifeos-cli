"""FastAPI dependencies for the local LifeOS Web service."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.session import session_scope

LIFEOS_SESSION_STATE_KEY = "lifeos_session"


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one transactional session using the configured LifeOS database.

    The session is registered on ``request.state`` (backed by
    ``scope["state"]``) so the response middleware can finalize it before the
    HTTP response start event is sent: successful responses are committed and
    error responses rolled back, guaranteeing a 2xx response implies durable,
    immediately readable data. The session is never committed here
    (``commit_on_exit=False``); requests must go through ``create_app`` so the
    ``CommitSessionMiddleware`` is registered as the sole commit point.
    """
    async with session_scope(commit_on_exit=False) as session:
        request.state[LIFEOS_SESSION_STATE_KEY] = session
        yield session
