import type { UUID } from "@/types/primitive";
import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { components } from "./generated/schema";

type FinanceAssetTransport = components["schemas"]["FinanceAssetResponse"];
export type FinanceAsset = Omit<FinanceAssetTransport, "name"> & {
  name?: FinanceAssetTransport["name"];
};
export type FinanceTreeNode = components["schemas"]["FinanceNodeResponse"];
export type FinanceTree = components["schemas"]["FinanceTreeResponse"];
export type FinanceSnapshot = components["schemas"]["FinanceSnapshotResponse"];
export type FinanceRateSnapshot = components["schemas"]["FinanceRateSnapshotResponse"];
export type FinanceTreeCreate = components["schemas"]["FinanceTreeCreate"];
export type FinanceTreeUpdate = components["schemas"]["FinanceTreeUpdate"];
export type FinanceNodeCreate = components["schemas"]["FinanceNodeCreate"];
export type FinanceNodeUpdate = components["schemas"]["FinanceNodeUpdate"];
export type FinanceSnapshotEntryCreate = components["schemas"]["FinanceSnapshotEntryCreate"];
export type FinanceSnapshotCreate = components["schemas"]["FinanceSnapshotCreate"];
export type FinanceSnapshotUpdate = components["schemas"]["FinanceSnapshotUpdate"];
export type FinanceRateSnapshotCreate = components["schemas"]["FinanceRateSnapshotCreate"];
export type FinanceRateSnapshotUpdate = components["schemas"]["FinanceRateSnapshotUpdate"];
export type FinanceTreeListResponse = components["schemas"]["ListResponse_FinanceTreeResponse_EmptyMeta_"];
type FinanceAssetListTransport = components["schemas"]["ListResponse_FinanceAssetResponse_EmptyMeta_"];
export type FinanceAssetListResponse = Omit<FinanceAssetListTransport, "items"> & {
  items: FinanceAsset[];
};
export type FinanceSnapshotListResponse =
  | components["schemas"]["ListResponse_FinanceSnapshotResponse_EmptyMeta_"]
  | components["schemas"]["ListResponse_FinanceSnapshotResponse_FinanceTreeSnapshotMeta_"];
export type FinanceRateSnapshotListResponse = components["schemas"]["ListResponse_FinanceRateSnapshotResponse_EmptyMeta_"];

export const financeApi = {
  listAssets: (params: { page?: number; size?: number } = {}) =>
    http.get<FinanceAssetListTransport>(ENDPOINTS.FINANCE.ASSETS, {
      page: params.page ?? 1,
      size: params.size ?? 200,
    }),
  createAsset: (payload: components["schemas"]["FinanceAssetCreate"]) =>
    http.post<FinanceAssetTransport>(ENDPOINTS.FINANCE.ASSETS, payload),
  updateAsset: (
    assetId: UUID,
    payload: components["schemas"]["FinanceAssetUpdate"],
  ) => http.patch<FinanceAssetTransport>(ENDPOINTS.FINANCE.ASSET_BY_ID(assetId), payload),
  deleteAsset: (assetId: UUID) =>
    http.delete<void>(ENDPOINTS.FINANCE.ASSET_BY_ID(assetId)),
  listTrees: (
    params: { page?: number; size?: number } = {},
  ) =>
    http.get<FinanceTreeListResponse>(ENDPOINTS.FINANCE.TREES, {
      page: params.page ?? 1,
      size: params.size ?? 100,
    }),
  createTree: (payload: FinanceTreeCreate) =>
    http.post<FinanceTree>(ENDPOINTS.FINANCE.TREES, payload),
  updateTree: (treeId: UUID, payload: FinanceTreeUpdate) =>
    http.patch<FinanceTree>(ENDPOINTS.FINANCE.TREE_BY_ID(treeId), payload),
  deleteTree: (treeId: UUID) =>
    http.delete<void>(ENDPOINTS.FINANCE.TREE_BY_ID(treeId)),
  listRateSnapshots: (params: { page?: number; size?: number } = {}) =>
    http.get<FinanceRateSnapshotListResponse>(
      ENDPOINTS.FINANCE.RATE_SNAPSHOTS,
      {
        page: params.page ?? 1,
        size: params.size ?? 50,
      },
    ),
  createRateSnapshot: (payload: FinanceRateSnapshotCreate) =>
    http.post<FinanceRateSnapshot>(
      ENDPOINTS.FINANCE.RATE_SNAPSHOTS,
      payload,
    ),
  updateRateSnapshot: (
    rateSnapshotId: UUID,
    payload: FinanceRateSnapshotUpdate,
  ) =>
    http.patch<FinanceRateSnapshot>(
      ENDPOINTS.FINANCE.RATE_SNAPSHOT_BY_ID(rateSnapshotId),
      payload,
    ),
  deleteRateSnapshot: (rateSnapshotId: UUID) =>
    http.delete<void>(ENDPOINTS.FINANCE.RATE_SNAPSHOT_BY_ID(rateSnapshotId)),
  getRateSnapshot: (rateSnapshotId: UUID) =>
    http.get<FinanceRateSnapshot>(
      ENDPOINTS.FINANCE.RATE_SNAPSHOT_BY_ID(rateSnapshotId),
    ),
  ensureDefaultTree: (primaryCurrency = "USD") =>
    http.post<FinanceTree>(
      ENDPOINTS.FINANCE.ENSURE_DEFAULT_TREE,
      undefined,
      {
        primary_currency: primaryCurrency,
      },
    ),
  getTree: (treeId: UUID) =>
    http.get<FinanceTree>(ENDPOINTS.FINANCE.TREE_BY_ID(treeId)),
  createNode: (treeId: UUID, payload: FinanceNodeCreate) =>
    http.post<FinanceTreeNode>(ENDPOINTS.FINANCE.TREE_NODES(treeId), payload),
  updateNode: (nodeId: UUID, payload: FinanceNodeUpdate) =>
    http.patch<FinanceTreeNode>(ENDPOINTS.FINANCE.NODE_BY_ID(nodeId), payload),
  deleteNode: (nodeId: UUID) =>
    http.delete<void>(ENDPOINTS.FINANCE.NODE_BY_ID(nodeId)),
  listSnapshots: (treeId: UUID, page = 1, size = 50) =>
    http.get<FinanceSnapshotListResponse>(
      ENDPOINTS.FINANCE.TREE_SNAPSHOTS(treeId),
      { page, size },
    ),
  listAllSnapshots: (page = 1, size = 200) =>
    http.get<FinanceSnapshotListResponse>(ENDPOINTS.FINANCE.SNAPSHOTS, {
      page,
      size,
    }),
  createSnapshot: (treeId: UUID, payload: FinanceSnapshotCreate) =>
    http.post<FinanceSnapshot>(
      ENDPOINTS.FINANCE.TREE_SNAPSHOTS(treeId),
      payload,
    ),
  updateSnapshot: (snapshotId: UUID, payload: FinanceSnapshotUpdate) =>
    http.patch<FinanceSnapshot>(ENDPOINTS.FINANCE.SNAPSHOT_BY_ID(snapshotId), payload),
  deleteSnapshot: (snapshotId: UUID) =>
    http.delete<void>(ENDPOINTS.FINANCE.SNAPSHOT_BY_ID(snapshotId)),
  getSnapshot: (snapshotId: UUID) =>
    http.get<FinanceSnapshot>(ENDPOINTS.FINANCE.SNAPSHOT_BY_ID(snapshotId)),
};
