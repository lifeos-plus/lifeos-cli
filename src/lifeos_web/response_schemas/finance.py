"""Finance response contracts."""

from lifeos_web.response_schemas.common import JsonObject, ResponseModel


class FinanceAssetResponse(ResponseModel):
    id: str
    code: str
    name: str | None
    decimal_places: int
    is_default: bool


class FinanceNodeResponse(ResponseModel):
    id: str
    parent_id: str | None
    name: str
    currency_code: str | None
    path: str
    depth: int
    display_order: int


class FinanceTreeResponse(ResponseModel):
    id: str
    name: str
    primary_currency: str
    display_order: int
    is_default: bool
    nodes: list[FinanceNodeResponse] | None = None


class FinanceRateEntryResponse(ResponseModel):
    id: str
    base_currency: str
    quote_currency: str
    rate: str
    source: str | None
    captured_at: str | None


class FinanceRateSnapshotResponse(ResponseModel):
    id: str
    captured_at: str
    source: str
    note: str | None
    entries: list[FinanceRateEntryResponse] | None = None


class FinanceSnapshotEntryResponse(ResponseModel):
    id: str
    node_id: str
    node_name: str | None
    amount: str
    currency_code: str
    amount_converted: str
    note: str | None
    is_auto_generated: bool


class FinanceSnapshotResponse(ResponseModel):
    id: str
    tree_id: str
    tree_name: str | None
    title: str | None
    snapshot_ts: str | None
    period_start: str | None
    period_end: str | None
    primary_currency: str
    rate_snapshot_id: str | None
    created_at: str
    exchange_rates: JsonObject | None = None
    summary: JsonObject | None = None
    note: str | None = None
    entries: list[FinanceSnapshotEntryResponse] | None = None


class FinanceTreeSnapshotMeta(ResponseModel):
    tree_id: str
