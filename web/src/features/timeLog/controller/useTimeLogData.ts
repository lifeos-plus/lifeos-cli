import { useState, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  invalidateTimelogLatestEndTime,
  invalidateTimelogList,
} from "@/services/api/cacheInvalidation/timelogs";
import { timelogsApi } from "@/services/api/timelogs";
import { processTimeEntries, type ProcessedEntry } from "@/utils/datetime";
import { logger } from "@/utils/core";
import { createDateBoundaries, sortTimeEntriesByTime } from "@/utils/datetime";
import { timelogsKeys } from "@/services/api/queryKeys";
import { useToast } from "@/contexts/ToastContext";
import type { UUID } from "@/types/primitive";

import type { QueryMode } from "@/hooks/useQueryMode";

interface UseTimeLogDataProps {
  selectedDate: Date;
  sortOrder: "asc" | "desc";
  queryMode: QueryMode;
  saveScrollPosition: (position: number) => void;
  timezone: string;
  ready?: boolean;
}

interface UseTimeLogDataReturn {
  processedEntries: ProcessedEntry[];
  loading: boolean;
  error: string | null;
  selectedEntryIds: Set<UUID>;
  isSelectMode: boolean;
  deletingEntryId: UUID | null;
  deletingEntryCount: number;
  requestDeleteEntry: (entryId: UUID) => void;
  confirmDeleteEntry: () => Promise<void>;
  cancelDeleteEntry: () => void;
  requestBatchDelete: () => void;
  confirmBatchDelete: () => Promise<void>;
  cancelBatchDelete: () => void;
  setIsSelectMode: (value: boolean) => void;
  // Advanced search support
  setAdvancedSearchResultsFromHook: (results: ProcessedEntry[]) => void;
  selectionHandlers: {
    handleSelectEntry: (entryId: UUID, checked: boolean) => void;
    handleSelectAll: () => void;
    handleSelectInverse: () => void;
    handleClearSelection: () => void;
  };
}

