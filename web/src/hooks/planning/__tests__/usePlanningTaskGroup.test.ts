import { describe, expect, it } from "vitest";
import type { CalendarAdapter } from "@/utils/calendar";
import {
  buildHabitActionRange,
  isTopLevelPlanningGroup,
} from "@/hooks/planning/usePlanningTaskGroup";

const calendarAdapter = {
  getPeriodRange: () => ({
    start: "2026-07-06",
    end: "2026-07-12",
  }),
} as unknown as CalendarAdapter;

describe("planning habit action helpers", () => {
  it("builds habit action range from the period and current reference date", () => {
    const range = buildHabitActionRange(
      "week",
      new Date("2026-07-06T00:00:00"),
      calendarAdapter,
      new Date("2026-07-10T00:00:00"),
    );

    expect(range).toEqual({
      startDate: "2026-07-06",
      endDate: "2026-07-12",
      referenceDate: "2026-07-10",
      cadenceFrequency: "weekly",
    });
  });

  it("only treats current-cycle groups as habit action display groups", () => {
    expect(isTopLevelPlanningGroup("week-2026-6-6", "week")).toBe(true);
    expect(isTopLevelPlanningGroup("day-2026-6-6-0", "week")).toBe(false);
    expect(isTopLevelPlanningGroup("mayan-month-2026-0", "month")).toBe(true);
    expect(isTopLevelPlanningGroup("mayan-week-2026-0", "month")).toBe(false);
    expect(
      isTopLevelPlanningGroup("mayan-seven-year-2025-07-26", "7years"),
    ).toBe(true);
  });
});
