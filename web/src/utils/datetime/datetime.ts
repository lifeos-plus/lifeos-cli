// Timezone policy: store and transmit ISO strings (UTC). Display in user-preferred timezone.

import { DateTime } from "luxon";

import { resolvePreferredTimezone, zonedDateTimeToUtc } from "./timezone";

function resolveTimezoneInput(timezone?: string): string {
  const trimmed = timezone?.trim();
  if (trimmed) return trimmed;
  return resolvePreferredTimezone();
}

const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/;

function parseInputToDateTime(
  value: string,
  timezone?: string,
): DateTime | null {
  if (!value) return null;
  const tz = resolveTimezoneInput(timezone);

  if (DATE_ONLY_RE.test(value)) {
    const dt = DateTime.fromISO(value, { zone: tz }).startOf("day");
    return dt.isValid ? dt : null;
  }

  // Prefer parsing with offset/zone info preserved.
  const dtFromIso = DateTime.fromISO(value, { setZone: true });
  if (dtFromIso.isValid) {
    return dtFromIso.setZone(tz);
  }

  const fallback = DateTime.fromJSDate(new Date(value));
  if (fallback.isValid) {
    return fallback.setZone(tz);
  }

  return null;
}

/*
 * Format a date string to Chinese locale date-time string for user display.
 */
export function formatDateTime(dateString: string, timezone?: string): string {
  if (!dateString) return "";
  const dt = parseInputToDateTime(dateString, timezone);
  if (!dt) return "";
  return dt.toFormat("yyyy-LL-dd HH:mm");
}

export function formatDate(dateString: string, timezone?: string): string {
  if (!dateString) return "";
  const dt = parseInputToDateTime(dateString, timezone);
  if (!dt) return "";
  return dt.toFormat("yyyy-LL-dd");
}

export function formatDateInTimezone(date: Date, timezone?: string): string {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
  const tz = resolveTimezoneInput(timezone);
  const dt = DateTime.fromJSDate(date).setZone(tz);
  if (!dt.isValid) return "";
  return dt.toFormat("yyyy-LL-dd");
}

export function formatTime(dateString: string, timezone?: string): string {
  if (!dateString) return "";
  const dt = parseInputToDateTime(dateString, timezone);
  if (!dt) return "";
  return dt.toFormat("HH:mm");
}

/*
 * Convert UTC ISO string to local datetime string for HTML datetime-local input.
 */
export function utcToLocalDateTimeLocal(
  utcIsoString: string,
  timezone?: string,
): string {
  if (!utcIsoString) return "";
  const dt = parseInputToDateTime(utcIsoString, timezone);
  if (!dt) return "";
  return dt.toFormat("yyyy-LL-dd'T'HH:mm");
}

/*
 * Interpret an HTML datetime-local value in the configured timezone and
 * convert it to the UTC timestamp used by the API.
 */
export function localDateTimeLocalToUtcIso(
  localDateTime: string,
  timezone?: string,
): string {
  if (!localDateTime) return "";
  const dt = DateTime.fromISO(localDateTime, {
    zone: resolveTimezoneInput(timezone),
  });
  if (!dt.isValid) return "";
  return dt.toUTC().toJSDate().toISOString();
}

export function hhmmOnDateToISO(
  baseDate: Date,
  hhmm: string,
  timezone?: string,
): string {
  const [hours, minutes] = hhmm.split(":").map((v) => parseInt(v, 10));
  const tz = resolveTimezoneInput(timezone);
  const dateOnly = formatDateInTimezone(baseDate, tz);
  if (!dateOnly) return "";
  const [yearStr, monthStr, dayStr] = dateOnly.split("-");
  const year = parseInt(yearStr, 10);
  const month = parseInt(monthStr, 10);
  const day = parseInt(dayStr, 10);
  if (
    !Number.isFinite(year) ||
    !Number.isFinite(month) ||
    !Number.isFinite(day)
  ) {
    return "";
  }
  return zonedDateTimeToUtc(
    year,
    month,
    day,
    Number.isFinite(hours) ? hours : 0,
    Number.isFinite(minutes) ? minutes : 0,
    0,
    0,
    tz,
  ).toISOString();
}

