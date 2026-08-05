import type { UUID } from "@/types/primitive";
import { http } from "./client";
import type { components } from "./generated/schema";

export type DailyAreaRow = components["schemas"]["DailyAreaResponse"];
export type AggregationGranularity = components["schemas"]["AggregatedAreaResponse"]["granularity"];
export type AggregatedAreaRow = components["schemas"]["AggregatedAreaResponse"];
export type DailyAreaListResponse = components["schemas"]["ListResponse_DailyAreaResponse_DailyAreaMeta_"];
export type AggregatedAreaListResponse = components["schemas"]["ListResponse_AggregatedAreaResponse_AggregatedAreaMeta_"];
export type DayBreakdownListResponse = components["schemas"]["ListResponse_DayBreakdownResponse_DayBreakdownMeta_"];

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
    return http.post<components["schemas"]["RecomputeDailyAreasResponse"]>(
      "/api/v1/stats/daily-areas/recompute",
      undefined,
      { start, end },
    );
  },
};
