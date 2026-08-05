import { describe, expect, it } from "vitest";

import { MayanCalendarAdapter } from "@/utils/calendar";
import type { TaskWithSubtasks } from "@/services/api";

const createTask = (
  overrides: Partial<TaskWithSubtasks>,
): TaskWithSubtasks => ({
  id: overrides.id ?? "task-id",
  vision_id: null,
  parent_task_id: null,
  content: overrides.content ?? "Task",
  notes_count: 0,
  status: "todo",
  priority: 1,
  display_order: 0,
  estimated_effort: null,
  planning_cycle_type: overrides.planning_cycle_type ?? "day",
  planning_cycle_days: null,
  planning_cycle_start_date:
    overrides.planning_cycle_start_date ?? "2026-07-26",
  actual_effort_self: 0,
  actual_effort_total: 0,
  created_at: "2026-07-26T00:00:00Z",
  updated_at: "2026-07-26T00:00:00Z",
  deleted_at: null,
  people: [],
  subtasks: [],
  completion_percentage: 0,
  depth: 0,
});

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

  it("keeps leap days from shifting later moon and week boundaries", () => {
    expect(adapter.getPeriodRange("month", new Date(2028, 1, 29))).toEqual({
      start: "2028-02-07",
      end: "2028-03-06",
    });
    expect(adapter.getPeriodRange("week", new Date(2028, 6, 24))).toEqual({
      start: "2028-07-18",
      end: "2028-07-24",
    });
    expect(adapter.getPeriodRange("week", new Date(2028, 6, 25))).toEqual({
      start: "2028-07-25",
      end: "2028-07-25",
    });

    const [leapWeek] = adapter.buildPlanningGroups(
      "week",
      new Date(2028, 1, 29),
      [],
    );
    expect(leapWeek.children).toHaveLength(8);
    expect(leapWeek.children?.[0]?.date).toEqual(new Date(2028, 1, 28));
    expect(leapWeek.children?.[7]?.date).toEqual(new Date(2028, 2, 6));
  });

  it("derives physical planning duration from Mayan boundaries", () => {
    expect(adapter.getPlanningCycleDays("month", new Date(2028, 1, 29))).toBe(
      29,
    );
    expect(adapter.getPlanningCycleDays("week", new Date(2028, 1, 29))).toBe(
      8,
    );
    expect(adapter.getPlanningCycleDays("week", new Date(2028, 6, 25))).toBe(
      1,
    );
    expect(adapter.getPlanningCycleDays("year", new Date(2027, 6, 26))).toBe(
      366,
    );
  });

  it("calculates Mayan days independently of daylight-saving transitions", () => {
    expect(adapter.getPeriodRange("week", new Date(2026, 3, 1))).toEqual({
      start: "2026-03-28",
      end: "2026-04-03",
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

  it("shows cycle-matched tasks on Day Out of Time", () => {
    const monthTask = createTask({
      id: "month-task",
      planning_cycle_type: "month",
      planning_cycle_days: 1,
      planning_cycle_start_date: "2026-07-25",
    });
    const weekTask = createTask({
      id: "week-task",
      planning_cycle_type: "week",
      planning_cycle_days: 1,
      planning_cycle_start_date: "2026-07-25",
    });
    const dayTask = createTask({
      id: "day-task",
      planning_cycle_type: "day",
      planning_cycle_days: 1,
      planning_cycle_start_date: "2026-07-25",
    });
    const otherYearDayTask = createTask({
      id: "other-year-day-task",
      planning_cycle_type: "day",
      planning_cycle_days: 1,
      planning_cycle_start_date: "2027-07-25",
    });
    const tasks = [monthTask, weekTask, dayTask, otherYearDayTask];

    const [monthGroup] = adapter.buildPlanningGroups(
      "month",
      new Date(2026, 6, 25),
      tasks,
    );
    const [weekGroup] = adapter.buildPlanningGroups(
      "week",
      new Date(2026, 6, 25),
      tasks,
    );
    const [dayGroup] = adapter.buildPlanningGroups(
      "day",
      new Date(2026, 6, 25),
      tasks,
    );

    expect(monthGroup.tasks.map((task) => task.id)).toEqual(["month-task"]);
    expect(weekGroup.tasks.map((task) => task.id)).toEqual(["week-task"]);
    expect(dayGroup.tasks.map((task) => task.id)).toEqual(["day-task"]);
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

  it("classifies date-only planning tasks in local Mayan periods", () => {
    const weekTask = createTask({
      id: "week-task",
      planning_cycle_type: "week",
    });
    const dayTask = createTask({
      id: "day-task",
      planning_cycle_type: "day",
    });

    const [weekGroup] = adapter.buildPlanningGroups(
      "week",
      new Date(2026, 6, 28),
      [weekTask, dayTask],
    );

    expect(weekGroup.tasks.map((task) => task.id)).toEqual(["week-task"]);
    expect(weekGroup.children?.[0]?.tasks.map((task) => task.id)).toEqual([
      "day-task",
    ]);
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
