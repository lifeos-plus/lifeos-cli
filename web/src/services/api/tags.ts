import type { UUID } from "@/types/primitive";
import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { components, operations } from "./generated/schema";

type TagSelectorTransport = components["schemas"]["TagSelectorResponse"];
type TagTransport = components["schemas"]["TagResponse"];
export type Tag = TagSelectorTransport & Partial<Omit<TagTransport, keyof TagSelectorTransport>>;
export type TagCreate = components["schemas"]["TagCreate"];
export type TagUpdate = components["schemas"]["TagUpdate"];
export type TagUsageStats = components["schemas"]["TagUsageResponse"];
type TagCategoryTransport = components["schemas"]["TagCategoryResponse"];
export type TagCategoryOption = Omit<TagCategoryTransport, "entity_type"> & {
  entity_type?: TagCategoryTransport["entity_type"];
};
export type TagCategoryCreate = components["schemas"]["TagCategoryCreate"];
export type TagCategoryUpdate = components["schemas"]["TagCategoryUpdate"];
export type TagBulkUpdateRequest = components["schemas"]["TagBulkCategoryUpdate"];
export type TagBulkUpdateResponse = components["schemas"]["TagBulkUpdateResponse"];

export type TagListFieldsMode = "selector" | "full";

type TagListTransport = components["schemas"]["ListResponse_Union_TagSelectorResponse__TagResponse__TagListMeta_"];
export type TagListResponse = Omit<TagListTransport, "items"> & { items: Tag[] };
type TagEntityTypesResponse = operations["list_tag_entity_types_api_v1_tags_entity_types__get"]["responses"][200]["content"]["application/json"];
type TagCategoriesResponse = operations["list_tag_categories_api_v1_tags_categories__get"]["responses"][200]["content"]["application/json"];

export const tagsApi = {
  getAll: (params?: {
    entity_type?: string;
    category?: string;
    page?: number;
    size?: number;
    fields?: TagListFieldsMode;
  }): Promise<TagListResponse> => http.get<TagListTransport>(ENDPOINTS.TAGS.BASE, params),
  getEntityTypes: (): Promise<TagEntityTypesResponse> =>
    http.get<TagEntityTypesResponse>(ENDPOINTS.TAGS.ENTITY_TYPES),
  getCategories: (entityType: string): Promise<TagCategoriesResponse> =>
    http.get<TagCategoriesResponse>(ENDPOINTS.TAGS.CATEGORIES, {
      entity_type: entityType,
    }),
  createCategory: (
    payload: TagCategoryCreate,
    entityType: string,
  ): Promise<TagCategoryOption> =>
    http.post<TagCategoryTransport>(ENDPOINTS.TAGS.CATEGORIES, payload, {
      entity_type: entityType,
    }),
  renameCategory: (
    value: string,
    payload: TagCategoryUpdate,
    entityType: string,
  ): Promise<TagCategoryOption> =>
    http.patch<TagCategoryTransport>(ENDPOINTS.TAGS.CATEGORY_BY_VALUE(value), payload, {
      entity_type: entityType,
    }),
  create: (tag: TagCreate): Promise<Tag> =>
    http.post<TagTransport>(ENDPOINTS.TAGS.BASE, tag),
  getById: (id: UUID): Promise<Tag> =>
    http.get<TagTransport>(ENDPOINTS.TAGS.BY_ID(id)),
  update: (id: UUID, tag: TagUpdate): Promise<Tag> =>
    http.patch<TagTransport>(ENDPOINTS.TAGS.BY_ID(id), tag),
  bulkUpdateCategories: (
    payload: TagBulkUpdateRequest,
  ): Promise<TagBulkUpdateResponse> =>
    http.patch<TagBulkUpdateResponse>(ENDPOINTS.TAGS.BATCH_UPDATE, payload),
  delete: (id: UUID): Promise<void> => http.delete<void>(ENDPOINTS.TAGS.BY_ID(id)),
  getUsage: (id: UUID): Promise<TagUsageStats> =>
    http.get<TagUsageStats>(ENDPOINTS.TAGS.USAGE(id)),
  getStatsBatch: (entityType: string) =>
    http.get<components["schemas"]["TagUsageByEntityResponse"]>(
      ENDPOINTS.STATS.TAGS_USAGE(entityType),
    ),
};
