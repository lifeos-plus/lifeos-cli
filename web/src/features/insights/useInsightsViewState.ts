import { useCallback, useEffect, useState } from "react";
import type {
  CalendarAdapter,
  ExtendedPlanningViewType,
} from "@/utils/calendar";
import { parseLocalDateString } from "@/utils/calendar";
import type { AggregationGranularity } from "@/services/api/stats";

export type InsightViewType = "year" | "month" | "week" | "sevenYear";

const DEFAULT_VIEW_TYPE: InsightViewType = "week";

interface ViewConfigEntry {
  defaultGranularity: AggregationGranularity;
  options: AggregationGranularity[];
}

export type InsightViewConfig = Record<InsightViewType, ViewConfigEntry>;

interface UseInsightsViewStateOptions {
  calendarAdapter: CalendarAdapter;
  calendarLoading: boolean;
  viewConfig: InsightViewConfig;
  initialViewMode?: "minutes" | "percent";
  initialViewType?: InsightViewType;
}

interface UseInsightsViewStateReturn {
  viewMode: "minutes" | "percent";
  setViewMode: (mode: "minutes" | "percent") => void;
  viewType: InsightViewType;
  handleViewTypeChange: (type: InsightViewType) => void;
  granularity: AggregationGranularity;
  setGranularity: (granularity: AggregationGranularity) => void;
  selectedDate: Date;
  setSelectedDate: (date: Date) => void;
  startDate: string;
  endDate: string;
  setStartDate: (value: string) => void;
  setEndDate: (value: string) => void;
  ready: boolean;
  navigateToPreviousPeriod: () => void;
  navigateToCurrentPeriod: () => void;
  navigateToNextPeriod: () => void;
}

export function useInsightsViewState({
  calendarAdapter,
  calendarLoading,
  viewConfig,
  initialViewMode = "minutes",
  initialViewType = DEFAULT_VIEW_TYPE,
}: UseInsightsViewStateOptions): UseInsightsViewStateReturn {
  const [viewMode, setViewMode] = useState<"minutes" | "percent">(
    initialViewMode,
  );
  const [viewType, setViewType] = useState<InsightViewType>(initialViewType);
  const [granularity, setGranularity] = useState<AggregationGranularity>(
    viewConfig[initialViewType].defaultGranularity,
  );
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!calendarLoading) {
      const { start, end } = calendarAdapter.getPeriodRange(
        initialViewType,
        new Date(),
      );
      setStartDate(start);
      setEndDate(end);
    }
  }, [calendarAdapter, calendarLoading, initialViewType]);

  useEffect(() => {
    if (startDate && endDate) {
      setReady(true);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    if (startDate) {
      setSelectedDate(parseLocalDateString(startDate));
    }
  }, [startDate]);

  useEffect(() => {
    const defaultGranularity = viewConfig[viewType].defaultGranularity;
    setGranularity((prev) =>
      prev === defaultGranularity ? prev : defaultGranularity,
    );
  }, [viewType, viewConfig]);

  const handleViewTypeChange = useCallback(
    (newViewType: InsightViewType) => {
      setViewType(newViewType);
      const now = new Date();
      const { start, end } = calendarAdapter.getPeriodRange(newViewType, now);
      setStartDate(start);
      setEndDate(end);
    },
    [calendarAdapter],
  );

  const navigateToPreviousPeriod = useCallback(() => {
    const { start, end } = calendarAdapter.shiftPeriodRange(
      viewType as ExtendedPlanningViewType,
      startDate,
      endDate,
      -1,
    );
    setStartDate(start);
    setEndDate(end);
  }, [calendarAdapter, endDate, startDate, viewType]);

  const navigateToCurrentPeriod = useCallback(() => {
    const now = new Date();
    const { start, end } = calendarAdapter.getPeriodRange(viewType, now);
    setStartDate(start);
    setEndDate(end);
  }, [calendarAdapter, viewType]);

  const navigateToNextPeriod = useCallback(() => {
    const { start, end } = calendarAdapter.shiftPeriodRange(
      viewType as ExtendedPlanningViewType,
      startDate,
      endDate,
      1,
    );
    setStartDate(start);
    setEndDate(end);
  }, [calendarAdapter, endDate, startDate, viewType]);

  return {
    viewMode,
    setViewMode,
    viewType,
    handleViewTypeChange,
    granularity,
    setGranularity,
    selectedDate,
    setSelectedDate,
    startDate,
    endDate,
    setStartDate,
    setEndDate,
    ready,
    navigateToPreviousPeriod,
    navigateToCurrentPeriod,
    navigateToNextPeriod,
  };
}
