import { useCallback } from "react";
import { usePersistentState } from "./usePersistentState";
import type { UUID } from "@/types/primitive";

interface UseTaskExpansionStateOptions {
  key: string; // Unique key for this state instance
  expireInHours?: number; // Default 48 hours
}

/**
 * Custom hook for managing task expansion state with persistence
 * Supports both scoped (by parent) and global task expansion
 */
export function useTaskExpansionState(options: UseTaskExpansionStateOptions) {
  const { key, expireInHours = 48 } = options;

  // Stable serialize/deserialize functions for expanded tasks
  const serializeExpandedTasks = useCallback(
    (record: Record<string, Set<UUID>>) => {
      const serialized: Record<string, UUID[]> = {};
      Object.entries(record).forEach(([scope, taskSet]) => {
        serialized[scope] = Array.from(taskSet);
      });
      return JSON.stringify(serialized);
    },
    [],
  );

  const deserializeExpandedTasks = useCallback(
    (str: string) => {
      if (!str) return {};
      try {
        const parsed = JSON.parse(str);
        const result: Record<string, Set<UUID>> = {};
        Object.entries(parsed).forEach(([scope, taskArray]) => {
          result[scope] = new Set(taskArray as UUID[]);
        });
        return result;
      } catch (error) {
        console.warn(
          `Failed to deserialize expanded tasks for key ${key}:`,
          error,
        );
        return {};
      }
    },
    [key],
  );

  // Expanded tasks state (Record<string, Set<UUID>>)
  // The scope can be vision ID, planning group ID, or any other identifier
  const {
    state: expandedTasksByScope,
    setState: setExpandedTasksByScope,
    isLoaded: tasksLoaded,
    clearState: clearExpandedTasks,
  } = usePersistentState<Record<string, Set<UUID>>>({
    key: `task_expansion_${key}`,
    defaultValue: {},
    expireInHours,
    serialize: serializeExpandedTasks,
    deserialize: deserializeExpandedTasks,
  });

  // Get expanded tasks for a specific scope
  const getExpandedTasks = useCallback(
    (scope: string): Set<UUID> => {
      if (!tasksLoaded) return new Set();
      return expandedTasksByScope[scope] || new Set();
    },
    [expandedTasksByScope, tasksLoaded],
  );

  // Toggle task expansion for a specific scope
  const toggleTaskExpansion = useCallback(
    (scope: string, taskId: UUID) => {
      setExpandedTasksByScope((prev) => {
        const currentExpanded = prev[scope] || new Set();
        const newExpanded = new Set(currentExpanded);
        if (newExpanded.has(taskId)) {
          newExpanded.delete(taskId);
        } else {
          newExpanded.add(taskId);
        }
        return { ...prev, [scope]: newExpanded };
      });
    },
    [setExpandedTasksByScope],
  );

  // Remove a scope (when parent entity is deleted)
  const removeScope = useCallback(
    (scope: string) => {
      setExpandedTasksByScope((prev) => {
        const newRecord = { ...prev };
        delete newRecord[scope];
        return newRecord;
      });
    },
    [setExpandedTasksByScope],
  );

  return {
    // State
    expandedTasksByScope,
    isLoaded: tasksLoaded,

    // Actions
    getExpandedTasks,
    toggleTaskExpansion,
    removeScope,

    // Utilities
    clearExpandedTasks,
  };
}
