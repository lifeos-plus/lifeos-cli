"""Shared Web API response contracts."""

from __future__ import annotations

from typing import TypeAlias

from pydantic import BaseModel, ConfigDict
from typing_extensions import TypeAliasType

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue = TypeAliasType(
    "JsonValue",
    JsonScalar | list["JsonValue"] | dict[str, "JsonValue"],
)
JsonObject: TypeAlias = dict[str, JsonValue]


class ResponseModel(BaseModel):
    """Base class that rejects undocumented response fields."""

    model_config = ConfigDict(extra="forbid")


class EmptyMeta(ResponseModel):
    """Metadata contract for list responses that return an empty object."""


class PersonNameResponse(ResponseModel):
    id: str
    name: str


class TagSummaryResponse(ResponseModel):
    id: str
    name: str
    entity_type: str
    category: str
    description: str | None
    color: str | None
    created_at: str
    updated_at: str


class TagCompactResponse(ResponseModel):
    id: str
    name: str
    entity_type: str | None
    category: str | None
    description: str | None
    color: str | None


class PersonSummaryResponse(ResponseModel):
    id: str
    name: str | None = None
    display_name: str
    primary_nickname: str
    birth_date: str | None = None
    location: str | None = None
    tags: list[TagSummaryResponse]


class TaskSummaryResponse(ResponseModel):
    id: str
    vision_id: str
    parent_task_id: str | None
    content: str
    status: str


class VisionSummaryResponse(ResponseModel):
    id: str
    name: str
    status: str


class TimelogSummaryResponse(ResponseModel):
    id: str
    title: str


class HabitActionSummaryResponse(ResponseModel):
    id: str
    habit_id: str
    habit_title: str | None
    action_date: str
    status: str
