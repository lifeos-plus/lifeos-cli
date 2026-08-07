import type { UUID } from "@/types/primitive";
import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { components } from "./generated/schema";
import type { PersonSummary } from "./types/common";

type PlannedEventTransport = components["schemas"]["PlannedEventResponse"];
export type PlannedEvent = Omit<PlannedEventTransport, "extra_data" | "people"> & {
  extra_data?: Record<string, unknown> | null;
  people?: PersonSummary[];
};
export type PlannedEventListResponse = components["schemas"]["ListResponse_PlannedEventResponse_PlannedEventListMeta_"];
type PlannedEventCreateTransport = components["schemas"]["PlannedEventCreate"];
type PlannedEventUpdateTransport = components["schemas"]["PlannedEventUpdate"];
type PlannedEventClientMetadata = { extra_data?: Record<string, unknown> };
export type PlannedEventCreate = PlannedEventCreateTransport & PlannedEventClientMetadata;
export type PlannedEventUpdate = PlannedEventUpdateTransport & PlannedEventClientMetadata;

export type PlannedEventDeleteOptions = {
  deleteType?: "single" | "all_future" | "all";
  instanceId?: UUID;
  instanceStart?: string;
};

export type PlannedEventUpdateOptions = {
  updateType?: "single" | "all_future" | "all";
  instanceId?: UUID;
  instanceStart?: string;
};

const toCreateTransport = ({
  extra_data: _extraData,
  ...payload
}: PlannedEventCreate): PlannedEventCreateTransport => payload;

const toUpdateTransport = ({
  extra_data: _extraData,
  ...payload
}: PlannedEventUpdate): PlannedEventUpdateTransport => payload;

export const plannedEventsApi = {
  fetchRange: async (start: string, end: string, status?: string) =>
    http.get<PlannedEventListResponse>(ENDPOINTS.PLANNED_EVENTS.BASE, {
      start,
      end,
      status,
      page: 1,
      size: 500,
    }),
  fetchRaw: async (page = 1, size = 100, status?: string) =>
    http.get<PlannedEventListResponse>(ENDPOINTS.PLANNED_EVENTS.RAW, {
      page,
      size,
      status,
    }),
  fetchByTask: async (taskId: UUID, page = 1, size = 100) =>
    http.get<PlannedEventListResponse>(
      ENDPOINTS.PLANNED_EVENTS.BY_TASK(taskId),
      { page, size },
    ),
  create: (payload: PlannedEventCreate): Promise<PlannedEvent> =>
    http.post<PlannedEventTransport>(
      ENDPOINTS.PLANNED_EVENTS.BASE,
      toCreateTransport(payload),
    ),
  getById: (id: UUID): Promise<PlannedEvent> =>
    http.get<PlannedEventTransport>(ENDPOINTS.PLANNED_EVENTS.BY_ID(id)),
  update: (
    id: UUID,
    payload: PlannedEventUpdate,
    options?: PlannedEventUpdateOptions,
  ): Promise<PlannedEvent> =>
    http.patch<PlannedEventTransport>(ENDPOINTS.PLANNED_EVENTS.BY_ID(id), toUpdateTransport(payload), {
      updateType: options?.updateType,
      instanceStart: options?.instanceStart,
    }),
  delete: (id: UUID, options?: PlannedEventDeleteOptions): Promise<void> =>
    http.delete<void>(ENDPOINTS.PLANNED_EVENTS.BY_ID(id), {
      deleteType: options?.deleteType,
      instanceStart: options?.instanceStart,
    }),
};
