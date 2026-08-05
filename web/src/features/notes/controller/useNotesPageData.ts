import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import type { UUID } from "@/types/primitive";
import {
  type Note as ApiNote,
  type NoteTagFilterMode,
  type NotePersonFilterMode,
  type NoteTaskFilterMode,
} from "@/services/api/notes";
import { useNotes } from "@/hooks/queries/useNotes";
import { useNoteFilters } from "@/features/notes/controller/useNoteFilters";
import {
  useNotesAdvancedSearchWithPagination,
  type NotesAdvancedSearchParams,
} from "@/hooks/queries/useNotesAdvancedSearch";
import { useAllTasks } from "@/hooks/queries/useTasks";
import { useSystemTimezone } from "@/hooks/useSystemTimezone";
import { useNoteCollapsePreference } from "@/hooks/notes/useNoteCollapsePreference";
import type { QueryMode } from "@/hooks/useQueryMode";
import type { PersonSummary, Task as ApiTask } from "@/services/api";
import { createDateBoundaries } from "@/utils/datetime";
import type { Note } from "@/types/newNotes";

export const NOTES_ADVANCED_PAGE_SIZE = 100;

export interface NotesPageData {
  filters: {
    tag_id?: UUID;
    person_id?: UUID;
    task_id?: UUID;
    keyword?: string;
    untagged?: boolean;
  };
  setFilters: React.Dispatch<
    React.SetStateAction<{
      tag_id?: UUID;
      person_id?: UUID;
      task_id?: UUID;
      keyword?: string;
      untagged?: boolean;
    }>
  >;
  notes: ReturnType<typeof useNotes>["notes"];
  isLoading: boolean;
  error: ReturnType<typeof useNotes>["error"];
  hasMore: boolean;
  isLoadingMore: boolean;
  stats: ReturnType<typeof useNotes>["stats"];
  isLoadingStats: boolean;
  createNote: ReturnType<typeof useNotes>["createNote"];
  deleteNote: ReturnType<typeof useNotes>["deleteNote"];
  loadMoreNotes: ReturnType<typeof useNotes>["loadMoreNotes"];
  timezonePreference: ReturnType<typeof useSystemTimezone>;
  activeTimezone: string;
  noteCollapsePreference: ReturnType<typeof useNoteCollapsePreference>;
  noteFilters: ReturnType<typeof useNoteFilters>;
  tasksForAdvancedSearch: Array<{ id: UUID; name: string }>;
  notesAdvancedSearch: ReturnType<typeof useNotesAdvancedSearchWithPagination>;
  notesAdvancedSearchRef: React.MutableRefObject<{
    search: (params: NotesAdvancedSearchParams) => void;
    clearSearch: () => void;
    refetch: () => void;
  }>;
  advancedSearchParams: {
    start_date: string | null;
    end_date: string | null;
    tag_mode: NoteTagFilterMode;
    tag_ids: UUID[];
    person_mode: NotePersonFilterMode;
    person_ids: UUID[];
    task_filter: NoteTaskFilterMode;
    task_id: UUID | null;
    keyword: string | null;
    sort_order: "asc" | "desc";
  };
  setAdvancedSearchParams: React.Dispatch<
    React.SetStateAction<{
      start_date: string | null;
      end_date: string | null;
      tag_mode: NoteTagFilterMode;
      tag_ids: UUID[];
      person_mode: NotePersonFilterMode;
      person_ids: UUID[];
      task_filter: NoteTaskFilterMode;
      task_id: UUID | null;
      keyword: string | null;
      sort_order: "asc" | "desc";
    }>
  >;
  advancedFormState: {
    start_date: Date | null;
    end_date: Date | null;
    tag_mode: NoteTagFilterMode;
    tag_ids: UUID[];
    person_mode: NotePersonFilterMode;
    person_ids: UUID[];
    task_filter: NoteTaskFilterMode;
    task_id: UUID | null;
    keyword: string;
    sort_order: "asc" | "desc";
  };
  mapApiNoteToLocal: (apiNote: ApiNote) => Note;
  advancedNotes: Note[];
  canCopyAdvancedResults: boolean;
  personLookup: Map<string, PersonSummary>;
}

