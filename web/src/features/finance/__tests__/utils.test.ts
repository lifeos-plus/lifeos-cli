import { describe, expect, it } from "vitest";

import {
  dateToEndIso,
  dateToStartIso,
  formatAmountForAsset,
  formatNumberForAsset,
  isoToDateInput,
  isoToDateTimeLocal,
  localDateTimeToIso,
  rateSnapshotLabel,
  snapshotLabel,
} from "@/features/finance/utils";
import type { FinanceRateSnapshot, FinanceSnapshot } from "@/services/api/finance";

const baseSnapshot = {
  id: "snapshot-1",
  tree_id: "tree-1",
  snapshot_ts: "2026-06-25T12:00:00.000Z",
  period_start: null,
  period_end: null,
  primary_currency: "USD",
  created_at: "2026-06-25T12:00:00.000Z",
} satisfies Partial<FinanceSnapshot>;

describe("finance snapshot labels", () => {
  it("uses a custom title when present", () => {
    expect(
      snapshotLabel({
        ...baseSnapshot,
        title: "June net worth",
      } as FinanceSnapshot),
    ).toBe("June net worth");
  });

  it("falls back to the snapshot timestamp when title is blank", () => {
    expect(
      snapshotLabel({
        ...baseSnapshot,
        title: " ",
      } as FinanceSnapshot),
    ).not.toBe(" ");
  });
});

describe("finance rate snapshot labels", () => {
  it("uses only the captured timestamp", () => {
    const label = rateSnapshotLabel({
      id: "rate-snapshot-1",
      captured_at: "2026-06-25T12:00:00.000Z",
      source: "manual",
      entries: [
        {
          id: "rate-entry-1",
          base_currency: "BTC",
          quote_currency: "USDT",
          rate: "100000",
        },
      ],
    } as FinanceRateSnapshot);

    expect(label).not.toContain("BTC/USDT");
  });
});

describe("finance asset amount formatting", () => {
  it("limits editable values to asset precision and trims trailing zeroes", () => {
    expect(
      formatAmountForAsset(
        "2.340000",
        "USDT",
        [{ id: "asset-usdt", code: "USDT", decimal_places: 6, is_default: true }],
      ),
    ).toBe("2.34");
  });

  it("rounds editable values to the selected asset precision", () => {
    expect(
      formatAmountForAsset(
        "7.129",
        "CNY",
        [{ id: "asset-cny", code: "CNY", decimal_places: 2, is_default: true }],
      ),
    ).toBe("7.13");
  });

  it("does not pad formatted display values to asset precision", () => {
    expect(
      formatNumberForAsset(
        1,
        "ETH",
        [{ id: "asset-eth", code: "ETH", decimal_places: 8, is_default: true }],
      ),
    ).toBe("1");
  });
});

describe("finance timestamp conversion", () => {
  it("interprets datetime-local values in the configured timezone", () => {
    expect(localDateTimeToIso("2026-07-01T08:30", "Asia/Shanghai")).toBe(
      "2026-07-01T00:30:00.000Z",
    );
    expect(
      isoToDateTimeLocal("2026-07-01T00:30:00.000Z", "Asia/Shanghai"),
    ).toBe("2026-07-01T08:30");
  });

  it("interprets finance period boundaries in the configured timezone", () => {
    expect(dateToStartIso("2024-03-10", "America/Los_Angeles")).toBe(
      "2024-03-10T08:00:00.000Z",
    );
    expect(dateToEndIso("2024-03-10", "America/Los_Angeles")).toBe(
      "2024-03-11T06:59:59.999Z",
    );
    expect(
      isoToDateInput("2024-03-11T06:59:59.999Z", "America/Los_Angeles"),
    ).toBe("2024-03-10");
  });
});
