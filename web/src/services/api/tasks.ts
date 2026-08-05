import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { components } from "./generated/schema";
import type { TimelogListResponse, TimelogListTransport } from "./timelogs";
import type { UUID } from "@/types/primitive";
import { MAX_TASKS_PAGE_SIZE } from "@/utils/constants";
import { formatDateKey } from "@/utils/datetime";

type TaskTransport = components["schemas"]["TaskResponse"];
type TaskCreateTransport = components["schemas"]["TaskCreate"];
type TaskUpdateTransport = components["schemas"]["TaskUpdate"];
type TaskOptionalFields =
  | "parent_task_id"
  | "planning_cycle_days"
  | "planning_cycle_start_date"
  | "planning_cycle_type";
export type Task = Omit<TaskTransport, TaskOptionalFields> &
  Partial<Pick<TaskTransport, TaskOptionalFields>>;
export type TaskMoveResponse = components["schemas"]["TaskMoveResponse"];
export type TaskCreate = Omit<TaskCreateTransport, "vision_id"> & {
  person_ids?: UUID[];
  vision_id: UUID | null;
};
export type TaskUpdate = TaskUpdateTransport & { person_ids?: UUID[] };
type TaskTreeTransport = components["schemas"]["TaskTreeResponse"];
export type TaskWithSubtasks = Task & {
  subtasks: TaskWithSubtasks[];
  completion_percentage: number;
  depth: number;
};
export type TaskHierarchy = Omit<
  components["schemas"]["TaskHierarchyResponse"],
  "root_tasks"
> & { root_tasks: TaskWithSubtasks[] };
export type TaskStatsResponse = components["schemas"]["TaskStatsResponse"];
type TaskListTransport = components["schemas"]["ListResponse_TaskResponse_TaskListMeta_"];
export type TaskListResponse = Omit<TaskListTransport, "items" | "meta"> & {
  items: Task[];
  meta: Partial<TaskListTransport["meta"]>;
};

const toTaskCreateTransport = ({
  person_ids: _personIds,
  vision_id: visionId,
  ...payload
}: TaskCreate): TaskCreateTransport => {
  if (!visionId) throw new Error("A vision is required to create a task.");
  return { ...payload, vision_id: visionId };
};

const toTaskUpdateTransport = ({
  person_ids: _personIds,
  ...payload
}: TaskUpdate): TaskUpdateTransport => payload;

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
    return http.get<TaskListTransport>(ENDPOINTS.TASKS.BASE, params);
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
    return http.get<components["schemas"]["TaskHierarchyResponse"]>(
      ENDPOINTS.TASKS.BY_VISION_HIERARCHY(visionId),
    );
  },

  async getById(id: UUID): Promise<Task> {
    return http.get<TaskTransport>(ENDPOINTS.TASKS.BY_ID(id));
  },

  async getWithSubtasks(id: UUID): Promise<TaskWithSubtasks> {
    return http.get<TaskTreeTransport>(ENDPOINTS.TASKS.WITH_SUBTASKS(id));
  },

  async create(task: TaskCreate): Promise<Task> {
    // 将 parent_task_id 为 0 的值改为 null
    if (task.parent_task_id === "") {
      task = { ...task, parent_task_id: null };
    }
    return http.post<TaskTransport>(
      ENDPOINTS.TASKS.BASE,
      toTaskCreateTransport(task),
    );
  },

  async update(id: UUID, task: TaskUpdate): Promise<Task> {
    // 将 parent_task_id 为 0 的值改为 null
    if (task.parent_task_id === "") {
      task = { ...task, parent_task_id: null };
    }
    return http.patch<TaskTransport>(
      ENDPOINTS.TASKS.BY_ID(id),
      toTaskUpdateTransport(task),
    );
  },

  async updateStatus(id: UUID, status: string): Promise<Task> {
    return http.patch<TaskTransport>(ENDPOINTS.TASKS.STATUS(id), { status });
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
    return http.get<TimelogListTransport>(ENDPOINTS.TIMELOGS.BASE, {
      task_id: id,
      page,
      size,
    });
  },
};
