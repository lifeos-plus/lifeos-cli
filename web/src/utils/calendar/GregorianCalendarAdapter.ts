import type {
  CalendarAdapter,
  ExtendedPlanningViewType,
  PlanningGroup,
} from "./CalendarAdapter";
import {
  countInclusiveLocalDates,
  DEFAULT_SEVEN_YEAR_ANCHOR_DATE,
  normalizePlanningViewType,
  taskPlanningWindowOverlaps,
} from "./CalendarAdapter";
import type { TaskWithSubtasks } from "@/services/api";
import {
  getDaysInWeek,
  getCurrentWeekRange,
  getCurrentMonthRangeLocal,
  formatDateKey,
  parseDateKey,
  shiftMonthRange,
} from "@/utils/datetime";

/**
 * Gregorian calendar adapter implementation
 * Handles all calendar operations for the standard Gregorian calendar
 */
export class GregorianCalendarAdapter implements CalendarAdapter {
  private firstDayOfWeek: number;
  private sevenYearAnchorDate: string;

  constructor(
    firstDayOfWeek: number = 1,
    sevenYearAnchorDate: string = DEFAULT_SEVEN_YEAR_ANCHOR_DATE,
  ) {
    this.firstDayOfWeek = firstDayOfWeek;
    this.sevenYearAnchorDate = sevenYearAnchorDate;
  }

  getYearStart(date: Date): Date {
    return new Date(date.getFullYear(), 0, 1);
  }

  getWeekStart(date: Date): Date {
    return this.getFirstDayOfWeek(date, this.firstDayOfWeek);
  }

  getNextPeriod(currentDate: Date, cycleType: ExtendedPlanningViewType): Date {
    return this.getAdjacentPeriodStart(currentDate, cycleType, 1);
  }

  getPreviousPeriod(
    currentDate: Date,
    cycleType: ExtendedPlanningViewType,
  ): Date {
    return this.getAdjacentPeriodStart(currentDate, cycleType, -1);
  }

  getPlanningCycleDays(
    cycleType: ExtendedPlanningViewType,
    baseDate: Date = new Date(),
  ): number {
    const range = this.getPeriodRange(cycleType, baseDate);
    return countInclusiveLocalDates(range.start, range.end);
  }

  private getAdjacentPeriodStart(
    currentDate: Date,
    cycleType: ExtendedPlanningViewType,
    step: 1 | -1,
  ): Date {
    const normalizedCycleType = normalizePlanningViewType(cycleType);
    if (normalizedCycleType === "sevenYear") {
      return this.shiftSevenYearPeriodStart(currentDate, step);
    }

    const currentRange = this.getPeriodRange(cycleType, currentDate);
    if (normalizedCycleType === "month") {
      return parseDateKey(
        this.shiftMonthRange(currentRange.start, step).start,
      );
    }

    const start = parseDateKey(currentRange.start);
    if (normalizedCycleType === "year") {
      start.setFullYear(start.getFullYear() + step);
    } else if (normalizedCycleType === "week") {
      start.setDate(start.getDate() + 7 * step);
    } else {
      start.setDate(start.getDate() + step);
    }
    return start;
  }

  private getSevenYearAnchorStart(): Date {
    const anchorDate = parseDateKey(this.sevenYearAnchorDate);
    return new Date(anchorDate.getFullYear(), 0, 1);
  }

  private getSevenYearPeriodStart(date: Date): Date {
    const anchorStart = this.getSevenYearAnchorStart();
    const targetYear = date.getFullYear();
    const deltaYears = targetYear - anchorStart.getFullYear();
    const periodOffsetYears = Math.floor(deltaYears / 7) * 7;
    return new Date(anchorStart.getFullYear() + periodOffsetYears, 0, 1);
  }

  private shiftSevenYearPeriodStart(date: Date, step: number): Date {
    const start = this.getSevenYearPeriodStart(date);
    start.setFullYear(start.getFullYear() + 7 * step);
    return start;
  }

  buildPlanningGroups(
    viewType: ExtendedPlanningViewType,
    date: Date,
    tasks: TaskWithSubtasks[],
    firstDayOfWeek: number = this.firstDayOfWeek,
  ): PlanningGroup[] {
    const groups: PlanningGroup[] = [];
    const normalizedViewType = normalizePlanningViewType(viewType);

    if (normalizedViewType === "sevenYear") {
      return this.buildSevenYearGroups(date, tasks);
    } else if (normalizedViewType === "year") {
      return this.buildYearGroups(date, tasks, firstDayOfWeek);
    } else if (normalizedViewType === "month") {
      return this.buildMonthGroups(date, tasks, firstDayOfWeek);
    } else if (normalizedViewType === "week") {
      return this.buildWeekGroups(date, tasks, firstDayOfWeek);
    } else if (normalizedViewType === "day") {
      return this.buildDayGroups(date, tasks);
    }

    return groups;
  }

