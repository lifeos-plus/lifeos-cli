"""Shared helpers for Web API routers."""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable

from fastapi import HTTPException

from lifeos_web.schemas import ListResponse, Pagination


async def soft_delete(
    delete_func: Callable[..., Awaitable[object]],
    **kwargs: object,
) -> None:
    """Run a soft-delete service call and map ``LookupError`` to HTTP 404."""
    try:
        await delete_func(**kwargs)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def page_envelope(
    *,
    items: list[dict[str, object]],
    page: int,
    size: int,
    total: int,
    meta: dict[str, object] | None = None,
) -> ListResponse:
    """Wrap items into the standard paginated list response."""
    pages = math.ceil(total / size) if size > 0 else 0
    return ListResponse(
        items=items,
        pagination=Pagination(page=page, size=size, total=total, pages=pages),
        meta=meta or {},
    )
