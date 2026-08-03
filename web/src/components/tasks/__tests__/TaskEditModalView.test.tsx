import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TaskEditModalView } from "@/components/tasks/TaskEditModalView";
import type { TaskCreate, TaskWithSubtasks } from "@/services/api";
import type { UseTaskEditorHandlers } from "@/hooks/tasks/useTaskEditor";
import { setupTranslationMock } from "@test/utils";

setupTranslationMock({
  translator: (key) => {
    if (key.startsWith("months.")) {
      return `Month ${key.split(".")[1]}`;
    }
    return key;
  },
});

vi.mock("@/hooks/useCalendarAdapter", async () => {
  const { MayanCalendarAdapter } = await import(
    "@/utils/calendar/MayanCalendarAdapter"
  );
  return {
    usePlanningCycle: () => ({
      adapter: new MayanCalendarAdapter(),
    }),
  };
});

vi.mock("@/layouts/ModalBase", () => ({
  __esModule: true,
  default: ({
    isOpen,
    header,
    children,
    footer,
  }: {
    isOpen: boolean;
    header?: React.ReactNode;
    children?: React.ReactNode;
    footer?: React.ReactNode;
  }) =>
    isOpen ? (
      <div>
        <h2>{header}</h2>
        {children}
        {footer}
      </div>
    ) : null,
}));

vi.mock("@/components/selects/EnumSelect", () => ({
  __esModule: true,
  default: ({
    value,
    onChange,
    options,
    id,
    idPrefix,
    label,
    showLabel = true,
    disabled,
  }: {
    value?: string | number | null;
    onChange: (value: string) => void;
    options: Array<{ value: string; label: string; disabled?: boolean }>;
    id?: string;
    idPrefix?: string;
    label?: string;
    showLabel?: boolean;
    disabled?: boolean;
  }) => {
    const selectId = id ?? idPrefix ?? "enum-select";
    return (
      <div>
        {label && showLabel ? <label htmlFor={selectId}>{label}</label> : null}
        <select
          id={selectId}
          value={value == null ? "" : String(value)}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
        >
          {options.map((option) => (
            <option
              key={option.value}
              value={option.value}
              disabled={option.disabled}
            >
              {option.label}
            </option>
          ))}
        </select>
      </div>
    );
  },
}));

vi.mock("@/components/selects/VisionSelector", () => ({
  __esModule: true,
  default: () => <div data-testid="vision-selector" />,
}));

vi.mock("@/components/selects/TaskSelector", () => ({
  __esModule: true,
  default: () => <div data-testid="task-selector" />,
}));

vi.mock("@/components/selects/PersonSelector", () => ({
  __esModule: true,
  default: () => <div data-testid="person-selector" />,
}));

const baseFormData: TaskCreate = {
  vision_id: null,
  content: "Plan the month",
  priority: 0,
  display_order: 0,
  parent_task_id: null,
  person_ids: [],
  planning_cycle_type: "month",
  planning_cycle_days: 28,
  planning_cycle_start_date: "2026-06-27",
};

const buildHandlers = (
  overrides: Partial<UseTaskEditorHandlers> = {},
): UseTaskEditorHandlers => ({
  handleVisionChange: vi.fn(),
  handleParentTaskChange: vi.fn(),
  handleContentChange: vi.fn(),
  handlePriorityChange: vi.fn(),
  handlePersonChange: vi.fn(),
  handlePlanningTypeChange: vi.fn(),
  handlePlanningStartDateChange: vi.fn(),
  handlePlanningNoPreset: vi.fn(),
  handlePlanningToday: vi.fn(),
  handlePlanningTomorrow: vi.fn(),
  handlePlanningThisWeek: vi.fn(),
  handlePlanningThisMonth: vi.fn(),
  handleSubmit: vi.fn(async (event) => event.preventDefault()),
  handleClose: vi.fn(),
  handleErrorDismiss: vi.fn(),
  ...overrides,
});

describe("TaskEditModalView", () => {
  it("routes edit-mode deletion through the existing close and confirmation flow", () => {
    const handleClose = vi.fn();
    const onRequestDelete = vi.fn();
    const task = {
      id: "11111111-1111-1111-1111-111111111111",
      content: "Plan the month",
    } as TaskWithSubtasks;

    render(
      <TaskEditModalView
        isOpen
        loading={false}
        error={null}
        modalTitle="Edit task"
        canChangeVision
        formData={baseFormData}
        handlers={buildHandlers({ handleClose })}
        filteredTasksForParent={[]}
        excludedParentTaskIds={[]}
        taskStatusFilter={[]}
        visionStatusFilter={[]}
        focusTrigger={0}
        task={task}
        allTasks={[]}
        visionId={null}
        onRequestDelete={onRequestDelete}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "common.delete" }));

    expect(handleClose).toHaveBeenCalledTimes(1);
    expect(onRequestDelete).toHaveBeenCalledWith(task);
    expect(
      screen.queryByRole("button", { name: "common.cancel" }),
    ).not.toBeInTheDocument();
  });

  it("keeps the Mayan moon when changing the monthly planning year", () => {
    const handlePlanningStartDateChange = vi.fn();
    render(
      <TaskEditModalView
        isOpen
        loading={false}
        error={null}
        modalTitle="Edit task"
        canChangeVision
        formData={baseFormData}
        handlers={buildHandlers({ handlePlanningStartDateChange })}
        filteredTasksForParent={[]}
        excludedParentTaskIds={[]}
        taskStatusFilter={[]}
        visionStatusFilter={[]}
        focusTrigger={0}
        allTasks={[]}
        visionId={null}
      />,
    );

    fireEvent.change(screen.getByLabelText("taskForm.planning.startLabels.year"), {
      target: { value: "2025" },
    });

    expect(handlePlanningStartDateChange).toHaveBeenLastCalledWith(
      "2026-06-27",
    );

    fireEvent.change(screen.getByLabelText("taskForm.planning.startLabels.year"), {
      target: { value: "2026" },
    });

    expect(handlePlanningStartDateChange).toHaveBeenLastCalledWith(
      "2027-06-27",
    );
  });
});
