import type { AggregationGranularity } from "@/services/api/stats";
import type { CalendarAdapter, ExtendedPlanningViewType } from "@/utils/calendar";
import { formatDateKey, parseDateKey } from "@/utils/datetime";

export interface PeriodBucketBoundary {
  start: string;
  end: string;
}

export const parseLocalDate = (isoDate: string): Date => {
  return parseDateKey(isoDate);
};

const toIsoDate = (date: Date): string => {
  const normalized = normalizeDate(date);
  return formatDateKey(normalized);
};

const normalizeDate = (date: Date): Date => {
  const normalized = new Date(date);
  normalized.setHours(0, 0, 0, 0);
  return normalized;
};

export const buildBucketBoundaries = (
  granularity: Exclude<AggregationGranularity, "day">,
  startDate: string,
  endDate: string,
  calendarAdapter: CalendarAdapter,
): PeriodBucketBoundary[] => {
  if (!startDate || !endDate) return [];
  const buckets: PeriodBucketBoundary[] = [];
  const rangeStart = parseLocalDate(startDate);
  const rangeEnd = parseLocalDate(endDate);

  const appendIntersectingBucket = (start: Date, end: Date) => {
    const normalizedStart = normalizeDate(start);
    const normalizedEnd = normalizeDate(end);
    if (normalizedEnd < rangeStart || normalizedStart > rangeEnd) return;
    buckets.push({
      start: toIsoDate(normalizedStart),
      end: toIsoDate(normalizedEnd),
    });
  };

  const viewTypeMap: Record<
    Exclude<AggregationGranularity, "day">,
    ExtendedPlanningViewType
  > = {
    week: "week",
    month: "month",
    year: "year",
  };

  const viewType = viewTypeMap[granularity];
  const parseRange = (range: { start: string; end: string }) => ({
    start: parseLocalDate(range.start),
    end: parseLocalDate(range.end),
  });

  let currentRange = calendarAdapter.getPeriodRange(viewType, rangeStart);
  let { start, end } = parseRange(currentRange);
  let safety = 0;

  while (end < rangeStart && safety < 500) {
    const nextRange = calendarAdapter.shiftPeriodRange(
      viewType,
      currentRange.start,
      currentRange.end,
      1,
    );
    currentRange = nextRange;
    ({ start, end } = parseRange(currentRange));
    safety += 1;
  }

  while (start <= rangeEnd && safety < 1500) {
    appendIntersectingBucket(start, end);
    if (end >= rangeEnd) break;

    const nextRange = calendarAdapter.shiftPeriodRange(
      viewType,
      currentRange.start,
      currentRange.end,
      1,
    );
    const nextParsed = parseRange(nextRange);
    if (nextParsed.start.getTime() === start.getTime()) {
      break;
    }
    currentRange = nextRange;
    start = nextParsed.start;
    end = nextParsed.end;
    safety += 1;
  }

  return buckets;
};
