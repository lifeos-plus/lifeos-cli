"""Tests for shared Web API router helpers."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from lifeos_web.router_utils import page_envelope, soft_delete


async def _raise_lookup_error() -> None:
    raise LookupError("missing resource")


async def _raise_value_error() -> None:
    raise ValueError("bad input")


async def _noop() -> None:
    return None


def test_page_envelope_builds_pagination_and_empty_meta() -> None:
    envelope = page_envelope(items=[{"id": "1"}], page=2, size=10, total=25)
    assert envelope.items == [{"id": "1"}]
    assert envelope.pagination.page == 2
    assert envelope.pagination.size == 10
    assert envelope.pagination.total == 25
    assert envelope.pagination.pages == 3
    assert envelope.meta == {}


def test_page_envelope_preserves_provided_meta() -> None:
    envelope = page_envelope(items=[], page=1, size=50, total=0, meta={"scope": "all"})
    assert envelope.meta == {"scope": "all"}
    assert envelope.pagination.pages == 0


def test_soft_delete_passes_through_success() -> None:
    assert asyncio.run(soft_delete(_noop)) is None


def test_soft_delete_maps_lookup_error_to_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(soft_delete(_raise_lookup_error))
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "missing resource"


def test_soft_delete_lets_other_errors_propagate() -> None:
    with pytest.raises(ValueError, match="bad input"):
        asyncio.run(soft_delete(_raise_value_error))
