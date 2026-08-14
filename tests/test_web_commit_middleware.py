"""Tests for the commit-before-response Web API middleware."""

from __future__ import annotations

import asyncio
import types
from typing import cast

from fastapi import Request
from starlette.datastructures import State
from starlette.responses import JSONResponse

from lifeos_web.app import commit_session_middleware


class FakeSession:
    """Stand-in for an AsyncSession that records commits."""

    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeCallNext:
    """Callable that returns a canned response and records invocation."""

    def __init__(self, response: JSONResponse) -> None:
        self.response = response
        self.invoked = False

    async def __call__(self, request: object) -> JSONResponse:
        self.invoked = True
        return self.response


def _request_with_session(session: FakeSession | None) -> Request:
    state = State({"lifeos_session": session} if session is not None else {})
    return cast(Request, types.SimpleNamespace(state=state))


def test_commit_runs_for_successful_response() -> None:
    session = FakeSession()
    response = JSONResponse({"ok": True}, status_code=200)
    call_next = FakeCallNext(response)

    result = asyncio.run(commit_session_middleware(_request_with_session(session), call_next))

    assert call_next.invoked is True
    assert result is response
    assert session.commits == 1


def test_commit_skipped_for_error_response() -> None:
    session = FakeSession()
    response = JSONResponse({"detail": "boom"}, status_code=500)

    result = asyncio.run(
        commit_session_middleware(_request_with_session(session), FakeCallNext(response))
    )

    assert result is response
    assert session.commits == 0


def test_commit_skipped_when_no_session_registered() -> None:
    response = JSONResponse({"ok": True}, status_code=200)

    result = asyncio.run(
        commit_session_middleware(_request_with_session(None), FakeCallNext(response))
    )

    assert result is response


def test_middleware_is_async_callable() -> None:
    assert asyncio.iscoroutinefunction(commit_session_middleware)
