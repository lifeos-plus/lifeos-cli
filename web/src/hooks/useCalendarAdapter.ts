import { useMemo } from "react";
import { usePreferenceWithBootstrap } from "./queries/usePreferenceWithBootstrap";
import {
  DEFAULT_SEVEN_YEAR_ANCHOR_DATE,
  createCalendarAdapter,
  isLocalDateString,
  parseLocalDateString,
} from "@/utils/calendar";
import type {
  CalendarAdapter,
  CalendarSystem,
  ExtendedPlanningViewType,
} from "@/utils/calendar";

interface CalendarAdapterState {
  adapter: CalendarAdapter;
  calendarSystem: CalendarSystem;
  firstDayOfWeek: number;
  sevenYearAnchorDate: string;
  loading: boolean;
}

/**
 * Hook to get calendar adapter based on user preferences
 * Provides a unified interface for calendar operations regardless of the underlying calendar system
 */
export function useCalendarAdapter(): CalendarAdapterState {
  const calendarSystemPreference = usePreferenceWithBootstrap<CalendarSystem>({
    key: "calendar.system",
    defaultValue: "gregorian",
    module: "calendar",
    validator: (value) => value === "gregorian" || value === "mayan_13_moon",
  });

  const firstDayPreference = usePreferenceWithBootstrap<number>({
    key: "calendar.first_day_of_week",
    defaultValue: 1,
    module: "calendar",
    validator: (value) => Number.isFinite(value) && value >= 1 && value <= 7,
  });
  const sevenYearAnchorPreference = usePreferenceWithBootstrap<string>({
    key: "calendar.seven_year_anchor_date",
    defaultValue: DEFAULT_SEVEN_YEAR_ANCHOR_DATE,
    module: "calendar",
    validator: isLocalDateString,
  });

  const calendarSystem: CalendarSystem =
    calendarSystemPreference.value === "mayan_13_moon"
      ? "mayan_13_moon"
      : "gregorian";
  const firstDayOfWeek = Number.isFinite(firstDayPreference.value)
    ? firstDayPreference.value
    : 1;
  const sevenYearAnchorDate = isLocalDateString(sevenYearAnchorPreference.value)
    ? sevenYearAnchorPreference.value
    : DEFAULT_SEVEN_YEAR_ANCHOR_DATE;

  const adapter = useMemo(() => {
    return createCalendarAdapter(
      calendarSystem,
      firstDayOfWeek,
      sevenYearAnchorDate,
    );
  }, [calendarSystem, firstDayOfWeek, sevenYearAnchorDate]);

  return {
    adapter,
    calendarSystem,
    firstDayOfWeek,
    sevenYearAnchorDate,
    loading:
      calendarSystemPreference.loading ||
      firstDayPreference.loading ||
      sevenYearAnchorPreference.loading,
  };
}

/**
 * Hook for planning cycle operations
 * Provides convenient methods for setting up planning cycles
 */
export function usePlanningCycle() {
  const { adapter, calendarSystem } = useCalendarAdapter();

  /**
   * Get default planning cycle settings for a given cycle type
   */
  const getDefaultCycleSettings = (
    cycleType: ExtendedPlanningViewType,
    baseDate: Date = new Date(),
  ) => {
    const range = adapter.getPeriodRange(cycleType, baseDate);
    const startDate = parseLocalDateString(range.start);
    const days = adapter.getPlanningCycleDays(cycleType, startDate);

    return {
      startDate: range.start,
      days,
    };
  };

  /**
   * Get quick set options for common planning cycles
   */
  const getQuickSetOptions = (baseDate: Date = new Date()) => {
    // Calculate tomorrow's date
    const tomorrow = new Date(baseDate);
    tomorrow.setDate(tomorrow.getDate() + 1);

    return {
      today: getDefaultCycleSettings("day", baseDate),
      tomorrow: getDefaultCycleSettings("day", tomorrow),
      thisWeek: getDefaultCycleSettings("week", baseDate),
      thisMonth: getDefaultCycleSettings("month", baseDate),
      thisYear: getDefaultCycleSettings("year", baseDate),
    };
  };

  return {
    adapter,
    calendarSystem,
    getDefaultCycleSettings,
    getQuickSetOptions,
  };
}
