"""FastAPI dependencies for the local LifeOS Web service."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.session import session_scope


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one transactional session using the configured LifeOS database.

    The session is registered on ``request.state`` (backed by ``scope["state"]``)
    so the response middleware can commit it before the HTTP response start
    event is sent, guaranteeing that a 2xx response implies durable,
    immediately readable data.
    """
    async with session_scope() as session:
        request.state.lifeos_session = session
        yield session