  private buildSevenYearGroups(
    date: Date,
    tasks: TaskWithSubtasks[],
  ): PlanningGroup[] {
    const periodStart = this.getSevenYearPeriodStart(date);
    const startYear = periodStart.getFullYear();
    const endYear = startYear + 6;
    const periodEnd = new Date(endYear + 1, 0, 0);
    const sevenYearTasks = this.getTasksByPlanningType(tasks, "7years");

    const tasksInCurrentPeriod = sevenYearTasks.filter((task) => {
      return taskPlanningWindowOverlaps(task, periodStart, periodEnd);
    });

    return [
      {
        id: `seven-year-${startYear}-${endYear}`,
        label: `${startYear}-${endYear}`,
        date: periodStart,
        tasks: tasksInCurrentPeriod,
        children: [],
      },
    ];
  }

  private buildYearGroups(
    date: Date,
    tasks: TaskWithSubtasks[],
    _firstDayOfWeek: number,
  ): PlanningGroup[] {
    const year = date.getFullYear();
    const yearTasks = this.getTasksByPlanningType(tasks, "year");
    const monthTasks = this.getTasksByPlanningType(tasks, "month");

    // Filter year tasks for current year
    const yearStart = new Date(year, 0, 1);
    const yearEnd = new Date(year, 11, 31);
    const yearTasksInCurrentYear = yearTasks.filter((task) =>
      taskPlanningWindowOverlaps(task, yearStart, yearEnd),
    );

    const yearGroup: PlanningGroup = {
      id: `year-${year}`,
      label: `${year}年`,
      date: new Date(year, 0, 1),
      tasks: yearTasksInCurrentYear,
      children: [],
    };

    // Add 12 months
    for (let month = 0; month < 12; month++) {
      const monthDate = new Date(year, month, 1);
      const monthEnd = new Date(year, month + 1, 0);
      const monthTasksInYear = monthTasks.filter((task) =>
        taskPlanningWindowOverlaps(task, monthDate, monthEnd),
      );

      yearGroup.children!.push({
        id: `month-${year}-${month}`,
        label: `${month + 1}月`,
        date: monthDate,
        tasks: monthTasksInYear,
        children: [],
      });
    }

    return [yearGroup];
  }

  private buildMonthGroups(
    date: Date,
    tasks: TaskWithSubtasks[],
    firstDayOfWeek: number,
  ): PlanningGroup[] {
    const year = date.getFullYear();
    const month = date.getMonth();
    const monthTasks = this.getTasksByPlanningType(tasks, "month");
    const weekTasks = this.getTasksByPlanningType(tasks, "week");

    const monthStart = new Date(year, month, 1);
    const monthEnd = new Date(year, month + 1, 0);
    const monthTasksInCurrentMonth = monthTasks.filter((task) =>
      taskPlanningWindowOverlaps(task, monthStart, monthEnd),
    );

    const monthGroup: PlanningGroup = {
      id: `month-${year}-${month}`,
      label: `${year}年${month + 1}月`,
      date: new Date(year, month, 1),
      tasks: monthTasksInCurrentMonth,
      children: [],
    };

    const weeksInMonth = this.getWeeksInMonth(year, month, firstDayOfWeek);

    weeksInMonth.forEach((week) => {
      const weekTasksInMonth = weekTasks.filter((task) =>
        taskPlanningWindowOverlaps(task, week.start, week.end),
      );

      monthGroup.children!.push({
        id: `week-${year}-${month}-${week.weekIndex}`,
        label: `第${week.weekIndex + 1}周`,
        date: week.start,
        tasks: weekTasksInMonth,
        children: [],
      });
    });

    return [monthGroup];
  }

  private buildWeekGroups(
    date: Date,
    tasks: TaskWithSubtasks[],
    _firstDayOfWeek: number,
  ): PlanningGroup[] {
    const weekStart = this.getWeekStart(date);
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 6);
    const weekTasks = this.getTasksByPlanningType(tasks, "week");
    const dayTasks = this.getTasksByPlanningType(tasks, "day");

    const weekTasksInWeek = weekTasks.filter((task) =>
      taskPlanningWindowOverlaps(task, weekStart, weekEnd),
    );

    const weekGroup: PlanningGroup = {
      id: `week-${weekStart.getFullYear()}-${weekStart.getMonth()}-${weekStart.getDate()}`,
      label: `第${Math.ceil(weekStart.getDate() / 7)}周`,
      date: weekStart,
      tasks: weekTasksInWeek,
      children: [],
    };

