import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { PersonSummary } from "./types/common";
import type { TimelogListResponse } from "./timelogs";
import type { UUID } from "@/types/primitive";
import type { ListResponse } from "@/types/pagination";
import { MAX_TASKS_PAGE_SIZE } from "@/utils/constants";
import { formatDateKey } from "@/utils/datetime";

// Types local to tasks
export interface Task {
  id: UUID;
  vision_id: UUID | null;
  parent_task_id?: UUID | null;
  content: string;
  status: string;
  priority: number;
  display_order: number;
  estimated_effort?: number | null;
  // Planning cycle fields
  planning_cycle_type?: string | null;
  planning_cycle_days?: number | null;
  planning_cycle_start_date?: string | null;
  // New fields for precise time investment rendering
  actual_effort_self: number;
  actual_effort_total: number;
  notes_count: number;
  timelogs_count?: number;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  people?: PersonSummary[];
}

export interface TaskMoveResponse extends Task {
  updated_descendants: Task[];
}

export interface TaskCreate {
  vision_id: UUID | null;
  parent_task_id?: UUID | null;
  content: string;
  priority?: number;
  estimated_effort?: number;
  display_order?: number;
  person_ids?: UUID[];
  planning_cycle_type?: string;
  planning_cycle_days?: number;
  planning_cycle_start_date?: string;
}

export interface TaskUpdate {
  content?: string;
  status?: string;
  priority?: number;
  estimated_effort?: number;
  display_order?: number;
  parent_task_id?: UUID | null;
  person_ids?: UUID[];
  planning_cycle_type?: string | null;
  planning_cycle_days?: number | null;
  planning_cycle_start_date?: string | null;
}

export interface TaskWithSubtasks extends Task {
  subtasks: TaskWithSubtasks[];
  completion_percentage: number;
  depth: number;
}

export interface TaskHierarchy {
  vision_id: UUID;
  root_tasks: TaskWithSubtasks[];
}

export interface TaskStatsResponse {
  total_subtasks: number;
  completed_subtasks: number;
  completion_percentage: number;
  total_estimated_effort?: number | null;
  total_actual_effort?: number | null;
}

interface TaskListMeta {
  vision_id?: UUID | null;
  vision_in?: string | null;
  status_filter?: string | null;
  status_in?: string | null;
  exclude_status?: string | null;
  planning_cycle_type?: string | null;
  planning_cycle_start_date?: string | null;
  calendar_system?: string | null;
  first_day_of_week?: number | null;
  seven_year_anchor_date?: string | null;
  query?: string | null;
  fields?: TaskFieldsMode | null;
}

export type TaskListResponse = ListResponse<Task, TaskListMeta>;

// Shared filters for listing tasks (keep snake_case to match query params)
export type TaskFieldsMode = "basic" | "full";

export interface TaskListFilters {
  vision_id?: UUID;
  vision_in?: string[];
  status_filter?: string;
  status_in?: string[];
  exclude_status?: string[];
  page?: number;
  size?: number;
  planning_cycle_type?: string;
  planning_cycle_start_date?: string; // YYYY-MM-DD
  query?: string;
  fields?: TaskFieldsMode;
}

// Small helper: convert Date to YYYY-MM-DD in user's timezone (or undefined)
export const toISODate = (d?: Date): string | undefined => {
  if (!d) return undefined;
  return formatDateKey(d);
};

