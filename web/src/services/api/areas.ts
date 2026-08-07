import type { UUID } from "@/types/primitive";
import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { components, operations } from "./generated/schema";

type AreaTransport = components["schemas"]["AreaResponse"];
export type Area = Pick<AreaTransport, "color" | "id" | "is_active" | "name"> &
  Partial<Omit<AreaTransport, "color" | "id" | "is_active" | "name">>;
export type AreaCreate = components["schemas"]["AreaCreate"];
export type AreaUpdate = components["schemas"]["AreaUpdate"];
type AreaListTransport = components["schemas"]["ListResponse_AreaResponse_AreaListMeta_"];
export type AreaListResponse = Omit<AreaListTransport, "items"> & { items: Area[] };
type AreaOrderResponse = operations["get_area_order_api_v1_areas_order_get"]["responses"][200]["content"]["application/json"];

export const areasApi = {
  async getAreas(
    includeInactive: boolean = false,
    page: number = 1,
    size: number = 100,
  ): Promise<AreaListResponse> {
    return http.get<AreaListTransport>(ENDPOINTS.AREAS.BASE, {
      include_inactive: includeInactive,
      page,
      size,
    });
  },
  getArea: (id: UUID): Promise<Area> =>
    http.get<AreaTransport>(ENDPOINTS.AREAS.BY_ID(id)),
  createArea: (area: AreaCreate): Promise<Area> =>
    http.post<AreaTransport>(ENDPOINTS.AREAS.BASE, area),
  updateArea: (
    id: UUID,
    area: AreaUpdate,
  ): Promise<Area> =>
    http.patch<AreaTransport>(ENDPOINTS.AREAS.BY_ID(id), area),
  deleteArea: (id: UUID): Promise<void> =>
    http.delete<void>(ENDPOINTS.AREAS.BY_ID(id)),
  activateArea: (id: UUID): Promise<Area> =>
    http.post<AreaTransport>(ENDPOINTS.AREAS.ACTIVATE(id)),
  getOrder: async (): Promise<AreaOrderResponse> =>
    http.get<AreaOrderResponse>(ENDPOINTS.AREAS.ORDER),
  setOrder: async (order: UUID[]): Promise<void> =>
    http.put<void>(ENDPOINTS.AREAS.ORDER, order),
  resetOrder: async (): Promise<void> =>
    http.delete<void>(ENDPOINTS.AREAS.ORDER),
};