export function useNotesPageData(
  options: { queryMode?: QueryMode } = {},
): NotesPageData {
  const [filters, setFilters] = useState<{
    tag_id?: UUID;
    person_id?: UUID;
    task_id?: UUID;
    keyword?: string;
    untagged?: boolean;
  }>({});

  const {
    notes,
    isLoading,
    error,
    hasMore,
    isLoadingMore,
    stats,
    isLoadingStats,
    createNote,
    deleteNote,
    loadMoreNotes,
  } = useNotes(filters);

  const timezonePreference = useSystemTimezone();
  const activeTimezone = timezonePreference.timezone;
  const noteCollapsePreference = useNoteCollapsePreference();

  const [advancedSearchParams, setAdvancedSearchParams] = useState(() => {
    return {
      start_date: null as string | null,
      end_date: null as string | null,
      tag_mode: "any" as NoteTagFilterMode,
      tag_ids: [] as UUID[],
      person_mode: "any" as NotePersonFilterMode,
      person_ids: [] as UUID[],
      task_filter: "any" as NoteTaskFilterMode,
      task_id: null as UUID | null,
      keyword: null as string | null,
      sort_order: "desc" as "asc" | "desc",
    };
  });

  const notesAdvancedSearch = useNotesAdvancedSearchWithPagination(
    NOTES_ADVANCED_PAGE_SIZE,
  );

  const notesAdvancedSearchRef = useRef({
    search: notesAdvancedSearch.search,
    clearSearch: notesAdvancedSearch.clearSearch,
    refetch: notesAdvancedSearch.refetch,
  });

  useEffect(() => {
    notesAdvancedSearchRef.current = {
      search: notesAdvancedSearch.search,
      clearSearch: notesAdvancedSearch.clearSearch,
      refetch: notesAdvancedSearch.refetch,
    };
  }, [
    notesAdvancedSearch.search,
    notesAdvancedSearch.clearSearch,
    notesAdvancedSearch.refetch,
  ]);

  const shouldLoadTasks =
    options.queryMode !== undefined ? options.queryMode === "advanced" : true;
  const { data: allFlatTasksRaw } = useAllTasks({
    excludeStatus: ["done", "cancelled"],
    enabled: shouldLoadTasks,
  });
  const allFlatTasks = useMemo(() => allFlatTasksRaw ?? [], [allFlatTasksRaw]);

  const noteFilterInput = useMemo(
    () =>
      notes.map((note) => ({
        id: note.id,
        content: note.content,
        createdAt: new Date(note.created_at),
        people: note.people,
        tags: note.tags,
        task: note.task,
        timelogs: note.timelogs,
        habit_actions: note.habit_actions,
      })),
    [notes],
  );

  const noteFilters = useNoteFilters(
    noteFilterInput,
    stats || null,
    async (filter) => {
      setFilters(filter || {});
    },
  );

  const tasksForAdvancedSearch = useMemo(
    () =>
      (allFlatTasks as ApiTask[]).map((task) => ({
        id: task.id,
        name: task.content,
      })),
    [allFlatTasks],
  );

  const personLookup = useMemo(() => {
    const map = new Map<string, PersonSummary>();
    noteFilters.uniquePersons.forEach((person) => {
      map.set(person.id, person);
    });
    return map;
  }, [noteFilters.uniquePersons]);

  const mapApiNoteToLocal = useCallback(
    (apiNote: ApiNote) => ({
      id: apiNote.id,
      content: apiNote.content,
      createdAt: new Date(apiNote.created_at),
      people: apiNote.people,
      tags: apiNote.tags,
      task: apiNote.task,
      timelogs: apiNote.timelogs,
      habit_actions: apiNote.habit_actions,
    }),
    [],
  );

  const advancedNotes = useMemo(
    () => notesAdvancedSearch.data.map(mapApiNoteToLocal),
    [notesAdvancedSearch.data, mapApiNoteToLocal],
  );

  const canCopyAdvancedResults = advancedNotes.length > 0;

  useEffect(() => {
    setAdvancedSearchParams((prev) => {
      let nextStart = prev.start_date;
      let nextEnd = prev.end_date;

      if (prev.start_date) {
        const startDate = new Date(prev.start_date);
        if (!Number.isNaN(startDate.getTime())) {
          const { startOfDay } = createDateBoundaries(
            startDate,
            activeTimezone,
          );
          nextStart = startOfDay.toISOString();
        }
      }

      if (prev.end_date) {
        const endDate = new Date(prev.end_date);
        if (!Number.isNaN(endDate.getTime())) {
          const { endOfDay } = createDateBoundaries(endDate, activeTimezone);
          nextEnd = endOfDay.toISOString();
        }
      }

      if (prev.start_date === nextStart && prev.end_date === nextEnd) {
        return prev;
      }
      return {
        ...prev,
        start_date: nextStart,
        end_date: nextEnd,
      };
    });
  }, [activeTimezone]);

  const advancedFormState = useMemo(
    () => ({
      start_date: advancedSearchParams.start_date
        ? new Date(advancedSearchParams.start_date)
        : null,
      end_date: advancedSearchParams.end_date
        ? new Date(advancedSearchParams.end_date)
        : null,
      tag_mode: advancedSearchParams.tag_mode,
      tag_ids: advancedSearchParams.tag_ids,
      person_mode: advancedSearchParams.person_mode,
      person_ids: advancedSearchParams.person_ids,
      task_filter: advancedSearchParams.task_filter,
      task_id: advancedSearchParams.task_id,
      keyword: advancedSearchParams.keyword ?? "",
      sort_order: advancedSearchParams.sort_order,
    }),
    [advancedSearchParams],
  );

  return {
    filters,
    setFilters,
    notes,
    isLoading,
    error,
    hasMore,
    isLoadingMore,
    stats,
    isLoadingStats,
    createNote,
    deleteNote,
    loadMoreNotes,
    timezonePreference,
    activeTimezone,
    noteCollapsePreference,
    noteFilters,
    tasksForAdvancedSearch,
    notesAdvancedSearch,
    notesAdvancedSearchRef,
    advancedSearchParams,
    setAdvancedSearchParams,
    advancedFormState,
    mapApiNoteToLocal,
    advancedNotes,
    canCopyAdvancedResults,
    personLookup,
  };
}
