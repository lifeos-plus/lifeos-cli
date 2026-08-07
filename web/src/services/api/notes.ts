import { http } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { components } from "./generated/schema";
import type { PersonSummary } from "./types/common";
import { tagsApi, type Tag } from "./tags";
import type { UUID } from "@/types/primitive";

type NoteTransport = components["schemas"]["NoteResponse"];
type TaskSummaryTransport = components["schemas"]["TaskSummaryResponse"];
type TimelogSummaryTransport = components["schemas"]["TimelogSummaryResponse"];
export type TaskSummary = TaskSummaryTransport & {
  actual_effort_total?: number | null;
  actual_effort_self?: number | null;
  created_at?: string;
  estimated_effort?: number | null;
  notes_count?: number;
  parent_summary?: { id: UUID; content: string; status?: string | null } | null;
  priority?: number | null;
  timelogs_count?: number;
  updated_at?: string;
  vision_summary?: { id: UUID; name: string; status?: string | null } | null;
};
export type NoteTimelogSummary = TimelogSummaryTransport & {
  area_id?: UUID | null;
  area_summary?: { id: UUID; name?: string | null; color?: string | null } | null;
  end_time?: string | null;
  start_time?: string | null;
  task_summary?: TaskSummary | null;
};
export type NoteHabitActionSummary = components["schemas"]["HabitActionSummaryResponse"];
export type Note = Pick<NoteTransport, "content" | "created_at" | "id" | "updated_at"> &
  Partial<Omit<NoteTransport, "content" | "created_at" | "id" | "people" | "tags" | "task" | "tasks" | "timelogs" | "updated_at">> & {
    people?: PersonSummary[];
    tags?: Tag[];
    task?: TaskSummary | null;
    tasks?: TaskSummary[];
    timelogs?: NoteTimelogSummary[];
  };
export type NoteSummary = Pick<Note, "id" | "content" | "created_at" | "updated_at">;
export type NoteCreate = components["schemas"]["NoteCreate"];
export type NoteUpdate = components["schemas"]["NoteUpdate"];

// New interfaces for statistics and filtering
export interface NoteStats {
  total_notes: number;
  tag_stats: Array<{
    id: UUID;
    name: string;
    usage_count: number;
  }>;
  person_stats: Array<{
    id: UUID;
    name: string;
    display_name: string;
    usage_count: number;
  }>;
}

type NotePersonStatsResponse = components["schemas"]["NotePersonStatsResponse"];

export type NoteTagFilterMode = "any" | "all" | "none";
export type NotePersonFilterMode = "any" | "all" | "none";
export type NoteTaskFilterMode = "any" | "none" | "specific" | "has";

export interface NoteAdvancedSearchPayload {
  start_date?: string | null;
  end_date?: string | null;
  tag_ids?: UUID[] | null;
  tag_mode: NoteTagFilterMode;
  person_ids?: UUID[] | null;
  person_mode: NotePersonFilterMode;
  task_filter: NoteTaskFilterMode;
  task_id?: UUID | null;
  keyword?: string | null;
  sort_order?: "asc" | "desc";
}

interface NoteBatchTagUpdatePayload {
  mode: "add" | "replace";
  tag_ids: UUID[];
}

interface NoteBatchPersonUpdatePayload {
  mode: "add" | "replace";
  person_ids: UUID[];
}

interface NoteBatchTaskUpdatePayload {
  mode: "replace" | "clear";
  task_id?: UUID | null;
}

interface NoteBatchContentUpdatePayload {
  find_text: string;
  replace_text: string;
  case_sensitive?: boolean;
}

export interface NoteBatchUpdatePayload {
  note_ids: UUID[];
  operation: "tags" | "people" | "task" | "content";
  tags?: NoteBatchTagUpdatePayload;
  people?: NoteBatchPersonUpdatePayload;
  task?: NoteBatchTaskUpdatePayload;
  content?: NoteBatchContentUpdatePayload;
}

export interface NoteBatchUpdateResult {
  updated_count: number;
  failed_ids: UUID[];
  errors: string[];
}

export interface NoteBatchDeletePayload {
  note_ids: UUID[];
}

export interface NoteBatchDeleteResult {
  deleted_count: number;
  failed_ids: UUID[];
  errors: string[];
}

interface NoteBulkCreateItemPayload {
  content: string;
}

export interface NoteBulkCreateRequestPayload {
  notes: NoteBulkCreateItemPayload[];
  person_ids?: UUID[];
  tag_ids?: UUID[];
  task_id?: UUID | null;
  timelog_ids?: UUID[];
}

interface NoteBulkCreateFailedItem {
  index: number;
  content_preview: string;
  error: string;
}

interface NoteBulkCreateResponsePayload {
  created_notes: Note[];
  failed_items: NoteBulkCreateFailedItem[];
  created_count: number;
  failed_count: number;
}

type NoteListTransport = components["schemas"]["ListResponse_NoteResponse_NoteListMeta_"];
export type NoteListResponse = Omit<NoteListTransport, "items"> & { items: Note[] };

