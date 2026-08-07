import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RateSnapshotsWorkspace } from "@/features/finance/RateSnapshotsWorkspace";
import type {
  FinanceAsset,
  FinanceAssetListResponse,
  FinanceRateSnapshot,
  FinanceRateSnapshotCreate,
  FinanceRateSnapshotListResponse,
} from "@/services/api/finance";
import { renderWithProviders, setupTranslationMock } from "@test/utils";

const financeApiMocks = vi.hoisted(() => ({
  listAssets: vi.fn(),
  createAsset: vi.fn(),
  listRateSnapshots: vi.fn(),
  createRateSnapshot: vi.fn(),
  updateRateSnapshot: vi.fn(),
  deleteRateSnapshot: vi.fn(),
}));

vi.mock("@/services/api/finance", () => ({
  financeApi: financeApiMocks,
}));

const assetListResponse = (items: FinanceAsset[]): FinanceAssetListResponse => ({
  items,
  pagination: { page: 1, size: 200, total: items.length, pages: 1 },
  meta: {},
});

const rateSnapshotListResponse = (
  items: FinanceRateSnapshot[],
): FinanceRateSnapshotListResponse => ({
  items,
  pagination: { page: 1, size: 50, total: items.length, pages: 1 },
  meta: {},
});

describe("RateSnapshotsWorkspace", () => {
  const sourceSnapshot: FinanceRateSnapshot = {
    id: "rate-source",
    captured_at: "2026-06-30T01:02:00.000Z",
    source: "wise",
    note: "Month-end rates",
    entries: [
      {
        id: "rate-entry-usd-cny",
        base_currency: "USD",
        quote_currency: "CNY",
        rate: "7.120000000000",
        source: "wise",
        captured_at: null,
      },
    ],
  };

  beforeEach(() => {
    setupTranslationMock();
    financeApiMocks.listAssets.mockResolvedValue(
      assetListResponse([
        {
          id: "asset-usd",
          code: "USD",
          name: "US Dollar",
          decimal_places: 2,
          is_default: true,
        },
        {
          id: "asset-cny",
          code: "CNY",
          name: "Chinese Yuan",
          decimal_places: 2,
          is_default: true,
        },
      ]),
    );
    financeApiMocks.listRateSnapshots.mockResolvedValue(
      rateSnapshotListResponse([sourceSnapshot]),
    );
    financeApiMocks.createRateSnapshot.mockImplementation(
      async (payload: FinanceRateSnapshotCreate): Promise<FinanceRateSnapshot> => ({
        ...sourceSnapshot,
        id: "rate-copy",
        captured_at: payload.captured_at ?? "2026-07-01T12:34:00.000Z",
        source: payload.source ?? "manual",
        note: payload.note ?? null,
        entries: (payload.entries ?? []).map((entry, index) => ({
          id: `rate-copy-entry-${index}`,
          base_currency: entry.base_currency,
          quote_currency: entry.quote_currency,
          rate: String(entry.rate),
          source: entry.source ?? null,
          captured_at: entry.captured_at ?? null,
        })),
      }),
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("copies an existing rate snapshot into a new saved snapshot", async () => {
    const user = userEvent.setup();

    renderWithProviders(<RateSnapshotsWorkspace />);

    const rateRow = (await screen.findByText("7.12")).closest("tr");
    expect(rateRow).toHaveClass("hover:bg-primary/10");
    expect(rateRow).toHaveClass("focus-within:bg-primary/10");

    await user.click(
      await screen.findByRole("button", { name: "common.copy" }),
    );
    await user.click(screen.getByRole("button", { name: "common.save" }));

    await waitFor(() => {
      expect(financeApiMocks.createRateSnapshot).toHaveBeenCalledTimes(1);
    });
    expect(financeApiMocks.updateRateSnapshot).not.toHaveBeenCalled();
    const payload = financeApiMocks.createRateSnapshot.mock.calls[0]?.[0];
    expect(payload).toMatchObject({
      source: "wise",
      note: "Month-end rates",
      entries: [
        {
          base_currency: "USD",
          quote_currency: "CNY",
          rate: "7.12",
          source: "wise",
        },
      ],
    });
    expect(payload.captured_at).toEqual(expect.any(String));
    expect(payload.captured_at).not.toBe(sourceSnapshot.captured_at);
  });
});
