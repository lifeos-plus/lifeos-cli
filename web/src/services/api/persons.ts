import { ENDPOINTS } from "./endpoints";
import { http } from "./client";
import type { components } from "./generated/schema";
import type { UUID } from "@/types/primitive";

export type Anniversary = components["schemas"]["AnniversaryResponse"];

// UI-only drafts for unsupported anniversary mutations; no network DTO exists yet.
export interface AnniversaryCreate {
  name: string;
  date: string;
}

export interface AnniversaryUpdate {
  name?: string;
  date?: string;
}

export type AnniversaryListResponse = components["schemas"]["ListResponse_AnniversaryResponse_AnniversaryListMeta_"];
export type Person = components["schemas"]["PersonResponse"];
export type PersonCreate = components["schemas"]["PersonCreate"];
export type PersonUpdate = components["schemas"]["PersonUpdate"];
export type PersonActivityItem = components["schemas"]["PersonActivityResponse"];

export type PersonActivityType = PersonActivityItem["type"];

export type PersonListResponse = components["schemas"]["ListResponse_PersonResponse_PersonListMeta_"];
export type PersonDetailListResponse = PersonListResponse;
export type PersonActivitiesResponse = components["schemas"]["ListResponse_PersonActivityResponse_PersonActivityMeta_"];

const unsupported = () =>
  Promise.reject(new Error("This person sub-feature is not supported by LifeOS Web UI yet."));

export const personsApi = {
  getAll: async (
    page: number = 1,
    size: number = 100,
    search?: string,
    tagFilter?: string,
    tagId?: UUID,
  ): Promise<PersonListResponse> =>
    http.get<PersonListResponse>(ENDPOINTS.PERSONS.BASE, {
      page,
      size,
      search,
      tag_filter: tagFilter,
      tag_id: tagId,
    }),
  getById: (id: UUID): Promise<Person> =>
    http.get<Person>(ENDPOINTS.PERSONS.BY_ID(id)),
  create: (person: PersonCreate): Promise<Person> =>
    http.post<Person>(ENDPOINTS.PERSONS.BASE, person),
  update: (id: UUID, person: PersonUpdate): Promise<Person> =>
    http.patch<Person>(ENDPOINTS.PERSONS.BY_ID(id), person),
  delete: (id: UUID): Promise<void> =>
    http.delete<void>(ENDPOINTS.PERSONS.BY_ID(id)),
  getActivities: (
    id: UUID,
    page: number = 1,
    size: number = 50,
    activityType?: PersonActivityType,
  ): Promise<PersonActivitiesResponse> =>
    http.get<PersonActivitiesResponse>(ENDPOINTS.PERSONS.ACTIVITIES(id), {
      page,
      size,
      activity_type: activityType,
    }),
  createAnniversary: (
    _personId: UUID,
    _anniversary: AnniversaryCreate,
  ): Promise<Anniversary> => unsupported(),
  getAnniversaries: (personId: UUID): Promise<AnniversaryListResponse> =>
    http.get<AnniversaryListResponse>(ENDPOINTS.PERSONS.ANNIVERSARIES(personId)),
  deleteAnniversary: (
    _personId: UUID,
    _anniversaryId: UUID,
  ): Promise<void> => unsupported(),
  updateAnniversary: (
    _personId: UUID,
    _anniversaryId: UUID,
    _payload: AnniversaryUpdate,
  ): Promise<Anniversary> => unsupported(),
  addTag: (_personId: UUID, _tagId: UUID): Promise<Person> => unsupported(),
  removeTag: (_personId: UUID, _tagId: UUID): Promise<Person> => unsupported(),
  searchByTag: async (
    tagName: string,
    page: number = 1,
    size: number = 50,
  ): Promise<PersonDetailListResponse> =>
    http.get<PersonDetailListResponse>(ENDPOINTS.PERSONS.SEARCH_BY_TAG, {
      tag_name: tagName,
      page,
      size,
    }),
};
