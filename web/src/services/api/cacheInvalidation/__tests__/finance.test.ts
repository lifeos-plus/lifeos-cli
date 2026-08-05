import type { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  addFinanceRateSnapshotToListCache,
  invalidateFinanceAssets,
  invalidateFinanceSnapshot,
  invalidateFinanceSnapshots,
  removeFinanceSnapshotCache,
  removeFinanceSnapshotFromAllListCache,
  removeFinanceSnapshotFromListCache,
  removeFinanceTreeCache,
  removeFinanceTreeFromListCache,
  setFinanceRateSnapshotCache,
  setFinanceSnapshotCache,
} from "@/services/api/cacheInvalidation/finance";
import type {
  FinanceRateSnapshot,
  FinanceRateSnapshotListResponse,
  FinanceSnapshot,
  FinanceSnapshotListResponse,
  FinanceTreeListResponse,
} from "@/services/api/finance";
import { financeKeys } from "@/services/api/queryKeys";

describe("finance cache invalidation helpers", () => {
  let invalidateQueriesMock: ReturnType<typeof vi.fn>;
  let removeQueriesMock: ReturnType<typeof vi.fn>;
  let setQueryDataMock: ReturnType<typeof vi.fn>;
  let queryClient: QueryClient;

  beforeEach(() => {
    invalidateQueriesMock = vi.fn().mockResolvedValue(undefined);
    removeQueriesMock = vi.fn();
    setQueryDataMock = vi.fn();
    queryClient = {
      invalidateQueries: invalidateQueriesMock,
      removeQueries: removeQueriesMock,
      setQueryData: setQueryDataMock,
    } as unknown as QueryClient;
  });

  it("invalidates finance asset lists", () => {
    invalidateFinanceAssets(queryClient);

    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: financeKeys.assets(),
    });
  });

  it("invalidates snapshot scopes", () => {
    invalidateFinanceSnapshots(queryClient, "tree-1");
    invalidateFinanceSnapshot(queryClient, "snapshot-1");

    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: financeKeys.snapshots("tree-1"),
    });
    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: financeKeys.snapshot("snapshot-1"),
      exact: true,
    });
  });

  it("writes snapshot and rate snapshot detail caches", () => {
    const snapshot = { id: "snapshot-1" } as FinanceSnapshot;
    const rateSnapshot = { id: "rate-snapshot-1" } as FinanceRateSnapshot;

    setFinanceSnapshotCache(queryClient, snapshot);
    setFinanceRateSnapshotCache(queryClient, rateSnapshot);

    expect(setQueryDataMock).toHaveBeenCalledWith(
      financeKeys.snapshot("snapshot-1"),
      snapshot,
    );
    expect(setQueryDataMock).toHaveBeenCalledWith(
      financeKeys.rateSnapshot("rate-snapshot-1"),
      rateSnapshot,
    );
  });

  it("removes snapshot detail cache", () => {
    removeFinanceSnapshotCache(queryClient, "snapshot-1");

    expect(removeQueriesMock).toHaveBeenCalledWith({
      queryKey: financeKeys.snapshot("snapshot-1"),
      exact: true,
    });
  });

  it("removes tree detail cache", () => {
    removeFinanceTreeCache(queryClient, "tree-1");

    expect(removeQueriesMock).toHaveBeenCalledWith({
      queryKey: financeKeys.tree("tree-1"),
      exact: true,
    });
  });

  it("removes deleted trees from the cached tree list", () => {
    const existing = {
      items: [
        {
          id: "tree-1",
          name: "Tree 1",
          primary_currency: "USD",
          display_order: 0,
          is_default: true,
        },
        {
          id: "tree-2",
          name: "Tree 2",
          primary_currency: "USD",
          display_order: 1,
          is_default: false,
        },
      ],
      pagination: { page: 1, size: 50, total: 2, pages: 1 },
      meta: {},
    } as FinanceTreeListResponse;

    removeFinanceTreeFromListCache(queryClient, "tree-1");

    const [, updater] = setQueryDataMock.mock.calls[0];
    const next = updater(existing) as FinanceTreeListResponse;

    expect(setQueryDataMock).toHaveBeenCalledWith(
      financeKeys.trees(),
      expect.any(Function),
    );
    expect(next.items.map((item) => item.id)).toEqual(["tree-2"]);
    expect(next.pagination.total).toBe(1);
  });

  it("removes deleted snapshots from the cached snapshot list", () => {
    const existing = {
      items: [{ id: "snapshot-1" }, { id: "snapshot-2" }],
      pagination: { page: 1, size: 50, total: 2, pages: 1 },
      meta: { tree_id: "tree-1" },
    } as unknown as FinanceSnapshotListResponse;

    removeFinanceSnapshotFromListCache(queryClient, "tree-1", "snapshot-1");

    const [, updater] = setQueryDataMock.mock.calls[0];
    const next = updater(existing) as FinanceSnapshotListResponse;

    expect(setQueryDataMock).toHaveBeenCalledWith(
      financeKeys.snapshots("tree-1"),
      expect.any(Function),
    );
    expect(next.items.map((item) => item.id)).toEqual(["snapshot-2"]);
    expect(next.pagination.total).toBe(1);
  });

  it("removes deleted snapshots from the cached all-snapshot list", () => {
    const existing = {
      items: [{ id: "snapshot-1" }, { id: "snapshot-2" }],
      pagination: { page: 1, size: 50, total: 2, pages: 1 },
      meta: { tree_id: null },
    } as unknown as FinanceSnapshotListResponse;

    removeFinanceSnapshotFromAllListCache(queryClient, "snapshot-1");

    const [, updater] = setQueryDataMock.mock.calls[0];
    const next = updater(existing) as FinanceSnapshotListResponse;

    expect(setQueryDataMock).toHaveBeenCalledWith(
      financeKeys.allSnapshots(),
      expect.any(Function),
    );
    expect(next.items.map((item) => item.id)).toEqual(["snapshot-2"]);
    expect(next.pagination.total).toBe(1);
  });

  it("prepends new rate snapshots into the cached rate snapshot list", () => {
    const rateSnapshot = {
      id: "rate-snapshot-2",
      captured_at: "2026-06-01T13:00:00Z",
      source: "manual",
    } as FinanceRateSnapshot;
    const existing = {
      items: [
        {
          id: "rate-snapshot-1",
          captured_at: "2026-06-01T12:00:00Z",
          source: "manual",
        },
      ],
      pagination: { page: 1, size: 50, total: 1, pages: 1 },
      meta: {},
    } as FinanceRateSnapshotListResponse;

    addFinanceRateSnapshotToListCache(queryClient, rateSnapshot);

    const [, updater] = setQueryDataMock.mock.calls[0];
    const next = updater(existing) as FinanceRateSnapshotListResponse;

    expect(setQueryDataMock).toHaveBeenCalledWith(
      financeKeys.rateSnapshots(),
      expect.any(Function),
    );
    expect(next.items.map((item) => item.id)).toEqual([
      "rate-snapshot-2",
      "rate-snapshot-1",
    ]);
    expect(next.pagination.total).toBe(2);
  });
});
