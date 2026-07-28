import { describe, expect, it } from "vitest";

import { MayanCalendarAdapter } from "@/utils/calendar";

describe("MayanCalendarAdapter", () => {
  const adapter = new MayanCalendarAdapter();

  it("uses July 26 as the year start and July 25 as Day Out of Time", () => {
    expect(adapter.getPeriodRange("year", new Date(2026, 6, 26))).toEqual({
      start: "2026-07-26",
      end: "2027-07-25",
    });
    expect(adapter.getPeriodRange("year", new Date(2026, 6, 25))).toEqual({
      start: "2025-07-26",
      end: "2026-07-25",
    });
    expect(adapter.getPeriodRange("7years", new Date(2026, 6, 26))).toEqual({
      start: "2025-07-26",
      end: "2032-07-25",
    });
    expect(adapter.getPeriodRange("month", new Date(2027, 6, 25))).toEqual({
      start: "2027-07-25",
      end: "2027-07-25",
    });
  });

  it("builds 28-day moon and fixed seven-day week ranges", () => {
    expect(adapter.getPeriodRange("month", new Date(2026, 6, 26))).toEqual({
      start: "2026-07-26",
      end: "2026-08-22",
    });
    expect(adapter.getPeriodRange("week", new Date(2026, 7, 2))).toEqual({
      start: "2026-08-02",
      end: "2026-08-08",
    });
  });

  it("navigates week boundaries through Day Out of Time", () => {
    expect(
      adapter.shiftPeriodRange(
        "week",
        "2026-07-26",
        "2026-08-01",
        -1,
      ),
    ).toEqual({
      start: "2026-07-25",
      end: "2026-07-25",
    });
    expect(
      adapter.shiftPeriodRange(
        "week",
        "2026-07-25",
        "2026-07-25",
        -1,
      ),
    ).toEqual({
      start: "2026-07-18",
      end: "2026-07-24",
    });
    expect(
      adapter.shiftPeriodRange(
        "week",
        "2026-07-18",
        "2026-07-24",
        2,
      ),
    ).toEqual({
      start: "2026-07-26",
      end: "2026-08-01",
    });
  });

  it("navigates month boundaries through Day Out of Time", () => {
    expect(
      adapter.shiftPeriodRange(
        "month",
        "2026-06-27",
        "2026-07-24",
        1,
      ),
    ).toEqual({
      start: "2026-07-25",
      end: "2026-07-25",
    });
    expect(
      adapter.shiftPeriodRange(
        "month",
        "2026-07-25",
        "2026-07-25",
        1,
      ),
    ).toEqual({
      start: "2026-07-26",
      end: "2026-08-22",
    });
  });

  it("uses calendar boundaries for planning period navigation", () => {
    expect(adapter.getPreviousPeriod(new Date(2026, 6, 26), "week")).toEqual(
      new Date(2026, 6, 25),
    );
    expect(adapter.getNextPeriod(new Date(2026, 6, 25), "week")).toEqual(
      new Date(2026, 6, 26),
    );
    expect(adapter.getNextPeriod(new Date(2026, 6, 24), "month")).toEqual(
      new Date(2026, 6, 25),
    );
  });

  it("enumerates thirteen moon options for a Mayan year", () => {
    const options = adapter.getMonthOptions(new Date(2026, 6, 26));

    expect(options).toHaveLength(13);
    expect(options[0]).toEqual({
      index: 1,
      name: "1 2026-07-26",
    });
    expect(options[12]).toEqual({
      index: 13,
      name: "13 2027-06-27",
    });
  });

  it("anchors 7-year ranges to the Mayan year containing the configured date", () => {
    const anchoredAdapter = new MayanCalendarAdapter(1, "2026-07-20");

    expect(anchoredAdapter.getPeriodRange("7years", new Date(2026, 6, 26))).toEqual({
      start: "2025-07-26",
      end: "2032-07-25",
    });
    expect(anchoredAdapter.getPeriodRange("7years", new Date(2025, 6, 25))).toEqual({
      start: "2018-07-26",
      end: "2025-07-25",
    });
  });
});
