import { useCallback } from "react";
import { usePersistentState } from "@/hooks/usePersistentState";
import { useTaskExpansionState } from "@/hooks/useTaskExpansionState";
import type { UUID } from "@/types/primitive";
/**
 * Custom hook for managing vision page UI state persistence
 * Handles expanded visions, expanded tasks, and scroll position
 */
export function useVisionUIState() {
  // Stable serialize/deserialize functions for expanded visions
  const serializeExpandedVisions = useCallback(
    (set: Set<UUID>) => JSON.stringify(Array.from(set)),
    [],
  );
  const deserializeExpandedVisions = useCallback(
    (str: string) => new Set(JSON.parse(str) as UUID[]),
    [],
  );

  // Expanded visions state (Set<UUID>)
  const {
    state: expandedVisions,
    setState: setExpandedVisions,
    isLoaded: visionsLoaded,
    clearState: clearExpandedVisions,
  } = usePersistentState<Set<UUID>>({
    key: "vision_expanded_visions",
    defaultValue: new Set(),
    expireInHours: 48, // 2 days
    serialize: serializeExpandedVisions,
    deserialize: deserializeExpandedVisions,
  });

  // Use the generic task expansion state hook
  const {
    expandedTasksByScope,
    isLoaded: tasksLoaded,
    toggleTaskExpansion,
    removeScope,
    clearExpandedTasks,
  } = useTaskExpansionState({
    key: "vision_expanded_tasks",
    expireInHours: 48, // 2 days
  });

  // Scroll position state
  const {
    state: scrollPosition,
    setState: setScrollPosition,
    isLoaded: scrollLoaded,
    clearState: clearScrollPosition,
  } = usePersistentState<number>({
    key: "vision_scroll_position",
    defaultValue: 0,
    expireInHours: 24, // 1 day
  });

  // Toggle vision expansion
  const toggleVisionExpansion = useCallback(
    (visionId: UUID) => {
      setExpandedVisions((prev) => {
        const newSet = new Set(prev);
        if (newSet.has(visionId)) {
          newSet.delete(visionId);
        } else {
          newSet.add(visionId);
        }
        return newSet;
      });
    },
    [setExpandedVisions],
  );

  // Remove vision from expanded state (when vision is deleted)
  const removeVisionFromExpanded = useCallback(
    (visionId: UUID) => {
      setExpandedVisions((prev) => {
        const newSet = new Set(prev);
        newSet.delete(visionId);
        return newSet;
      });

      removeScope(visionId.toString());
    },
    [setExpandedVisions, removeScope],
  );

  // Save scroll position
  const saveScrollPosition = useCallback(
    (position: number) => {
      setScrollPosition(position);
    },
    [setScrollPosition],
  );

  // Restore scroll position
  const restoreScrollPosition = useCallback(() => {
    if (scrollPosition > 0) {
      window.scrollTo(0, scrollPosition);
    }
  }, [scrollPosition]);

  // Clear all UI state
  const clearAllUIState = useCallback(() => {
    clearExpandedVisions();
    clearExpandedTasks();
    clearScrollPosition();
  }, [clearExpandedVisions, clearExpandedTasks, clearScrollPosition]);

  // Check if all states are loaded
  const isFullyLoaded = visionsLoaded && tasksLoaded && scrollLoaded;

  return {
    // State
    expandedVisions,
    expandedTasksByScope,
    scrollPosition,
    isFullyLoaded,

    // Actions
    toggleVisionExpansion,
    toggleTaskExpansion,
    removeVisionFromExpanded,
    saveScrollPosition,
    restoreScrollPosition,
    clearAllUIState,

    // Direct setters (for advanced use cases)
    setExpandedVisions,
    setScrollPosition,
  };
}
