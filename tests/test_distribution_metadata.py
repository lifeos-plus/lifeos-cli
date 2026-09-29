from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _declared_dependencies() -> list[str]:
    document = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    return list(document["project"]["dependencies"])


def test_sqlalchemy_requirement_declares_the_asyncio_extra() -> None:
    """SQLAlchemy 2.1 keeps ``greenlet`` behind ``[asyncio]``, which the CLI needs."""
    sqlalchemy_requirements = [
        requirement
        for requirement in _declared_dependencies()
        if requirement.startswith("sqlalchemy")
    ]

    assert sqlalchemy_requirements, "the project must declare a SQLAlchemy requirement"
    assert all(
        requirement.startswith("sqlalchemy[asyncio]") for requirement in sqlalchemy_requirements
    )
