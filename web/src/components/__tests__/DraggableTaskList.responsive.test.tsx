import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DraggableTaskList from "@/components/DraggableTaskList";
import type { TaskWithSubtasks, Vision } from "@/services/api";
import type { UUID } from "@/types/primitive";
import { renderWithProviders } from "@test/utils";

const task = {
  id: "task-1" as UUID,
  vision_id: "vision-1" as UUID,
  content: "Responsive planning task",
  status: "pending",
  priority: 1,
  display_order: 0,
  actual_effort_self: 0,
  actual_effort_total: 0,
  notes_count: 0,
  timelogs_count: 0,
  created_at: "2026-08-03T00:00:00Z",
  updated_at: "2026-08-03T00:00:00Z",
  subtasks: [],
  completion_percentage: 0,
  depth: 0,
} satisfies TaskWithSubtasks;

const vision = {
  id: "vision-1" as UUID,
  name: "A vision name that may need truncation",
} as Vision;

describe("DraggableTaskList responsive layout", () => {
  it("stacks content and wraps actions before the desktop breakpoint", () => {
    renderWithProviders(
      <DraggableTaskList
        tasks={[task]}
        onEditTask={vi.fn()}
        onDeleteTask={vi.fn()}
        onStatusUpdate={vi.fn()}
        onAddSubtask={vi.fn()}
        onViewTimeRecords={vi.fn()}
        onCreateNote={vi.fn()}
        onViewNotes={vi.fn()}
        onCreateTimeRecord={vi.fn()}
        visions={[vision]}
        showVisionInfo
        isPlanningPage
      />,
    );

    expect(screen.getByTestId("draggable-task-layout")).toHaveClass(
      "flex-col",
      "lg:flex-row",
    );
    expect(screen.getByTestId("draggable-task-actions")).toHaveClass(
      "flex-wrap",
      "lg:flex-nowrap",
    );
  });
});