    const daysInWeekArr = getDaysInWeek(weekStart);
    daysInWeekArr.forEach((dayDate, index) => {
      const dayTasksInWeek = dayTasks.filter((task) =>
        taskPlanningWindowOverlaps(task, dayDate, dayDate),
      );
      weekGroup.children!.push({
        id: `day-${weekStart.getFullYear()}-${weekStart.getMonth()}-${weekStart.getDate()}-${index}`,
        label: `${dayDate.getMonth() + 1}月${dayDate.getDate()}日`,
        date: dayDate,
        tasks: dayTasksInWeek,
        children: [],
      });
    });

    return [weekGroup];
  }

  private buildDayGroups(
    date: Date,
    tasks: TaskWithSubtasks[],
  ): PlanningGroup[] {
    const year = date.getFullYear();
    const month = date.getMonth();
    const day = date.getDate();
    const dayTasks = this.getTasksByPlanningType(tasks, "day");

    const dayGroup: PlanningGroup = {
      id: `day-${year}-${month}-${day}`,
      label: `${year}年${month + 1}月${day}日`,
      date: date,
      tasks: dayTasks.filter((task) =>
        taskPlanningWindowOverlaps(task, date, date),
      ),
      children: [],
    };

    return [dayGroup];
  }

  private getTasksByPlanningType(
    tasks: TaskWithSubtasks[],
    type: ExtendedPlanningViewType,
  ): TaskWithSubtasks[] {
    return tasks.filter((task) => task.planning_cycle_type === type);
  }

  shiftWeekRange(
    startDate: string,
    endDate: string,
    deltaWeeks: number,
  ): { start: string; end: string } {
    const start = parseDateKey(startDate);
    const end = parseDateKey(endDate);

    start.setDate(start.getDate() + 7 * deltaWeeks);
    end.setDate(end.getDate() + 7 * deltaWeeks);

    return {
      start: formatDateKey(start),
      end: formatDateKey(end),
    };
  }

  /**
   * Get month information for a given date (unified interface)
   * @param date - The date to get month info for
   * @returns Object containing month index and whether it's a valid month
   */
  getMonthInfo(date: Date): {
    monthIndex: number | null;
    isValidMonth: boolean;
    monthStart: Date | null;
  } {
    const monthIndex = date.getMonth() + 1; // Convert to 1-based
    const yearStart = this.getYearStart(date);
    const monthStart = new Date(yearStart);
    monthStart.setMonth(monthIndex - 1);

    return {
      monthIndex,
      isValidMonth: true,
      monthStart,
    };
  }

  /**
   * Get the start date of a specific month (unified interface)
   * @param yearStart - The start of the year
   * @param monthIndex - The month index (1-based)
   * @returns Date object representing the start of the specified month
   */
  getMonthStart(yearStart: Date, monthIndex: number): Date {
    return new Date(yearStart.getFullYear(), monthIndex - 1, 1);
  }

  /**
   * Get all available months for selection (unified interface)
   * @returns Array of month objects with index and display name
   */
  getMonthOptions(
    _baseDate?: Date,
    monthNames?: string[],
  ): Array<{ index: number; name: string }> {
    // Use provided month names or default to English month names
    const defaultMonthNames = [
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
    ];

    const namesToUse = monthNames || defaultMonthNames;

    return Array.from({ length: 12 }, (_, i) => ({
      index: i + 1,
      name: namesToUse[i] || `Month ${i + 1}`, // Fallback if month name not provided
    }));
  }

  /**
   * Get the first day of the week containing the given date
   * @param date - The date to find the first day for
   * @param firstDayOfWeek - First day of week (1=Monday, 2=Tuesday, ..., 7=Sunday)
   * @returns Date object representing first day of that week
   */
  private getFirstDayOfWeek(date: Date, firstDayOfWeek: number = 1): Date {
    const dayOfWeek = date.getDay(); // 0=Sunday, 1=Monday, ..., 6=Saturday

    // Convert firstDayOfWeek to JavaScript day format (0=Sunday, 1=Monday, etc.)
    const jsFirstDay = firstDayOfWeek === 7 ? 0 : firstDayOfWeek;

    // Calculate days to first day of week
    const daysToFirstDay = (dayOfWeek - jsFirstDay + 7) % 7;

    const firstDay = new Date(date);
    firstDay.setDate(date.getDate() - daysToFirstDay);
    return firstDay;
  }

  /**
   * Get all weeks in a month with customizable first day of week
   * @param year - The year
   * @param month - The month (0-based)
   * @param firstDayOfWeek - First day of week (1=Monday, 2=Tuesday, ..., 7=Sunday)
   * @returns Array of week objects with start and end dates
   */
  private getWeeksInMonth(
    year: number,
    month: number,
    firstDayOfWeek: number = 1,
  ): Array<{
    start: Date;
    end: Date;
    weekIndex: number;
  }> {
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const firstWeekStart = this.getFirstDayOfWeek(firstDay, firstDayOfWeek);

    const weeks = [];
    const currentWeek = new Date(firstWeekStart);
    let weekIndex = 0;

    while (currentWeek <= lastDay) {
      const weekEnd = new Date(currentWeek);
      weekEnd.setDate(currentWeek.getDate() + 6);

      weeks.push({
        start: new Date(currentWeek),
        end: weekEnd,
        weekIndex,
      });

      currentWeek.setDate(currentWeek.getDate() + 7);
      weekIndex++;
    }

    return weeks;
  }

  /**
   * Get the current week range based on Gregorian calendar
   */
  getCurrentWeekRange(): { start: string; end: string } {
    return getCurrentWeekRange(this.firstDayOfWeek);
  }

  /**
   * Get the current month range based on Gregorian calendar
   */
  getCurrentMonthRange(): { start: string; end: string } {
    return getCurrentMonthRangeLocal();
  }

  /**
   * Shift month range by specified number of months for Gregorian calendar
   */
  shiftMonthRange(
    startDate: string,
    deltaMonths: number,
  ): { start: string; end: string } {
    return shiftMonthRange(startDate, deltaMonths);
  }

  getPeriodRange(
    viewType: ExtendedPlanningViewType,
    date: Date,
  ): { start: string; end: string } {
    const normalizedViewType = normalizePlanningViewType(viewType);

    switch (normalizedViewType) {
      case "year": {
        const yearStart = this.getYearStart(date);
        const yearEnd = new Date(yearStart.getFullYear() + 1, 0, 1);
        return {
          start: formatDateKey(yearStart),
          end: formatDateKey(new Date(yearEnd.getTime() - 24 * 60 * 60 * 1000)),
        };
      }
      case "sevenYear": {
        const periodStart = this.getSevenYearPeriodStart(date);
        const startYear = periodStart.getFullYear();
        const endYear = startYear + 6;
        const endDateExclusive = new Date(endYear + 1, 0, 1);
        return {
          start: formatDateKey(periodStart),
          end: formatDateKey(
            new Date(endDateExclusive.getTime() - 24 * 60 * 60 * 1000),
          ),
        };
      }
      case "month": {
        // current month relative to provided date
        const y = date.getFullYear();
        const m = date.getMonth();
        const s = new Date(y, m, 1);
        const e = new Date(y, m + 1, 0);
        return {
          start: formatDateKey(s),
          end: formatDateKey(e),
        };
      }
      case "week": {
        const weekStart = this.getWeekStart(date);
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekStart.getDate() + 6);
        return {
          start: formatDateKey(weekStart),
          end: formatDateKey(weekEnd),
        };
      }
      case "day": {
        const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        const iso = formatDateKey(d);
        return { start: iso, end: iso };
      }
      default: {
        const week = this.getCurrentWeekRange();
        return week;
      }
    }
  }

  shiftPeriodRange(
    viewType: ExtendedPlanningViewType,
    startDate: string,
    endDate: string,
    step: number,
  ): { start: string; end: string } {
    const normalizedViewType = normalizePlanningViewType(viewType);

    switch (normalizedViewType) {
      case "year": {
        const s = parseDateKey(startDate);
        const e = parseDateKey(endDate);
        s.setFullYear(s.getFullYear() + step);
        e.setFullYear(e.getFullYear() + step);
        return {
          start: formatDateKey(s),
          end: formatDateKey(e),
        };
      }
      case "sevenYear": {
        const s = parseDateKey(startDate);
        const e = parseDateKey(endDate);
        s.setFullYear(s.getFullYear() + 7 * step);
        e.setFullYear(e.getFullYear() + 7 * step);
        return {
          start: formatDateKey(s),
          end: formatDateKey(e),
        };
      }
      case "month": {
        return this.shiftMonthRange(startDate, step);
      }
      case "week": {
        return this.shiftWeekRange(startDate, endDate, step);
      }
      case "day": {
        const s = parseDateKey(startDate);
        const e = parseDateKey(endDate);
        s.setDate(s.getDate() + step);
        e.setDate(e.getDate() + step);
        return {
          start: formatDateKey(s),
          end: formatDateKey(e),
        };
      }
      default:
        return { start: startDate, end: endDate };
    }
  }

  enumerateDates(startDate: string, endDate: string): string[] {
    const res: string[] = [];
    if (!startDate || !endDate) return res;
    const s = parseDateKey(startDate);
    const e = parseDateKey(endDate);
    for (let d = new Date(s); d <= e; d.setDate(d.getDate() + 1)) {
      res.push(formatDateKey(d));
    }
    return res;
  }

  getDisplayYear(storedDate: string): number {
    if (!storedDate) return new Date().getFullYear();

    // Parse the YYYY-MM-DD format directly to avoid timezone issues
    const match = storedDate.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!match) return new Date().getFullYear();

    const year = parseInt(match[1]);
    return year;
  }

  getDateForYearSelection(year: number): Date {
    return new Date(year, 0, 1);
  }
}
