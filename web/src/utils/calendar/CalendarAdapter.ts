import type { TaskWithSubtasks } from "@/services/api";
import { parseDateKey } from "@/utils/datetime";

export type PlanningViewType = "7years" | "year" | "month" | "week" | "day";
export type ExtendedPlanningViewType = PlanningViewType | "sevenYear";

export const DEFAULT_SEVEN_YEAR_ANCHOR_DATE = "2025-07-26";

export const normalizePlanningViewType = (
  viewType: ExtendedPlanningViewType,
): "sevenYear" | "year" | "month" | "week" | "day" =>
  viewType === "7years" ? "sevenYear" : viewType;

const localDateOrdinal = (date: Date): number =>
  Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());

export const countInclusiveLocalDates = (
  startDate: string,
  endDate: string,
): number => {
  const start = parseDateKey(startDate);
  const end = parseDateKey(endDate);
  const startOrdinal = localDateOrdinal(start);
  const endOrdinal = localDateOrdinal(end);
  return Math.floor((endOrdinal - startOrdinal) / (24 * 60 * 60 * 1000)) + 1;
};

export const taskPlanningWindowOverlaps = (
  task: TaskWithSubtasks,
  periodStart: Date,
  periodEnd: Date,
): boolean => {
  const startValue = task.planning_cycle_start_date;
  if (!startValue) return false;

  const taskStart = parseDateKey(startValue);
  const configuredDays = task.planning_cycle_days;
  if (
    typeof configuredDays !== "number" ||
    !Number.isInteger(configuredDays) ||
    configuredDays <= 0
  ) {
    return false;
  }
  const taskStartOrdinal = localDateOrdinal(taskStart);
  const taskEndOrdinal =
    taskStartOrdinal + (configuredDays - 1) * 86_400_000;

  return (
    taskStartOrdinal <= localDateOrdinal(periodEnd) &&
    taskEndOrdinal >= localDateOrdinal(periodStart)
  );
};

export interface PlanningGroup {
  id: string;
  label: string;
  date: Date;
  tasks: TaskWithSubtasks[];
  children?: PlanningGroup[];
}

/**
 * Calendar adapter interface for different calendar systems
 * Provides a unified interface for calendar operations regardless of the underlying calendar system
 */
export interface CalendarAdapter {
  /**
   * Get the start of the year containing the given date
   */
  getYearStart(date: Date): Date;

  /**
   * Get the start of the week containing the given date
   */
  getWeekStart(date: Date): Date;

  /**
   * Get the next period start date based on cycle type
   */
  getNextPeriod(currentDate: Date, cycleType: ExtendedPlanningViewType): Date;

  /**
   * Get the previous period start date based on cycle type
   */
  getPreviousPeriod(
    currentDate: Date,
    cycleType: ExtendedPlanningViewType,
  ): Date;

  /**
   * Build planning groups for a specific view type and date
   */
  buildPlanningGroups(
    viewType: ExtendedPlanningViewType,
    date: Date,
    tasks: TaskWithSubtasks[],
    firstDayOfWeek?: number,
  ): PlanningGroup[];

  /**
   * Get the number of days in a planning cycle
   */
  getPlanningCycleDays(
    cycleType: ExtendedPlanningViewType,
    baseDate?: Date,
  ): number;

  /**
   * Check if a date is a special day (e.g., Day Out of Time for Mayan calendar)
   */
  isSpecialDay?(date: Date): boolean;

  /**
   * Get the display name for a special day
   */
  getSpecialDayName?(date: Date): string;

  /**
   * Shift week range by specified number of weeks
   */
  shiftWeekRange(
    startDate: string,
    endDate: string,
    deltaWeeks: number,
  ): { start: string; end: string };

  /**
   * Get month information for a given date
   * @param date - The date to get month info for
   * @returns Object containing month index and whether it's a valid month
   */
  getMonthInfo(date: Date): {
    monthIndex: number | null;
    isValidMonth: boolean;
    monthStart: Date | null;
  };

  /**
   * Get the start date of a specific month
   * @param yearStart - The start of the year
   * @param monthIndex - The month index (1-based)
   * @returns Date object representing the start of the specified month
   */
  getMonthStart(yearStart: Date, monthIndex: number): Date;

  /**
   * Get all available months for selection
   * @param baseDate - Optional base date to calculate month start dates
   * @param monthNames - Optional custom month names array (index 1-12)
   * @returns Array of month objects with index and display name
   */
  getMonthOptions(
    baseDate?: Date,
    monthNames?: string[],
  ): Array<{ index: number; name: string }>;

  /**
   * Get the current week range based on calendar system
   * @returns Object containing start and end dates in YYYY-MM-DD format
   */
  getCurrentWeekRange(): { start: string; end: string };

  /**
   * Get the current month range based on calendar system
   * @returns Object containing start and end dates in YYYY-MM-DD format
   */
  getCurrentMonthRange(): { start: string; end: string };

  /**
   * Shift month range by specified number of months
   * @param startDate - The start date in YYYY-MM-DD format
   * @param deltaMonths - Number of months to shift (positive or negative)
   * @returns Object containing new start and end dates in YYYY-MM-DD format
   */
  shiftMonthRange(
    startDate: string,
    deltaMonths: number,
  ): { start: string; end: string };

  /**
   * Get a period range for a given view type and base date
   * @param viewType - one of 7years/year/month/week/day/sevenYear
   * @param date - base date
   * @returns start/end in YYYY-MM-DD
   */
  getPeriodRange(
    viewType: ExtendedPlanningViewType,
    date: Date,
  ): { start: string; end: string };

  /**
   * Shift a period range forward/backward by a step
   * @param viewType - one of 7years/year/month/week/day/sevenYear
   * @param startDate - current range start (YYYY-MM-DD)
   * @param endDate - current range end (YYYY-MM-DD)
   * @param step - positive for next, negative for previous
   * @returns new start/end in YYYY-MM-DD
   */
  shiftPeriodRange(
    viewType: ExtendedPlanningViewType,
    startDate: string,
    endDate: string,
    step: number,
  ): { start: string; end: string };

  /**
   * Enumerate dates between start and end (inclusive), formatted as YYYY-MM-DD
   */
  enumerateDates(startDate: string, endDate: string): string[];

  /**
   * Get the display year for a given stored date and selected year
   * This handles the mapping between stored dates and display years for different calendar systems
   * @param storedDate - The date that's actually stored in the database
   * @param selectedYear - The year that was selected by the user (if known)
   * @returns The year that should be displayed to the user
   */
  getDisplayYear?(storedDate: string, selectedYear?: number): number;

  /**
   * Get the date to store when a user selects a specific year
   * @param year - The year the user selected
   * @returns The date that should be stored in the database
   */
  getDateForYearSelection?(year: number): Date;
}
