import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { type ReactNode } from "react";

import { renderWithProviders, setupTranslationMock } from "@test/utils";
import type {
  Timelog,
  TimelogAdvancedSearchMetadata,
} from "@/services/api/timelogs";
import { SelectorSpecialValue } from "@/components/selects/selectorTypes";

setupTranslationMock();

vi.mock("@/layouts/PageLayout", () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/TimeLogToolbar", () => ({
  __esModule: true,
  default: ({
    onQueryModeChange,
    onExportDaily,
  }: {
    onQueryModeChange: (mode: "single" | "advanced" | "import") => void;
    onExportDaily: () => void;
  }) => (
    <div>
      <button type="button" onClick={() => onQueryModeChange("advanced")}>
        switch-advanced
      </button>
      <button type="button" onClick={() => onQueryModeChange("single")}>
        switch-single
      </button>
      <button type="button" onClick={() => onQueryModeChange("import")}>
        switch-import
      </button>
      <button type="button" onClick={onExportDaily}>
        export-daily
      </button>
    </div>
  ),
}));

vi.mock("@/components/AdvancedSearchPanel", () => ({
  __esModule: true,
  default: ({
    params,
    onParamsChange,
    onSearch,
    onReset,
    onExport,
    onBatchDelete,
    selectedEntryIds,
  }: {
    params: {
      start_date: Date;
      end_date: Date;
      area_id: string | null | undefined;
      description_keyword: string | null;
      task_id: string | null | undefined;
      with_task: boolean;
    };
    onParamsChange: (params: {
      start_date: Date;
      end_date: Date;
      area_id: string | null | undefined;
      description_keyword: string | null;
      task_id: string | null | undefined;
      with_task: boolean;
    }) => void;
    onSearch: () => void;
    onReset: () => void;
    onExport: () => void;
    onBatchDelete: () => void;
    selectedEntryIds: Set<string>;
  }) => (
    <div data-testid="advanced-panel">
      <button type="button" onClick={onSearch}>
        advanced-search
      </button>
      <button type="button" onClick={onReset}>
        advanced-reset
      </button>
      <button type="button" onClick={onExport}>
        advanced-export
      </button>
      <button
        type="button"
        onClick={() =>
          onParamsChange({
            ...params,
            area_id: null,
          })
        }
      >
        advanced-set-no-area
      </button>
      <button
        type="button"
        onClick={() =>
          onParamsChange({
            ...params,
            task_id: null,
            with_task: false,
          })
        }
      >
        advanced-set-no-task
      </button>
      <button
        type="button"
        onClick={() =>
          onParamsChange({
            ...params,
            task_id: undefined,
            with_task: false,
          })
        }
      >
        advanced-set-all-tasks
      </button>
      <button
        type="button"
        onClick={() =>
          onParamsChange({
            ...params,
            task_id: undefined,
            with_task: true,
          })
        }
      >
        advanced-set-has-task
      </button>
      <button type="button" onClick={onBatchDelete}>
        advanced-batch-delete
      </button>
      <span>selected:{selectedEntryIds.size}</span>
    </div>
  ),
}));

vi.mock("@/components/TimeProgressBar", () => ({
  __esModule: true,
  default: () => <div data-testid="time-progress" />,
}));

vi.mock("@/components/TimeEntriesTable", () => ({
  __esModule: true,
  default: ({ entries }: { entries: unknown[] }) => (
    <div data-testid="entries-table">entries:{entries.length}</div>
  ),
}));

vi.mock("@/components/TimeEntryModal", () => ({
  __esModule: true,
  default: () => <div data-testid="time-entry-modal" />,
}));

vi.mock("@/components/AreaManagerModal", () => ({
  __esModule: true,
  default: () => <div data-testid="area-modal" />,
}));

vi.mock("@/components/QuickTemplatesManagerModal", () => ({
  __esModule: true,
  default: () => <div data-testid="templates-modal" />,
}));

