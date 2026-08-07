"""Preference response contracts."""

from lifeos_web.response_schemas.common import JsonValue, ResponseModel


class PreferenceMetaResponse(ResponseModel):
    default_value: JsonValue
    module: str
    allowed_values: list[JsonValue] | None = None
    description: str | None = None


class PreferenceResponse(ResponseModel):
    key: str
    value: JsonValue
    meta: PreferenceMetaResponse
