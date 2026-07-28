import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  useInsightsViewState,
  type InsightViewConfig,
} from "@/features/insights/useInsightsViewState";
import { MayanCalendarAdapter } from "@/utils/calendar";

const VIEW_CONFIG: InsightViewConfig = {
  year: { defaultGranularity: "month", options: ["month", "week"] },
  month: { defaultGranularity: "week", options: ["week", "day"] },
  week: { defaultGranularity: "day", options: ["day"] },
  sevenYear: { defaultGranularity: "year", options: ["year", "month"] },
};

describe("useInsightsViewState", () => {
  beforeEach(() => {
    vi.stubEnv("TZ", "America/Toronto");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("keeps Mayan period start dates on the intended local day", async () => {
    const calendarAdapter = new MayanCalendarAdapter();
    vi.spyOn(calendarAdapter, "getPeriodRange").mockReturnValue({
      start: "2026-07-26",
      end: "2026-08-01",
    });

    const { result } = renderHook(() =>
      useInsightsViewState({
        calendarAdapter,
        calendarLoading: false,
        viewConfig: VIEW_CONFIG,
      }),
    );

    await waitFor(() => expect(result.current.ready).toBe(true));

    expect(result.current.startDate).toBe("2026-07-26");
    expect(result.current.endDate).toBe("2026-08-01");
    expect([
      result.current.selectedDate.getFullYear(),
      result.current.selectedDate.getMonth(),
      result.current.selectedDate.getDate(),
    ]).toEqual([2026, 6, 26]);
  });
});
