import { describe, expect, it } from "vitest";
import {
  formatDate,
  formatDateTime,
  formatDateKey,
  formatDuration,
  formatDurationFromTimes,
  hhmmOnDateToISO,
  isDateKey,
  localDateTimeLocalToUtcIso,
  parseDateKey,
  utcToLocalDateTimeLocal,
} from "@/utils/datetime";

describe("datetime helpers", () => {
  it("formats duration for mixed hours and minutes", () => {
    expect(formatDuration(135)).toBe("2h15m");
    expect(formatDuration(60)).toBe("1h");
    expect(formatDuration(45)).toBe("45m");
  });

  it("handles invalid or zero durations gracefully", () => {
    expect(formatDuration(NaN)).toBe("0m");
    expect(formatDuration(-5)).toBe("0m");
    expect(formatDuration(0)).toBe("0m");
  });

  it("returns placeholder when start or end time is missing", () => {
    expect(formatDurationFromTimes(null, null)).toBe("--");
    expect(formatDurationFromTimes("2024-01-01T00:00:00.000Z", null)).toBe(
      "--",
    );
  });

  it("computes duration between start and end times", () => {
    expect(
      formatDurationFromTimes(
        "2024-01-01T00:00:00.000Z",
        "2024-01-01T02:30:00.000Z",
      ),
    ).toBe("2h30m");
  });

  it("merges hh:mm input onto the provided date in the explicit timezone", () => {
    const baseDate = new Date("2024-05-15T08:30:00.000Z");
    const isoString = hhmmOnDateToISO(baseDate, "14:45", "Asia/Shanghai");

    expect(isoString).toBe("2024-05-15T06:45:00.000Z");
  });

  it("keeps UTC+8 task quick-entry times on the selected local day", () => {
    const baseDate = new Date("2026-07-02T09:00:00.000Z");

    expect(hhmmOnDateToISO(baseDate, "17:00", "Asia/Shanghai")).toBe(
      "2026-07-02T09:00:00.000Z",
    );
    expect(hhmmOnDateToISO(baseDate, "17:10", "Asia/Shanghai")).toBe(
      "2026-07-02T09:10:00.000Z",
    );
  });

  it("formats datetime strings with explicit timezone", () => {
    const value = "2024-01-01T00:00:00.000Z";
    expect(formatDateTime(value, "Asia/Shanghai")).toBe("2024-01-01 08:00");
    expect(formatDate(value, "America/Los_Angeles")).toBe("2023-12-31");
  });

  it("converts UTC string to datetime-local respecting timezone", () => {
    const value = "2024-01-01T12:00:00.000Z";
    expect(utcToLocalDateTimeLocal(value, "Asia/Shanghai")).toBe(
      "2024-01-01T20:00",
    );
  });

  it("converts datetime-local input using the explicit timezone", () => {
    expect(
      localDateTimeLocalToUtcIso("2024-01-01T08:00", "Asia/Shanghai"),
    ).toBe("2024-01-01T00:00:00.000Z");
  });

  it("uses the named timezone offset across DST boundaries", () => {
    expect(
      localDateTimeLocalToUtcIso(
        "2024-03-10T01:30",
        "America/Los_Angeles",
      ),
    ).toBe("2024-03-10T09:30:00.000Z");
    expect(
      localDateTimeLocalToUtcIso(
        "2024-03-10T03:30",
        "America/Los_Angeles",
      ),
    ).toBe("2024-03-10T10:30:00.000Z");
  });

  it("rejects local wall times skipped by a DST transition", () => {
    expect(
      localDateTimeLocalToUtcIso(
        "2024-03-10T02:30",
        "America/Los_Angeles",
      ),
    ).toBe("");
  });

  it("formats date-only strings as floating days (no UTC shift)", () => {
    // If this were parsed as UTC midnight and then rendered in LA, it would become 2023-12-31.
    expect(formatDate("2024-01-01", "America/Los_Angeles")).toBe("2024-01-01");
  });

  it("uses one strict contract for date-only parsing and formatting", () => {
    expect(isDateKey("2028-02-29")).toBe(true);
    expect(isDateKey("2026-02-29")).toBe(false);
    expect(formatDateKey(parseDateKey("2028-02-29"))).toBe("2028-02-29");
    expect(() => parseDateKey("2026-02-29")).toThrow(RangeError);
  });

  it("handles DST transitions in named time zones", () => {
    // 2024-03-10 is the spring-forward DST transition in America/Los_Angeles.
    expect(
      formatDateTime("2024-03-10T09:30:00.000Z", "America/Los_Angeles"),
    ).toBe("2024-03-10 01:30");
    expect(
      formatDateTime("2024-03-10T10:30:00.000Z", "America/Los_Angeles"),
    ).toBe("2024-03-10 03:30");
  });
});