export const useTimeLogData = ({
  selectedDate,
  sortOrder,
  queryMode,
  saveScrollPosition,
  timezone,
  ready = true,
}: UseTimeLogDataProps): UseTimeLogDataReturn => {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { startOfDay, endOfDay } = createDateBoundaries(selectedDate, timezone);
  const singleDayListFilters = {
    start: startOfDay.toISOString(),
    end: endOfDay.toISOString(),
    sort_order: sortOrder,
    timezone,
  };

  // Local state for UI interactions
  const [selectedEntryIds, setSelectedEntryIds] = useState<Set<UUID>>(
    new Set(),
  );
  const [isSelectMode, setIsSelectMode] = useState(false);
  const [deletingEntryId, setDeletingEntryId] = useState<UUID | null>(null);
  const [deletingEntryCount, setDeletingEntryCount] = useState<number>(0);
  const [advancedSearchResults, setAdvancedSearchResults] = useState<
    ProcessedEntry[]
  >([]);

  useEffect(() => {
    if (queryMode === "advanced") {
      return;
    }

    setSelectedEntryIds(new Set());
    setIsSelectMode(false);
    setDeletingEntryCount(0);
    setAdvancedSearchResults([]);
  }, [queryMode]);

  // Query for single day entries
  const {
    data: singleDayData,
    isLoading: isLoadingSingleDay,
    error: singleDayError,
  } = useQuery({
    queryKey: timelogsKeys.list(singleDayListFilters),
    queryFn: async () => {
      const timelogs = await timelogsApi.fetchRange(
        startOfDay.toISOString(),
        endOfDay.toISOString(),
      );
      const events = timelogs.items;

      // Sort by start time, then end time for stable ordering
      sortTimeEntriesByTime(events);

      // Process entries for validation and placeholders
      let processed = processTimeEntries(events, selectedDate, timezone);
      // Apply sort order
      if (sortOrder === "desc") {
        processed = [...processed].reverse();
      }

      return processed;
    },
    enabled: ready && queryMode === "single",
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Process entries based on query mode
  let processedEntries: ProcessedEntry[] = [];
  if (queryMode === "advanced") {
    processedEntries = advancedSearchResults;
  } else if (queryMode === "single") {
    processedEntries = singleDayData ?? [];
  }

  const loading = queryMode === "single" ? isLoadingSingleDay : false;
  const error =
    queryMode === "single" ? (singleDayError?.message ?? null) : null;

  // Delete single entry mutation
  const deleteEntryMutation = useMutation({
    mutationFn: (entryId: UUID) => timelogsApi.delete(entryId),
    onSuccess: () => {
      toast.showSuccess("时间日志删除成功！");
      invalidateTimelogList(queryClient, singleDayListFilters);
      invalidateTimelogLatestEndTime(queryClient);
    },
    onError: (err: Error) => {
      logger.error("Failed to delete entry:", err);
      toast.showError("删除时间日志失败", err.message);
    },
  });

  // Batch delete mutation
  const batchDeleteMutation = useMutation({
    mutationFn: (eventIds: UUID[]) => timelogsApi.batchDelete(eventIds),
    onSuccess: (result) => {
      if (result.failed_ids.length > 0) {
        toast.showError(
          "批量删除部分失败",
          `成功删除${result.deleted_count}条记录，${result.failed_ids.length}条删除失败：${result.errors.join(", ")}`,
        );
      } else {
        toast.showSuccess("批量删除成功！");
        // Clear selection after successful deletion
        setSelectedEntryIds(new Set());
        setIsSelectMode(false);
      }
      invalidateTimelogList(queryClient, singleDayListFilters);
      invalidateTimelogLatestEndTime(queryClient);
    },
    onError: (err: Error) => {
      logger.error("Failed to batch delete entries:", err);
      toast.showError("批量删除时间日志失败", err.message);
    },
  });

  const requestDeleteEntry = (entryId: UUID) => {
    setDeletingEntryId(entryId);
  };

  const confirmDeleteEntry = async () => {
    if (!deletingEntryId) return;
    try {
      // Save current scroll position before reloading
      saveScrollPosition(window.scrollY);

      await deleteEntryMutation.mutateAsync(deletingEntryId);
    } finally {
      setDeletingEntryId(null);
    }
  };

  const cancelDeleteEntry = () => {
    setDeletingEntryId(null);
  };

  const requestBatchDelete = () => {
    if (selectedEntryIds.size === 0) return;
    setDeletingEntryCount(selectedEntryIds.size);
  };

  const confirmBatchDelete = async () => {
    if (deletingEntryCount === 0) return;
    try {
      saveScrollPosition(window.scrollY);

      const eventIds = Array.from(selectedEntryIds);
      await batchDeleteMutation.mutateAsync(eventIds);
    } finally {
      setDeletingEntryCount(0);
    }
  };

  const cancelBatchDelete = () => {
    setDeletingEntryCount(0);
  };

  // Batch selection functions
  const handleSelectEntry = (entryId: UUID, checked: boolean) => {
    setSelectedEntryIds((prev) => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(entryId);
      } else {
        newSet.delete(entryId);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    let allEntryIds: UUID[];

    if (queryMode === "advanced") {
      // 在高级搜索模式下，使用 advancedSearchResults
      // 这些数据应该已经通过 setAdvancedSearchResultsFromHook 同步
      allEntryIds = advancedSearchResults
        .filter((entry) => !entry.isPlaceholder)
        .map((entry) => entry.id as UUID);
    } else {
      // 在单日模式下，使用 processedEntries (来自 TanStack Query)
      allEntryIds = processedEntries
        .filter((entry) => !entry.isPlaceholder)
        .map((entry) => entry.id as UUID);
    }

    setSelectedEntryIds(new Set(allEntryIds));
  };

  const handleSelectInverse = () => {
    let allEntryIds: UUID[];

    if (queryMode === "advanced") {
      // 在高级搜索模式下，使用 advancedSearchResults
      allEntryIds = advancedSearchResults
        .filter((entry) => !entry.isPlaceholder)
        .map((entry) => entry.id as UUID);
    } else {
      // 在单日模式下，使用 processedEntries (来自 TanStack Query)
      allEntryIds = processedEntries
        .filter((entry) => !entry.isPlaceholder)
        .map((entry) => entry.id as UUID);
    }

    const newSelectedIds = new Set<UUID>();

    allEntryIds.forEach((id) => {
      if (!selectedEntryIds.has(id)) {
        newSelectedIds.add(id);
      }
    });

    setSelectedEntryIds(newSelectedIds);
  };

  const handleClearSelection = () => {
    setSelectedEntryIds(new Set());
  };

  // Advanced search support
  const setAdvancedSearchResultsFromHook = useCallback(
    (results: ProcessedEntry[]) => {
      setAdvancedSearchResults(results);
    },
    [],
  );

  return {
    processedEntries,
    loading,
    error,
    selectedEntryIds,
    isSelectMode,
    deletingEntryId,
    deletingEntryCount,
    requestDeleteEntry,
    confirmDeleteEntry,
    cancelDeleteEntry,
    requestBatchDelete,
    confirmBatchDelete,
    cancelBatchDelete,
    setIsSelectMode,
    setAdvancedSearchResultsFromHook,
    selectionHandlers: {
      handleSelectEntry,
      handleSelectAll,
      handleSelectInverse,
      handleClearSelection,
    },
  };
};
