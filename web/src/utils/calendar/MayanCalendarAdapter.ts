import type {
  CalendarAdapter,
  ExtendedPlanningViewType,
  PlanningGroup,
} from "./CalendarAdapter";
import {
  countInclusiveLocalDates,
  DEFAULT_SEVEN_YEAR_ANCHOR_DATE,
  normalizePlanningViewType,
} from "./CalendarAdapter";
import type { TaskWithSubtasks } from "@/services/api";
import {
  formatDateKey,
  isDateKey,
  parseDateKey,
} from "@/utils/datetime";

/**
 * Mayan 13-Moon calendar adapter implementation
 * Handles all calendar operations for the Mayan 13-Moon calendar system
 */
export class MayanCalendarAdapter implements CalendarAdapter {
  private firstDayOfWeek: number;
  private sevenYearAnchorDate: string;

  constructor(
    firstDayOfWeek: number = 1,
    sevenYearAnchorDate: string = DEFAULT_SEVEN_YEAR_ANCHOR_DATE,
  ) {
    this.firstDayOfWeek = firstDayOfWeek;
    this.sevenYearAnchorDate = sevenYearAnchorDate;
  }

  /**
   * Convert a date to Mayan calendar parts
   * @param date - The date to convert
   * @returns Object containing Mayan calendar components
   */
  toMayanParts(date: Date): {
    mayanYearStart: Date;
    dayOfYear: number;
    moonIndex?: number; // 1..13
    dayInMoon?: number; // 1..28
    weekIndex?: number; // 1..52
    isDayOutOfTime: boolean;
  } {
    const mayanYearStart = this.getMayanYearStart(date);
    const dayOfYear = this.getMayanDayOfYear(date);
    const isDayOutOfTime = dayOfYear === 365;
    if (isDayOutOfTime) {
      return { mayanYearStart, dayOfYear, isDayOutOfTime };
    }
    const moonIndex = Math.ceil(dayOfYear / 28); // 1..13
    const dayInMoon = ((dayOfYear - 1) % 28) + 1; // 1..28
    const weekIndex = Math.ceil(dayOfYear / 7); // 1..52
    return {
      mayanYearStart,
      dayOfYear,
      moonIndex,
      dayInMoon,
      weekIndex,
      isDayOutOfTime,
    };
  }

  /**
   * Get the start of the Mayan year for a given date
   * Mayan year starts at July 26 each Gregorian year
   * @param date - The date to get Mayan year start for
   * @returns Date object representing the start of the Mayan year
   */
  getMayanYearStart(date: Date): Date {
    const y = date.getFullYear();
    const july26ThisYear = new Date(y, 6, 26);
    if (date >= july26ThisYear) {
      return new Date(y, 6, 26);
    }
    return new Date(y - 1, 6, 26);
  }

  private getDateOrdinal(date: Date): number {
    return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  }

  private getLeapDayForYear(yearStart: Date): Date | null {
    const leapDay = new Date(yearStart.getFullYear() + 1, 1, 29);
    return leapDay.getMonth() === 1 ? leapDay : null;
  }

  private getDateForMayanDay(yearStart: Date, dayOfYear: number): Date {
    const date = new Date(yearStart);
    date.setDate(yearStart.getDate() + dayOfYear - 1);
    const leapDay = this.getLeapDayForYear(yearStart);
    if (
      leapDay &&
      this.getDateOrdinal(date) >= this.getDateOrdinal(leapDay)
    ) {
      date.setDate(date.getDate() + 1);
    }
    return date;
  }

  /**
   * Get the day of year in Mayan calendar (1-365)
   * @param date - The date to get day of year for
   * @returns Day of year (1-365)
   */
  private getMayanDayOfYear(date: Date): number {
    const start = this.getMayanYearStart(date);
    const millisecondsPerDay = 24 * 60 * 60 * 1000;
    let dayOfYear =
      Math.floor(
        (this.getDateOrdinal(date) - this.getDateOrdinal(start)) /
          millisecondsPerDay,
      ) + 1;
    const leapDay = this.getLeapDayForYear(start);
    if (
      leapDay &&
      this.getDateOrdinal(date) > this.getDateOrdinal(leapDay)
    ) {
      // February 29 is intercalary, so it must not shift later moon/week indices.
      dayOfYear -= 1;
    }
    return dayOfYear;
  }

