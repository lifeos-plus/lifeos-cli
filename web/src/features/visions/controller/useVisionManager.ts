import { useState, useCallback, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { logger } from "@/utils/core";
import { visionsApi } from "@/services/api/visions";
import { tasksApi } from "@/services/api/tasks";
import type { Task } from "@/services/api/tasks";
import { habitsApi } from "@/services/api/habits";
import type { Vision, TaskWithSubtasks } from "@/services/api";
import { useVisionUIState } from "./useVisionUIState";
import { visionsKeys, habitsKeys } from "@/services/api/queryKeys";
import { useToast } from "@/contexts/ToastContext";
import type { UUID } from "@/types/primitive";
import {
  invalidateVisionsLists,
  invalidateVisionHierarchy,
} from "@/services/api/cacheInvalidation/visions";

type TaskUpdateLike = {
  id: UUID;
  vision_id: UUID | null;
  parent_task_id: UUID | null;
} & Partial<Omit<Task, "id" | "vision_id" | "parent_task_id">>;

const mergeTaskWithExisting = (
  existing: TaskWithSubtasks,
  update: TaskUpdateLike,
): TaskWithSubtasks => {
  return {
    ...existing,
    ...update,
    subtasks: existing.subtasks ?? [],
  };
};

const replaceTaskInHierarchy = (
  tasks: TaskWithSubtasks[],
  update: TaskUpdateLike,
): { changed: boolean; tasks: TaskWithSubtasks[] } => {
  let changed = false;

  const nextTasks = tasks.map((task) => {
    if (task.id === update.id) {
      changed = true;
      return mergeTaskWithExisting(task, update);
    }

    if (task.subtasks?.length) {
      const { changed: childChanged, tasks: nextSubtasks } =
        replaceTaskInHierarchy(task.subtasks, update);
      if (childChanged) {
        changed = true;
        return {
          ...task,
          subtasks: nextSubtasks,
        };
      }
    }

    return task;
  });

  return { changed, tasks: nextTasks };
};
/**
 * Custom hook for managing vision-related state and operations
 */
export const useVisionManager = (statusFilter: string = "active") => {
  const queryClient = useQueryClient();
  const toast = useToast();

  // Confirmation states
  const [deletingVision, setDeletingVision] = useState<Vision | null>(null);
  const [harvestingVision, setHarvestingVision] = useState<Vision | null>(null);

  // UI state management with persistence
  const {
    expandedVisions,
    expandedTasksByScope,
    isFullyLoaded: uiStateLoaded,
    toggleVisionExpansion,
    toggleTaskExpansion,
    removeVisionFromExpanded,
    restoreScrollPosition,
  } = useVisionUIState();

  const page = 1;
  const size = 100;

  // 1. 使用 useQuery 获取愿景列表
  const {
    data: visionsData,
    isLoading: loading,
    error,
  } = useQuery({
    queryKey: visionsKeys.list({ status: statusFilter, page, size }),
    queryFn: () => visionsApi.getAll(statusFilter, page, size),
  });
  const visions = useMemo(() => visionsData?.items ?? [], [visionsData]);

  // 2. 使用 useQuery 获取习惯-任务关联
  const { data: habitTaskAssociationsData } = useQuery({
    queryKey: habitsKeys.list({}),
    queryFn: async () => {
      const response = await habitsApi.getHabitTaskAssociations();
      return response.associations;
    },
    enabled: visions.length > 0, // 只有当有愿景时才加载
  });
  const habitTaskAssociations = useMemo(
    () => habitTaskAssociationsData ?? {},
    [habitTaskAssociationsData],
  );

  // 3. 任务状态管理 - 使用本地状态存储已加载的任务
  const [visionTasks, setVisionTasks] = useState<
    Record<UUID, TaskWithSubtasks[]>
  >({});
  const [visionTasksLoading, setVisionTasksLoading] = useState<
    Record<UUID, boolean>
  >({});

  const applyTaskAttributesUpdate = useCallback(
    (taskUpdate: TaskUpdateLike) => {
      const targetVisionId = taskUpdate.vision_id;
      if (!targetVisionId) {
        return;
      }

      setVisionTasks((prev) => {
        const existingTasks = prev[targetVisionId];
        if (!existingTasks) {
          return prev;
        }

        const { changed, tasks } = replaceTaskInHierarchy(
          existingTasks,
          taskUpdate,
        );

        if (!changed) {
          return prev;
        }

        // 同时更新React Query缓存中的数据
        const hierarchyKey = visionsKeys.hierarchy(targetVisionId);
        queryClient.setQueryData(
          hierarchyKey,
          (oldData: { root_tasks: TaskWithSubtasks[] } | undefined) => {
            if (!oldData) return oldData;
            return {
              ...oldData,
              root_tasks: tasks,
            };
          },
        );

        return {
          ...prev,
          [targetVisionId]: tasks,
        };
      });
    },
    [setVisionTasks, queryClient],
  );

  // Error handler
  const handleError = useCallback(
    (error: unknown, defaultMessage: string) => {
      const message = error instanceof Error ? error.message : defaultMessage;
      logger.error(defaultMessage, error);
      toast.showError(defaultMessage, message);
    },
    [toast],
  );

  // 刷新愿景数据
  const loadVisions = useCallback(async () => {
    await invalidateVisionsLists(queryClient);
  }, [queryClient]);

  // 4. 任务加载逻辑 - 使用 useQuery 获取特定愿景的任务
  const loadVisionTasks = useCallback(
    async (visionId: UUID, force: boolean = false) => {
      if (!force && visionTasks[visionId]) {
        return;
      }

      const hierarchyKey = visionsKeys.hierarchy(visionId);

      if (!force) {
        const cached = queryClient.getQueryData<{
          root_tasks: TaskWithSubtasks[];
        }>(hierarchyKey);
        if (cached) {
          setVisionTasks((prev) => ({
            ...prev,
            [visionId]: cached.root_tasks,
          }));
          return;
        }

        if (visionTasksLoading[visionId]) {
          return;
        }
      }

      try {
        // 优化：延迟显示loading状态，避免快速请求导致的闪烁
        let loadingTimeout: number | null = null;

        if (force) {
          // 对于强制刷新（如创建任务后），延迟300ms再显示loading
          loadingTimeout = window.setTimeout(() => {
            setVisionTasksLoading((prev) => ({ ...prev, [visionId]: true }));
          }, 300);
        } else {
          // 对于初次加载，立即显示loading
          setVisionTasksLoading((prev) => ({ ...prev, [visionId]: true }));
        }

        let hierarchy: { root_tasks: TaskWithSubtasks[] };

        if (force) {
          hierarchy = await tasksApi.getVisionHierarchy(visionId);
          queryClient.setQueryData(hierarchyKey, hierarchy);
        } else {
          hierarchy = await queryClient.fetchQuery({
            queryKey: hierarchyKey,
            queryFn: () => tasksApi.getVisionHierarchy(visionId),
            staleTime: 2 * 60 * 1000,
          });
        }

        // 清除延迟的loading定时器
        if (loadingTimeout) {
          clearTimeout(loadingTimeout);
        }

        setVisionTasks((prev) => ({
          ...prev,
          [visionId]: hierarchy.root_tasks,
        }));

        // 确保loading状态被重置
        setVisionTasksLoading((prev) => ({
          ...prev,
          [visionId]: false,
        }));
      } catch (err) {
        handleError(err, `Failed to load tasks for vision ${visionId}`);
        // 确保在错误情况下也重置loading状态
        setVisionTasksLoading((prev) => ({
          ...prev,
          [visionId]: false,
        }));
      }
    },
    [handleError, queryClient, visionTasks, visionTasksLoading],
  );

  useEffect(() => {
    const unsubscribe = queryClient.getQueryCache().subscribe((event) => {
      const query = event.query;
      if (!query) {
        return;
      }
      const key = query.queryKey;
      if (!Array.isArray(key) || key.length < 4) {
        return;
      }
      if (key[0] !== "visions" || key[key.length - 1] !== "hierarchy") {
        return;
      }
      const visionId = key[2] as UUID | undefined;
      if (!visionId) return;
      const data = query.state.data as
        | { root_tasks: TaskWithSubtasks[] }
        | undefined;
      if (!data) return;
      setVisionTasks((prev) => ({
        ...prev,
        [visionId]: data.root_tasks,
      }));
    });

    return () => {
      unsubscribe();
    };
  }, [queryClient]);

  // 习惯关联数据已通过 useQuery 自动管理，无需手动加载

  // Load tasks for expanded visions when visions are loaded and UI state is ready
  // Coalesce expanded tasks auto-load to once per vision per mount
  useEffect(() => {
    if (!uiStateLoaded || visions.length === 0 || expandedVisions.size === 0) {
      return;
    }
    const toLoad: UUID[] = [];
    for (const visionId of expandedVisions) {
      if (visions.some((v) => v.id === visionId) && !visionTasks[visionId]) {
        toLoad.push(visionId);
      }
    }
    if (toLoad.length === 0) return;

    // Add a delay to ensure DOM is stable before loading tasks
    const timer = setTimeout(async () => {
      for (const id of toLoad) {
        await loadVisionTasks(id);
      }
    }, 300); // 300ms delay to ensure layout is stable

    return () => clearTimeout(timer);
  }, [uiStateLoaded, visions, expandedVisions, loadVisionTasks, visionTasks]);

  // Restore scroll position when UI state is loaded
  useEffect(() => {
    if (uiStateLoaded) {
      // Small delay to ensure DOM is ready
      const timer = setTimeout(() => {
        restoreScrollPosition();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [uiStateLoaded, restoreScrollPosition]);

  // 5. 愿景操作 - 使用 useMutation
  const requestDeleteVision = useCallback((vision: Vision) => {
    setDeletingVision(vision);
  }, []);

  const deleteVisionMutation = useMutation<
    void,
    Error,
    { visionId: UUID; visionName: string }
  >({
    mutationFn: ({ visionId }) => visionsApi.delete(visionId),
    onSuccess: async (_, variables) => {
      await Promise.all([
        invalidateVisionsLists(queryClient),
        invalidateVisionHierarchy(queryClient, variables.visionId),
      ]);
      removeVisionFromExpanded(variables.visionId);
      toast.showSuccess(
        "愿景删除成功",
        `愿景"${variables.visionName}"已成功删除`,
      );
    },
    onError: (err: Error) => {
      handleError(err, "删除失败");
    },
  });

  const confirmDeleteVision = useCallback(() => {
    if (!deletingVision) return;

    const payload = {
      visionId: deletingVision.id,
      visionName: deletingVision.name,
    };

    setDeletingVision(null);
    deleteVisionMutation.mutate(payload);
  }, [deletingVision, deleteVisionMutation]);

  const requestHarvestVision = useCallback((vision: Vision) => {
    setHarvestingVision(vision);
  }, []);

  const harvestVisionMutation = useMutation<
    Vision,
    Error,
    { visionId: UUID; visionName: string }
  >({
    mutationFn: ({ visionId }) => visionsApi.harvest(visionId),
    onSuccess: async (_, variables) => {
      await Promise.all([
        invalidateVisionsLists(queryClient),
        invalidateVisionHierarchy(queryClient, variables.visionId),
      ]);
      toast.showSuccess(
        "愿景收获成功",
        `愿景"${variables.visionName}"已成功收获，恭喜您！`,
      );
    },
    onError: (err: Error) => {
      handleError(err, "收获失败");
    },
  });

  const confirmHarvestVision = useCallback(() => {
    if (!harvestingVision) return;

    const payload = {
      visionId: harvestingVision.id,
      visionName: harvestingVision.name,
    };

    setHarvestingVision(null);
    harvestVisionMutation.mutate(payload);
  }, [harvestingVision, harvestVisionMutation]);

  // Enhanced expansion state management with task loading
  const handleVisionExpansion = useCallback(
    async (visionId: UUID) => {
      const isCurrentlyExpanded = expandedVisions.has(visionId);

      if (!isCurrentlyExpanded) {
        // Load tasks when expanding
        await loadVisionTasks(visionId);
      }

      toggleVisionExpansion(visionId);
    },
    [expandedVisions, loadVisionTasks, toggleVisionExpansion],
  );

  return {
    // State
    visions,
    loading,
    error: error?.message || null,
    expandedVisions,
    visionTasks,
    visionTasksLoading,
    expandedTasksByScope,
    habitTaskAssociations,
    deletingVision,
    harvestingVision,

    // Operations
    loadVisions,
    loadVisionTasks,
    requestDeleteVision,
    confirmDeleteVision,
    cancelDeleteVision: () => setDeletingVision(null),
    requestHarvestVision,
    confirmHarvestVision,
    cancelHarvestVision: () => setHarvestingVision(null),
    toggleVisionExpansion: handleVisionExpansion,
    toggleTaskExpansion,

    // Utility
    handleError,
    setVisionTasks,
    applyTaskAttributesUpdate,
  };
};
