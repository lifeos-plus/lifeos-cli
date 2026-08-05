import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { Task } from "./tasks";
import type { UUID } from "@/types/primitive";
import type { ListResponse } from "@/types/pagination";

// Types for habits
export interface Habit {
  id: UUID;
  title: string;
  description?: string | null;
  start_date: string;
  duration_days: number;
  cadence_frequency?: string | null;
  cadence_weekdays?: string[] | null;
  cadence_monthdays?: number[] | null;
  target_per_cycle?: number | null;
  status: string;
  stats?: HabitStats | null;
  task_id?: UUID | null;
  task?: Task | null;
}

export interface HabitCreate {
  title: string;
  description?: string;
  start_date: string;
  duration_days?: number;
  end_date?: string | null;
  repeat_count?: number | null;
  cadence_frequency?: string | null;
  cadence_weekdays?: string[] | null;
  cadence_monthdays?: number[] | null;
  target_per_cycle?: number | null;
  task_id?: UUID | null;
}

export interface HabitUpdate {
  title?: string;
  description?: string;
  start_date?: string;
  duration_days?: number;
  end_date?: string | null;
  repeat_count?: number | null;
  cadence_frequency?: string | null;
  cadence_weekdays?: string[] | null;
  cadence_monthdays?: number[] | null;
  target_per_cycle?: number | null;
  status?: string;
  task_id?: UUID | null;
}

export interface HabitAction {
  id: UUID;
  habit_id: UUID;
  action_date: string;
  status: string;
  notes?: string | null;
  linked_notes_count?: number;
}

interface HabitActionHabitSummary {
  title: string;
  description?: string | null;
  start_date: string;
  duration_days: number;
  cadence_frequency?: string | null;
}

export interface HabitActionUpdate {
  status?: string;
  notes?: string;
}

export interface HabitStats {
  habit_id: UUID;
  total_actions: number;
  completed_actions: number;
  missed_actions: number;
  skipped_actions: number;
  progress_percentage: number;
  current_streak: number;
  longest_streak: number;
}

interface HabitOverview {
  habit: Habit;
  stats: HabitStats;
}

export type HabitOverviewResponse = HabitOverview;

interface HabitListMeta {
  status_filter?: string | null;
}

interface HabitActionListMeta {
  status_filter?: string | null;
  center_date?: string | null;
  days_before?: number | null;
  days_after?: number | null;
}

interface HabitActionRangeListMeta {
  start_date?: string | null;
  end_date?: string | null;
  reference_date?: string | null;
  cadence_frequency?: string | null;
}

export type HabitOverviewListResponse = ListResponse<
  HabitOverview,
  HabitListMeta
>;

export type HabitListResponse = ListResponse<Habit, HabitListMeta>;

export type HabitActionListResponse = ListResponse<
  HabitAction,
  HabitActionListMeta
>;

export interface HabitActionWithHabit extends HabitAction {
  habit: HabitActionHabitSummary;
}

export type HabitActionRangeListResponse = ListResponse<
  HabitActionWithHabit,
  HabitActionRangeListMeta
>;

export interface HabitTaskAssociationsResponse {
  associations: Record<UUID, Habit[]>;
}

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
    return http.get<Habit>(ENDPOINTS.HABITS.BY_ID(id));
  },

  async getOverview(id: UUID): Promise<HabitOverviewResponse> {
    return http.get<HabitOverviewResponse>(ENDPOINTS.HABITS.OVERVIEW_BY_ID(id));
  },

  async create(habit: HabitCreate): Promise<Habit> {
    return http.post<Habit>(ENDPOINTS.HABITS.BASE, habit);
  },

  async update(id: UUID, habit: HabitUpdate): Promise<Habit> {
    return http.patch<Habit>(ENDPOINTS.HABITS.BY_ID(id), habit);
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
