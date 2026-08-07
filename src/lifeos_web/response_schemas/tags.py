"""Tag response contracts."""

from lifeos_web.response_schemas.common import ResponseModel


class TagSelectorResponse(ResponseModel):
    id: str
    name: str
    entity_type: str
    category: str


class TagResponse(TagSelectorResponse):
    description: str | None
    color: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class TagListMeta(ResponseModel):
    entity_type: str | None
    category: str | None
    fields: str


class TagCategoryResponse(ResponseModel):
    value: str
    label: str
    entity_type: str | None


class TagBulkUpdateResponse(ResponseModel):
    updated_count: int
    failed_ids: list[str]
    errors: list[str]
    updated_tags: list[TagResponse]


class TagUsageResponse(ResponseModel):
    tag_id: str
    tag_name: str
    entity_type: str
    category: str
    usage_by_entity_type: dict[str, int]
    total_usage: int