// ---- Time helpers (from timeUtils.ts)
export function getNearestFiveMinuteTime(
  date: Date = new Date(),
  timezone?: string,
): string {
  const dt = DateTime.fromJSDate(date).setZone(resolveTimezoneInput(timezone));
  if (!dt.isValid) return "";
  const minutes = dt.minute;
  const roundedMinutes = Math.round(minutes / 5) * 5;
  return dt
    .startOf("hour")
    .plus({ minutes: roundedMinutes })
    .toFormat("HH:mm");
}

export function formatDuration(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes <= 0) return "0m";
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours > 0 && mins > 0) return `${hours}h${mins}m`;
  if (hours > 0) return `${hours}h`;
  return `${mins}m`;
}

export function formatDurationFromTimes(
  startTime: string | null | undefined,
  endTime: string | null | undefined,
): string {
  if (!startTime || !endTime) return "--";
  const start = new Date(startTime);
  const end = new Date(endTime);
  const durationMs = end.getTime() - start.getTime();
  const totalMinutes = Math.round(durationMs / (1000 * 60));
  return formatDuration(totalMinutes);
}

/**
 * Add minutes to an ISO datetime string and return the resulting ISO string.
 * @param startIso - ISO string representing the starting time
 * @param minutes - Minutes to add (can be negative)
 */
export function addMinutesToIso(startIso: string, minutes: number): string {
  if (!startIso || !Number.isFinite(minutes)) return startIso;
  const base = new Date(startIso);
  if (Number.isNaN(base.getTime())) return startIso;
  const result = new Date(base.getTime() + minutes * 60 * 1000);
  return result.toISOString();
}

/**
 * Sort time entries by start time, then by end time for stable ordering
 * This provides consistent sorting for entries with the same start time
 *
 * @param entries - Array of time entries with start_time and end_time properties
 * @returns Sorted array of entries
 */
export function sortTimeEntriesByTime<
  T extends { start_time?: string | null; end_time?: string | null },
>(entries: T[]): T[] {
  return entries.sort((a, b) => {
    const aStartTime = a.start_time;
    const bStartTime = b.start_time;
    const aEndTime = a.end_time;
    const bEndTime = b.end_time;

    // If both start times are missing, sort by end time
    if (!aStartTime && !bStartTime) {
      if (!aEndTime) return 1;
      if (!bEndTime) return -1;
      return new Date(aEndTime).getTime() - new Date(bEndTime).getTime();
    }

    // If only one start time is missing, prioritize the one with start time
    if (!aStartTime) return 1;
    if (!bStartTime) return -1;

    // Compare start times
    const startTimeDiff =
      new Date(aStartTime).getTime() - new Date(bStartTime).getTime();
    if (startTimeDiff !== 0) {
      return startTimeDiff;
    }

    // Start times are equal, sort by end time
    if (!aEndTime && !bEndTime) return 0;
    if (!aEndTime) return 1;
    if (!bEndTime) return -1;
    return new Date(aEndTime).getTime() - new Date(bEndTime).getTime();
  });
}

// ---- Date Range Navigation Helpers ----

/**
 * Get the current week range with customizable first day of week
 * @param firstDayOfWeek - First day of week (1=Monday, 2=Tuesday, ..., 7=Sunday)
 * @returns Object with start and end dates in YYYY-MM-DD format
 */