  /**
   * Get Mayan moon information for a given date
   * @param date - The date to get moon info for
   * @returns Object containing moon index, start/end dates, and weeks
   */
  getMayanMoonInfo(date: Date): {
    moonIndex?: number;
    start: Date;
    end: Date;
    isDayOutOfTime: boolean;
    weeks: Array<{ start: Date; end: Date; weekIndexWithinYear: number }>;
  } {
    const parts = this.toMayanParts(date);
    if (parts.isDayOutOfTime) {
      const outOfTimeDate = new Date(
        date.getFullYear(),
        date.getMonth(),
        date.getDate(),
      );
      return {
        start: new Date(outOfTimeDate),
        end: new Date(outOfTimeDate),
        isDayOutOfTime: true,
        weeks: [],
      };
    }
    const firstDayOfMoon = (parts.moonIndex! - 1) * 28 + 1;
    const start = this.getDateForMayanDay(
      parts.mayanYearStart,
      firstDayOfMoon,
    );
    const end = this.getDateForMayanDay(
      parts.mayanYearStart,
      firstDayOfMoon + 27,
    );
    const firstWeekIndex = Math.ceil(((parts.moonIndex! - 1) * 28 + 1) / 7);
    const weeks = Array.from({ length: 4 }).map((_, i) => {
      const firstDayOfWeek = firstDayOfMoon + i * 7;
      const wStart = this.getDateForMayanDay(
        parts.mayanYearStart,
        firstDayOfWeek,
      );
      const wEnd = this.getDateForMayanDay(
        parts.mayanYearStart,
        firstDayOfWeek + 6,
      );
      return {
        start: wStart,
        end: wEnd,
        weekIndexWithinYear: firstWeekIndex + i,
      };
    });
    return {
      moonIndex: parts.moonIndex,
      start,
      end,
      isDayOutOfTime: false,
      weeks,
    };
  }

  /**
   * Get Mayan week range for a given date
   * @param date - The date to get week range for
   * @returns Object containing week start/end dates and week index
   */
  getMayanWeekRange(date: Date): {
    start: Date;
    end: Date;
    weekIndexWithinYear?: number;
    isDayOutOfTime: boolean;
  } {
    const parts = this.toMayanParts(date);
    if (parts.isDayOutOfTime) {
      const outOfTimeDate = new Date(
        date.getFullYear(),
        date.getMonth(),
        date.getDate(),
      );
      return { start: outOfTimeDate, end: outOfTimeDate, isDayOutOfTime: true };
    }
    const firstDayOfWeek = (parts.weekIndex! - 1) * 7 + 1;
    const start = this.getDateForMayanDay(
      parts.mayanYearStart,
      firstDayOfWeek,
    );
    const end = this.getDateForMayanDay(
      parts.mayanYearStart,
      firstDayOfWeek + 6,
    );
    return {
      start,
      end,
      weekIndexWithinYear: parts.weekIndex,
      isDayOutOfTime: false,
    };
  }