vi.mock("@/components/ConfirmDialog", () => ({
  __esModule: true,
  default: ({
    onConfirm,
    onCancel,
  }: {
    onConfirm: () => void;
    onCancel: () => void;
  }) => (
    <div data-testid="confirm-dialog">
      <button type="button" onClick={onConfirm}>
        confirm-dialog-confirm
      </button>
      <button type="button" onClick={onCancel}>
        confirm-dialog-cancel
      </button>
    </div>
  ),
}));

vi.mock("@/components/LoadingSpinner", () => ({
  __esModule: true,
  default: ({ message }: { message?: string }) => (
    <div role="status">{message ?? "loading"}</div>
  ),
}));

vi.mock("@/components/ErrorDisplay", () => ({
  __esModule: true,
  default: ({ error }: { error: string | null }) =>
    error ? <div role="alert">error:{error}</div> : null,
}));

const setHeaderMock = vi.fn();
vi.mock("@/contexts/PageHeaderContext", () => ({
  usePageHeader: () => ({ setHeader: setHeaderMock }),
}));

const useToastMock = {
  showSuccess: vi.fn(),
  showError: vi.fn(),
  showInfo: vi.fn(),
  showWarning: vi.fn(),
};
vi.mock("@/contexts/ToastContext", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/contexts/ToastContext")>();
  return {
    ...actual,
    useToast: () => useToastMock,
  };
});

vi.mock("@/hooks/queries/useAreas", () => ({
  useAreas: () => ({ areas: [], areaMap: new Map() }),
}));

const useTimeLogUIStateMock = vi.fn();
vi.mock("@/features/timeLog/controller/useTimeLogUIState", () => ({
  useTimeLogUIState: () => useTimeLogUIStateMock(),
}));

const buildUiState = (overrides: Record<string, unknown> = {}) => ({
  sortOrder: "asc",
  setSortOrder: vi.fn(),
  selectedAreaId: "",
  setSelectedAreaId: vi.fn(),
  saveScrollPosition: vi.fn(),
  scrollPosition: 0,
  clearScrollPosition: vi.fn(),
  ...overrides,
});

const useTimeLogDataMock = vi.fn();
vi.mock("@/features/timeLog/controller/useTimeLogData", () => ({
  useTimeLogData: (props: unknown) => useTimeLogDataMock(props),
}));

const createTimelog = (
  overrides: Partial<Timelog> = {},
): Timelog => ({
  id: (overrides.id ?? "timelog-entry") as Timelog["id"],
  title: overrides.title ?? "entry",
  start_time: overrides.start_time ?? "2025-01-01T00:00:00Z",
  end_time: overrides.end_time ?? "2025-01-01T01:00:00Z",
  area_id: overrides.area_id ?? null,
  tracking_method: overrides.tracking_method ?? "manual",
  location: overrides.location ?? null,
  energy_level: overrides.energy_level ?? null,
  notes: overrides.notes ?? null,
  tags: overrides.tags ?? [],
  extra_data: overrides.extra_data ?? null,
  created_at: overrides.created_at ?? "2025-01-01T00:00:00Z",
  updated_at: overrides.updated_at ?? "2025-01-01T01:30:00Z",
  people: overrides.people ?? [],
  task: overrides.task ?? null,
});

type AdvancedSearchMock = {
  data: Timelog[];
  totalCount: number;
  currentPage: number;
  totalPages: number;
  isLoading: boolean;
  hasPreviousPage: boolean;
  hasNextPage: boolean;
  search: ReturnType<typeof vi.fn>;
  clearSearch: ReturnType<typeof vi.fn>;
  previousPage: ReturnType<typeof vi.fn>;
  nextPage: ReturnType<typeof vi.fn>;
  goToPage: ReturnType<typeof vi.fn>;
  refetch: ReturnType<typeof vi.fn>;
  metadata: TimelogAdvancedSearchMetadata | null;
};

const advancedSearchMock: AdvancedSearchMock = {
  data: [],
  totalCount: 0,
  currentPage: 1,
  totalPages: 1,
  isLoading: false,
  hasPreviousPage: false,
  hasNextPage: false,
  search: vi.fn(),
  clearSearch: vi.fn(),
  previousPage: vi.fn(),
  nextPage: vi.fn(),
  goToPage: vi.fn(),
  refetch: vi.fn(),
  metadata: null,
};
vi.mock("@/hooks/queries/useAdvancedSearch", () => ({
  useAdvancedSearchWithPagination: () => advancedSearchMock,
}));

