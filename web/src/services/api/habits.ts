import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { components } from "./generated/schema";
import type { UUID } from "@/types/primitive";

type HabitTransport = components["schemas"]["HabitResponse"];
export type HabitStats = components["schemas"]["HabitStatsResponse"];
type HabitRequiredFields = "duration_days" | "id" | "start_date" | "status" | "title";
export type Habit = Pick<HabitTransport, HabitRequiredFields> &
  Partial<Omit<HabitTransport, HabitRequiredFields>> & { stats?: HabitStats | null };
export type HabitCreate = components["schemas"]["HabitCreate"];
export type HabitUpdate = components["schemas"]["HabitUpdate"];
export type HabitAction = components["schemas"]["HabitActionResponse"];
export type HabitActionUpdate = components["schemas"]["HabitActionUpdate"];
export type HabitOverviewResponse = components["schemas"]["HabitOverviewResponse"];
export type HabitOverviewListResponse = components["schemas"]["ListResponse_HabitOverviewResponse_HabitListMeta_"];
export type HabitListResponse = components["schemas"]["ListResponse_HabitResponse_HabitListMeta_"];
export type HabitActionListResponse = components["schemas"]["ListResponse_HabitActionResponse_HabitActionListMeta_"];
export type HabitActionWithHabit = components["schemas"]["HabitActionWithHabitResponse"];
export type HabitActionRangeListResponse = components["schemas"]["ListResponse_HabitActionWithHabitResponse_HabitActionRangeMeta_"];
export type HabitTaskAssociationsResponse = components["schemas"]["HabitAssociationsResponse"];

export interface HabitActionsQueryParams {
  page?: number;
  size?: number;
  statusFilter?: string;
  centerDate?: string;
  daysBefore?: number;
  daysAfter?: number;
}

export const habitsApi = {
  async getAll(
    statusFilter?: string,
    params?: { page?: number; size?: number },
  ): Promise<HabitListResponse> {
    return http.get<HabitListResponse>(ENDPOINTS.HABITS.BASE, {
      status_filter: statusFilter,
      page: params?.page,
      size: params?.size,
    });
  },

  async getOverviews(
    statusFilter?: string,
    params?: { page?: number; size?: number },
  ): Promise<HabitOverviewListResponse> {
    return http.get<HabitOverviewListResponse>(ENDPOINTS.HABITS.OVERVIEWS, {
      status_filter: statusFilter,
      page: params?.page,
      size: params?.size,
    });
  },

  async getActionsInRange(params: {
    startDate: string;
    endDate: string;
    referenceDate: string;
    cadenceFrequency?: string | null;
    page?: number;
    size?: number;
  }): Promise<HabitActionRangeListResponse> {
    return http.get<HabitActionRangeListResponse>(
      ENDPOINTS.HABITS.ACTIONS_IN_RANGE,
      {
        start_date: params.startDate,
        end_date: params.endDate,
        reference_date: params.referenceDate,
        cadence_frequency: params.cadenceFrequency ?? undefined,
        page: params.page,
        size: params.size,
      },
    );
  },

  async getById(id: UUID): Promise<Habit> {
    return http.get<HabitTransport>(ENDPOINTS.HABITS.BY_ID(id));
  },

  async getOverview(id: UUID): Promise<HabitOverviewResponse> {
    return http.get<HabitOverviewResponse>(ENDPOINTS.HABITS.OVERVIEW_BY_ID(id));
  },

  async create(habit: HabitCreate): Promise<Habit> {
    return http.post<HabitTransport>(ENDPOINTS.HABITS.BASE, habit);
  },

  async update(id: UUID, habit: HabitUpdate): Promise<Habit> {
    return http.patch<HabitTransport>(ENDPOINTS.HABITS.BY_ID(id), habit);
  },

  async delete(id: UUID): Promise<void> {
    return http.delete<void>(ENDPOINTS.HABITS.BY_ID(id));
  },

  async getActions(
    habitId: UUID,
    {
      page,
      size,
      statusFilter,
      centerDate,
      daysBefore,
      daysAfter,
    }: HabitActionsQueryParams = {},
  ): Promise<HabitActionListResponse> {
    return http.get<HabitActionListResponse>(
      ENDPOINTS.HABITS.ACTIONS(habitId),
      {
        page,
        size,
        status_filter: statusFilter,
        center_date: centerDate,
        days_before: daysBefore,
        days_after: daysAfter,
      },
    );
  },

  async updateAction(
    habitId: UUID,
    actionId: UUID,
    actionUpdate: HabitActionUpdate,
  ): Promise<HabitAction> {
    return http.patch<HabitAction>(
      ENDPOINTS.HABITS.ACTION_BY_ID(habitId, actionId),
      actionUpdate,
    );
  },

  async getHabitTaskAssociations(): Promise<HabitTaskAssociationsResponse> {
    return http.get<HabitTaskAssociationsResponse>(
      ENDPOINTS.HABITS.TASK_ASSOCIATIONS,
    );
  },
};