export function getCurrentWeekRange(firstDayOfWeek: number = 1): {
  start: string;
  end: string;
} {
  const today = new Date();
  const day = today.getDay(); // 0=Sunday, 1=Monday, ..., 6=Saturday

  // Convert firstDayOfWeek to JavaScript day format (0=Sunday, 1=Monday, etc.)
  const jsFirstDay = firstDayOfWeek === 7 ? 0 : firstDayOfWeek;

  // Calculate days to first day of week
  const diffToFirstDay = (day - jsFirstDay + 7) % 7;

  const weekStart = new Date(today);
  weekStart.setDate(today.getDate() - diffToFirstDay);

  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekStart.getDate() + 6);

  return {
    start: formatDateKey(weekStart),
    end: formatDateKey(weekEnd),
  };
}

/**
 * Get the current month range (1st to last day) in local timezone
 * @returns Object with start and end dates in YYYY-MM-DD format
 */
export function getCurrentMonthRangeLocal(): { start: string; end: string } {
  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth();

  // First day of current month
  const firstDay = new Date(year, month, 1);

  // Last day of current month (next month 1st - 1 day) with time set to 23:59:59
  const lastDay = new Date(year, month + 1, 0, 23, 59, 59);

  return {
    start: formatDateKey(firstDay),
    end: formatDateKey(lastDay),
  };
}

/**
 * Shift month range by specified number of months
 * @param startDate - Start date in YYYY-MM-DD format
 * @param deltaMonths - Number of months to shift (positive for future, negative for past)
 * @returns Object with new start and end dates in YYYY-MM-DD format
 */
export function shiftMonthRange(
  startDate: string,
  deltaMonths: number,
): { start: string; end: string } {
  if (!DATE_ONLY_RE.test(startDate)) {
    return { start: "", end: "" };
  }
  const [y, m] = startDate.split("-").map((v) => parseInt(v, 10));
  if (!Number.isFinite(y) || !Number.isFinite(m)) {
    return { start: "", end: "" };
  }
  const currentYear = y;
  const currentMonth = m - 1;

  // Calculate target year and month
  let targetYear = currentYear;
  let targetMonth = currentMonth + deltaMonths;

  // Handle year boundaries
  while (targetMonth < 0) {
    targetMonth += 12;
    targetYear -= 1;
  }
  while (targetMonth >= 12) {
    targetMonth -= 12;
    targetYear += 1;
  }

  // Calculate complete month range for target month
  const newStart = new Date(targetYear, targetMonth, 1);
  const newEnd = new Date(targetYear, targetMonth + 1, 1);
  newEnd.setDate(newEnd.getDate() - 1);

  return {
    start: formatDateKey(newStart),
    end: formatDateKey(newEnd),
  };
}

/**
 * Create date boundaries for a specific date (00:00:00.001 to 23:59:59.999)
 * @param date - The date to create boundaries for
 * @returns Object with startOfDay and endOfDay Date objects
 */
export function createDateBoundaries(
  date: Date,
  timezone?: string,
): {
  startOfDay: Date;
  endOfDay: Date;
} {
  const tz = resolveTimezoneInput(timezone);
  const dateOnly = formatDateInTimezone(date, tz);
  const startIso = dateStringToISO(dateOnly, tz, false);
  const endIso = dateStringToISO(dateOnly, tz, true);
  return { startOfDay: new Date(startIso), endOfDay: new Date(endIso) };
}

// ---- Planning Page Date Helpers ----

/**
 * Get all days in a week with customizable first day
 * @param weekStart - The first day of the week
 * @returns Array of Date objects for each day of the week
 */
export function getDaysInWeek(weekStart: Date): Date[] {
  const days = [];
  for (let i = 0; i < 7; i++) {
    const day = new Date(weekStart);
    day.setDate(weekStart.getDate() + i);
    days.push(day);
  }
  return days;
}

/**
 * Convert date string (YYYY-MM-DD) to ISO string using timezone boundaries
 * @param dateString - Date string in YYYY-MM-DD format
 * @param timezone - User's preferred timezone
 * @param isEndDate - Whether this is an end date (should be 23:59:59)
 * @returns ISO string for the start or end of the day in the given timezone
 */
