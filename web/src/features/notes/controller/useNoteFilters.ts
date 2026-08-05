import { useState, useMemo, useCallback } from "react";
import type { Note } from "@/types/newNotes";
import type { PersonSummary, Tag } from "@/services/api";
import type { NoteStats } from "@/services/api/notes";
import type { UUID } from "@/types/primitive";

export function useNoteFilters(
  notes: Note[],
  stats: NoteStats | null,
  onLoadFilteredNotes: (
    filter: {
      tag_id?: UUID;
      person_id?: UUID;
      task_id?: UUID;
      keyword?: string;
      untagged?: boolean;
    } | null,
  ) => Promise<void>,
) {
  const [selectedFilterTags, setSelectedFilterTags] = useState<Tag[]>([]);
  const [selectedFilterPersons, setSelectedFilterPersons] = useState<
    PersonSummary[]
  >([]);
  const [searchKeyword, setSearchKeyword] = useState<string>("");
  const [isSearchApplied, setIsSearchApplied] = useState<boolean>(false);
  const [selectedFilterTaskId, setSelectedFilterTaskId] = useState<
    string | null
  >(null);
  const [showUntaggedOnly, setShowUntaggedOnly] = useState<boolean>(false);

  // Filter notes based on selected tag or person (for display purposes)
  // This maintains the original behavior where clicking tag/person immediately filters
  const filteredNotes = useMemo(() => {
    if (showUntaggedOnly) {
      return notes.filter((note) => !note.tags || note.tags.length === 0);
    }
    if (selectedFilterTags.length === 1) {
      return notes.filter((note) =>
        note.tags?.some((tag) => tag.id === selectedFilterTags[0].id),
      );
    }
    if (selectedFilterPersons.length === 1) {
      return notes.filter((note) =>
        note.people?.some(
          (person) => person.id === selectedFilterPersons[0].id,
        ),
      );
    }
    if (selectedFilterTaskId != null) {
      return notes.filter(
        (note) => note.task?.id === String(selectedFilterTaskId),
      );
    }
    return notes;
  }, [
    notes,
    selectedFilterTags,
    selectedFilterPersons,
    selectedFilterTaskId,
    showUntaggedOnly,
  ]);

  // Use server-side statistics instead of local calculation
  const tagUsageStats = useMemo(() => {
    if (!stats) return {};

    const tagStats: { [key: UUID]: number } = {};
    stats.tag_stats.forEach((tagStat) => {
      tagStats[tagStat.id] = tagStat.usage_count;
    });
    return tagStats;
  }, [stats]);

  const personUsageStats = useMemo(() => {
    if (!stats) return {};

    const personStats: { [key: UUID]: number } = {};
    stats.person_stats.forEach((personStat) => {
      personStats[personStat.id] = personStat.usage_count;
    });
    return personStats;
  }, [stats]);

  // Get unique persons from server statistics
  const uniquePersons = useMemo(() => {
    if (!stats) return [];

    return stats.person_stats
      .map((personStat) => ({
        id: personStat.id,
        name: personStat.name,
        display_name: personStat.display_name,
        primary_nickname: personStat.display_name, // Use display_name as primary nickname
        birth_date: null,
        location: null,
        tags: [],
      }))
      .sort((a, b) => a.display_name.localeCompare(b.display_name));
  }, [stats]);

  // Handle tag click for filtering (immediate effect)
  const handleTagClick = useCallback(
    async (tag: Tag) => {
      if (selectedFilterTags.some((t) => t.id === tag.id)) {
        // If clicking the same tag, clear the filter
        setSelectedFilterTags([]);
        setSelectedFilterPersons([]);
        setSelectedFilterTaskId(null);
        setShowUntaggedOnly(false);
        await onLoadFilteredNotes(null);
      } else {
        // Set new filter tag and clear person filter and untagged filter
        setSelectedFilterTags([tag]);
        setSelectedFilterPersons([]);
        setSelectedFilterTaskId(null);
        setShowUntaggedOnly(false);
        await onLoadFilteredNotes({ tag_id: tag.id });
      }
    },
    [selectedFilterTags, onLoadFilteredNotes],
  );

  // Handle person click for filtering (immediate effect)
  const handlePersonClick = useCallback(
    async (person: PersonSummary) => {
      if (selectedFilterPersons.some((p) => p.id === person.id)) {
        // If clicking the same person, clear the filter
        setSelectedFilterPersons([]);
        setSelectedFilterTags([]);
        setSelectedFilterTaskId(null);
        setShowUntaggedOnly(false);
        await onLoadFilteredNotes(null);
      } else {
        // Set new filter person and clear tag filter and untagged filter
        setSelectedFilterPersons([person]);
        setSelectedFilterTags([]);
        setSelectedFilterTaskId(null);
        setShowUntaggedOnly(false);
        await onLoadFilteredNotes({ person_id: person.id });
      }
    },
    [selectedFilterPersons, onLoadFilteredNotes],
  );

  // Handle task click for filtering (immediate effect)
  const handleTaskClick = useCallback(
    async (taskId: UUID) => {
      if (selectedFilterTaskId === String(taskId)) {
        setSelectedFilterTaskId(null);
        setSelectedFilterTags([]);
        setSelectedFilterPersons([]);
        setShowUntaggedOnly(false);
        await onLoadFilteredNotes(null);
      } else {
        setSelectedFilterTaskId(taskId);
        setSelectedFilterTags([]);
        setSelectedFilterPersons([]);
        setShowUntaggedOnly(false);
        await onLoadFilteredNotes({ task_id: taskId });
      }
    },
    [selectedFilterTaskId, onLoadFilteredNotes],
  );

  // Handle untagged filter toggle
  const handleUntaggedToggle = useCallback(async () => {
    if (showUntaggedOnly) {
      // If currently showing untagged, clear all filters
      setShowUntaggedOnly(false);
      setSelectedFilterTags([]);
      setSelectedFilterPersons([]);
      await onLoadFilteredNotes(null);
    } else {
      // Set untagged filter and clear other filters
      setShowUntaggedOnly(true);
      setSelectedFilterTags([]);
      setSelectedFilterPersons([]);
      await onLoadFilteredNotes({ untagged: true });
    }
  }, [showUntaggedOnly, onLoadFilteredNotes]);

  // Apply text search filter to backend (independent of tag/person filters)
  const applyTextSearch = useCallback(async () => {
    setIsSearchApplied(true); // Mark that search has been applied

    if (searchKeyword.trim()) {
      // Apply text search while preserving current tag/person/untagged filters
      const filter: {
        tag_id?: UUID;
        person_id?: UUID;
        task_id?: string;
        keyword?: string;
        untagged?: boolean;
      } = {};

      if (selectedFilterTags.length === 1) {
        filter.tag_id = selectedFilterTags[0].id;
      }
      if (selectedFilterPersons.length === 1) {
        filter.person_id = selectedFilterPersons[0].id;
      }
      if (selectedFilterTaskId != null) {
        filter.task_id = selectedFilterTaskId;
      }
      if (showUntaggedOnly) {
        filter.untagged = true;
      }
      filter.keyword = searchKeyword.trim();

      await onLoadFilteredNotes(filter);
    } else {
      // Clear text search, but keep tag/person/untagged filters
      const filter: {
        tag_id?: UUID;
        person_id?: UUID;
        task_id?: string;
        untagged?: boolean;
      } | null = {};

      if (selectedFilterTags.length === 1) {
        filter.tag_id = selectedFilterTags[0].id;
      }
      if (selectedFilterPersons.length === 1) {
        filter.person_id = selectedFilterPersons[0].id;
      }
      if (selectedFilterTaskId != null) {
        filter.task_id = selectedFilterTaskId;
      }
      if (showUntaggedOnly) {
        filter.untagged = true;
      }

      if (Object.keys(filter).length > 0) {
        await onLoadFilteredNotes(filter);
      } else {
        await onLoadFilteredNotes(null);
      }
    }
  }, [
    selectedFilterTags,
    selectedFilterPersons,
    selectedFilterTaskId,
    showUntaggedOnly,
    searchKeyword,
    onLoadFilteredNotes,
  ]);

  // Clear all filters
  const clearAllFilters = useCallback(async () => {
    setSelectedFilterTags([]);
    setSelectedFilterPersons([]);
    setSearchKeyword("");
    setIsSearchApplied(false); // Reset search applied state
    setShowUntaggedOnly(false);
    setSelectedFilterTaskId(null);
    await onLoadFilteredNotes(null);
  }, [onLoadFilteredNotes]);

  return {
    selectedFilterTaskId,
    selectedFilterTags,
    selectedFilterPersons,
    showUntaggedOnly,

    // Filtered results
    filteredNotes,

    // Statistics and derived data from server
    tagUsageStats,
    personUsageStats,
    uniquePersons,

    // Filter actions
    handleTagClick,
    handlePersonClick,
    handleTaskClick,
    handleUntaggedToggle,
    applyTextSearch,
    clearAllFilters,

    // Search state
    isSearchApplied,
    searchKeyword,

    // Direct setters for external use
    setSelectedFilterTag: (tag: Tag | null) =>
      setSelectedFilterTags(tag ? [tag] : []),
    setSelectedFilterPerson: (person: PersonSummary | null) =>
      setSelectedFilterPersons(person ? [person] : []),
    setSearchKeyword,
  };
}
