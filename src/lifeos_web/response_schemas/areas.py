"""Area response contracts."""

from lifeos_web.response_schemas.common import ResponseModel


class AreaResponse(ResponseModel):
    id: str
    name: str
    description: str | None
    color: str
    icon: str | None
    is_active: bool
    display_order: int


class AreaListMeta(ResponseModel):
    include_inactive: bool
