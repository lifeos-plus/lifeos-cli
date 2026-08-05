import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PlanningTaskList from "@/components/PlanningTaskList";
import type { PlanningGroup } from "@/utils/calendar";
import type { Vision } from "@/services/api";

const cardSpy = vi.fn();

vi.mock("@/components/planning/TaskGroupCard", () => ({
  TaskGroupCard: (props: unknown) => {
    cardSpy(props);
    return <div data-testid="task-card" />;
  },
}));

const hookSpy = vi.fn();

vi.mock("@/hooks/planning/usePlanningTaskGroup", () => ({
  usePlanningTaskGroup: (args: unknown) => {
    hookSpy(args);
    return {
      statusFilter: "all",
      statusFilterOptions: [],
      visionFilter: "all",
      visionFilterOptions: [],
      selectedVisionFilterName: "All",
      totalTimeSpent: 0,
      canCreateTask: true,
      canAddTask: true,
      isCreatingTask: false,
      isAddingTask: false,
      isCarryingForward: false,
      carryForwardCount: 0,
      showCreateTask: false,
      showTaskSelector: false,
      showCarryForwardConfirm: false,
      showHabitActionsCard: false,
      newTaskContent: "",
      selectedVisionId: null,
      selectedTaskId: null,
      filteredTasks: [],
      sortedTasks: [],
      habitActions: [],
      carryForwardableTasks: [],
      handlers: {},
      getExpandedTasks: vi.fn(),
      toggleTaskExpansion: vi.fn(),
      planningTaskFilterStatus: ["all"],
      periodRangeLabel: "2025-01-01",
    };
  },
}));

describe("PlanningTaskList", () => {
  it("passes hook results and props into TaskGroupCard", () => {
    const group: PlanningGroup = {
      id: "group-1",
      label: "Group",
      date: new Date("2025-01-01T00:00:00Z"),
      tasks: [],
    };
    const visions: Vision[] = [];

    render(
      <PlanningTaskList
        group={group}
        visions={visions}
        onTaskUpdate={vi.fn()}
        onTaskStatusUpdate={vi.fn()}
        planningCycleType="week"
      />,
    );

    expect(hookSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        group,
        visions,
        planningCycleType: "week",
      }),
    );
    expect(cardSpy).toHaveBeenCalledWith(
      expect.objectContaining({ group, visions, planningCycleType: "week" }),
    );
  });
});
