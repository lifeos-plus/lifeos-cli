import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PeriodNavigation from "@/components/PeriodNavigation";
import { renderWithProviders, setupTranslationMock } from "@test/utils";

setupTranslationMock({
  translator: (key: string, options) => {
    const dictionary: Record<string, string> = {
      "planning.periodNavigation.current": "Current",
      "planning.periodNavigation.goToCurrent": "Go to current",
      "planning.periodNavigation.previous": "Previous",
      "planning.periodNavigation.next": "Next",
      "planning.periodNavigation.periodTypes.day": "Day",
      "planning.periodNavigation.periodTypes.week": "Week",
      "planning.periodNavigation.pickDateButton": "Pick Date",
      "planning.periodNavigation.pickDateLabel": "Select date",
      "planning.periodNavigation.pickDatePlaceholder": "YYYY-MM-DD",
      "common.confirm": "Confirm",
      "common.cancel": "Cancel",
    };
    if (typeof options === "object" && options?.defaultValue) {
      return String(options.defaultValue);
    }
    return dictionary[key] ?? key;
  },
});

const actionButtonSpy = vi.fn();

vi.mock("@/components/ActionButton", () => ({
  __esModule: true,
  default: (props: unknown) => {
    actionButtonSpy(props);
    const { label, onClick, disabled, type, ariaLabel } = props as {
      label: string;
      onClick: () => void;
      disabled?: boolean;
      type?: "button" | "submit" | "reset";
      ariaLabel?: string;
    };
    return (
      <button
        type={type ?? "button"}
        disabled={disabled}
        onClick={onClick}
        aria-label={ariaLabel}
      >
        {label}
      </button>
    );
  },
}));

const calendarAdapterMock = {
  getWeekStart: vi.fn((date: Date) => {
    const cloned = new Date(date);
    cloned.setDate(cloned.getDate() - cloned.getDay() + 1);
    return cloned;
  }),
  getMonthInfo: vi.fn((date: Date) => ({
    isValidMonth: true,
    monthStart: new Date(
      Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1),
    ),
    monthIndex: date.getUTCMonth() + 1,
  })),
  getPeriodRange: vi.fn((viewType: string, date: Date) => {
    const year = date.getUTCFullYear();
    const month = date.getUTCMonth(); // 0-based

    if (viewType === "month") {
      const start = new Date(Date.UTC(year, month, 1));
      const end = new Date(Date.UTC(year, month + 1, 0));
      const pad2 = (value: number) => String(value).padStart(2, "0");
      const toIsoDate = (d: Date) =>
        `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())}`;
      return { start: toIsoDate(start), end: toIsoDate(end) };
    }

    return { start: `${year}-01-01`, end: `${year}-12-31` };
  }),
};

vi.mock("@/utils/calendar", () => ({
  DEFAULT_SEVEN_YEAR_ANCHOR_DATE: "2025-07-26",
  isLocalDateString: (value: unknown) =>
    typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value),
  parseLocalDateString: (value: string) => new Date(`${value}T00:00:00`),
  createCalendarAdapter: vi.fn(() => calendarAdapterMock),
}));

vi.mock("@/hooks/queries/usePreferenceWithBootstrap", () => ({
  usePreferenceWithBootstrap: vi.fn((opts: { defaultValue: unknown }) => ({
    value: opts.defaultValue,
  })),
}));

describe("PeriodNavigation", () => {
  beforeEach(() => {
    vi.useRealTimers();
    actionButtonSpy.mockClear();
    Object.values(calendarAdapterMock).forEach((fn) => fn.mockClear?.());
  });

  it("renders current day label with indicator", () => {
    vi.useFakeTimers();
    const now = new Date("2025-01-01T00:00:00Z");
    vi.setSystemTime(now);

    renderWithProviders(
      <PeriodNavigation
        periodType="day"
        selectedDate={now}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        onCurrent={vi.fn()}
      />,
    );

    const buttons = actionButtonSpy.mock.calls.map(
      (call) => call[0] as { label: string },
    );
    const centerButton = buttons[1];
    expect(centerButton.label).toMatch(/Current/);
  });

  it("renders day labels in the provided timezone", () => {
    const selectedDate = new Date("2026-04-13T16:00:00.000Z");

    renderWithProviders(
      <PeriodNavigation
        periodType="day"
        selectedDate={selectedDate}
        timezone="Asia/Shanghai"
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        onCurrent={vi.fn()}
      />,
    );

    const buttons = actionButtonSpy.mock.calls.map(
      (call) => call[0] as { label: string },
    );
    const centerButton = buttons[1];
    expect(centerButton.label).toBe("2026-04-14");
  });

  it("selects date input values at the start of the provided timezone day", async () => {
    const user = userEvent.setup();
    const onSelectDate = vi.fn();

    renderWithProviders(
      <PeriodNavigation
        periodType="day"
        selectedDate={new Date("2026-04-13T16:00:00.000Z")}
        timezone="Asia/Shanghai"
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        onCurrent={vi.fn()}
        onSelectDate={onSelectDate}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Pick Date" }));
    const input = screen.getByDisplayValue("2026-04-14");
    expect(input).toHaveValue("2026-04-14");

    await user.clear(input);
    await user.type(input, "2026-04-15");
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(onSelectDate).toHaveBeenCalledWith(
      new Date("2026-04-14T16:00:00.000Z"),
    );
  });

  it("uses adapter range for month label when provided", async () => {
    const date = new Date("2025-02-10T00:00:00Z");

    renderWithProviders(
      <PeriodNavigation
        periodType="month"
        selectedDate={date}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        onCurrent={vi.fn()}
      />,
    );

    await waitFor(() =>
      expect(actionButtonSpy.mock.calls[1]?.[0]).toBeDefined(),
    );
    const centerButton = actionButtonSpy.mock.calls[1][0] as { label: string };
    expect(centerButton.label).toBe("2025-02-01-2025-02-28");
  });

  it("uses the adapter end boundary for a special one-day week", async () => {
    calendarAdapterMock.getPeriodRange.mockReturnValueOnce({
      start: "2026-07-25",
      end: "2026-07-25",
    });

    renderWithProviders(
      <PeriodNavigation
        periodType="week"
        selectedDate={new Date(2026, 6, 25)}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        onCurrent={vi.fn()}
      />,
    );

    await waitFor(() =>
      expect(actionButtonSpy.mock.calls[1]?.[0]).toBeDefined(),
    );
    const centerButton = actionButtonSpy.mock.calls[1][0] as { label: string };
    expect(centerButton.label).toBe("2026-07-25");
  });

  it("triggers navigation callbacks on button clicks", async () => {
    const user = userEvent.setup();
    const previous = vi.fn();
    const next = vi.fn();
    const current = vi.fn();

    renderWithProviders(
      <PeriodNavigation
        periodType="day"
        selectedDate={new Date("2025-03-02T00:00:00Z")}
        onPrevious={previous}
        onNext={next}
        onCurrent={current}
      />,
    );

    const buttons = screen.getAllByRole("button");
    await user.click(buttons[0]);
    await user.click(buttons[1]);
    await user.click(buttons[2]);

    expect(previous).toHaveBeenCalled();
    expect(current).toHaveBeenCalled();
    expect(next).toHaveBeenCalled();
  });
});
