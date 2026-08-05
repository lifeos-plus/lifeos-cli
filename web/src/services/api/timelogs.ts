import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { components } from "./generated/schema";
import type { PersonSummary } from "./types/common";
import type { UUID } from "@/types/primitive";
import { DataCleaner } from "@/utils/protocol";
import type { NoteSummary } from "./notes";

type TimelogTransport = components["schemas"]["TimelogResponse"];
type TimelogCreateTransport = components["schemas"]["TimelogCreate"];
type TimelogUpdateTransport = components["schemas"]["TimelogUpdate"];
type TimelogClientFields = {
  extra_data?: Record<string, unknown> | null;
  linked_notes?: NoteSummary[];
};
type TimelogDraftFields = {
  extra_data?: Record<string, unknown>;
  tags?: string[];
};

type TimelogTaskTransport = components["schemas"]["TaskSummaryResponse"];
export type TimelogTaskSummary = Omit<
  TimelogTaskTransport,
  "parent_task_id" | "status" | "vision_id"
> & {
  parent_task_id?: UUID | null;
  status?: string;
  vision_id: UUID | null;
  vision_summary?: { id: UUID; name: string } | null;
};
export type Timelog = Omit<
  TimelogTransport,
  "deleted_at" | "linked_notes_count" | "people" | "task" | "task_id"
> &
  TimelogClientFields & {
    deleted_at?: string | null;
    linked_notes_count?: number;
    people?: PersonSummary[] | null;
    task?: TimelogTaskSummary | null;
    task_id?: UUID | null;
  };
export type TimelogCreate = TimelogCreateTransport & TimelogDraftFields;
export type TimelogUpdate = TimelogUpdateTransport & TimelogDraftFields;
export type TimelogWithEnergyResponse = TimelogTransport;

export interface TimelogAdvancedSearchRequest {
  start_date: string;
  end_date?: string;
  area_id?: UUID | null;
  without_area?: boolean;
  area_name?: string | null;
  description_keyword?: string | null;
  task_id?: UUID | null;
  without_task?: boolean;
  with_task?: boolean;
}

export type TimelogListTransport = components["schemas"]["ListResponse_TimelogResponse_TimelogListMeta_"];
export type TimelogAdvancedSearchMetadata = Partial<components["schemas"]["TimelogListMeta"]> & {
  description_keyword?: string | null;
};
export type TimelogListResponse = Omit<TimelogListTransport, "items" | "meta"> & {
  items: Timelog[];
  meta: Partial<TimelogListTransport["meta"]>;
};
export type TimelogAdvancedSearchResponse = Omit<TimelogListTransport, "meta"> & {
  meta: TimelogAdvancedSearchMetadata;
};
export type LatestTimelogEndTimeResponse = components["schemas"]["LatestTimelogEndResponse"];

const TIMELOG_PAGE_SIZE = 500;
const MAX_TIMELOG_RANGE_PAGES = 100;

function toTimelogPayload(
  payload: TimelogCreate | TimelogUpdate,
): TimelogCreateTransport | TimelogUpdateTransport {
  return {
    title: payload.title,
    start_time: payload.start_time,
    end_time: payload.end_time,
    tracking_method: payload.tracking_method ?? "manual",
    location: payload.location,
    energy_level: payload.energy_level,
    notes: payload.notes,
    area_id: payload.area_id,
    task_id: payload.task_id,
    person_ids: payload.person_ids,
  };
}

