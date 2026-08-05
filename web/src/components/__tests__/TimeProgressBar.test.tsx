import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { ProcessedEntry } from "@/utils/datetime";
import type { Area } from "@/services/api/areas";

import { setupTranslationMock } from "@test/utils";

const getLocalDayBreakdown = vi.fn();
const formatDurationMock = vi.fn((minutes: number) => `fmt(${minutes})`);
const useAreaOrderReadOnlyMock = vi.fn(() => ({ order: [] as string[] }));

setupTranslationMock();

vi.mock("@/services/api/stats", () => ({
  statsApi: {
    getLocalDayBreakdown: (localDateISO: string) =>
      getLocalDayBreakdown(localDateISO),
  },
}));

vi.mock("@/utils/datetime", () => ({
  formatDuration: (minutes: number) => formatDurationMock(minutes),
}));

vi.mock("@/hooks/queries/useAreaOrderReadOnly", () => ({
  useAreaOrderReadOnly: () => useAreaOrderReadOnlyMock(),
}));

vi.mock("@/layouts/Card", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="card">{children}</div>
  ),
}));

let TimeProgressBar: typeof import("@/components/TimeProgressBar").default;

const buildEntry = (
  overrides: Partial<ProcessedEntry> & { id: string },
): ProcessedEntry =>
  ({
    id: overrides.id,
    title: overrides.title ?? "Entry",
    start_time: overrides.start_time ?? "2025-10-10T00:00:00.000Z",
    end_time: overrides.end_time ?? "2025-10-10T01:00:00.000Z",
    area_id: overrides.area_id ?? "area-a",
    tracking_method: overrides.tracking_method ?? "manual",
    created_at: overrides.created_at ?? "2025-10-10T00:00:00.000Z",
    updated_at: overrides.updated_at ?? "2025-10-10T00:00:00.000Z",
    isPlaceholder: overrides.isPlaceholder,
    people: overrides.people,
    validationResult: overrides.validationResult,
    notes: overrides.notes,
    tags: overrides.tags,
    extra_data: overrides.extra_data,
    location: overrides.location,
    energy_level: overrides.energy_level,
    task: overrides.task,
  }) as ProcessedEntry;

beforeAll(async () => {
  ({ default: TimeProgressBar } = await import("@/components/TimeProgressBar"));
});

beforeEach(() => {
  getLocalDayBreakdown.mockReset();
  formatDurationMock.mockReset();
  formatDurationMock.mockImplementation((minutes: number) => `fmt(${minutes})`);
  useAreaOrderReadOnlyMock.mockReset();
  useAreaOrderReadOnlyMock.mockReturnValue({ order: [] });
});

describe("TimeProgressBar", () => {
  it("renders server breakdown data when available", async () => {
    useAreaOrderReadOnlyMock.mockReturnValue({
      order: ["area-b", "area-a"],
    });
    getLocalDayBreakdown.mockResolvedValue({
      items: [
        { area_id: "area-a", minutes: 60 },
        { area_id: "area-b", minutes: 120 },
      ],
      pagination: { page: 1, size: 2, total: 2, pages: 1 },
      meta: { day: "2025-10-10", timezone: "UTC" },
    });

    const areas: Area[] = [
      {
        id: "area-a",
        name: "Deep Work",
        color: "#111",
        is_active: true,
      },
      {
        id: "area-b",
        name: "Shallow Work",
        color: "#222",
        is_active: true,
      },
    ];

    render(
      <TimeProgressBar
        entries={[]}
        areas={areas}
        localDateISO="2025-10-10"
        timezone="UTC"
      />,
    );

    expect(getLocalDayBreakdown).toHaveBeenCalledWith("2025-10-10");

    await waitFor(() => {
      expect(screen.getByText("Deep Work")).toBeInTheDocument();
      expect(screen.getByText("Shallow Work")).toBeInTheDocument();
    });

    expect(formatDurationMock).toHaveBeenCalledWith(60);
    expect(formatDurationMock).toHaveBeenCalledWith(120);
    expect(screen.getByText("(8.3%)")).toBeInTheDocument();
    expect(screen.getByText("(4.2%)")).toBeInTheDocument();
  });

  it("falls back to client entries when no server data is fetched", () => {
    const areas: Area[] = [
      {
        id: "area-a",
        name: "Focus",
        color: "#123",
        is_active: true,
      },
    ];

    const entries: ProcessedEntry[] = [
      buildEntry({
        id: "entry-1",
        start_time: "2025-10-10T08:00:00.000Z",
        end_time: "2025-10-10T09:00:00.000Z",
        area_id: "area-a",
      }),
      buildEntry({
        id: "placeholder-1",
        start_time: "2025-10-10T09:00:00.000Z",
        end_time: "2025-10-10T09:30:00.000Z",
        isPlaceholder: true,
        area_id: null,
      }),
    ];

    render(
      <TimeProgressBar
        entries={entries}
        areas={areas}
        timezone="UTC"
      />,
    );

    expect(getLocalDayBreakdown).not.toHaveBeenCalled();
    expect(screen.getByText("Focus")).toBeInTheDocument();
    expect(
      screen.getByText("timeLog.progressBar.unknownUnfilled"),
    ).toBeInTheDocument();
    expect(formatDurationMock).toHaveBeenCalledWith(60);
    expect(formatDurationMock).toHaveBeenCalledWith(30);
    expect(screen.getByText("(4.2%)")).toBeInTheDocument();
    expect(screen.getByText("(2.1%)")).toBeInTheDocument();
  });

  it("shows 100% unknown when no time data exists", async () => {
    getLocalDayBreakdown.mockResolvedValue({
      items: [],
      pagination: { page: 1, size: 0, total: 0, pages: 0 },
      meta: { day: "2025-10-10", timezone: "UTC" },
    });

    render(
      <TimeProgressBar
        entries={[]}
        areas={[]}
        localDateISO="2025-10-11"
      />,
    );

    await waitFor(() => {
      expect(getLocalDayBreakdown).toHaveBeenCalledWith("2025-10-11");
    });

    expect(
      screen.getByText("timeLog.progressBar.unknownUnfilled"),
    ).toBeInTheDocument();
    expect(formatDurationMock).toHaveBeenCalledWith(1440);
    expect(screen.getByText("(100.0%)")).toBeInTheDocument();
  });
});