export function dateStringToISO(
  dateString: string,
  timezone?: string,
  isEndDate: boolean = false,
): string {
  const tz = resolveTimezoneInput(timezone);
  if (!isDateKey(dateString)) {
    return "";
  }
  const [yearStr, monthStr, dayStr] = dateString.split("-");
  const year = parseInt(yearStr, 10);
  const month = parseInt(monthStr, 10);
  const day = parseInt(dayStr, 10);
  if (
    !Number.isFinite(year) ||
    !Number.isFinite(month) ||
    !Number.isFinite(day)
  ) {
    return "";
  }

  if (isEndDate) {
    // For end date, we want 23:59:59.999 in the user's timezone
    return zonedDateTimeToUtc(
      year,
      month,
      day,
      23,
      59,
      59,
      999,
      tz,
    ).toISOString();
  } else {
    // For start date, we want 00:00:00.000 in the user's timezone
    return zonedDateTimeToUtc(year, month, day, 0, 0, 0, 0, tz).toISOString();
  }
}

// ---- Calendar Arithmetic Helpers (local Date-based) ----

export function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

export function addMonths(date: Date, months: number): Date {
  const d = new Date(date);
  const day = d.getDate();
  d.setDate(1);
  d.setMonth(d.getMonth() + months);
  // Clamp to end of month if the original day doesn't exist in target month
  const lastDay = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  d.setDate(Math.min(day, lastDay));
  return d;
}

export function subMonths(date: Date, months: number): Date {
  return addMonths(date, -months);
}

export function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

export function endOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

export function startOfWeek(date: Date, weekStartsOn: number = 0): Date {
  const d = new Date(date);
  const day = d.getDay(); // 0..6 (Sun..Sat)
  const diff = (day - weekStartsOn + 7) % 7;
  d.setDate(d.getDate() - diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

export function endOfWeek(date: Date, weekStartsOn: number = 0): Date {
  return addDays(startOfWeek(date, weekStartsOn), 6);
}

export function eachDayOfInterval(interval: {
  start: Date;
  end: Date;
}): Date[] {
  const days: Date[] = [];
  const cursor = new Date(interval.start);
  cursor.setHours(0, 0, 0, 0);
  const end = new Date(interval.end);
  end.setHours(0, 0, 0, 0);

  while (cursor <= end) {
    days.push(new Date(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function getTodayDateString(): string {
  // Keep date-only defaults aligned with how HTML date inputs behave (floating local day).
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function parseDateOnlyToLocalDate(dateString: string): Date | null {
  if (!DATE_ONLY_RE.test(dateString)) return null;
  const [yearStr, monthStr, dayStr] = dateString.split("-");
  const year = parseInt(yearStr, 10);
  const month = parseInt(monthStr, 10);
  const day = parseInt(dayStr, 10);
  if (
    !Number.isFinite(year) ||
    !Number.isFinite(month) ||
    !Number.isFinite(day)
  ) {
    return null;
  }
  const parsed = new Date(year, month - 1, day);
  if (
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) {
    return null;
  }
  return parsed;
}

export function isDateKey(value: unknown): value is string {
  return typeof value === "string" && parseDateOnlyToLocalDate(value) !== null;
}

export function parseDateKey(value: string): Date {
  const parsed = parseDateOnlyToLocalDate(value);
  if (!parsed) {
    throw new RangeError(`Invalid date-only value: ${value}`);
  }
  return parsed;
}

export function parseDateStringToLocalDate(value: string): Date {
  const parsedDateOnly = parseDateOnlyToLocalDate(value);
  if (parsedDateOnly) return parsedDateOnly;
  return new Date(value);
}

export function startOfLocalDay(date: Date): Date {
  if (!(date instanceof Date) || Number.isNaN(date.getTime()))
    return new Date(NaN);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function formatDateKey(date: Date): string {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function formatMonthKey(date: Date): string {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}
