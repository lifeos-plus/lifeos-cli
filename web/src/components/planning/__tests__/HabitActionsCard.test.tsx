import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@test/utils";
import type { HabitActionWithHabit } from "@/services/api/habits";
import type { UUID } from "@/types/primitive";
import { HabitActionsCard } from "@/components/planning/HabitActionsCard";

const createAction = (
  id: string,
  linkedNotesCount: number,
): HabitActionWithHabit => ({
  id: id as UUID,
  habit_id: "habit-1" as UUID,
  action_date: "2026-07-06",
  status: "pending",
  notes: null,
  linked_notes_count: linkedNotesCount,
  habit: {
    title: `Habit ${id}`,
    description: null,
    start_date: "2026-07-01",
    duration_days: 30,
    cadence_frequency: "weekly",
  },
});

describe("HabitActionsCard", () => {
  it("always renders related note buttons and subdues empty note collections", () => {
    renderWithProviders(
      <HabitActionsCard
        habitActions={[createAction("action-empty", 0), createAction("action-linked", 2)]}
        onStatusChange={vi.fn()}
      />,
    );

    const viewButtons = screen.getAllByRole("button", {
      name: "notes.actions.viewNotes",
    });

    expect(viewButtons).toHaveLength(2);
    expect(viewButtons[0]).toBeEnabled();
    expect(viewButtons[0].className).toContain("opacity-40");
    expect(viewButtons[1]).toBeEnabled();
    expect(viewButtons[1].className).not.toContain("opacity-40");
    expect(screen.getAllByTestId("planning-habit-action-row")[0]).not.toHaveTextContent(
      "common.expand",
    );
    expect(screen.getAllByTestId("planning-habit-action-layout")[0]).toHaveClass(
      "flex-col",
      "md:flex-row",
    );
  });
});
