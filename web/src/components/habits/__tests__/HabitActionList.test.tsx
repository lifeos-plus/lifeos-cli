import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@test/utils";
import type { HabitAction } from "@/services/api/habits";
import type { UUID } from "@/types/primitive";
import { HabitActionList } from "@/components/habits/HabitActionList";
import { GregorianCalendarAdapter } from "@/utils/calendar";

const action: HabitAction = {
  id: "action-1" as UUID,
  habit_id: "habit-1" as UUID,
  action_date: "2026-07-04",
  status: "done",
  notes: "Completed after lunch",
  linked_notes_count: 1,
};
const actionWithoutNotes: HabitAction = {
  id: "action-0" as UUID,
  habit_id: "habit-1" as UUID,
  action_date: "2026-07-03",
  status: "pending",
  notes: null,
  linked_notes_count: 0,
};

describe("HabitActionList", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-06T12:00:00"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not render note details in the five day view", () => {
    const { container } = renderWithProviders(
      <HabitActionList
        actions={[actionWithoutNotes, action]}
        habitId={"habit-1" as UUID}
        habitTitle="Morning Walk"
        durationDays={5}
        startDate="2026-07-02"
        cadenceFrequency="daily"
        calendarAdapter={new GregorianCalendarAdapter()}
        centerDate={new Date("2026-07-04T00:00:00")}
        onCenterDateChange={vi.fn()}
        onStatusUpdate={vi.fn()}
      />,
    );

    expect(screen.queryByText("Completed after lunch")).not.toBeInTheDocument();
    const viewButtons = screen.getAllByRole("button", {
      name: "notes.actions.viewNotes",
    });
    expect(viewButtons).toHaveLength(2);
    expect(viewButtons[0]).toBeEnabled();
    expect(viewButtons[0].className).toContain("opacity-40");
    expect(viewButtons[1]).toBeEnabled();
    expect(viewButtons[1].className).not.toContain("opacity-40");
    expect(container.querySelector(".space-y-2 > div")).toHaveClass(
      "flex-col",
      "sm:flex-row",
      "min-w-0",
    );
  });

  it("uses habit action occurrence periods for weekly five period view", () => {
    const weeklyActions: HabitAction[] = [
      "2026-07-06",
      "2026-07-13",
      "2026-07-20",
      "2026-07-27",
      "2026-08-03",
    ].map((actionDate, index) => ({
      id: `weekly-action-${index}` as UUID,
      habit_id: "habit-1" as UUID,
      action_date: actionDate,
      status: "pending",
      notes: null,
      linked_notes_count: 0,
    }));

    renderWithProviders(
      <HabitActionList
        actions={weeklyActions}
        habitId={"habit-1" as UUID}
        habitTitle="Weekly Review"
        durationDays={60}
        startDate="2026-07-01"
        cadenceFrequency="weekly"
        calendarAdapter={new GregorianCalendarAdapter(1)}
        centerDate={new Date("2026-07-20T00:00:00")}
        onCenterDateChange={vi.fn()}
        onStatusUpdate={vi.fn()}
      />,
    );

    expect(screen.getByText(/2026-07-06 - 2026-07-12/)).toBeInTheDocument();
    expect(screen.getByText(/2026-07-13 - 2026-07-19/)).toBeInTheDocument();
    expect(screen.getByText(/2026-07-20 - 2026-07-26/)).toBeInTheDocument();
    expect(screen.getByText(/2026-07-27 - 2026-08-02/)).toBeInTheDocument();
    expect(screen.getByText(/2026-08-03 - 2026-08-09/)).toBeInTheDocument();
    expect(screen.queryByText("2026-07-18")).not.toBeInTheDocument();
    expect(screen.queryByText("2026-07-19")).not.toBeInTheDocument();
  });

  it("shows the action status when today falls within a weekly action period", () => {
    const currentWeeklyAction: HabitAction = {
      id: "weekly-current-action" as UUID,
      habit_id: "habit-1" as UUID,
      action_date: "2026-07-10",
      status: "pending",
      notes: null,
      linked_notes_count: 0,
    };

    const { container } = renderWithProviders(
      <HabitActionList
        actions={[currentWeeklyAction]}
        habitId={"habit-1" as UUID}
        habitTitle="Weekly Review"
        durationDays={30}
        startDate="2026-07-01"
        cadenceFrequency="weekly"
        calendarAdapter={new GregorianCalendarAdapter(6)}
        centerDate={new Date("2026-07-06T00:00:00")}
        onCenterDateChange={vi.fn()}
        onStatusUpdate={vi.fn()}
      />,
    );

    expect(screen.getByText(/2026-07-04 - 2026-07-10/)).toBeInTheDocument();
    expect(
      container.querySelector("#status-select-weekly-current-action"),
    ).toBeInTheDocument();
  });
});
