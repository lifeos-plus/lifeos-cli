import { act, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import React from "react";

import { renderWithProviders, setupTranslationMock } from "@test/utils";
import { SelectorSpecialValue } from "@/components/selects/selectorTypes";
import { tasksApi } from "@/services/api/tasks";
import type { UUID } from "@/types/primitive";

setupTranslationMock();

const mockAsyncSelect = vi.fn();

vi.mock("@/components/selects/AsyncEntitySelect", () => ({
  __esModule: true,
  default: React.forwardRef((props: unknown, _ref) => {
    mockAsyncSelect(props);
    return <div data-testid="task-selector" />;
  }),
}));

vi.mock("@/hooks/queries/useVisions", () => ({
  useVisions: () => ({
    visions: [{ id: "vision-1", name: "Vision 1" }],
  }),
}));

vi.mock("@/services/api/tasks", () => ({
  tasksApi: {
    getById: vi.fn(),
    searchSelectorPage: vi.fn(),
  },
}));

let TaskSelector: typeof import("@/components/selects/TaskSelector").default;

beforeAll(async () => {
  ({ default: TaskSelector } = await import(
    "@/components/selects/TaskSelector"
  ));
});

const getTaskSelector = () => {
  if (!TaskSelector) {
    throw new Error("TaskSelector was not loaded");
  }
  return TaskSelector;
};

const buildTask = (
  id: string,
  content: string,
  overrides: Record<string, unknown> = {},
) =>
  ({
    id,
    content,
    status: "todo",
    parent_task_id: null,
    vision_id: "vision-1",
    priority: 0,
    display_order: 0,
    actual_effort_self: 0,
    actual_effort_total: 0,
    notes_count: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }) as never;

const preloadedTasks = [
  buildTask("task-1", "Parent task", { display_order: 1 }),
  buildTask("task-2", "Child task", {
    parent_task_id: "task-1",
    display_order: 2,
  }),
];

describe("TaskSelector", () => {
  beforeEach(() => {
    vi.useRealTimers();
    mockAsyncSelect.mockClear();
    vi.mocked(tasksApi.getById).mockReset();
    vi.mocked(tasksApi.searchSelectorPage).mockReset();
    vi.mocked(tasksApi.searchSelectorPage).mockResolvedValue({
      items: [],
      pagination: { page: 1, size: 50, total: 0, pages: 0 },
      meta: {},
    });
  });

  it("builds special options and task options from preloaded tasks", () => {
    const handleChange = vi.fn();
    const Component = getTaskSelector();

    renderWithProviders(
      <Component
        value={null}
        onChange={handleChange}
        preloadedTasks={preloadedTasks}
        filterStatus={["todo"]}
        showSpecialOptions
        showNoTaskOption
      />,
    );

    const props = mockAsyncSelect.mock.calls.at(-1)?.[0] as Record<
      string,
      unknown
    >;
    const options = props.options as Array<{ id: string; label: string }>;

    expect(options.map((option) => option.id)).toEqual([
      SelectorSpecialValue.None,
      SelectorSpecialValue.All,
      SelectorSpecialValue.Has,
      "task-1",
      "task-2",
    ]);
    expect(props.dropdownClassName).toBe("max-h-96");
    expect(props.dropdownMinWidth).toBe(480);
    expect(props.dropdownMaxWidth).toBe(800);
  });

  it("maps selection back to task ids and special values", () => {
    const handleChange = vi.fn();
    const handleTaskSelect = vi.fn();
    const Component = getTaskSelector();

    renderWithProviders(
      <Component
        value={null}
        onChange={handleChange}
        onTaskSelect={handleTaskSelect}
        preloadedTasks={preloadedTasks}
        filterStatus={["todo"]}
        showSpecialOptions
        showNoTaskOption
      />,
    );

    const props = mockAsyncSelect.mock.calls.at(-1)?.[0] as Record<
      string,
      unknown
    >;
    const onChange = props.onChange as (value: string) => void;

    onChange("task-1");
    expect(handleChange).toHaveBeenLastCalledWith("task-1");
    expect(handleTaskSelect).toHaveBeenLastCalledWith(
      expect.objectContaining({ id: "task-1" }),
      expect.objectContaining({ id: "vision-1" }),
    );

    onChange(SelectorSpecialValue.None);
    expect(handleChange).toHaveBeenLastCalledWith(null);
    expect(handleTaskSelect).toHaveBeenLastCalledWith(null, undefined);

    onChange(SelectorSpecialValue.All);
    expect(handleChange).toHaveBeenLastCalledWith(SelectorSpecialValue.All);
    expect(handleTaskSelect).toHaveBeenLastCalledWith(null, undefined);

    onChange(SelectorSpecialValue.Has);
    expect(handleChange).toHaveBeenLastCalledWith(SelectorSpecialValue.Has);
    expect(handleTaskSelect).toHaveBeenLastCalledWith(null, undefined);
  });

  it("can map empty selection to the all special value", () => {
    const handleChange = vi.fn();
    const handleTaskSelect = vi.fn();
    const Component = getTaskSelector();

    renderWithProviders(
      <Component
        value={null}
        onChange={handleChange}
        onTaskSelect={handleTaskSelect}
        preloadedTasks={preloadedTasks}
        filterStatus={["todo"]}
        showSpecialOptions
        showNoTaskOption
        clearBehavior="all"
      />,
    );

    const props = mockAsyncSelect.mock.calls.at(-1)?.[0] as Record<
      string,
      unknown
    >;
    const onChange = props.onChange as (value: string | undefined) => void;

    onChange(undefined);
    expect(handleChange).toHaveBeenLastCalledWith(SelectorSpecialValue.All);
    expect(handleTaskSelect).toHaveBeenLastCalledWith(null, undefined);
  });

  it("does not fetch special task selector values as task ids", async () => {
    const Component = getTaskSelector();

    renderWithProviders(
      <Component
        value={SelectorSpecialValue.Has as unknown as UUID}
        onChange={vi.fn()}
        preloadedTasks={preloadedTasks}
        filterStatus={["todo"]}
        showSpecialOptions
        showNoTaskOption
      />,
    );

    await waitFor(() => expect(mockAsyncSelect).toHaveBeenCalled());
    expect(tasksApi.getById).not.toHaveBeenCalled();
  });

  it("loads additional task pages from the server on demand", async () => {
    vi.mocked(tasksApi.searchSelectorPage).mockImplementation(async (opts) => ({
      items:
        opts.page === 2
          ? [buildTask("remote-2", "Remote task 2")]
          : [buildTask("remote-1", "Remote task 1")],
      pagination: { page: opts.page ?? 1, size: 50, total: 2, pages: 2 },
      meta: {},
    }));
    const Component = getTaskSelector();

    renderWithProviders(
      <Component
        value={null}
        onChange={vi.fn()}
        deferRemoteLoad={false}
        filterStatus={["todo"]}
        showNoTaskOption={false}
      />,
    );

    await waitFor(() => {
      const props = mockAsyncSelect.mock.calls.at(-1)?.[0] as Record<
        string,
        unknown
      >;
      const options = props.options as Array<{ id: string; label: string }>;
      expect(options.map((option) => option.id)).toContain("remote-1");
      expect(props.hasMoreOptions).toBe(true);
    });

    const props = mockAsyncSelect.mock.calls.at(-1)?.[0] as Record<
      string,
      unknown
    >;
    const onLoadMore = props.onLoadMore as () => void;

    act(() => onLoadMore());

    await waitFor(() => {
      const nextProps = mockAsyncSelect.mock.calls.at(-1)?.[0] as Record<
        string,
        unknown
      >;
      const options = nextProps.options as Array<{ id: string; label: string }>;
      expect(options.map((option) => option.id)).toEqual([
        "remote-1",
        "remote-2",
      ]);
    });
  });

  it("debounces server search queries", async () => {
    vi.mocked(tasksApi.searchSelectorPage).mockImplementation(async (opts) => ({
      items:
        opts.query === "needle"
          ? [buildTask("needle-task", "Needle task")]
          : [],
      pagination: {
        page: 1,
        size: 50,
        total: opts.query === "needle" ? 1 : 0,
        pages: opts.query === "needle" ? 1 : 0,
      },
      meta: {},
    }));
    const Component = getTaskSelector();

    renderWithProviders(
      <Component
        value={null}
        onChange={vi.fn()}
        deferRemoteLoad={false}
        filterStatus={["todo"]}
        showNoTaskOption={false}
      />,
    );

    await waitFor(() =>
      expect(tasksApi.searchSelectorPage).toHaveBeenCalledWith(
        expect.objectContaining({ query: "" }),
      ),
    );

    const props = mockAsyncSelect.mock.calls.at(-1)?.[0] as Record<
      string,
      unknown
    >;
    const onSearchQueryChange = props.onSearchQueryChange as (
      query: string,
    ) => void;
    act(() => onSearchQueryChange("needle"));

    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 300));
    });

    await waitFor(() => {
      expect(tasksApi.searchSelectorPage).toHaveBeenCalledWith(
        expect.objectContaining({ query: "needle" }),
      );
      const nextProps = mockAsyncSelect.mock.calls.at(-1)?.[0] as Record<
        string,
        unknown
      >;
      const options = nextProps.options as Array<{ id: string; label: string }>;
      expect(options.map((option) => option.id)).toContain("needle-task");
    });
  });
});
