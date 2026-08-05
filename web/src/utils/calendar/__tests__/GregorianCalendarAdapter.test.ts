import { describe, expect, it, vi } from "vitest";

import { GregorianCalendarAdapter } from "@/utils/calendar";
import type { TaskWithSubtasks } from "@/services/api";

const createTask = (
  overrides: Partial<TaskWithSubtasks>,
): TaskWithSubtasks => ({
  id: overrides.id ?? "task-id",
  vision_id: null,
  parent_task_id: overrides.parent_task_id ?? null,
  content: overrides.content ?? "Task",
  notes_count: overrides.notes_count ?? 0,
  status: overrides.status ?? "todo",
  priority: 1,
  display_order: 0,
  estimated_effort: null,
  planning_cycle_type: overrides.planning_cycle_type ?? "day",
  planning_cycle_days: overrides.planning_cycle_days ?? 1,
  planning_cycle_start_date:
    overrides.planning_cycle_start_date ?? "2025-01-01",
  actual_effort_self: 0,
  actual_effort_total: 0,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
  deleted_at: null,
  people: [],
  subtasks: overrides.subtasks ?? [],
  completion_percentage: overrides.completion_percentage ?? 0,
  depth: overrides.depth ?? 0,
});

describe("GregorianCalendarAdapter", () => {
  it("returns week start based on configured first day", () => {
    const thursday = new Date("2025-01-02T12:00:00Z");

    const mondayStart = new GregorianCalendarAdapter(1).getWeekStart(thursday);
    expect(mondayStart.getDay()).toBe(1);

    const sundayStart = new GregorianCalendarAdapter(7).getWeekStart(thursday);
    expect(sundayStart.getDay()).toBe(0);
  });

  it("preserves non-Monday week starts in the current week range", () => {
    vi.useFakeTimers();
    try {
      vi.setSystemTime(new Date("2026-08-05T12:00:00"));

      expect(new GregorianCalendarAdapter(2).getCurrentWeekRange()).toEqual({
        start: "2026-08-04",
        end: "2026-08-10",
      });
    } finally {
      vi.useRealTimers();
    }
  });

  it("computes next and previous periods", () => {
    const adapter = new GregorianCalendarAdapter();
    const base = new Date("2025-01-01T12:00:00Z");

    expect(adapter.getNextPeriod(base, "year").getFullYear()).toBe(2026);
    expect(adapter.getPreviousPeriod(base, "year").getFullYear()).toBe(2024);
    expect(adapter.getNextPeriod(base, "7years").getFullYear()).toBe(2032);
    expect(adapter.getPreviousPeriod(base, "7years").getFullYear()).toBe(
      2018,
    );
    expect(adapter.getNextPeriod(base, "month").getMonth()).toBe(1);
    expect(adapter.getPreviousPeriod(base, "day").getDate()).toBe(31);
  });

  it("navigates months by their complete calendar ranges at short-month boundaries", () => {
    const adapter = new GregorianCalendarAdapter();

    expect(adapter.getNextPeriod(new Date(2025, 0, 31), "month")).toEqual(
      new Date(2025, 1, 1),
    );
    expect(adapter.getPreviousPeriod(new Date(2025, 2, 31), "month")).toEqual(
      new Date(2025, 1, 1),
    );
    expect(adapter.getNextPeriod(new Date(2024, 0, 31), "month")).toEqual(
      new Date(2024, 1, 1),
    );
  });

  it("computes 7-year ranges from the configured anchor year", () => {
    const adapter = new GregorianCalendarAdapter();

    expect(adapter.getPeriodRange("7years", new Date(2026, 4, 15))).toEqual({
      start: "2025-01-01",
      end: "2031-12-31",
    });
    expect(adapter.getPeriodRange("7years", new Date(2024, 4, 15))).toEqual({
      start: "2018-01-01",
      end: "2024-12-31",
    });
  });

  it("derives planning duration from Gregorian period boundaries", () => {
    const adapter = new GregorianCalendarAdapter();

    expect(adapter.getPlanningCycleDays("month", new Date(2024, 1, 15))).toBe(
      29,
    );
    expect(adapter.getPlanningCycleDays("month", new Date(2025, 1, 15))).toBe(
      28,
    );
    expect(adapter.getPlanningCycleDays("year", new Date(2024, 6, 1))).toBe(
      366,
    );
  });

  it("builds week groups with nested day children", () => {
    const adapter = new GregorianCalendarAdapter(1);
    const base = new Date("2025-01-08T00:00:00Z");

    const weekTask = createTask({
      id: "week-1",
      planning_cycle_type: "week",
      planning_cycle_start_date: "2025-01-06",
    });
    const mondayTask = createTask({
      id: "day-monday",
      planning_cycle_type: "day",
      planning_cycle_start_date: "2025-01-06",
    });
    const tuesdayTask = createTask({
      id: "day-tuesday",
      planning_cycle_type: "day",
      planning_cycle_start_date: "2025-01-07",
    });

    const groups = adapter.buildPlanningGroups(
      "week",
      base,
      [weekTask, mondayTask, tuesdayTask],
      1,
    );

    expect(groups).toHaveLength(1);
    const weekGroup = groups[0];
    expect(weekGroup.tasks.map((task) => task.id)).toEqual(["week-1"]);
    expect(weekGroup.children).toHaveLength(7);
    const mondayGroup = weekGroup.children?.[0];
    const tuesdayGroup = weekGroup.children?.[1];
    expect(mondayGroup?.tasks[0].id).toBe("day-monday");
    expect(tuesdayGroup?.tasks[0].id).toBe("day-tuesday");
  });

  it("builds year groups including month children", () => {
    const adapter = new GregorianCalendarAdapter();
    const base = new Date("2025-05-15T00:00:00Z");

    const yearTask = createTask({
      id: "year-1",
      planning_cycle_type: "year",
      planning_cycle_start_date: "2025-01-01",
    });
    const monthTask = createTask({
      id: "month-5",
      planning_cycle_type: "month",
      planning_cycle_start_date: "2025-05-01",
    });

    const groups = adapter.buildPlanningGroups(
      "year",
      base,
      [yearTask, monthTask],
      1,
    );

    expect(groups).toHaveLength(1);
    const yearGroup = groups[0];
    expect(yearGroup.tasks.map((task) => task.id)).toEqual(["year-1"]);
    expect(yearGroup.children).toHaveLength(12);
    const mayGroup = yearGroup.children?.[4];
    expect(mayGroup?.tasks.map((task) => task.id)).toEqual(["month-5"]);
  });

  it("includes tasks whose physical windows overlap the displayed month", () => {
    const adapter = new GregorianCalendarAdapter();
    const overlappingTask = createTask({
      id: "overlapping-month",
      planning_cycle_type: "month",
      planning_cycle_start_date: "2026-07-25",
      planning_cycle_days: 22,
    });
    const previousTask = createTask({
      id: "previous-month",
      planning_cycle_type: "month",
      planning_cycle_start_date: "2026-07-01",
      planning_cycle_days: 24,
    });

    const [august] = adapter.buildPlanningGroups(
      "month",
      new Date(2026, 7, 1),
      [overlappingTask, previousTask],
      1,
    );

    expect(august.tasks.map((task) => task.id)).toEqual([
      "overlapping-month",
    ]);
  });

  it("builds 7-year groups for 7years tasks", () => {
    const adapter = new GregorianCalendarAdapter();
    const base = new Date("2026-01-01T00:00:00Z");

    const sevenYearTask = createTask({
      id: "seven-year-1",
      planning_cycle_type: "7years",
      planning_cycle_start_date: "2026-01-01",
    });
    const nextPeriodTask = createTask({
      id: "seven-year-next",
      planning_cycle_type: "7years",
      planning_cycle_start_date: "2033-01-01",
    });

    const groups = adapter.buildPlanningGroups(
      "7years",
      base,
      [sevenYearTask, nextPeriodTask],
      1,
    );

    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("2025-2031");
    expect(groups[0].tasks.map((task) => task.id)).toEqual(["seven-year-1"]);
  });
});