  /**
   * Check if a date is the Day Out of Time in the Mayan 13-Moon calendar
   * @param date - The date to check
   * @returns true if the date is the Day Out of Time (July 25)
   */
  private isMayanDayOutOfTime(date: Date): boolean {
    const parts = this.toMayanParts(date);
    return parts.isDayOutOfTime;
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
    const parts = this.toMayanParts(date);
    const isValidMonth = !parts.isDayOutOfTime && parts.moonIndex !== undefined;

    if (!isValidMonth) {
      return {
        monthIndex: null,
        isValidMonth: false,
        monthStart: null,
      };
    }

    const yearStart = this.getYearStart(date);
    const monthStart = this.getDateForMayanDay(
      yearStart,
      (parts.moonIndex! - 1) * 28 + 1,
    );

    return {
      monthIndex: parts.moonIndex || null,
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
    return this.getDateForMayanDay(yearStart, (monthIndex - 1) * 28 + 1);
  }

  /**
   * Get all available months for selection (unified interface)
   * @returns Array of month objects with index and display name
   */
  getMonthOptions(
    baseDate?: Date,
    _monthNames?: string[],
  ): Array<{ index: number; name: string }> {
    const yearStart = baseDate
      ? this.getMayanYearStart(baseDate)
      : this.getMayanYearStart(new Date());

    return Array.from({ length: 13 }, (_, i) => {
      const moonIndex = i + 1;
      const monthStart = this.getDateForMayanDay(
        yearStart,
        (moonIndex - 1) * 28 + 1,
      );

      // Format: 3 2025-09-20
      const year = monthStart.getFullYear();
      const month = String(monthStart.getMonth() + 1).padStart(2, "0"); // 1-12 -> 01-12
      const day = String(monthStart.getDate()).padStart(2, "0"); // 1-31 -> 01-31
      const name = `${moonIndex} ${year}-${month}-${day}`;

      return {
        index: moonIndex,
        name,
      };
    });
  }

  getYearStart(date: Date): Date {
    return this.getMayanYearStart(date);
  }

  private getSevenYearAnchorStart(): Date {
    return this.getMayanYearStart(parseDateKey(this.sevenYearAnchorDate));
  }

  private getSevenYearPeriodStart(date: Date): Date {
    const anchorStart = this.getSevenYearAnchorStart();
    const targetStart = this.getMayanYearStart(date);
    const deltaYears = targetStart.getFullYear() - anchorStart.getFullYear();
    const periodOffsetYears = Math.floor(deltaYears / 7) * 7;
    const periodStart = new Date(anchorStart);
    periodStart.setFullYear(anchorStart.getFullYear() + periodOffsetYears);
    return periodStart;
  }

  getWeekStart(date: Date): Date {
    const range = this.getMayanWeekRange(date);
    return range.start;
  }

  private shiftAdjacentPeriodRange(
    viewType: "month" | "week",
    startDate: string,
    step: number,
  ): { start: string; end: string } {
    let range = this.getPeriodRange(
      viewType,
      parseDateKey(startDate),
    );
    const direction = Math.sign(step);

    for (let index = 0; index < Math.abs(Math.trunc(step)); index += 1) {
      const boundary = parseDateKey(
        direction > 0 ? range.end : range.start,
      );
      boundary.setDate(boundary.getDate() + direction);
      range = this.getPeriodRange(viewType, boundary);
    }

    return range;
  }

  getNextPeriod(currentDate: Date, cycleType: ExtendedPlanningViewType): Date {
    const nextDate = new Date(currentDate);
    const normalizedCycleType = normalizePlanningViewType(cycleType);

    switch (normalizedCycleType) {
      case "year": {
        const start = this.getMayanYearStart(currentDate);
        start.setFullYear(start.getFullYear() + 1);
        return start;
      }
      case "sevenYear": {
        const start = this.getSevenYearPeriodStart(currentDate);
        start.setFullYear(start.getFullYear() + 7);
        return start;
      }
      case "month": {
        const range = this.getPeriodRange("month", currentDate);
        return parseDateKey(
          this.shiftAdjacentPeriodRange("month", range.start, 1).start,
        );
      }
      case "week": {
        const range = this.getPeriodRange("week", currentDate);
        return parseDateKey(
          this.shiftAdjacentPeriodRange("week", range.start, 1).start,
        );
      }
      case "day":
        nextDate.setDate(nextDate.getDate() + 1);
        return nextDate;
      default:
        return nextDate;
    }
  }

  getPreviousPeriod(
    currentDate: Date,
    cycleType: ExtendedPlanningViewType,
  ): Date {
    const previousDate = new Date(currentDate);
    const normalizedCycleType = normalizePlanningViewType(cycleType);

    switch (normalizedCycleType) {
      case "year": {
        const start = this.getMayanYearStart(currentDate);
        start.setFullYear(start.getFullYear() - 1);
        return start;
      }
      case "sevenYear": {
        const start = this.getSevenYearPeriodStart(currentDate);
        start.setFullYear(start.getFullYear() - 7);
        return start;
      }
      case "month": {
        const range = this.getPeriodRange("month", currentDate);
        return parseDateKey(
          this.shiftAdjacentPeriodRange("month", range.start, -1).start,
        );
      }
      case "week": {
        const range = this.getPeriodRange("week", currentDate);
        return parseDateKey(
          this.shiftAdjacentPeriodRange("week", range.start, -1).start,
        );
      }
      case "day":
        previousDate.setDate(previousDate.getDate() - 1);
        return previousDate;
      default:
        return previousDate;
    }
  }

  getPlanningCycleDays(
    cycleType: ExtendedPlanningViewType,
    baseDate: Date = new Date(),
  ): number {
    const range = this.getPeriodRange(cycleType, baseDate);
    return countInclusiveLocalDates(range.start, range.end);
  }

  isSpecialDay(date: Date): boolean {
    return this.isMayanDayOutOfTime(date);
  }

  getSpecialDayName(_date: Date): string {
    return "无时间日";
  }

  buildPlanningGroups(
    viewType: ExtendedPlanningViewType,
    date: Date,
    tasks: TaskWithSubtasks[],
    _firstDayOfWeek: number = this.firstDayOfWeek,
  ): PlanningGroup[] {
    const groups: PlanningGroup[] = [];
    const normalizedViewType = normalizePlanningViewType(viewType);

    if (normalizedViewType === "sevenYear") {
      return this.buildSevenYearGroups(date, tasks);
    } else if (normalizedViewType === "year") {
      return this.buildYearGroups(date, tasks);
    } else if (normalizedViewType === "month") {
      return this.buildMonthGroups(date, tasks);
    } else if (normalizedViewType === "week") {
      return this.buildWeekGroups(date, tasks);
    } else if (normalizedViewType === "day") {
      return this.buildDayGroups(date, tasks);
    }

    return groups;
  }

  private getPlanningCycleDate(task: TaskWithSubtasks): Date | null {
    const value = task.planning_cycle_start_date;
    if (!value || !isDateKey(value)) return null;
    return parseDateKey(value);
  }

  private isTaskOnDate(task: TaskWithSubtasks, date: Date): boolean {
    const taskDate = this.getPlanningCycleDate(task);
    return taskDate !== null && formatDateKey(taskDate) === formatDateKey(date);
  }

  private buildSevenYearGroups(
    date: Date,
    tasks: TaskWithSubtasks[],
  ): PlanningGroup[] {
    const start = this.getSevenYearPeriodStart(date);
    const end = new Date(start);
    end.setFullYear(start.getFullYear() + 7);
    end.setDate(end.getDate() - 1);
    const sevenYearTasks = this.getTasksByPlanningType(tasks, "7years");

    const tasksInCurrentPeriod = sevenYearTasks.filter((task) => {
      const taskDate = this.getPlanningCycleDate(task);
      if (!taskDate) return false;
      return taskDate >= start && taskDate <= end;
    });

    return [
      {
        id: `mayan-seven-year-${formatDateKey(start)}`,
        label: `${start.getFullYear()}-${start.getFullYear() + 6}`,
        date: start,
        tasks: tasksInCurrentPeriod,
        children: [],
      },
    ];
  }

  private buildYearGroups(
    date: Date,
    tasks: TaskWithSubtasks[],
  ): PlanningGroup[] {
    const mayanYearStart = this.getMayanYearStart(date);
    const nextMayanYearStart = new Date(mayanYearStart);
    nextMayanYearStart.setFullYear(mayanYearStart.getFullYear() + 1);
    const yearTasks = this.getTasksByPlanningType(tasks, "year");
    const monthTasks = this.getTasksByPlanningType(tasks, "month");
    const dayTasks = this.getTasksByPlanningType(tasks, "day");

    const tasksInMayanYear = yearTasks.filter((task) => {
      const taskDate = this.getPlanningCycleDate(task);
      return (
        taskDate !== null &&
        taskDate >= mayanYearStart &&
        taskDate < nextMayanYearStart
      );
    });

    const yearGroup: PlanningGroup = {
      id: `mayan-year-${mayanYearStart.getFullYear()}`,
      label: `${mayanYearStart.getFullYear()}年玛雅年`,
      date: mayanYearStart,
      tasks: tasksInMayanYear,
      children: [],
    };

    // 13 moons
    for (let m = 1; m <= 13; m++) {
      const firstDayOfMoon = (m - 1) * 28 + 1;
      const moonStart = this.getDateForMayanDay(
        mayanYearStart,
        firstDayOfMoon,
      );
      const tasksInMoon = monthTasks.filter((task) => {
        const taskDate = this.getPlanningCycleDate(task);
        if (!taskDate) return false;
        const parts = this.toMayanParts(taskDate);
        return !parts.isDayOutOfTime && parts.moonIndex === m;
      });
      yearGroup.children!.push({
        id: `mayan-month-${mayanYearStart.getFullYear()}-${m}`,
        label: `第${m}月`,
        date: moonStart,
        tasks: tasksInMoon,
        children: [],
      });
    }

    // Day out of time (single day)
    const outOfTimeDate = new Date(mayanYearStart.getFullYear() + 1, 6, 25);
    const outOfTimeTasks = dayTasks.filter((task) =>
      this.isTaskOnDate(task, outOfTimeDate),
    );
    yearGroup.children!.push({
      id: `mayan-day-out-of-time-${mayanYearStart.getFullYear()}`,
      label: `无时间日`,
      date: outOfTimeDate,
      tasks: outOfTimeTasks,
      children: [],
    });

    return [yearGroup];
  }

  private buildMonthGroups(
    date: Date,
    tasks: TaskWithSubtasks[],
  ): PlanningGroup[] {
    const monthTasks = this.getTasksByPlanningType(tasks, "month");
    const weekTasks = this.getTasksByPlanningType(tasks, "week");
    const info = this.getMayanMoonInfo(date);

    if (info.isDayOutOfTime) {
      return [
        {
          id: `mayan-month-out-of-time-${info.start.toISOString()}`,
          label: "无时间日",
          date: info.start,
          tasks: monthTasks.filter((task) =>
            this.isTaskOnDate(task, info.start),
          ),
          children: [],
        },
      ];
    }

    const monthGroup: PlanningGroup = {
      id: `mayan-month-${info.start.getFullYear()}-${info.moonIndex}`,
      label: `第${info.moonIndex}月`,
      date: info.start,
      tasks: monthTasks.filter((task) => {
        const taskDate = this.getPlanningCycleDate(task);
        if (!taskDate) return false;
        const parts = this.toMayanParts(taskDate);
        return !parts.isDayOutOfTime && parts.moonIndex === info.moonIndex;
      }),
      children: [],
    };

    info.weeks.forEach((w) => {
      const weekTasksIn = weekTasks.filter((task) => {
        const taskDate = this.getPlanningCycleDate(task);
        if (!taskDate) return false;
        const range = this.getMayanWeekRange(taskDate);
        return (
          !range.isDayOutOfTime && range.start.getTime() === w.start.getTime()
        );
      });
      monthGroup.children!.push({
        id: `mayan-week-${w.start.toISOString()}`,
        label: `第${w.weekIndexWithinYear}周`,
        date: w.start,
        tasks: weekTasksIn,
        children: [],
      });
    });

    return [monthGroup];
  }

  private buildWeekGroups(
    date: Date,
    tasks: TaskWithSubtasks[],
  ): PlanningGroup[] {
    const range = this.getMayanWeekRange(date);
    const weekTasks = this.getTasksByPlanningType(tasks, "week");
    const dayTasks = this.getTasksByPlanningType(tasks, "day");

    if (range.isDayOutOfTime) {
      return [
        {
          id: `mayan-week-out-of-time-${range.start.toISOString()}`,
          label: "无时间日",
          date: range.start,
          tasks: weekTasks.filter((task) =>
            this.isTaskOnDate(task, range.start),
          ),
          children: [],
        },
      ];
    }

    const weekTasksInWeek = weekTasks.filter((task) => {
      const taskDate = this.getPlanningCycleDate(task);
      if (!taskDate) return false;
      const r = this.getMayanWeekRange(taskDate);
      return !r.isDayOutOfTime && r.start.getTime() === range.start.getTime();
    });

    const weekGroup: PlanningGroup = {
      id: `mayan-week-${range.start.toISOString()}`,
      label: `第${range.weekIndexWithinYear}周`,
      date: range.start,
      tasks: weekTasksInWeek,
      children: [],
    };

    const days: Date[] = [];
    for (
      let current = new Date(range.start);
      current <= range.end;
      current.setDate(current.getDate() + 1)
    ) {
      days.push(new Date(current));
    }
    days.forEach((dayDate, index) => {
      const dayTasksInWeek = dayTasks.filter((task) => {
        const taskDate = this.getPlanningCycleDate(task);
        return (
          taskDate !== null &&
          taskDate.toDateString() === dayDate.toDateString()
        );
      });
      weekGroup.children!.push({
        id: `mayan-day-${range.start.toISOString()}-${index}`,
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
    const dayTasks = this.getTasksByPlanningType(tasks, "day");

    if (this.isMayanDayOutOfTime(date)) {
      return [
        {
          id: `mayan-day-out-of-time-${date.toISOString()}`,
          label: `无时间日`,
          date: date,
          tasks: dayTasks.filter((task) => this.isTaskOnDate(task, date)),
          children: [],
        },
      ];
    }

    const year = date.getFullYear();
    const month = date.getMonth();
    const day = date.getDate();
    const dayGroup: PlanningGroup = {
      id: `day-${year}-${month}-${day}`,
      label: `${year}年${month + 1}月${day}日`,
      date: date,
      tasks: dayTasks.filter((task) => {
        const taskDate = this.getPlanningCycleDate(task);
        return (
          taskDate !== null && taskDate.toDateString() === date.toDateString()
        );
      }),
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
    _endDate: string,
    deltaWeeks: number,
  ): { start: string; end: string } {
    return this.shiftAdjacentPeriodRange("week", startDate, deltaWeeks);
  }

  /**
   * Get the current week range based on Mayan calendar
   */
  getCurrentWeekRange(): { start: string; end: string } {
    const range = this.getMayanWeekRange(new Date());
    return {
      start: formatDateKey(range.start),
      end: formatDateKey(range.end),
    };
  }

  /**
   * Get the current month range based on Mayan calendar
   */
  getCurrentMonthRange(): { start: string; end: string } {
    const info = this.getMayanMoonInfo(new Date());
    return {
      start: formatDateKey(info.start),
      end: formatDateKey(info.end),
    };
  }

  /**
   * Shift month range by specified number of months for Mayan calendar
   */
  shiftMonthRange(
    startDate: string,
    deltaMonths: number,
  ): { start: string; end: string } {
    return this.shiftAdjacentPeriodRange("month", startDate, deltaMonths);
  }

  getPeriodRange(
    viewType: ExtendedPlanningViewType,
    date: Date,
  ): { start: string; end: string } {
    const normalizedViewType = normalizePlanningViewType(viewType);

    switch (normalizedViewType) {
      case "year": {
        const start = this.getMayanYearStart(date);
        const end = new Date(start);
        end.setFullYear(start.getFullYear() + 1);
        end.setDate(end.getDate() - 1);
        return {
          start: formatDateKey(start),
          end: formatDateKey(end),
        };
      }
      case "sevenYear": {
        const start = this.getSevenYearPeriodStart(date);
        const end = new Date(start);
        end.setFullYear(start.getFullYear() + 7);
        end.setDate(end.getDate() - 1);
        return {
          start: formatDateKey(start),
          end: formatDateKey(end),
        };
      }
      case "month": {
        const info = this.getMayanMoonInfo(date);
        return {
          start: formatDateKey(info.start),
          end: formatDateKey(info.end),
        };
      }
      case "week": {
        const r = this.getMayanWeekRange(date);
        return {
          start: formatDateKey(r.start),
          end: formatDateKey(r.end),
        };
      }
      case "day": {
        const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        const iso = formatDateKey(d);
        return { start: iso, end: iso };
      }
      default: {
        const r = this.getMayanWeekRange(date);
        return {
          start: formatDateKey(r.start),
          end: formatDateKey(r.end),
        };
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
    const month = parseInt(match[2]); // 1-12
    const day = parseInt(match[3]);

    if (month === 7 && day === 26) {
      // New format: stored as July 26, use the year directly
      return year;
    } else if (month === 1 && day === 1) {
      // Old format: January 1st, assume user intended the Gregorian year
      return year;
    } else {
      // For other dates, use the Mayan year calculation
      const date = parseDateKey(storedDate);
      const mayanYearStart = this.getMayanYearStart(date);
      return mayanYearStart.getFullYear();
    }
  }

  getDateForYearSelection(year: number): Date {
    return new Date(year, 6, 26);
  }
}
