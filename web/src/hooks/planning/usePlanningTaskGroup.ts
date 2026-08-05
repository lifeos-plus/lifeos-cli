import { useCallback, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { Task, TaskWithSubtasks, Vision } from "@/services/api";
import type { HabitActionWithHabit } from "@/services/api/habits";
import { tasksApi } from "@/services/api/tasks";
import { habitsApi } from "@/services/api/habits";
import { useToast } from "@/contexts/ToastContext";
import { usePlanningCycle } from "@/hooks/useCalendarAdapter";
import { useDefaultInboxVision } from "@/hooks/queries/useDefaultInboxVision";
import { usePreferenceWithBootstrap } from "@/hooks/queries/usePreferenceWithBootstrap";
import { useMultipleTaskTimelogs } from "@/hooks/queries/useTaskTimelogs";
import { useHabitActionsInRange } from "@/hooks/queries/useHabitActionsInRange";
import { useTaskExpansionState } from "@/hooks/useTaskExpansionState";
import { usePersistentState } from "@/hooks/usePersistentState";
import type {
  CalendarAdapter,
  PlanningGroup,
  PlanningViewType,
} from "@/utils/calendar";
import {
  formatDate,
  formatDateKey,
  formatDuration,
} from "@/utils/datetime";
import { ACTIVE_TASK_STATUSES, TASK_STATUS_LABELS } from "@/utils/constants";

import type { UUID } from "@/types/primitive";
import {
  invalidateAllTaskLists,
  invalidateTasksByIds,
  updateTaskCaches,
} from "@/utils/query";
import { invalidatePlanningSnapshots } from "@/utils/query";

interface PlanningStatusCounts {
  all: number;
  todo: number;
  in_progress: number;
  done: number;
  paused: number;
  cancelled: number;
}

export interface StatusFilterOption {
  value: string;
  label: string;
}

interface PlanningTaskGroupHookParams {
  group: PlanningGroup;
  visions: Vision[];
  onTaskUpdate?: () => void;
  planningCycleType?: PlanningViewType;
  calendarAdapter?: CalendarAdapter;
}

export interface PlanningTaskGroupHandlers {
  handleStatusFilterChange: (value: string) => void;
  handleVisionFilterChange: (value: string) => void;
  handleCreateTaskClick: () => void;
  handleAddTaskClick: () => void;
  handleCancelTaskSelect: () => void;
  handleTaskSelect: (taskId: UUID | null) => Promise<void>;
  handleTaskSelectorChange: (taskId: UUID | null) => void;
  handleCreateTask: () => Promise<void>;
  handleCancelCreateTask: () => void;
  handleVisionChange: (visionId: UUID | null) => void;
  handleTaskContentChange: (value: string) => void;
  handleCarryForwardClick: () => void;
  handleCarryForwardTasks: () => Promise<void>;
  handleCancelCarryForward: () => void;
  handleHabitActionStatusUpdate: (
    actionId: UUID,
    habitId: UUID,
    newStatus: string,
  ) => Promise<void>;

  handleHabitActionNotesChanged: () => Promise<void>;
}

interface PlanningTaskGroupHookResult {
  statusFilter: string;
  statusFilterOptions: StatusFilterOption[];
  visionFilter: string;
  visionFilterOptions: StatusFilterOption[];
  selectedVisionFilterLabel: string;
  selectedVisionFilterName: string;
  statusCounts: PlanningStatusCounts;
  planningTaskFilterStatus: readonly string[];
  filteredTasks: TaskWithSubtasks[];
  sortedTasks: TaskWithSubtasks[];
  totalTimeSpent: string;
  showCreateTask: boolean;
  isCreatingTask: boolean;
  newTaskContent: string;
  selectedVisionId: UUID | null;
  showTaskSelector: boolean;
  isAddingTask: boolean;
  selectedTaskId: UUID | null;
  showCarryForwardConfirm: boolean;
  isCarryingForward: boolean;
  carryForwardableTasks: TaskWithSubtasks[];
  periodRangeLabel?: string;
  canCreateTask: boolean;
  canAddTask: boolean;
  carryForwardCount: number;
  habitActions: HabitActionWithHabit[];
  showHabitActionsCard: boolean;
  defaultInboxVision: UUID | null;
  handlers: PlanningTaskGroupHandlers;
  getExpandedTasksForDraggable: (groupId: string) => Set<UUID>;
  toggleTaskExpansion: (groupId: string, taskId: string) => void;
}

const habitCadenceByPlanningCycle: Partial<Record<PlanningViewType, string>> = {
  day: "daily",
  week: "weekly",
  month: "monthly",
};

export function isTopLevelPlanningGroup(
  groupId: string,
  planningCycleType?: PlanningViewType,
): boolean {
  if (!planningCycleType) return false;
  if (planningCycleType === "7years") {
    return (
      groupId.startsWith("seven-year-") ||
      groupId.startsWith("mayan-seven-year-")
    );
  }
  return (
    groupId.startsWith(`${planningCycleType}-`) ||
    groupId.startsWith(`mayan-${planningCycleType}-`)
  );
}

export function buildHabitActionRange(
  planningCycleType: PlanningViewType | undefined,
  groupDate: Date,
  calendarAdapter: CalendarAdapter,
  referenceDate: Date = new Date(),
): {
  startDate: string;
  endDate: string;
  referenceDate: string;
  cadenceFrequency: string;
} | null {
  if (!planningCycleType) return null;
  const cadenceFrequency = habitCadenceByPlanningCycle[planningCycleType];
  if (!cadenceFrequency) return null;
  const periodRange = calendarAdapter.getPeriodRange(planningCycleType, groupDate);
  return {
    startDate: periodRange.start,
    endDate: periodRange.end,
    referenceDate: formatDateKey(referenceDate),
    cadenceFrequency,
  };
}

export function usePlanningTaskGroup(
  params: PlanningTaskGroupHookParams,
): PlanningTaskGroupHookResult {
  const { group, visions, onTaskUpdate, planningCycleType, calendarAdapter } =
    params;

  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { getDefaultCycleSettings, adapter } = usePlanningCycle();
  const { defaultInboxVision } = useDefaultInboxVision();
  const { value: showHabitActions } = usePreferenceWithBootstrap<boolean>({
    key: "planning.show_habit_actions",
    defaultValue: false,
    module: "planning",
    validator: (value) => {
      if (typeof value === "boolean") return true;
      if (typeof value === "number") return value === 0 || value === 1;
      if (typeof value === "string")
        return value === "true" || value === "false";
      return false;
    },
  });
  const planningTaskFilterStatus = useMemo(() => ACTIVE_TASK_STATUSES, []);

  const [showTaskSelector, setShowTaskSelector] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<UUID | null>(null);
  const [isAddingTask, setIsAddingTask] = useState(false);

  const [showCreateTask, setShowCreateTask] = useState(false);
  const [newTaskContent, setNewTaskContent] = useState("");
  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const [selectedVisionId, setSelectedVisionId] = useState<UUID | null>(null);

  const [isCarryingForward, setIsCarryingForward] = useState(false);
  const [showCarryForwardConfirm, setShowCarryForwardConfirm] = useState(false);

  const { getExpandedTasksForDraggable, toggleTaskExpansion } =
    useTaskExpansionState({
      key: `planning_group_${group.id}`,
      expireInHours: 24,
    });

  const taskIds = useMemo(
    () => group.tasks.map((task) => task.id),
    [group.tasks],
  );
  const { taskTimelogs } = useMultipleTaskTimelogs(taskIds, {
    enabled: group.tasks.length > 0,
  });

  const habitActionRange = useMemo(() => {
    const localAdapter = calendarAdapter ?? adapter;
    return buildHabitActionRange(
      planningCycleType,
      group.date,
      localAdapter,
      new Date(),
    );
  }, [adapter, calendarAdapter, group.date, planningCycleType]);
  const canShowHabitActionsForGroup = isTopLevelPlanningGroup(
    group.id,
    planningCycleType,
  );
  const habitsQuery = useHabitActionsInRange(
    habitActionRange ?? {
      startDate: formatDateKey(group.date),
      endDate: formatDateKey(group.date),
      referenceDate: formatDateKey(new Date()),
      cadenceFrequency: null,
    },
    {
      enabled: Boolean(
        planningCycleType &&
          showHabitActions &&
          habitActionRange &&
          canShowHabitActionsForGroup,
      ),
      staleTimeMs: 5 * 60 * 1000,
    },
  );
  const habitActions = (habitsQuery.data || []) as HabitActionWithHabit[];

  const { state: statusFilter, setState: setStatusFilter } =
    usePersistentState<string>({
      key: `planning-status-filter-${group.id}`,
      defaultValue: "all",
      expireInHours: 0,
    });

  const { state: visionFilter, setState: setVisionFilter } =
    usePersistentState<string>({
      key: `planning-vision-filter-${group.id}`,
      defaultValue: "all",
      expireInHours: 0,
    });

  const visionLookup = useMemo(() => {
    return visions.reduce<Map<string, Vision>>((acc, vision) => {
      acc.set(vision.id, vision);
      return acc;
    }, new Map());
  }, [visions]);

  const VISION_FILTER_NONE = "__none__";

  const tasksMatchingStatus = useMemo(() => {
    if (statusFilter === "all") return group.tasks;
    return group.tasks.filter((task) => task.status === statusFilter);
  }, [group.tasks, statusFilter]);

  const visionCounts = useMemo(() => {
    const counts = new Map<string, number>();
    tasksMatchingStatus.forEach((task) => {
      const key = task.vision_id ?? VISION_FILTER_NONE;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });
    return counts;
  }, [tasksMatchingStatus]);

  const normalizedVisionFilter = useMemo(() => {
    if (visionFilter === "all") return visionFilter;
    if (visionFilter === VISION_FILTER_NONE) return visionFilter;
    if (visionLookup.has(visionFilter)) return visionFilter;
    return "all";
  }, [visionFilter, visionLookup]);

  const visionFilterOptions = useMemo<StatusFilterOption[]>(() => {
    const totalCount = tasksMatchingStatus.length;
    const options: StatusFilterOption[] = [
      {
        value: "all",
        label: `${t("common.all")} (${totalCount})`,
      },
    ];

    const keys = new Set(visionCounts.keys());
    if (normalizedVisionFilter !== "all" && !keys.has(normalizedVisionFilter)) {
      keys.add(normalizedVisionFilter);
    }

    const sortedKeys = Array.from(keys).sort((a, b) => {
      if (a === VISION_FILTER_NONE) return 1;
      if (b === VISION_FILTER_NONE) return -1;
      const nameA = visionLookup.get(a)?.name?.toLowerCase() ?? "";
      const nameB = visionLookup.get(b)?.name?.toLowerCase() ?? "";
      return nameA.localeCompare(nameB);
    });

    sortedKeys.forEach((key) => {
      const count = visionCounts.get(key) ?? 0;
      const isNone = key === VISION_FILTER_NONE;
      const visionName = isNone
        ? t("planning.filters.vision.none")
        : (visionLookup.get(key)?.name ?? t("planning.filters.vision.unknown"));
      options.push({
        value: isNone ? VISION_FILTER_NONE : key,
        label: `${visionName} (${count})`,
      });
    });

    return options;
  }, [
    tasksMatchingStatus.length,
    visionCounts,
    visionLookup,
    normalizedVisionFilter,
    t,
  ]);

  const visionFilteredTasks = useMemo(() => {
    if (normalizedVisionFilter === "all") return group.tasks;
    if (normalizedVisionFilter === VISION_FILTER_NONE) {
      return group.tasks.filter((task) => task.vision_id === null);
    }

    return group.tasks.filter(
      (task) => task.vision_id === normalizedVisionFilter,
    );
  }, [group.tasks, normalizedVisionFilter]);

  const selectedVisionFilterLabel = useMemo(() => {
    const option = visionFilterOptions.find(
      (opt) => opt.value === normalizedVisionFilter,
    );
    return option?.label ?? "";
  }, [normalizedVisionFilter, visionFilterOptions]);

  const selectedVisionFilterName = useMemo(() => {
    if (normalizedVisionFilter === "all") {
      return t("common.all");
    }
    if (normalizedVisionFilter === VISION_FILTER_NONE) {
      return t("planning.filters.vision.none");
    }
    return (
      visionLookup.get(normalizedVisionFilter)?.name ??
      t("planning.filters.vision.unknown")
    );
  }, [normalizedVisionFilter, t, visionLookup]);

  const statusCounts = useMemo<PlanningStatusCounts>(() => {
    const counts: PlanningStatusCounts = {
      all: visionFilteredTasks.length,
      todo: 0,
      in_progress: 0,
      done: 0,
      paused: 0,
      cancelled: 0,
    };

    visionFilteredTasks.forEach((task) => {
      switch (task.status) {
        case "todo":
          counts.todo++;
          break;
        case "in_progress":
          counts.in_progress++;
          break;
        case "done":
          counts.done++;
          break;
        case "paused":
          counts.paused++;
          break;
        case "cancelled":
          counts.cancelled++;
          break;
        default:
          break;
      }
    });

    return counts;
  }, [visionFilteredTasks]);

  const filteredTasks = useMemo(() => {
    if (statusFilter === "all") {
      return visionFilteredTasks;
    }
    return visionFilteredTasks.filter((task) => task.status === statusFilter);
  }, [visionFilteredTasks, statusFilter]);

  const sortedTasks = useMemo(() => {
    const toNumber = (value: unknown, fallback: number) =>
      typeof value === "number" && Number.isFinite(value) ? value : fallback;
    const toDate = (value: unknown) =>
      typeof value === "string" ? new Date(value).getTime() : 0;

    const copy = [...filteredTasks];
    copy.sort((a, b) => {
      const priorityDiff = toNumber(b.priority, 0) - toNumber(a.priority, 0);
      if (priorityDiff !== 0) return priorityDiff;

      const displayDiff =
        toNumber(a.display_order, 0) - toNumber(b.display_order, 0);
      if (displayDiff !== 0) return displayDiff;

      return toDate(a.created_at) - toDate(b.created_at);
    });

    return copy;
  }, [filteredTasks]);

  const totalTimeSpent = useMemo(() => {
    let totalMinutes = 0;

    group.tasks.forEach((task) => {
      const timeRecords = taskTimelogs.get(task.id) || [];
      timeRecords.forEach((event) => {
        if (event.start_time && event.end_time) {
          const startTime = new Date(event.start_time);
          const endTime = new Date(event.end_time);
          const durationMs = endTime.getTime() - startTime.getTime();
          if (durationMs > 0) {
            totalMinutes += Math.round(durationMs / (1000 * 60));
          }
        }
      });
    });

    return formatDuration(totalMinutes);
  }, [group.tasks, taskTimelogs]);

  const carryForwardableTasks = useMemo(
    () =>
      group.tasks.filter(
        (task) => !["done", "cancelled"].includes(task.status),
      ),
    [group.tasks],
  );

  const periodRangeLabel = useMemo(() => {
    if (!planningCycleType) return undefined;

    const localAdapter = calendarAdapter ?? adapter;
    const periodRange = localAdapter.getPeriodRange(
      planningCycleType,
      group.date,
    );
    const startLabel = formatDate(periodRange.start);

    if (periodRange.start === periodRange.end) {
      return startLabel;
    }

    const endLabel = formatDate(periodRange.end);

    return `${startLabel} - ${endLabel}`;
  }, [adapter, calendarAdapter, group.date, planningCycleType]);

  const statusFilterOptions = useMemo<StatusFilterOption[]>(
    () => [
      {
        value: "all",
        label: `${t("common.all")} (${statusCounts.all})`,
      },
      {
        value: "todo",
        label: `${TASK_STATUS_LABELS.todo} (${statusCounts.todo})`,
      },
      {
        value: "in_progress",
        label: `${TASK_STATUS_LABELS.in_progress} (${statusCounts.in_progress})`,
      },
      {
        value: "done",
        label: `${TASK_STATUS_LABELS.done} (${statusCounts.done})`,
      },
      {
        value: "paused",
        label: `${TASK_STATUS_LABELS.paused} (${statusCounts.paused})`,
      },
      {
        value: "cancelled",
        label: `${TASK_STATUS_LABELS.cancelled} (${statusCounts.cancelled})`,
      },
    ],
    [statusCounts, t],
  );

  const canCreateTask = Boolean(planningCycleType && defaultInboxVision);
  const canAddTask = Boolean(planningCycleType);
  const carryForwardCount = carryForwardableTasks.length;
  const showHabitActionsCard =
    Boolean(planningCycleType) &&
    showHabitActions &&
    canShowHabitActionsForGroup &&
    habitActions.length > 0;

  const handleVisionFilterChange = useCallback(
    (value: string) => {
      setVisionFilter(value);
    },
    [setVisionFilter],
  );

  const handleAddTaskClick = useCallback(() => {
    if (showCreateTask) {
      setShowCreateTask(false);
      setNewTaskContent("");
      setSelectedVisionId(null);
    }
    if (showCarryForwardConfirm) {
      setShowCarryForwardConfirm(false);
    }

    setShowTaskSelector(true);
    setSelectedTaskId(null);
  }, [showCreateTask, showCarryForwardConfirm]);

  const handleCreateTaskClick = useCallback(() => {
    if (showTaskSelector) {
      setShowTaskSelector(false);
      setSelectedTaskId(null);
    }
    if (showCarryForwardConfirm) {
      setShowCarryForwardConfirm(false);
    }

    setShowCreateTask(true);
    setNewTaskContent("");
    setSelectedVisionId(null);
  }, [showTaskSelector, showCarryForwardConfirm]);

  const handleTaskSelect = useCallback(
    async (taskId: UUID | null) => {
      if (!taskId || !planningCycleType) return;

      try {
        setIsAddingTask(true);

        const task = await tasksApi.getById(taskId);
        if (!task) {
          toast.showError(
            t("planning.messages.taskNotFound"),
            t("planning.messages.taskNotFoundMessage"),
          );
          return;
        }

        const cycleSettings = getDefaultCycleSettings(
          planningCycleType,
          group.date,
        );

        const updatedTask = await tasksApi.update(taskId, {
          planning_cycle_type: planningCycleType,
          planning_cycle_days: cycleSettings.days,
          planning_cycle_start_date: formatDateKey(group.date),
        });

        const originalPlanningSnapshot = {
          planning_cycle_type: task.planning_cycle_type,
          planning_cycle_start_date: task.planning_cycle_start_date,
        };
        const newPlanningSnapshot = {
          planning_cycle_type: planningCycleType,
          planning_cycle_start_date: formatDateKey(group.date),
        };

        updateTaskCaches(queryClient, updatedTask);
        await invalidateTasksByIds(queryClient, [updatedTask.id], {
          skipEvents: true,
        });

        await invalidatePlanningSnapshots(queryClient, [
          originalPlanningSnapshot,
          newPlanningSnapshot,
        ]);
        // 任务缓存通过 updateTaskCaches 已更新，不需要额外全量刷新

        toast.showSuccess(
          t("planning.messages.taskAdded"),
          t("planning.messages.taskAddedToPeriod", { period: group.label }),
        );

        onTaskUpdate?.();
        setShowTaskSelector(false);
        setSelectedTaskId(null);
      } catch (error) {
        console.error("Failed to add task to planning:", error);
        toast.showError(
          t("planning.messages.addFailed"),
          t("planning.messages.addFailedMessage"),
        );
      } finally {
        setIsAddingTask(false);
      }
    },
    [
      planningCycleType,
      group.date,
      group.label,
      onTaskUpdate,
      toast,
      getDefaultCycleSettings,
      t,
      queryClient,
    ],
  );

  const handleCancelTaskSelect = useCallback(() => {
    setShowTaskSelector(false);
    setSelectedTaskId(null);
  }, []);

  const handleCreateTask = useCallback(async () => {
    if (!newTaskContent.trim() || !planningCycleType) {
      toast.showError(
        t("planning.messages.createFailed"),
        t("planning.messages.createFailedNoContent"),
      );
      return;
    }

    const visionId = selectedVisionId || defaultInboxVision;
    if (!visionId) {
      toast.showError(
        t("planning.messages.createFailed"),
        t("planning.messages.createFailedNoVision"),
      );
      return;
    }

    try {
      setIsCreatingTask(true);

      const cycleSettings = getDefaultCycleSettings(
        planningCycleType,
        group.date,
      );
      const planningStartDate = formatDateKey(group.date);

      const createdTask = await tasksApi.create({
        content: newTaskContent.trim(),
        vision_id: visionId,
        planning_cycle_type: planningCycleType,
        planning_cycle_days: cycleSettings.days,
        planning_cycle_start_date: planningStartDate,
      });

      updateTaskCaches(queryClient, createdTask);

      void Promise.all([
        invalidateTasksByIds(queryClient, [createdTask.id], {
          skipEvents: true,
        }),
        invalidatePlanningSnapshots(queryClient, [
          {
            planning_cycle_type: planningCycleType,
            planning_cycle_start_date: planningStartDate,
          },
        ]),
        invalidateAllTaskLists(queryClient),
      ]).catch((refreshError) => {
        console.error(
          "Failed to refresh planning caches after creating task:",
          refreshError,
        );
      });

      toast.showSuccess(
        t("planning.messages.createSuccess"),
        t("planning.messages.createSuccessMessage", { period: group.label }),
      );

      onTaskUpdate?.();
      setShowCreateTask(false);
      setNewTaskContent("");
      setSelectedVisionId(null);
    } catch (error) {
      console.error("Failed to create planning task:", error);
      toast.showError(
        t("planning.messages.createFailed"),
        t("planning.messages.createFailedMessage"),
      );
    } finally {
      setIsCreatingTask(false);
    }
  }, [
    newTaskContent,
    planningCycleType,
    selectedVisionId,
    defaultInboxVision,
    group.date,
    group.label,
    onTaskUpdate,
    toast,
    getDefaultCycleSettings,
    t,
    queryClient,
  ]);

  const handleCancelCreateTask = useCallback(() => {
    setShowCreateTask(false);
    setNewTaskContent("");
    setSelectedVisionId(null);
  }, []);

  const handleCarryForwardClick = useCallback(() => {
    if (carryForwardableTasks.length === 0) {
      toast.showInfo(
        t("planning.carryForward.noTasksMessage"),
        t("planning.carryForward.noTasksMessage"),
      );
      return;
    }

    if (showCreateTask) {
      setShowCreateTask(false);
      setNewTaskContent("");
      setSelectedVisionId(null);
    }
    if (showTaskSelector) {
      setShowTaskSelector(false);
      setSelectedTaskId(null);
    }

    setShowCarryForwardConfirm(true);
  }, [
    carryForwardableTasks.length,
    toast,
    t,
    showCreateTask,
    showTaskSelector,
  ]);

  const handleCarryForwardTasks = useCallback(async () => {
    if (!planningCycleType) return;

    try {
      setIsCarryingForward(true);
      setShowCarryForwardConfirm(false);

      if (carryForwardableTasks.length === 0) {
        toast.showInfo(
          t("planning.carryForward.noTasksMessage"),
          t("planning.carryForward.noTasksMessage"),
        );
        return;
      }

      const nextPeriodStart =
        calendarAdapter?.getNextPeriod(group.date, planningCycleType) ??
        adapter.getNextPeriod(group.date, planningCycleType);

      const cycleSettings = getDefaultCycleSettings(
        planningCycleType,
        nextPeriodStart,
      );

      const results = await Promise.allSettled(
        carryForwardableTasks.map((task) =>
          tasksApi.update(task.id, {
            planning_cycle_type: planningCycleType,
            planning_cycle_days: cycleSettings.days,
            planning_cycle_start_date:
              formatDateKey(nextPeriodStart),
          }),
        ),
      );

      const successCount = results.filter(
        (result) => result.status === "fulfilled",
      ).length;
      const failedCount = results.filter(
        (result) => result.status === "rejected",
      ).length;

      const succeededTasks: Task[] = [];
      results.forEach((result) => {
        if (result.status === "fulfilled") {
          updateTaskCaches(queryClient, result.value);
          succeededTasks.push(result.value);
        }
      });

      if (successCount > 0) {
        toast.showSuccess(
          t("planning.messages.carryForwardSuccess"),
          t("planning.messages.carryForwardSuccessMessage", {
            count: successCount,
          }),
        );
      }

      if (failedCount > 0) {
        toast.showError(
          t("planning.messages.carryForwardPartialFailed"),
          t("planning.messages.carryForwardPartialFailedMessage", {
            count: failedCount,
          }),
        );
      }

      // Invalidate cache for both current and next periods
      const currentPeriodDate = formatDateKey(group.date);
      const nextPeriodDate = formatDateKey(nextPeriodStart);

      const succeededIds = succeededTasks.map((task) => task.id);
      await invalidateTasksByIds(queryClient, succeededIds, {
        skipEvents: true,
      });

      await invalidatePlanningSnapshots(queryClient, [
        {
          planning_cycle_type: planningCycleType,
          planning_cycle_start_date: currentPeriodDate,
        },
        {
          planning_cycle_type: planningCycleType,
          planning_cycle_start_date: nextPeriodDate,
        },
      ]);
      // 任务缓存已通过 updateTaskCaches 更新，不需要刷新所有任务列表

      onTaskUpdate?.();
    } catch (error) {
      console.error("Failed to carry forward tasks:", error);
      toast.showError(
        t("planning.messages.carryForwardFailed"),
        t("planning.messages.carryForwardFailedMessage"),
      );
    } finally {
      setIsCarryingForward(false);
    }
  }, [
    planningCycleType,
    carryForwardableTasks,
    group.date,
    onTaskUpdate,
    toast,
    calendarAdapter,
    adapter,
    getDefaultCycleSettings,
    t,
    queryClient,
  ]);

  const handleCancelCarryForward = useCallback(() => {
    setShowCarryForwardConfirm(false);
  }, []);

  const handleHabitActionStatusUpdate = useCallback(
    async (actionId: UUID, habitId: UUID, newStatus: string) => {
      try {
        await habitsApi.updateAction(habitId, actionId, { status: newStatus });
        await habitsQuery.refetch();
      } catch (error) {
        console.error("Failed to update habit action status:", error);
        toast.showError(
          t("planning.messages.habitActionUpdateFailed"),
          t("planning.messages.habitActionUpdateFailedMessage"),
        );
      }
    },
    [toast, t, habitsQuery],
  );

  const handleHabitActionNotesChanged = useCallback(async () => {
    await habitsQuery.refetch();
  }, [habitsQuery]);

  const handlers: PlanningTaskGroupHandlers = {
    handleStatusFilterChange: (value) => {
      setStatusFilter(value);
    },
    handleVisionFilterChange,
    handleCreateTaskClick,
    handleAddTaskClick,
    handleCancelTaskSelect,
    handleTaskSelect,
    handleTaskSelectorChange: (taskId) => {
      setSelectedTaskId(taskId);
    },
    handleCreateTask,
    handleCancelCreateTask,
    handleVisionChange: (visionId) => {
      setSelectedVisionId(visionId);
    },
    handleTaskContentChange: (value) => {
      setNewTaskContent(value);
    },
    handleCarryForwardClick,
    handleCarryForwardTasks,
    handleCancelCarryForward,
    handleHabitActionStatusUpdate,
    handleHabitActionNotesChanged,
  };

  return {
    statusFilter,
    statusFilterOptions,
    visionFilter: normalizedVisionFilter,
    visionFilterOptions,
    selectedVisionFilterLabel,
    selectedVisionFilterName,
    statusCounts,
    planningTaskFilterStatus,
    filteredTasks,
    sortedTasks,
    totalTimeSpent,
    showCreateTask,
    isCreatingTask,
    newTaskContent,
    selectedVisionId,
    showTaskSelector,
    isAddingTask,
    selectedTaskId,
    showCarryForwardConfirm,
    isCarryingForward,
    carryForwardableTasks,
    periodRangeLabel,
    canCreateTask,
    canAddTask,
    carryForwardCount,
    habitActions,
    showHabitActionsCard,
    defaultInboxVision,
    handlers,
    getExpandedTasksForDraggable,
    toggleTaskExpansion,
  };
}
