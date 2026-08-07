import type { UUID } from "@/types/primitive";
import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { components } from "./generated/schema";

export type TimelogTemplate = components["schemas"]["TimelogTemplateResponse"];
export type TimelogTemplatesListResponse = components["schemas"]["ListResponse_TimelogTemplateResponse_TimelogTemplateListMeta_"];
export type TimelogTemplateCreateRequest = components["schemas"]["TimelogTemplateCreate"];
export type TimelogTemplateUpdateRequest = components["schemas"]["TimelogTemplateUpdate"];
export type TimelogTemplateReorderItem = components["schemas"]["TimelogTemplateReorderItem"];

export const timelogTemplatesApi = {
  list: (params?: {
    page?: number;
    size?: number;
    order_by?: "position" | "usage" | "recent";
  }): Promise<TimelogTemplatesListResponse> =>
    http.get<TimelogTemplatesListResponse>(ENDPOINTS.TIMELOGS.TEMPLATES.BASE, {
      page: params?.page,
      size: params?.size,
      order_by: params?.order_by,
    }),
  create: (payload: TimelogTemplateCreateRequest): Promise<TimelogTemplate> =>
    http.post<TimelogTemplate>(ENDPOINTS.TIMELOGS.TEMPLATES.BASE, payload),
  bulkCreate: (
    items: TimelogTemplateCreateRequest[],
  ): Promise<TimelogTemplatesListResponse> =>
    http.post<TimelogTemplatesListResponse>(ENDPOINTS.TIMELOGS.TEMPLATES.BULK, {
      items,
    }),
  update: (
    id: UUID,
    payload: TimelogTemplateUpdateRequest,
  ): Promise<TimelogTemplate> =>
    http.patch<TimelogTemplate>(
      ENDPOINTS.TIMELOGS.TEMPLATES.BY_ID(id),
      payload,
    ),
  remove: (id: UUID): Promise<void> =>
    http.delete<void>(ENDPOINTS.TIMELOGS.TEMPLATES.BY_ID(id)),
  reorder: (items: TimelogTemplateReorderItem[]): Promise<void> =>
    http.patch<void>(ENDPOINTS.TIMELOGS.TEMPLATES.REORDER, { items }),
  bumpUsage: (id: UUID): Promise<TimelogTemplate> =>
    http.post<TimelogTemplate>(ENDPOINTS.TIMELOGS.TEMPLATES.BUMP_USAGE(id)),
};