const toNote = (note: NoteTransport): Note => note;
const toNoteList = (response: NoteListTransport): NoteListResponse => ({
  ...response,
  items: response.items.map(toNote),
});

export const notesApi = {
  create: (noteData: NoteCreate) =>
    http.post<NoteTransport>(ENDPOINTS.NOTES.BASE, noteData).then(toNote),

  fetchAll: () => http.get<NoteListTransport>(ENDPOINTS.NOTES.BASE).then(toNoteList),

  fetchPaged: (
    params: {
      page?: number;
      size?: number;
      tag_id?: UUID;
      person_id?: UUID;
      task_id?: UUID;
      timelog_id?: UUID;
      habit_action_id?: UUID;
      keyword?: string;
      untagged?: boolean;
    },
    options?: { signal?: AbortSignal },
  ) => {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.append("page", params.page.toString());
    if (params.size) searchParams.append("size", params.size.toString());
    if (params.tag_id) searchParams.append("tag_id", params.tag_id.toString());
    if (params.person_id)
      searchParams.append("person_id", params.person_id.toString());
    if (params.keyword) searchParams.append("keyword", params.keyword);
    if (params.task_id)
      searchParams.append("task_id", params.task_id.toString());
    if (params.timelog_id)
      searchParams.append("timelog_id", params.timelog_id.toString());
    if (params.habit_action_id)
      searchParams.append("habit_action_id", params.habit_action_id.toString());
    if (params.untagged) searchParams.append("untagged", "true");

    const queryString = searchParams.toString();
    const url = `${ENDPOINTS.NOTES.BASE}${queryString ? `?${queryString}` : ""}`;

    return http
      .get<NoteListTransport>(url, undefined, { signal: options?.signal })
      .then(toNoteList);
  },

  // New method to get statistics (aggregated from split endpoints)
  getStats: async (): Promise<NoteStats> => {
    const [notes, tagUsage, personUsage] = await Promise.all([
      notesApi.fetchPaged({ page: 1, size: 1 }),
      tagsApi.getStatsBatch("note"),
      http.get<NotePersonStatsResponse>(ENDPOINTS.NOTES.STATS_PERSONS),
    ]);
    return {
      total_notes: notes.pagination.total,
      tag_stats: tagUsage.tag_stats.map((tagStat) => ({
        id: tagStat.id,
        name: "",
        usage_count: tagStat.usage_count,
      })),
      person_stats: personUsage.person_stats,
    };
  },

  update: (noteId: UUID, noteData: NoteUpdate) =>
    http.patch<NoteTransport>(ENDPOINTS.NOTES.BY_ID(noteId), noteData).then(toNote),

  delete: async (noteId: UUID): Promise<void> => {
    try {
      await http.delete<void>(ENDPOINTS.NOTES.BY_ID(noteId));
    } catch (err) {
      // Preserve enhanced error semantics similar to old api.ts implementation
      const anyErr = err as unknown as { status?: number; message?: string };
      if (anyErr && typeof anyErr === "object" && "status" in anyErr) {
        const status = anyErr.status ?? 0;
        const message =
          status === 404
            ? "Note not found (may have been already deleted)"
            : (anyErr.message ?? "Request failed");
        const e: Error & { status?: number } = new Error(message);
        e.status = status;
        throw err as Error;
      }
      throw err as Error;
    }
  },

  advancedSearch: (payload: NoteAdvancedSearchPayload) =>
    notesApi.fetchPaged({
      page: 1,
      size: 500,
      keyword: payload.keyword ?? undefined,
    }),

  batchUpdate: (payload: NoteBatchUpdatePayload) =>
    Promise.resolve({
      updated_count: 0,
      failed_ids: payload.note_ids,
      errors: ["Batch note update is not supported by LifeOS Web UI yet."],
    } satisfies NoteBatchUpdateResult),

  batchDelete: (payload: NoteBatchDeletePayload) =>
    Promise.allSettled(payload.note_ids.map((noteId) => notesApi.delete(noteId))).then(
      (results) => {
        const failedIds = payload.note_ids.filter(
          (_, index) => results[index].status === "rejected",
        );
        return {
          deleted_count: payload.note_ids.length - failedIds.length,
          failed_ids: failedIds,
          errors: [],
        } satisfies NoteBatchDeleteResult;
      },
    ),

  batchCreate: (payload: NoteBulkCreateRequestPayload) =>
    Promise.allSettled(
      payload.notes.map((note) => notesApi.create({ content: note.content })),
    ).then((results) => {
      const createdNotes = results
        .filter((result): result is PromiseFulfilledResult<Note> => result.status === "fulfilled")
        .map((result) => result.value);
      const failedItems = results.flatMap((result, index) =>
        result.status === "rejected"
          ? [
              {
                index,
                content_preview: payload.notes[index].content.slice(0, 80),
                error:
                  result.reason instanceof Error
                    ? result.reason.message
                    : String(result.reason),
              },
            ]
          : [],
      );
      return {
        created_notes: createdNotes,
        failed_items: failedItems,
        created_count: createdNotes.length,
        failed_count: failedItems.length,
      } satisfies NoteBulkCreateResponsePayload;
  }),
};