export const timelogsApi = {
  fetchLatestEndTime: () =>
    http.get<LatestTimelogEndTimeResponse>(
      ENDPOINTS.TIMELOGS.LATEST_END_TIME,
    ),

  fetchRange: async (start: string, end: string, trackingMethod?: string) => {
    const items: Timelog[] = [];
    let firstResponse: TimelogListResponse | null = null;
    let page = 1;
    let totalCount = 0;
    let totalPages = 0;

    while (page <= MAX_TIMELOG_RANGE_PAGES) {
      const response = await http.get<TimelogListTransport>(
        ENDPOINTS.TIMELOGS.BASE,
        {
          window_start: start,
          window_end: end,
          tracking_method: trackingMethod,
          page,
          size: TIMELOG_PAGE_SIZE,
        },
      );

      firstResponse ??= response;
      items.push(...response.items);
      totalPages = response.pagination?.pages ?? 0;
      totalCount = response.pagination?.total ?? items.length;
      const backendTruncated = response.meta?.truncated === true;

      if (items.length >= totalCount) break;
      if (totalPages > 0 && page >= totalPages) break;
      if (!backendTruncated && response.items.length < TIMELOG_PAGE_SIZE) break;

      page += 1;
    }

    if (!firstResponse) {
      return {
        items: [],
        pagination: { page: 1, size: 0, total: 0, pages: 0 },
        meta: {
          returned_count: 0,
          total_count: 0,
          truncated: false,
        },
      };
    }

    const truncated = items.length < totalCount;
    return {
      items,
      pagination: {
        page: 1,
        size: items.length,
        total: totalCount,
        pages: truncated ? Math.max(totalPages, 1) : 1,
      },
      meta: {
        ...firstResponse.meta,
        returned_count: items.length,
        total_count: totalCount,
        truncated,
      },
    };
  },

  create: (payload: TimelogCreate) => {
    const cleanedData = DataCleaner.create(toTimelogPayload(payload));
    return http.post<TimelogTransport>(
      ENDPOINTS.TIMELOGS.BASE,
      cleanedData,
    );
  },

  batchCreate: (timelogs: TimelogCreate[]) => {
    const cleanedTimelogs = timelogs.map((timelog) =>
      DataCleaner.create(toTimelogPayload(timelog)),
    );

    return Promise.all(
      cleanedTimelogs.map((timelog) =>
        http.post<TimelogTransport>(ENDPOINTS.TIMELOGS.BASE, timelog),
      ),
    ).then((createdTimelogs) => ({
      created_count: createdTimelogs.length,
      failed_count: 0,
      created_timelogs: createdTimelogs,
      errors: [],
    }));
  },

  update: (id: UUID, payload: TimelogUpdate) => {
    const cleanedData = DataCleaner.update(toTimelogPayload(payload));

    return http.patch<TimelogTransport>(
      ENDPOINTS.TIMELOGS.BY_ID(id),
      cleanedData,
    );
  },

  quickEnd: (id: UUID) =>
    http.patch<TimelogTransport>(ENDPOINTS.TIMELOGS.BY_ID(id), {
      end_time: new Date().toISOString(),
    }),

  delete: (id: UUID) => http.delete<void>(ENDPOINTS.TIMELOGS.BY_ID(id)),

  batchDelete: (eventIds: UUID[]) =>
    Promise.allSettled(
      eventIds.map((eventId) => http.delete<void>(ENDPOINTS.TIMELOGS.BY_ID(eventId))),
    ).then((results) => {
      const failedIds = eventIds.filter((_, index) => results[index].status === "rejected");
      return {
        deleted_count: eventIds.length - failedIds.length,
        failed_ids: failedIds,
        errors: [],
      };
    }),

  restore: (_id: UUID) =>
    Promise.reject(new Error("Restore is not supported by LifeOS timelogs yet.")),

  batchRestore: (eventIds: UUID[]) =>
    Promise.resolve({
      deleted_count: 0,
      failed_ids: eventIds,
      errors: ["Restore is not supported by LifeOS timelogs yet."],
    }),

  advancedSearch: async (params: TimelogAdvancedSearchRequest) => {
    const withoutArea =
      params.without_area ?? params.area_id === null;
    const withoutTask =
      params.without_task ?? params.task_id === null;
    const withTask = params.with_task ?? false;
    const response = await http.get<TimelogListTransport>(
      ENDPOINTS.TIMELOGS.BASE,
      {
        window_start: params.start_date,
        window_end: params.end_date,
        query: params.description_keyword ?? undefined,
        area_id: withoutArea
          ? undefined
          : (params.area_id ?? undefined),
        without_area: withoutArea || undefined,
        area_name: params.area_name ?? undefined,
        task_id: withoutTask ? undefined : (params.task_id ?? undefined),
        without_task: withoutTask || undefined,
        with_task: withTask || undefined,
        size: 500,
      },
    );
    const returnedCount = response.items.length;
    const totalCount = response.pagination?.total ?? returnedCount;
    return {
      ...response,
      meta: {
        ...response.meta,
        start_date: response.meta?.start_date ?? params.start_date,
        end_date:
          response.meta?.end_date ??
          (params.end_date ? params.end_date : null),
        window_start: response.meta?.window_start ?? params.start_date,
        window_end:
          response.meta?.window_end ?? (params.end_date ? params.end_date : null),
        area_id:
          response.meta?.area_id ?? params.area_id ?? null,
        without_area:
          response.meta?.without_area ?? withoutArea,
        area_name:
          response.meta?.area_name ?? params.area_name ?? null,
        description_keyword:
          response.meta?.query ??
          params.description_keyword ??
          null,
        task_id: response.meta?.task_id ?? params.task_id ?? null,
        without_task:
          response.meta?.without_task ?? withoutTask,
        with_task: response.meta?.with_task ?? withTask,
        limit: response.meta?.limit ?? 500,
        returned_count: response.meta?.returned_count ?? returnedCount,
        total_count: response.meta?.total_count ?? totalCount,
        truncated: response.meta?.truncated ?? returnedCount < totalCount,
      },
    };
  },

  batchUpdate: (params: {
    timelog_ids: UUID[];
    update_type: "people" | "title" | "task" | "area";
    people?: {
      mode: "add" | "replace" | "clear";
      person_ids: UUID[];
    };
    title?: {
      mode: "replace" | "find_replace";
      value: string;
      find?: string;
    };
    task?: {
      mode: "replace" | "clear";
      task_id?: UUID;
    };
    area?: {
      area_id: UUID | null;
    };
  }) =>
    http.post<components["schemas"]["TimelogBatchUpdateResponse"]>(
      ENDPOINTS.TIMELOGS.BATCH_UPDATE,
      params satisfies components["schemas"]["TimelogBatchUpdate"],
    ),
};
