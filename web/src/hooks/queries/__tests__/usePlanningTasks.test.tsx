import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { type PropsWithChildren } from "react";

import { usePlanningTasks } from "@/hooks/queries/usePlanningTasks";
import type { Task } from "@/services/api/tasks";

const tasksGetAllMock = vi.fn();

vi.mock("@/services/api/tasks", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/api/tasks")>();
  return {
    ...actual,
    tasksApi: {
      ...actual.tasksApi,
      getAll: (...args: Parameters<typeof actual.tasksApi.getAll>) =>
        tasksGetAllMock(...args),
    },
  };
});

describe("usePlanningTasks", () => {
  const createTask = (overrides: Partial<Task>): Task => ({
    id: (overrides.id ?? `task-${Math.random()}`) as Task["id"],
    vision_id: overrides.vision_id ?? null,
    parent_task_id: overrides.parent_task_id ?? null,
    content: overrides.content ?? "Task",
    status: overrides.status ?? "todo",
    priority: overrides.priority ?? 1,
    display_order: overrides.display_order ?? 0,
    estimated_effort: overrides.estimated_effort ?? null,
    planning_cycle_type: overrides.planning_cycle_type ?? null,
    planning_cycle_days: overrides.planning_cycle_days ?? null,
    planning_cycle_start_date: overrides.planning_cycle_start_date ?? null,
    actual_effort_self: overrides.actual_effort_self ?? 0,
    actual_effort_total: overrides.actual_effort_total ?? 0,
    notes_count: overrides.notes_count ?? 0,
    created_at: overrides.created_at ?? "2025-01-01T00:00:00Z",
    updated_at: overrides.updated_at ?? "2025-01-01T00:00:00Z",
    deleted_at: overrides.deleted_at ?? null,
    people: overrides.people ?? [],
  });

  let queryClient: QueryClient;
  const wrapper = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    tasksGetAllMock.mockReset();
  });

  it("builds task hierarchy and filters deleted records", async () => {
    const root = createTask({ id: "task-root" });
    const child = createTask({ id: "task-child", parent_task_id: "task-root" });
    const deleted = createTask({
      id: "task-deleted",
      deleted_at: "2025-01-01T00:00:00Z",
    });

    tasksGetAllMock.mockResolvedValue({
      items: [root, child, deleted],
      pagination: { page: 1, size: 100, total: 3, pages: 1 },
      meta: {},
    });

    const { result } = renderHook(
      () => usePlanningTasks("day", new Date("2025-01-01T00:00:00Z")),
      { wrapper },
    );

    await waitFor(() => expect(result.current.tasks.length).toBeGreaterThan(0));

    expect(result.current.tasks).toHaveLength(1);
    expect(result.current.tasks[0].id).toBe("task-root");
    expect(result.current.tasks[0].subtasks).toHaveLength(1);
    expect(result.current.tasks[0].subtasks[0].id).toBe("task-child");
  });

  it("prefetches other planning cycles using query client", async () => {
    tasksGetAllMock.mockResolvedValue({
      items: [],
      pagination: { page: 1, size: 100, total: 0, pages: 0 },
      meta: {},
    });

    const { result } = renderHook(
      () => usePlanningTasks("day", new Date("2025-01-01T00:00:00Z")),
      { wrapper },
    );

    await waitFor(() => expect(tasksGetAllMock).toHaveBeenCalled());
    tasksGetAllMock.mockClear();

    await result.current.prefetch("week", new Date("2025-02-01T00:00:00Z"));

    await waitFor(() => expect(tasksGetAllMock).toHaveBeenCalled());
    const [, , filters] = tasksGetAllMock.mock.calls[0];
    expect(filters).toMatchObject({ planning_cycle_type: "week" });
  });

  it("includes calendar context in planning queries", async () => {
    tasksGetAllMock.mockResolvedValue({
      items: [],
      pagination: { page: 1, size: 100, total: 0, pages: 0 },
      meta: {},
    });

    renderHook(
      () =>
        usePlanningTasks("month", new Date("2026-07-26T00:00:00Z"), {
          calendarSystem: "mayan_13_moon",
          firstDayOfWeek: 7,
          sevenYearAnchorDate: "2025-07-26",
        }),
      { wrapper },
    );

    await waitFor(() => expect(tasksGetAllMock).toHaveBeenCalled());
    const [, , filters] = tasksGetAllMock.mock.calls[0];
    expect(filters).toMatchObject({
      planning_cycle_type: "month",
      planning_cycle_start_date: "2026-07-26",
      calendar_system: "mayan_13_moon",
      first_day_of_week: 7,
      seven_year_anchor_date: "2025-07-26",
    });
  });

  it("uses 7years as the planning cycle query value", async () => {
    tasksGetAllMock.mockResolvedValue({
      items: [],
      pagination: { page: 1, size: 100, total: 0, pages: 0 },
      meta: {},
    });

    renderHook(
      () =>
        usePlanningTasks("7years", new Date("2025-01-01T00:00:00Z"), {
          sevenYearAnchorDate: "2025-07-26",
        }),
      { wrapper },
    );

    await waitFor(() => expect(tasksGetAllMock).toHaveBeenCalled());
    const [, , filters] = tasksGetAllMock.mock.calls[0];
    expect(filters).toMatchObject({
      planning_cycle_type: "7years",
      planning_cycle_start_date: "2025-01-01",
      seven_year_anchor_date: "2025-07-26",
    });
  });
});
