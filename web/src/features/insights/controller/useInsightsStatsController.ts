import { useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  statsApi,
  type AggregatedAreaRow,
  type AggregationGranularity,
  type DailyAreaRow,
} from "@/services/api/stats";
import { statsKeys } from "@/services/api/queryKeys";
import { logger } from "@/utils/core";

interface UseInsightsStatsControllerParams {
  ready: boolean;
  startDate: string;
  endDate: string;
  granularity: AggregationGranularity;
  activeTimezone: string;
  firstDayOfWeek: number;
  calendarSystem: "gregorian" | "mayan_13_moon";
  refreshErrorMessage: string;
}

interface UseInsightsStatsControllerResult {
  dailyStats: DailyAreaRow[];
  aggregatedRows: AggregatedAreaRow[];
  isLoading: boolean;
  displayError: string | null;
  refreshStats: () => Promise<void>;
}

export function useInsightsStatsController({
  ready,
  startDate,
  endDate,
  granularity,
  activeTimezone,
  firstDayOfWeek,
  calendarSystem,
  refreshErrorMessage,
}: UseInsightsStatsControllerParams): UseInsightsStatsControllerResult {
  const queryClient = useQueryClient();
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const normalizedFirstDayOfWeek = firstDayOfWeek ?? 1;
  const needsDailyStats = granularity === "day";

  const dailyQuery = useQuery<DailyAreaRow[]>({
    queryKey: statsKeys.dailyAreas({
      start: startDate,
      end: endDate,
      timezone: activeTimezone,
    }),
    queryFn: async () => {
      const response = await statsApi.getDailyAreas(
        startDate,
        endDate,
        undefined,
      );
      return response.items ?? [];
    },
    enabled: Boolean(ready && startDate && endDate && needsDailyStats),
    staleTime: 10 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    placeholderData: [],
  });

  const aggregatedQuery = useQuery<AggregatedAreaRow[]>({
    queryKey: statsKeys.aggregatedAreas({
      granularity,
      start: startDate,
      end: endDate,
      timezone: activeTimezone,
      first_day_of_week: normalizedFirstDayOfWeek,
      calendar_system: calendarSystem,
    }),
    queryFn: async () => {
      const response = await statsApi.getAggregatedAreas(
        granularity,
        startDate,
        endDate,
      );
      return response.items ?? [];
    },
    enabled: Boolean(ready && startDate && endDate && granularity !== "day"),
    staleTime: 10 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    placeholderData: [],
  });

  const dailyStats = useMemo(() => {
    if (!needsDailyStats) return [];
    return dailyQuery.data ?? [];
  }, [dailyQuery.data, needsDailyStats]);

  const aggregatedRows = useMemo(() => {
    if (granularity === "day") return [];
    return aggregatedQuery.data ?? [];
  }, [aggregatedQuery.data, granularity]);

  const queryError = useMemo(() => {
    if (needsDailyStats) {
      if (!dailyQuery.error) return null;
      return dailyQuery.error instanceof Error
        ? dailyQuery.error.message
        : String(dailyQuery.error);
    }

    if (!aggregatedQuery.error) return null;
    return aggregatedQuery.error instanceof Error
      ? aggregatedQuery.error.message
      : String(aggregatedQuery.error);
  }, [aggregatedQuery.error, dailyQuery.error, needsDailyStats]);

  const refreshStats = useCallback(async () => {
    if (!startDate || !endDate) return;

    setRefreshError(null);

    try {
      await statsApi.recomputeDailyAreas(
        startDate,
        endDate,
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: statsKeys.dailyAreas({
            start: startDate,
            end: endDate,
            timezone: activeTimezone,
          }),
        }),
        queryClient.invalidateQueries({
          queryKey: statsKeys.aggregatedAreas({
            granularity,
            start: startDate,
            end: endDate,
            timezone: activeTimezone,
            first_day_of_week: normalizedFirstDayOfWeek,
            calendar_system: calendarSystem,
          }),
        }),
      ]);
    } catch (error) {
      setRefreshError(refreshErrorMessage);
      logger.error("Failed to refresh stats", error);
    }
  }, [
    activeTimezone,
    calendarSystem,
    endDate,
    granularity,
    normalizedFirstDayOfWeek,
    queryClient,
    refreshErrorMessage,
    startDate,
  ]);

  return {
    dailyStats,
    aggregatedRows,
    isLoading: dailyQuery.isFetching || aggregatedQuery.isFetching,
    displayError: refreshError || queryError,
    refreshStats,
  };
}
