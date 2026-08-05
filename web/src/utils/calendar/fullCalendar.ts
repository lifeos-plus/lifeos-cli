import type { CalendarAdapter } from "./CalendarAdapter";
import type { CalendarSystem } from "./createCalendarAdapter";
import { parseLocalDateString } from "./CalendarAdapter";
import { formatDateKey } from "@/utils/datetime";

export function getFullCalendarFirstDay(
  calendarSystem: CalendarSystem,
  adapter: CalendarAdapter,
  referenceDate: Date,
  firstDayOfWeek: number,
): number {
  if (calendarSystem === "mayan_13_moon") {
    return adapter.getYearStart(referenceDate).getDay();
  }

  return firstDayOfWeek === 7 ? 0 : firstDayOfWeek;
}

export function getFullCalendarVisibleRange(
  adapter: CalendarAdapter,
  viewType: "week" | "day",
  referenceDate: Date,
): { start: string; end: string } {
  const range = adapter.getPeriodRange(viewType, referenceDate);
  const endExclusive = parseLocalDateString(range.end);
  endExclusive.setDate(endExclusive.getDate() + 1);
  return { start: range.start, end: formatDateKey(endExclusive) };
}
