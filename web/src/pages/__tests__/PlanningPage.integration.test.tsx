import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { type ReactNode } from "react";

import { renderWithProviders, setupTranslationMock } from "@test/utils";

setupTranslationMock();

vi.mock("@/layouts/PageLayout", () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => (
    <div data-testid="page-layout">{children}</div>
  ),
}));

vi.mock("@/components/PlanningTaskList", () => ({
  __esModule: true,
  default: ({ group }: { group: { tasks?: unknown[] } }) => (
    <div data-testid="planning-task-list">
      tasks:{(group?.tasks ?? []).length}
    </div>
  ),
}));

vi.mock("@/components/ToolbarContainer", () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => (
    <div data-testid="toolbar">{children}</div>
  ),
}));

vi.mock("@/components/PeriodNavigation", () => ({
  __esModule: true,
  default: ({ periodType }: { periodType: string }) => (
    <div data-testid="period-navigation">{periodType}</div>
  ),
}));

vi.mock("@/components/EmptyState", () => ({
  __esModule: true,
  default: () => <div data-testid="empty-state" />,
}));

vi.mock("@/components/LoadingSpinner", () => ({
  __esModule: true,
  default: () => <div role="status">loading</div>,
}));

vi.mock("@/components/ErrorDisplay", () => ({
  __esModule: true,
  default: ({ error }: { error: string }) => (
    <div role="alert">error:{error}</div>
  ),
}));

const setHeaderMock = vi.fn();
vi.mock("@/contexts/PageHeaderContext", () => ({
  usePageHeader: () => ({ setHeader: setHeaderMock }),
}));

const useVisionsMock = vi.fn(() => ({ visions: [] }));
vi.mock("@/hooks/queries/useVisions", () => ({
  useVisions: () => useVisionsMock(),
}));

const usePreferenceWithBootstrapMock = vi.fn(
  (opts: { defaultValue: unknown }) => ({
    value: opts.defaultValue,
  }),
);
vi.mock("@/hooks/queries/usePreferenceWithBootstrap", () => ({
  usePreferenceWithBootstrap: (opts: never) =>
    usePreferenceWithBootstrapMock(opts),
}));

const calendarAdapter = {
  getYearStart: vi.fn(() => new Date("2025-01-01T00:00:00.000Z")),
  getMonthInfo: vi.fn(() => ({
    isValidMonth: true,
    monthStart: new Date("2025-02-01T00:00:00.000Z"),
  })),
  getWeekStart: vi.fn(() => new Date("2025-01-06T00:00:00.000Z")),
  getPreviousPeriod: vi.fn(() => new Date("2024-12-31T00:00:00.000Z")),
  getNextPeriod: vi.fn(() => new Date("2025-01-02T00:00:00.000Z")),
  getPeriodRange: vi.fn((viewType: string, date: Date) => {
    const start = date.toLocaleDateString("en-CA");
    return { start, end: start, viewType };
  }),
  buildPlanningGroups: vi.fn((_, __, tasks: unknown[]) => [
    { id: "group-1", tasks },
  ]),
};

vi.mock("@/utils/calendar", () => ({
  DEFAULT_SEVEN_YEAR_ANCHOR_DATE: "2025-07-26",
  isLocalDateString: (value: unknown) =>
    typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value),
  parseLocalDateString: (value: string) => new Date(`${value}T00:00:00`),
  createCalendarAdapter: vi.fn(() => calendarAdapter),
}));

interface UsePlanningTasksMockResult {
  tasks: Array<{ id: string }>;
  query: { isLoading: boolean; error: unknown };
  prefetch: ReturnType<typeof vi.fn>;
}

const { prefetchMock, usePlanningTasksMock } = vi.hoisted(() => {
  const prefetch = vi.fn();
  const usePlanningTasks = vi.fn<() => UsePlanningTasksMockResult>(() => ({
    tasks: [],
    query: { isLoading: true, error: null },
    prefetch,
  }));

  return {
    prefetchMock: prefetch,
    usePlanningTasksMock: usePlanningTasks,
  };
});

vi.mock("@/hooks/queries/usePlanningTasks", () => ({
  usePlanningTasks: usePlanningTasksMock,
}));

import PlanningPage from "@/pages/PlanningPage";

describe("PlanningPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    usePlanningTasksMock.mockReturnValue({
      tasks: [],
      query: { isLoading: true, error: null },
      prefetch: prefetchMock,
    } satisfies UsePlanningTasksMockResult);
    calendarAdapter.buildPlanningGroups.mockClear();
    prefetchMock.mockClear();
  });

  it("renders loading spinner while query loading", () => {
    renderWithProviders(<PlanningPage />);
    expect(screen.getByRole("status")).toHaveTextContent("loading");
  });

  it("renders error message when query fails", () => {
    usePlanningTasksMock.mockReturnValue({
      tasks: [],
      query: { isLoading: false, error: new Error("boom") },
      prefetch: prefetchMock,
    } satisfies UsePlanningTasksMockResult);

    renderWithProviders(<PlanningPage />);

    expect(screen.getByRole("alert")).toHaveTextContent("boom");
  });

  it("keeps the day planning group mounted when there are no tasks", async () => {
    usePlanningTasksMock.mockReturnValue({
      tasks: [],
      query: { isLoading: false, error: null },
      prefetch: prefetchMock,
    } satisfies UsePlanningTasksMockResult);

    renderWithProviders(<PlanningPage />);

    await waitFor(() =>
      expect(calendarAdapter.buildPlanningGroups).toHaveBeenCalledWith(
        "day",
        expect.any(Date),
        [],
        expect.anything(),
      ),
    );

    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    expect(screen.getByTestId("planning-task-list")).toHaveTextContent(
      "tasks:0",
    );
  });

  it("renders planning content and handles view changes", async () => {
    const user = userEvent.setup();

    usePlanningTasksMock.mockReturnValue({
      tasks: [{ id: "task-1" }],
      query: { isLoading: false, error: null },
      prefetch: prefetchMock,
    } satisfies UsePlanningTasksMockResult);

    renderWithProviders(<PlanningPage />);

    await waitFor(() =>
      expect(calendarAdapter.buildPlanningGroups).toHaveBeenCalled(),
    );

    expect(screen.getByTestId("planning-task-list")).toHaveTextContent(
      "tasks:1",
    );

    const weekOption = screen.getByRole("radio", { name: "target.week" });
    await user.click(weekOption);

    await waitFor(() =>
      expect(calendarAdapter.buildPlanningGroups).toHaveBeenLastCalledWith(
        "week",
        expect.any(Date),
        expect.any(Array),
        expect.anything(),
      ),
    );

    await waitFor(() => expect(prefetchMock).toHaveBeenCalled());
  });
});