export const tasksApi = {
  async getAll(
    visionId?: UUID,
    statusFilter?: string,
    extra?: TaskListFilters,
  ): Promise<TaskListResponse> {
    const params: Record<string, string | number | boolean | undefined> = {
      vision_id: visionId,
      status_filter: statusFilter,
    };
    if (extra?.vision_in && extra.vision_in.length > 0) {
      params.vision_in = extra.vision_in.join(",");
    }
    if (extra?.status_in && extra.status_in.length > 0) {
      params.status_in = extra.status_in.join(",");
    }
    if (extra?.exclude_status && extra.exclude_status.length > 0) {
      params.exclude_status = extra.exclude_status.join(",");
    }
    if (typeof extra?.page === "number") params.page = extra.page;
    if (typeof extra?.size === "number") params.size = extra.size;
    if (extra?.planning_cycle_type)
      params.planning_cycle_type = extra.planning_cycle_type;
    if (extra?.planning_cycle_start_date)
      params.planning_cycle_start_date = extra.planning_cycle_start_date;
    if (extra?.query) params.query = extra.query;
    const fields: TaskFieldsMode = extra?.fields ?? "basic";
    params.fields = fields;
    return http.get<TaskListResponse>(ENDPOINTS.TASKS.BASE, params);
  },

  async searchSelectorPage(opts: {
    visionId?: UUID | null;
    query?: string;
    statusIn?: readonly string[];
    page?: number;
    pageSize?: number;
    fields?: TaskFieldsMode;
  }): Promise<TaskListResponse> {
    return tasksApi.getAll(undefined, undefined, {
      vision_in: opts.visionId ? [String(opts.visionId)] : undefined,
      status_in: opts.statusIn ? [...opts.statusIn] : undefined,
      page: opts.page ?? 1,
      size: Math.min(
        Math.max(opts.pageSize ?? 50, 1),
        MAX_TASKS_PAGE_SIZE,
      ),
      query: opts.query?.trim() || undefined,
      fields: opts.fields ?? "basic",
    });
  },

  async queryAllPaged(opts: {
    visionIds?: UUID[];
    statusFilter?: string;
    statusIn?: string[];
    excludeStatus?: string[];
    pageSize?: number;
    maxPages?: number;
    fields?: TaskFieldsMode;
  }): Promise<Task[]> {
    const out: Task[] = [];
    const pageSize = Math.min(
      Math.max(opts.pageSize ?? 100, 1),
      MAX_TASKS_PAGE_SIZE,
    );
    let page = 1;
    while (true) {
      if (opts.maxPages && page > opts.maxPages) break;
      const response = await tasksApi.getAll(undefined, opts.statusFilter, {
        vision_in: opts.visionIds?.map((id) => String(id)),
        status_in: opts.statusIn,
        exclude_status: opts.excludeStatus,
        page,
        size: pageSize,
        fields: opts.fields ?? "basic",
      });
      out.push(...response.items);
      if (response.items.length < pageSize) break;
      if (response.pagination?.pages && page >= response.pagination.pages)
        break;
      page += 1;
    }
    return out;
  },

  async getAllPaged(opts: {
    visionId?: UUID;
    statusFilter?: string;
    statusIn?: string[];
    excludeStatus?: string[];
    pageSize?: number;
    maxPages?: number;
    fields?: TaskFieldsMode;
  }): Promise<Task[]> {
    const out: Task[] = [];
    const pageSize = Math.min(
      Math.max(opts.pageSize ?? 100, 1),
      MAX_TASKS_PAGE_SIZE,
    );
    let page = 1;
    while (true) {
      // guard to avoid infinite loops
      if (opts.maxPages && page > opts.maxPages) break;
      const response = await tasksApi.getAll(opts.visionId, opts.statusFilter, {
        status_in: opts.statusIn,
        exclude_status: opts.excludeStatus,
        page,
        size: pageSize,
        fields: opts.fields ?? "basic",
      });
      out.push(...response.items);
      if (response.items.length < pageSize) break; // no more data
      if (response.pagination?.pages && page >= response.pagination.pages)
        break;
      page += 1;
    }
    return out;
  },

  async getVisionHierarchy(visionId: UUID): Promise<TaskHierarchy> {
    return http.get<TaskHierarchy>(
      ENDPOINTS.TASKS.BY_VISION_HIERARCHY(visionId),
    );
  },

  async getById(id: UUID): Promise<Task> {
    return http.get<Task>(ENDPOINTS.TASKS.BY_ID(id));
  },

  async getWithSubtasks(id: UUID): Promise<TaskWithSubtasks> {
    return http.get<TaskWithSubtasks>(ENDPOINTS.TASKS.WITH_SUBTASKS(id));
  },

  async create(task: TaskCreate): Promise<Task> {
    // 将 parent_task_id 为 0 的值改为 null
    if (task.parent_task_id === "") {
      task = { ...task, parent_task_id: null };
    }
    return http.post<Task>(ENDPOINTS.TASKS.BASE, task);
  },

  async update(id: UUID, task: TaskUpdate): Promise<Task> {
    // 将 parent_task_id 为 0 的值改为 null
    if (task.parent_task_id === "") {
      task = { ...task, parent_task_id: null };
    }
    return http.patch<Task>(ENDPOINTS.TASKS.BY_ID(id), task);
  },

  async updateStatus(id: UUID, status: string): Promise<Task> {
    return http.patch<Task>(ENDPOINTS.TASKS.STATUS(id), { status });
  },

  async delete(id: UUID): Promise<void> {
    return http.delete<void>(ENDPOINTS.TASKS.BY_ID(id));
  },

  async reorder(
    taskOrders: { id: UUID; display_order: number }[],
  ): Promise<void> {
    return http.post<void>(ENDPOINTS.TASKS.REORDER, {
      task_orders: taskOrders,
    });
  },

  async move(
    id: UUID,
    oldParentTaskId?: UUID,
    newParentTaskId?: UUID,
    newVisionId?: UUID | null,
    newDisplayOrder: number = 0,
  ): Promise<TaskMoveResponse> {
    // 将 parent_task_id 为 0 的值改为 null
    const moveData = {
      old_parent_task_id: oldParentTaskId === "" ? null : oldParentTaskId,
      new_parent_task_id: newParentTaskId === "" ? null : newParentTaskId,
      new_vision_id: newVisionId,
      new_display_order: newDisplayOrder,
    };
    return http.post<TaskMoveResponse>(ENDPOINTS.TASKS.MOVE(id), moveData);
  },

  async getStats(id: UUID): Promise<TaskStatsResponse> {
    try {
      return await http.get<TaskStatsResponse>(ENDPOINTS.TASKS.STATS(id));
    } catch {
      return {
        total_subtasks: 0,
        completed_subtasks: 0,
        completion_percentage: 0,
        total_estimated_effort: null,
        total_actual_effort: null,
      };
    }
  },

  async getTimelogs(
    id: UUID,
    page: number = 1,
    size: number = 100,
  ): Promise<TimelogListResponse> {
    return http.get<TimelogListResponse>(ENDPOINTS.TIMELOGS.BASE, {
      task_id: id,
      page,
      size,
    });
  },
};