vi.mock("@/hooks/queries/useTasks", () => ({
  useAllTasks: vi.fn(() => ({ data: [] })),
}));

vi.mock("@/utils/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/utils/core")>();
  return {
    ...actual,
    logger: {
      error: vi.fn(),
      warn: vi.fn(),
      info: vi.fn(),
      debug: vi.fn(),
    },
  };
});

import TimeLogPage from "@/pages/TimeLogPage";

const buildDataReturn = (
  overrides: Partial<ReturnType<typeof useTimeLogDataMock>> = {},
) => ({
  processedEntries: [],
  loading: false,
  error: null,
  selectedEntryIds: new Set(),
  isSelectMode: false,
  deletingEntryId: null,
  deletingEntryCount: 0,
  requestDeleteEntry: vi.fn(),
  confirmDeleteEntry: vi.fn(),
  cancelDeleteEntry: vi.fn(),
  requestBatchDelete: vi.fn(),
  confirmBatchDelete: vi.fn(),
  cancelBatchDelete: vi.fn(),
  setIsSelectMode: vi.fn(),
  setAdvancedSearchResultsFromHook: vi.fn(),
  selectionHandlers: {
    handleSelectEntry: vi.fn(),
    handleSelectAll: vi.fn(),
    handleSelectInverse: vi.fn(),
    handleClearSelection: vi.fn(),
  },
  ...overrides,
});

