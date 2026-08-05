import { render, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { setupTranslationMock } from "@test/utils";
import CalendarPage from "@/pages/CalendarPage";

setupTranslationMock();

const calendarMetrics = vi.hoisted(() => ({
  datesSetCalls: 0,
  renders: 0,
}));

const calendarAdapter = vi.hoisted(() => ({
  getPreviousPeriod: (date: Date) => date,
  getNextPeriod: (date: Date) => date,
  getPeriodRange: () => ({ start: "2026-08-05", end: "2026-08-05" }),
}));

vi.mock("@fullcalendar/react", async () => {
  const React = await import("react");

  const MockFullCalendar = React.forwardRef(
    (
      {
        datesSet,
        visibleRange,
      }: {
        datesSet: (info: { start: Date; end: Date; startStr: string }) => void;
        visibleRange: (date: Date) => { start: string; end: string };
      },
      ref,
    ) => {
      calendarMetrics.renders += 1;
      React.useImperativeHandle(ref, () => ({
        getApi: () => ({
          view: { title: "2026年8月5日", type: "timeGridDay" },
        }),
      }));
      React.useEffect(() => {
        calendarMetrics.datesSetCalls += 1;
        datesSet({
          start: new Date("2026-08-05T00:00:00.000Z"),
          end: new Date("2026-08-06T00:00:00.000Z"),
          startStr: "2026-08-05T00:00:00Z",
        });
      }, [datesSet, visibleRange]);
      return <div data-testid="full-calendar" />;
    },
  );

  return { default: MockFullCalendar };
});

vi.mock("@fullcalendar/timegrid", () => ({ default: {} }));
vi.mock("@fullcalendar/interaction", () => ({ default: {} }));
vi.mock("@fullcalendar/luxon3", () => ({ default: {} }));

vi.mock("@/contexts/PageHeaderContext", () => ({
  usePageHeader: () => ({ setHeader: vi.fn() }),
}));

vi.mock("@/hooks/usePersistentState", () => ({
  usePersistentState: () => ({ state: "day", setState: vi.fn() }),
}));

vi.mock("@/hooks/useCalendarAdapter", () => ({
  useCalendarAdapter: () => ({
    adapter: calendarAdapter,
    calendarSystem: "gregorian",
    firstDayOfWeek: 1,
    loading: false,
  }),
}));

vi.mock("@/hooks/useSystemTimezone", () => ({
  useSystemTimezone: () => ({ timezone: "UTC", loading: false }),
}));

vi.mock("@/hooks/queries/useVisions", () => ({
  useVisions: () => ({ visions: [] }),
}));

vi.mock("@/hooks/queries/useTasks", () => ({
  useAllTasks: () => ({ data: [] }),
}));

vi.mock("@/features/calendar/controller/useCalendarScheduleController", () => ({
  useCalendarScheduleController: () => ({
    scheduleEntries: [],
    loading: false,
    error: null,
    showPlannedEventModal: false,
    plannedEventModalProps: {},
    handleDateSelect: vi.fn(),
    handlePlannedEventClick: vi.fn(),
  }),
}));

vi.mock("@/layouts/PageLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/layouts/Container", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ToolbarContainer", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/PeriodNavigation", () => ({
  default: () => <div />,
}));

vi.mock("@/components/forms", () => ({
  SegmentedControl: () => <div />,
}));

vi.mock("@/components/ActionButton", () => ({
  default: () => <button type="button" />,
}));

describe("CalendarPage", () => {
  it("does not retrigger FullCalendar date profiles after datesSet state sync", async () => {
    calendarMetrics.datesSetCalls = 0;
    calendarMetrics.renders = 0;

    render(<CalendarPage />);

    await waitFor(() => expect(calendarMetrics.renders).toBeGreaterThan(1));
    expect(calendarMetrics.datesSetCalls).toBe(1);
  });
});
