import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { components } from "./generated/schema";
import type { UUID } from "@/types/primitive";

export type Vision = components["schemas"]["VisionResponse"];
export type VisionCreate = components["schemas"]["VisionCreate"];
export type VisionUpdate = components["schemas"]["VisionUpdate"];
export type VisionWithTasks = components["schemas"]["VisionWithTasksResponse"];
export type VisionStatsResponse = components["schemas"]["VisionStatsResponse"];

export interface VisionExperienceRateUpdatePayload {
  id: UUID;
  experience_rate_per_hour: number | null;
}

export type VisionListResponse = components["schemas"]["ListResponse_VisionResponse_VisionListMeta_"];

export const visionsApi = {
  async getAll(
    statusFilter?: string,
    page: number = 1,
    size: number = 100,
  ): Promise<VisionListResponse> {
    return http.get<VisionListResponse>(ENDPOINTS.VISIONS.BASE, {
      status_filter: statusFilter,
      page,
      size,
    });
  },

  async getById(id: UUID): Promise<Vision> {
    return http.get<Vision>(ENDPOINTS.VISIONS.BY_ID(id));
  },

  async getWithTasks(id: UUID): Promise<Vision> {
    return http.get<Vision>(ENDPOINTS.VISIONS.WITH_TASKS(id));
  },

  async create(vision: VisionCreate): Promise<VisionWithTasks> {
    return http.post<VisionWithTasks>(ENDPOINTS.VISIONS.BASE, vision);
  },

  async update(id: UUID, vision: VisionUpdate): Promise<Vision> {
    return http.patch<Vision>(ENDPOINTS.VISIONS.BY_ID(id), vision);
  },

  async delete(id: UUID): Promise<void> {
    return http.delete<void>(ENDPOINTS.VISIONS.BY_ID(id));
  },

  async addExperience(id: UUID, experiencePoints: number): Promise<Vision> {
    return http.post<Vision>(ENDPOINTS.VISIONS.ADD_EXPERIENCE(id), {
      experience_points: experiencePoints,
    });
  },

  async harvest(id: UUID): Promise<Vision> {
    return http.post<Vision>(ENDPOINTS.VISIONS.HARVEST(id));
  },

  async getStats(id: UUID): Promise<VisionStatsResponse> {
    return http.get<VisionStatsResponse>(ENDPOINTS.VISIONS.STATS(id));
  },

  async recomputeEfforts(
    id: UUID,
  ): Promise<components["schemas"]["VisionRecomputeResponse"]> {
    return http.post<components["schemas"]["VisionRecomputeResponse"]>(
      ENDPOINTS.VISIONS.RECOMPUTE_EFFORTS(id),
    );
  },

  async syncExperience(id: UUID): Promise<Vision> {
    return http.post<Vision>(ENDPOINTS.VISIONS.SYNC_EXPERIENCE(id));
  },

  async bulkUpdateExperienceRates(
    items: VisionExperienceRateUpdatePayload[],
  ): Promise<Vision[]> {
    const updated = await Promise.all(
      items.map((item) =>
        visionsApi.update(item.id, {
          experience_rate_per_hour: item.experience_rate_per_hour,
        }),
      ),
    );
    return updated;
  },
};