describe("TimeLogPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    advancedSearchMock.data = [];
    advancedSearchMock.totalCount = 0;
    advancedSearchMock.isLoading = false;
    advancedSearchMock.metadata = null;
    advancedSearchMock.clearSearch.mockClear();
    advancedSearchMock.search.mockClear();
    useTimeLogUIStateMock.mockImplementation(() => buildUiState());
    useTimeLogDataMock.mockImplementation(() => buildDataReturn());
  });

  it("shows loading spinner when data hook is loading", () => {
    useTimeLogDataMock.mockReturnValue(buildDataReturn({ loading: true }));

    renderWithProviders(<TimeLogPage />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "timeLog.messages.loadingTimeLogs",
    );
  });

  it("displays error message when hook returns error", () => {
    useTimeLogDataMock.mockReturnValue(
      buildDataReturn({ error: "boom", loading: false }),
    );

    renderWithProviders(<TimeLogPage />);

    expect(screen.getByRole("alert")).toHaveTextContent("boom");
  });

  it("renders advanced search metadata inline with truncation warning", async () => {
    const user = userEvent.setup();
    advancedSearchMock.metadata = {
      limit: 1000,
      total_count: 42,
      returned_count: 42,
      truncated: true,
    };

    renderWithProviders(<TimeLogPage />);

    await user.click(screen.getByText("switch-advanced"));

    expect(
      await screen.findByText("timeLog.messages.foundRecords"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("timeLog.messages.searchTruncatedDescription"),
    ).toBeInTheDocument();
  });

  it("filters single-day entries when no-area filter is selected", () => {
    useTimeLogUIStateMock.mockImplementation(() =>
      buildUiState({ selectedAreaId: SelectorSpecialValue.None }),
    );
    useTimeLogDataMock.mockReturnValue(
      buildDataReturn({
        processedEntries: [
          createTimelog({
            id: "entry-no-area" as Timelog["id"],
            area_id: null,
          }),
          createTimelog({
            id: "entry-with-area" as Timelog["id"],
            area_id: "area-1" as Timelog["area_id"],
          }),
        ],
      }),
    );

    renderWithProviders(<TimeLogPage />);

    expect(screen.getByTestId("entries-table")).toHaveTextContent("entries:1");
  });

  it("sends explicit null area filter in advanced search", async () => {
    const user = userEvent.setup();

    renderWithProviders(<TimeLogPage />);

    await user.click(screen.getByText("switch-advanced"));
    await user.click(screen.getByText("advanced-set-no-area"));
    await user.click(screen.getByText("advanced-search"));

    await waitFor(() => expect(advancedSearchMock.search).toHaveBeenCalled());
    expect(advancedSearchMock.search).toHaveBeenLastCalledWith(
      expect.objectContaining({
        area_id: null,
        area_name: null,
      }),
    );
  });

  it("sends explicit null task filter in advanced search", async () => {
    const user = userEvent.setup();

    renderWithProviders(<TimeLogPage />);

    await user.click(screen.getByText("switch-advanced"));
    await user.click(screen.getByText("advanced-set-no-task"));
    await user.click(screen.getByText("advanced-search"));

    await waitFor(() => expect(advancedSearchMock.search).toHaveBeenCalled());
    expect(advancedSearchMock.search).toHaveBeenLastCalledWith(
      expect.objectContaining({
        task_id: null,
      }),
    );
  });

  it("omits task filter in advanced search when all tasks are selected", async () => {
    const user = userEvent.setup();

    renderWithProviders(<TimeLogPage />);

    await user.click(screen.getByText("switch-advanced"));
    await user.click(screen.getByText("advanced-set-no-task"));
    await user.click(screen.getByText("advanced-set-all-tasks"));
    await user.click(screen.getByText("advanced-search"));

    await waitFor(() => expect(advancedSearchMock.search).toHaveBeenCalled());
    const [payload] = advancedSearchMock.search.mock.calls.at(-1) ?? [];
    expect(Object.prototype.hasOwnProperty.call(payload, "task_id")).toBe(
      false,
    );
  });

  it("sends has task filter in advanced search", async () => {
    const user = userEvent.setup();

    renderWithProviders(<TimeLogPage />);

    await user.click(screen.getByText("switch-advanced"));
    await user.click(screen.getByText("advanced-set-has-task"));
    await user.click(screen.getByText("advanced-search"));

    await waitFor(() => expect(advancedSearchMock.search).toHaveBeenCalled());
    const [payload] = advancedSearchMock.search.mock.calls.at(-1) ?? [];
    expect(Object.prototype.hasOwnProperty.call(payload, "task_id")).toBe(
      false,
    );
    expect(payload).toEqual(expect.objectContaining({ with_task: true }));
  });

  it("does not clear selection before advanced batch delete confirmation", async () => {
    const user = userEvent.setup();
    const requestBatchDelete = vi.fn();
    const handleClearSelection = vi.fn();
    const setIsSelectMode = vi.fn();

    useTimeLogDataMock.mockReturnValue(
      buildDataReturn({
        isSelectMode: true,
        selectedEntryIds: new Set(["entry-1", "entry-2"]),
        requestBatchDelete,
        setIsSelectMode,
        selectionHandlers: {
          handleSelectEntry: vi.fn(),
          handleSelectAll: vi.fn(),
          handleSelectInverse: vi.fn(),
          handleClearSelection,
        },
      }),
    );

    renderWithProviders(<TimeLogPage />);

    await user.click(screen.getByText("switch-advanced"));
    await user.click(screen.getByText("advanced-batch-delete"));

    expect(requestBatchDelete).toHaveBeenCalledTimes(1);
    expect(handleClearSelection).not.toHaveBeenCalled();
    expect(setIsSelectMode).not.toHaveBeenCalled();
  });

  it("refreshes advanced search after confirming batch delete", async () => {
    const user = userEvent.setup();
    const confirmBatchDelete = vi.fn().mockResolvedValue(undefined);

    useTimeLogDataMock.mockReturnValue(
      buildDataReturn({
        isSelectMode: true,
        selectedEntryIds: new Set(["entry-1"]),
        deletingEntryCount: 1,
        confirmBatchDelete,
      }),
    );

    renderWithProviders(<TimeLogPage />);

    await user.click(screen.getByText("switch-advanced"));
    await user.click(screen.getByText("confirm-dialog-confirm"));

    await waitFor(() => expect(confirmBatchDelete).toHaveBeenCalledTimes(1));
    expect(advancedSearchMock.search).toHaveBeenCalledTimes(1);
  });
});
