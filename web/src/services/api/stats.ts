import type { UUID } from "@/types/primitive";
import type { ListResponse } from "@/types/pagination";
import { http } from "./client";

export interface DailyAreaRow {
  date: string;
  area_id: UUID;
  minutes: number;
}

export type AggregationGranularity = "day" | "week" | "month" | "year";

export interface AggregatedAreaRow {
  granularity: AggregationGranularity;
  period_start: string;
  period_end: string;
  area_id: UUID;
  minutes: number;
}

interface DailyAreaStatsMeta {
  start?: string | null;
  end?: string | null;
  timezone?: string | null;
  area_ids?: string[] | null;
}

export type DailyAreaListResponse = ListResponse<
  DailyAreaRow,
  DailyAreaStatsMeta
>;

interface AggregatedAreaStatsMeta {
  granularity?: AggregationGranularity | null;
  start?: string | null;
  end?: string | null;
  timezone?: string | null;
  area_ids?: string[] | null;
  first_day_of_week?: number | null;
  calendar_system?: string | null;
}

export type AggregatedAreaListResponse = ListResponse<
  AggregatedAreaRow,
  AggregatedAreaStatsMeta
>;

interface DayBreakdownRow {
  area_id: UUID;
  minutes: number;
}

interface DayBreakdownMeta {
  day?: string | null;
  timezone?: string | null;
}

export type DayBreakdownListResponse = ListResponse<
  DayBreakdownRow,
  DayBreakdownMeta
>;

export const statsApi = {
  async getDailyAreas(
    start: string,
    end: string,
    areaIds?: UUID[],
  ) {
    return http.get<DailyAreaListResponse>("/api/v1/stats/daily-areas", {
      start,
      end,
      area_ids: areaIds,
    });
  },
  async getLocalDayBreakdown(day: string) {
    return http.get<DayBreakdownListResponse>("/api/v1/stats/day-breakdown", {
      day,
    });
  },
  async getAggregatedAreas(
    granularity: AggregationGranularity,
    start: string,
    end: string,
    options?: {
      areaIds?: UUID[];
    },
  ) {
    return http.get<AggregatedAreaListResponse>(
      "/api/v1/stats/aggregated-areas",
      {
        granularity,
        start,
        end,
        area_ids: options?.areaIds,
      },
    );
  },
  async recomputeDailyAreas(
    start: string,
    end: string,
  ) {
    return http.post<{ days_recomputed: number }>(
      "/api/v1/stats/daily-areas/recompute",
      undefined,
      { start, end },
    );
  },
};
