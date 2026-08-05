import { useTranslation } from "react-i18next";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { tasksApi } from "@/services/api/tasks";
import type {
  Task,
  TaskCreate,
  TaskUpdate,
  TaskWithSubtasks,
  Vision,
} from "@/services/api";
import { useModalState } from "@/hooks/useModalState";
import { useToast } from "@/contexts/ToastContext";
import { usePlanningCycle } from "@/hooks/useCalendarAdapter";
import { usePreferenceWithBootstrap } from "@/hooks/queries/usePreferenceWithBootstrap";
import { ALL_TASK_STATUSES, ALL_VISION_STATUSES } from "@/utils/constants";
import type { ExtendedPlanningViewType } from "@/utils/calendar";
import type { UUID } from "@/types/primitive";
import { logger } from "@/utils/core";
import { parseDateKey } from "@/utils/datetime";
import { invalidateTasksByIds, updateTaskCaches } from "@/utils/query";
import {
  invalidatePlanningSnapshots,
  type PlanningSnapshot,
} from "@/utils/query";

export interface TaskEditResultPayload {
  updatedTask?: {
    id: UUID;
    vision_id: UUID | null;
    parent_task_id: UUID | null;
    content?: string;
    priority?: number;
    estimated_effort?: number | undefined;
    status?: string;
    planning_cycle_type?: string | null;
    planning_cycle_days?: number | null;
    planning_cycle_start_date?: string | null;
    people?: TaskWithSubtasks["people"];
  };
  structureChanged?: boolean;
  visionChanged?: boolean;
  parentTaskStatusChanged?: {
    taskId: UUID;
    oldStatus: string;
    newStatus: string;
  };
}

interface UseTaskEditorParams {
  isOpen: boolean;
  task?: TaskWithSubtasks | null;
  visionId: UUID | null;
  parentTaskId?: UUID | null;
  allTasks: TaskWithSubtasks[];
  allVisions?: Vision[];
  onSave?: (payload?: TaskEditResultPayload) => void;
  onClose: () => void;
  mode?: "single" | "bulk";
  visionLocked?: boolean;
  /** 控制子任务是否继承父任务规划周期，默认继承 */
  inheritPlanningFromParent?: boolean;
}

export interface UseTaskEditorHandlers {
  handleVisionChange: (visionId: UUID | null) => void;
  handleParentTaskChange: (parentTaskId: UUID | null) => void;
  handleContentChange: (content: string) => void;
  handlePriorityChange: (priority: number) => void;
  handlePersonChange: (personIds: UUID[]) => void;
  handlePlanningTypeChange: (cycleType: string | undefined) => void;
  handlePlanningStartDateChange: (startDate?: string) => void;
  handlePlanningNoPreset: () => void;
  handlePlanningToday: () => void;
  handlePlanningTomorrow: () => void;
  handlePlanningThisWeek: () => void;
  handlePlanningThisMonth: () => void;
  handleSubmit: (event: React.FormEvent<HTMLFormElement>) => Promise<void>;
  handleClose: () => void;
  handleErrorDismiss: () => void;
}

interface UseTaskEditorResult {
  formData: TaskCreate;
  loading: boolean;
  error: string | null;
  modalTitle: string;
  canChangeVision: boolean;
  filteredTasksForParent: TaskWithSubtasks[];
  excludedParentTaskIds: UUID[];
  visionStatusFilter: string[];
  taskStatusFilter: string[];
  focusTrigger: number;
  handlers: UseTaskEditorHandlers;
}

export function useTaskEditor(
  params: UseTaskEditorParams,
): UseTaskEditorResult {
  const {
    isOpen,
    task,
    visionId,
    parentTaskId,
    allTasks,
    onSave,
    onClose,
    mode = "single",
    visionLocked = false,
    inheritPlanningFromParent = true,
  } = params;

  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { getQuickSetOptions, getDefaultCycleSettings } = usePlanningCycle();
  const { value: preset, loading: presetLoading } = usePreferenceWithBootstrap<
    "none" | "today" | "this_week" | "this_month"
  >({
    key: "tasks.default_planning_preset",
    defaultValue: "none",
    module: "tasks",
    validator: (value) =>
      ["none", "today", "this_week", "this_month"].includes(value),
  });
  const { loading, error, setError, withLoading } = useModalState();
  const isBulkMode = mode === "bulk";

  const [formData, setFormData] = useState<TaskCreate>({
    vision_id: visionId,
    content: "",
    priority: 0,
    display_order: 0,
    parent_task_id: null,
    person_ids: [],
    planning_cycle_type: undefined,
    planning_cycle_days: undefined,
    planning_cycle_start_date: undefined,
  });

  const hasInitializedRef = useRef(false);
  const lastTaskIdRef = useRef<UUID | null>(null);
  const [focusTrigger, setFocusTrigger] = useState(0);

  const taskStatusFilter = useMemo(() => [...ALL_TASK_STATUSES], []);
  const visionStatusFilter = useMemo(() => [...ALL_VISION_STATUSES], []);

  const parentTask = useMemo(() => {
    if (!parentTaskId) return undefined;
    return allTasks.find((candidate) => candidate.id === parentTaskId);
  }, [parentTaskId, allTasks]);

  const initializeForm = useCallback(() => {
    if (task) {
      setFormData({
        vision_id: task.vision_id,
        content: task.content,
        priority: task.priority,
        display_order: task.display_order,
        parent_task_id: task.parent_task_id,
        person_ids: task.people?.map((person) => person.id) || [],
        planning_cycle_type:
          task.planning_cycle_type === "undefined" || !task.planning_cycle_type
            ? undefined
            : task.planning_cycle_type,
        planning_cycle_days: task.planning_cycle_days || undefined,
        planning_cycle_start_date: task.planning_cycle_start_date || undefined,
      });
    } else {
      let initialVisionId = visionId;
      let initialPlanningCycleType: string | undefined;
      let initialPlanningCycleDays: number | undefined;
      let initialPlanningCycleStartDate: string | undefined;

      if (parentTask) {
        initialVisionId = parentTask.vision_id || null;
        // 按需继承父任务的规划周期属性
        if (inheritPlanningFromParent) {
          initialPlanningCycleType =
            parentTask.planning_cycle_type || undefined;
          initialPlanningCycleDays =
            parentTask.planning_cycle_days || undefined;
          initialPlanningCycleStartDate =
            parentTask.planning_cycle_start_date || undefined;
        }
      }

      setFormData({
        vision_id: initialVisionId,
        content: "",
        priority: 0,
        display_order: 0,
        parent_task_id: parentTaskId ?? null,
        person_ids: [],
        planning_cycle_type: initialPlanningCycleType,
        planning_cycle_days: initialPlanningCycleDays,
        planning_cycle_start_date: initialPlanningCycleStartDate,
      });
    }

    setError(null);
    setFocusTrigger((value) => value + 1);
  }, [
    task,
    visionId,
    parentTaskId,
    setError,
    inheritPlanningFromParent,
    parentTask,
  ]);

  useEffect(() => {
    if (!isOpen) {
      hasInitializedRef.current = false;
      return;
    }

    const currentTaskId = task?.id ?? null;
    const isNewTaskContext = lastTaskIdRef.current !== currentTaskId;

    if (!hasInitializedRef.current || isNewTaskContext) {
      initializeForm();
      hasInitializedRef.current = true;
      lastTaskIdRef.current = currentTaskId;
    }
  }, [isOpen, task?.id, initializeForm]);

  const getDescendantTaskIds = useCallback(
    (taskId: UUID): Set<UUID> => {
      const descendants = new Set<UUID>();
      const taskMap = new Map<UUID, TaskWithSubtasks>();

      allTasks.forEach((candidate) => taskMap.set(candidate.id, candidate));

      const collectDescendants = (currentTaskId: UUID) => {
        const currentTask = taskMap.get(currentTaskId);
        if (!currentTask) return;
        currentTask.subtasks?.forEach((subtask) => {
          descendants.add(subtask.id);
          collectDescendants(subtask.id);
        });
      };

      collectDescendants(taskId);
      return descendants;
    },
    [allTasks],
  );

  const isAtMaxDepth = useCallback(
    (taskId: UUID): boolean => {
      const currentTask = allTasks.find((candidate) => candidate.id === taskId);
      return currentTask ? (currentTask.depth || 0) >= 4 : false;
    },
    [allTasks],
  );

  const filteredTasksForParent = useMemo(() => {
    const tasksWithSubtasks: TaskWithSubtasks[] = allTasks.map(
      (candidate) => ({
        ...candidate,
        subtasks: [],
        completion_percentage: 0,
        depth: 0,
      }),
    );

    return tasksWithSubtasks.filter((taskOption) => {
      if (taskOption.vision_id !== formData.vision_id) return false;

      if (!task) {
        if (taskOption.status === "done") {
          return !isAtMaxDepth(taskOption.id);
        }
        return !isAtMaxDepth(taskOption.id);
      }

      if (taskOption.id === task.id) return false;
      const descendantIds = getDescendantTaskIds(task.id);
      if (descendantIds.has(taskOption.id)) return false;
      return !isAtMaxDepth(taskOption.id);
    });
  }, [
    allTasks,
    formData.vision_id,
    task,
    getDescendantTaskIds,
    isAtMaxDepth,
  ]);

  const excludedParentTaskIds = useMemo(() => {
    const excluded = new Set<UUID>();
    allTasks.forEach((candidate) => {
      if (candidate.vision_id !== formData.vision_id) return;
      if (isAtMaxDepth(candidate.id)) {
        excluded.add(candidate.id);
      }
    });

    if (task) {
      excluded.add(task.id);
      getDescendantTaskIds(task.id).forEach((taskId) => excluded.add(taskId));
    }

    return Array.from(excluded);
  }, [allTasks, formData.vision_id, getDescendantTaskIds, isAtMaxDepth, task]);

  const updateParentTaskStatusRecursively = useCallback(
    async (taskId: UUID) => {
      const updatedParentIds: UUID[] = [];
      const oldStatuses: string[] = [];
      const newStatuses: string[] = [];
      const updatedTasks: Task[] = [];

      let currentTaskId: UUID | null = taskId;

      while (currentTaskId) {
        const currentTask = allTasks.find(
          (candidate) => candidate.id === currentTaskId,
        );
        if (!currentTask) break;

        if (currentTask.status === "done") {
          try {
            const updated = await tasksApi.update(currentTask.id, {
              status: "in_progress",
            });
            updatedParentIds.push(currentTask.id);
            oldStatuses.push("done");
            newStatuses.push("in_progress");
            updatedTasks.push(updated);
          } catch (err) {
            logger.warn(
              `Failed to update parent task ${currentTask.id} status:`,
              err,
            );
          }
        }

        currentTaskId = currentTask.parent_task_id || null;
      }

      return { updatedParentIds, oldStatuses, newStatuses, updatedTasks };
    },
    [allTasks],
  );

  const applyPlanningPreset = useCallback(
    (presetKey: "today" | "tomorrow" | "thisWeek" | "thisMonth") => {
      const now = new Date();
      const options = getQuickSetOptions(now);
      const presetSettings = options[presetKey];

      const cycleType: ExtendedPlanningViewType =
        presetKey === "thisWeek"
          ? "week"
          : presetKey === "thisMonth"
            ? "month"
            : "day";

      setFormData((prev) => ({
        ...prev,
        planning_cycle_type: cycleType,
        planning_cycle_days: presetSettings.days,
        planning_cycle_start_date: presetSettings.startDate,
      }));
    },
    [getQuickSetOptions],
  );

  const handlePlanningNoPreset = useCallback(() => {
    setFormData((prev) => ({
      ...prev,
      planning_cycle_type: undefined,
      planning_cycle_days: undefined,
      planning_cycle_start_date: undefined,
    }));
  }, []);

  const handlePlanningToday = useCallback(() => {
    applyPlanningPreset("today");
  }, [applyPlanningPreset]);

  const handlePlanningTomorrow = useCallback(() => {
    applyPlanningPreset("tomorrow");
  }, [applyPlanningPreset]);

  const handlePlanningThisWeek = useCallback(() => {
    applyPlanningPreset("thisWeek");
  }, [applyPlanningPreset]);

  const handlePlanningThisMonth = useCallback(() => {
    applyPlanningPreset("thisMonth");
  }, [applyPlanningPreset]);

  useEffect(() => {
    if (!isOpen || task || presetLoading) return;

    const inheritedPlanningActive =
      inheritPlanningFromParent &&
      Boolean(parentTaskId && parentTask) &&
      Boolean(
        parentTask?.planning_cycle_type &&
          parentTask?.planning_cycle_days &&
          parentTask?.planning_cycle_start_date,
      );

    if (inheritedPlanningActive) return;

    const isPlanningEmpty =
      (!formData.planning_cycle_type || formData.planning_cycle_type === "") &&
      !formData.planning_cycle_days &&
      !formData.planning_cycle_start_date;

    if (!isPlanningEmpty) return;

    if (preset === "today") {
      handlePlanningToday();
    } else if (preset === "this_week") {
      handlePlanningThisWeek();
    } else if (preset === "this_month") {
      handlePlanningThisMonth();
    }
  }, [
    isOpen,
    task,
    preset,
    presetLoading,
    formData.planning_cycle_type,
    formData.planning_cycle_days,
    formData.planning_cycle_start_date,
    inheritPlanningFromParent,
    parentTaskId,
    parentTask,
    handlePlanningToday,
    handlePlanningThisWeek,
    handlePlanningThisMonth,
  ]);

  const handleVisionChange = useCallback(
    (newVisionId: UUID | null) => {
      setFormData((prev) => ({
        ...prev,
        vision_id: newVisionId ?? visionId,
        parent_task_id:
          (newVisionId ?? visionId) !== visionId ? null : prev.parent_task_id,
      }));
    },
    [visionId],
  );

  const handleParentTaskChange = useCallback((parentId: UUID | null) => {
    setFormData((prev) => ({
      ...prev,
      parent_task_id: parentId,
    }));
  }, []);

  const handleContentChange = useCallback((content: string) => {
    setFormData((prev) => ({
      ...prev,
      content,
    }));
  }, []);

  const handlePriorityChange = useCallback((priority: number) => {
    setFormData((prev) => ({
      ...prev,
      priority,
    }));
  }, []);

  const handlePersonChange = useCallback((personIds: UUID[]) => {
    setFormData((prev) => ({
      ...prev,
      person_ids: personIds,
    }));
  }, []);

  const handlePlanningTypeChange = useCallback(
    (cycleType: string | undefined) => {
      const resolvedType = cycleType === "" ? undefined : cycleType;

      let defaultStartDate: string | undefined = undefined;
      let defaultDays: number | undefined = undefined;

      if (resolvedType) {
        const now = new Date();
        const settings = getDefaultCycleSettings(
          resolvedType as ExtendedPlanningViewType,
          now,
        );
        defaultStartDate = settings.startDate;
        defaultDays = settings.days;
      }

      setFormData((prev) => ({
        ...prev,
        planning_cycle_type: resolvedType,
        planning_cycle_days: defaultDays,
        planning_cycle_start_date: defaultStartDate,
      }));
    },
    [getDefaultCycleSettings],
  );

  const handlePlanningStartDateChange = useCallback(
    (startDate?: string) => {
      setFormData((prev) => {
        const cycleType = prev.planning_cycle_type;
        const planningCycleDays =
          cycleType && startDate
            ? getDefaultCycleSettings(
                cycleType as ExtendedPlanningViewType,
                parseDateKey(startDate),
              ).days
            : prev.planning_cycle_days;

        return {
          ...prev,
          planning_cycle_days: planningCycleDays,
          planning_cycle_start_date: startDate,
        };
      });
    },
    [getDefaultCycleSettings],
  );

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      if (!formData.content.trim()) {
        setError(t("taskForm.validation.contentRequired"));
        return;
      }

      if (
        isBulkMode &&
        formData.content
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter((line) => line.length > 0).length === 0
      ) {
        setError(t("taskForm.validation.contentRequired"));
        return;
      }

      try {
        await withLoading(async () => {
          const cacheCandidates: Task[] = [];
          const affectedTaskIds = new Set<UUID>();
          const planningSnapshots: PlanningSnapshot[] = [];

          const recordTask = (updatedTask?: Task | null) => {
            if (updatedTask && typeof updatedTask.id === "string") {
              cacheCandidates.push(updatedTask);
              affectedTaskIds.add(updatedTask.id);
            }
          };

          const recordTasks = (tasks: Task[] = []) => {
            tasks.forEach((item) => recordTask(item));
          };

          const trackPlanningChange = (
            previous?: Task | TaskWithSubtasks | null,
            next?: Task | null,
          ) => {
            const prevType = previous?.planning_cycle_type ?? null;
            const prevDate = previous?.planning_cycle_start_date ?? null;
            const nextType = next?.planning_cycle_type ?? null;
            const nextDate = next?.planning_cycle_start_date ?? null;

            if (prevType === nextType && prevDate === nextDate) {
              return;
            }

            planningSnapshots.push({
              planning_cycle_type: prevType,
              planning_cycle_start_date: prevDate,
            });
            planningSnapshots.push({
              planning_cycle_type: nextType,
              planning_cycle_start_date: nextDate,
            });
          };

          const applyCacheUpdates = async () => {
            cacheCandidates.forEach((updatedTask) =>
              updateTaskCaches(queryClient, updatedTask),
            );

            if (affectedTaskIds.size > 0) {
              await invalidateTasksByIds(
                queryClient,
                Array.from(affectedTaskIds),
                { skipEvents: true },
              );
            }

            if (planningSnapshots.length > 0) {
              await invalidatePlanningSnapshots(queryClient, planningSnapshots);
            }
          };

          if (task) {
            const visionChanged = formData.vision_id !== task.vision_id;
            let latestUpdatedTask: Task | null = null;

            if (visionChanged) {
              const moveResult = await tasksApi.move(
                task.id,
                task.parent_task_id || undefined,
                formData.parent_task_id || undefined,
                formData.vision_id,
                formData.display_order,
              );
              recordTask(moveResult);
              recordTasks(moveResult.updated_descendants ?? []);
              const updateData: TaskUpdate = {
                content: formData.content.trim(),
                priority: formData.priority,
                planning_cycle_type:
                  formData.planning_cycle_type === "undefined" ||
                  !formData.planning_cycle_type
                    ? null
                    : formData.planning_cycle_type,
                planning_cycle_days: formData.planning_cycle_days || null,
                planning_cycle_start_date:
                  formData.planning_cycle_start_date || null,
                person_ids: formData.person_ids ?? [],
              };

              if (formData.parent_task_id !== task.parent_task_id) {
                updateData.parent_task_id = formData.parent_task_id;
              }

              if (
                Object.keys(updateData).some(
                  (key) => updateData[key as keyof TaskUpdate] !== undefined,
                )
              ) {
                const updatedTask = await tasksApi.update(task.id, updateData);
                latestUpdatedTask = updatedTask;
                recordTask(updatedTask);
                trackPlanningChange(task, updatedTask);
              }

              onSave?.({
                updatedTask: {
                  id: task.id,
                  vision_id: formData.vision_id,
                  parent_task_id: formData.parent_task_id || null,
                  content: formData.content.trim(),
                  priority: formData.priority,
                  planning_cycle_type:
                    formData.planning_cycle_type === "undefined" ||
                    !formData.planning_cycle_type
                      ? null
                      : formData.planning_cycle_type,
                  planning_cycle_days: formData.planning_cycle_days || null,
                  planning_cycle_start_date:
                    formData.planning_cycle_start_date || null,
                  people: latestUpdatedTask?.people ?? task.people ?? undefined,
                },
                structureChanged:
                  visionChanged ||
                  (task.parent_task_id || null) !==
                    (formData.parent_task_id || null),
                visionChanged,
              });

              await applyCacheUpdates();

              toast.showSuccess(
                t("taskForm.messages.updateSuccessTitle"),
                t("taskForm.messages.updateSuccessMessage", {
                  content: formData.content.trim(),
                }),
              );
            } else {
              const updateData: TaskUpdate = {
                content: formData.content.trim(),
                priority: formData.priority,
                planning_cycle_type:
                  formData.planning_cycle_type === "undefined" ||
                  !formData.planning_cycle_type
                    ? null
                    : formData.planning_cycle_type,
                planning_cycle_days: formData.planning_cycle_days || null,
                planning_cycle_start_date:
                  formData.planning_cycle_start_date || null,
                parent_task_id: formData.parent_task_id,
                person_ids: formData.person_ids ?? [],
              };

              const updatedTask = await tasksApi.update(task.id, updateData);
              recordTask(updatedTask);
              trackPlanningChange(task, updatedTask);

              onSave?.({
                updatedTask: {
                  id: task.id,
                  vision_id: visionId,
                  parent_task_id: formData.parent_task_id || null,
                  content: formData.content.trim(),
                  priority: formData.priority,
                  planning_cycle_type:
                    formData.planning_cycle_type === "undefined" ||
                    !formData.planning_cycle_type
                      ? null
                      : formData.planning_cycle_type,
                  planning_cycle_days: formData.planning_cycle_days || null,
                  planning_cycle_start_date:
                    formData.planning_cycle_start_date || null,
                  people: updatedTask.people ?? task.people ?? undefined,
                },
                structureChanged:
                  (task.parent_task_id || null) !==
                  (formData.parent_task_id || null),
                visionChanged: false,
              });

              await applyCacheUpdates();

              toast.showSuccess(
                t("taskForm.messages.updateSuccessTitle"),
                t("taskForm.messages.updateSuccessMessage", {
                  content: formData.content.trim(),
                }),
              );
            }
          } else {
            if (isBulkMode) {
              const rawLines = formData.content.split(/\r?\n/);
              const preparedLines = rawLines
                .map((line) => line.trim())
                .filter((line) => line.length > 0);

              interface FailedLine {
                index: number;
                message: string;
                content: string;
              }

              const failedLines: FailedLine[] = [];
              const successfulTasks: Task[] = [];

              for (const [index, content] of preparedLines.entries()) {
                const createData: TaskCreate = {
                  ...formData,
                  content,
                  parent_task_id: formData.parent_task_id,
                };

                try {
                  const createdTask = await tasksApi.create(createData);
                  successfulTasks.push(createdTask);
                  recordTask(createdTask);
                  trackPlanningChange(null, createdTask);
                } catch (err) {
                  const errorMessage =
                    err instanceof Error
                      ? err.message
                      : t("common.operationFailed");
                  failedLines.push({
                    index: index + 1,
                    message: errorMessage,
                    content,
                  });
                }
              }

              if (successfulTasks.length === 0) {
                const detail = failedLines
                  .map((line) => `#${line.index}: ${line.message}`)
                  .join("; ");
                setError(
                  t("taskForm.messages.bulkCreateFailedInline", { detail }),
                );
                toast.showError(
                  t("taskForm.messages.bulkCreateFailedTitle"),
                  t("taskForm.messages.bulkCreateFailedMessage"),
                );
                return;
              }

              let parentTaskStatusChangedPayload:
                | TaskEditResultPayload["parentTaskStatusChanged"]
                | undefined;

              if (formData.parent_task_id) {
                try {
                  const {
                    updatedParentIds,
                    oldStatuses,
                    newStatuses,
                    updatedTasks,
                  } = await updateParentTaskStatusRecursively(
                    formData.parent_task_id,
                  );
                  recordTasks(updatedTasks);

                  if (updatedParentIds.length > 0) {
                    parentTaskStatusChangedPayload = {
                      taskId: updatedParentIds[0],
                      oldStatus: oldStatuses.join(", "),
                      newStatus: newStatuses.join(", "),
                    };
                  }
                } catch (err) {
                  logger.warn(
                    "Failed to auto-update parent task statuses:",
                    err,
                  );
                }
              }

              onSave?.({
                structureChanged: true,
                visionChanged: false,
                ...(parentTaskStatusChangedPayload
                  ? { parentTaskStatusChanged: parentTaskStatusChangedPayload }
                  : {}),
              });

              await applyCacheUpdates();

              if (failedLines.length > 0) {
                const detail = failedLines
                  .slice(0, 3)
                  .map((line) => `#${line.index}: ${line.message}`)
                  .join("; ");
                setError(
                  t("taskForm.messages.bulkCreatePartialInline", { detail }),
                );
                setFormData((prev) => ({
                  ...prev,
                  content: failedLines.map((line) => line.content).join("\n"),
                }));
                toast.showWarning(
                  t("taskForm.messages.bulkCreatePartialTitle"),
                  t("taskForm.messages.bulkCreatePartialMessage", {
                    successCount: successfulTasks.length,
                    failureCount: failedLines.length,
                  }),
                );
                return;
              }

              toast.showSuccess(
                t("taskForm.messages.bulkCreateSuccessTitle"),
                t("taskForm.messages.bulkCreateSuccessMessage", {
                  successCount: successfulTasks.length,
                }),
              );

              setTimeout(() => {
                onClose();
              }, 100);
              return;
            }

            const createData: TaskCreate = {
              ...formData,
              content: formData.content.trim(),
              parent_task_id: formData.parent_task_id,
            };

            const createdTask = await tasksApi.create(createData);
            recordTask(createdTask);
            trackPlanningChange(null, createdTask);

            if (formData.parent_task_id) {
              try {
                const {
                  updatedParentIds,
                  oldStatuses,
                  newStatuses,
                  updatedTasks,
                } = await updateParentTaskStatusRecursively(
                  formData.parent_task_id,
                );
                recordTasks(updatedTasks);

                if (updatedParentIds.length > 0) {
                  onSave?.({
                    structureChanged: true,
                    visionChanged: false,
                    parentTaskStatusChanged: {
                      taskId: updatedParentIds[0],
                      oldStatus: oldStatuses.join(", "),
                      newStatus: newStatuses.join(", "),
                    },
                  });
                  await applyCacheUpdates();
                  onClose();
                  return;
                }
              } catch (err) {
                logger.warn("Failed to auto-update parent task statuses:", err);
              }
            }

            onSave?.({ structureChanged: true, visionChanged: false });
            await applyCacheUpdates();

            toast.showSuccess(
              t("taskForm.messages.createSuccessTitle"),
              t("taskForm.messages.createSuccessMessage", {
                content: formData.content.trim(),
              }),
            );

            setTimeout(() => {
              onClose();
            }, 100);
          }
        });
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : t("common.operationFailed");
        setError(errorMessage);

        toast.showError(
          t("taskForm.messages.saveFailedTitle"),
          `${t("common.operationFailed")}：${errorMessage}`,
        );
      }
    },
    [
      formData,
      task,
      t,
      setError,
      withLoading,
      toast,
      queryClient,
      onSave,
      visionId,
      onClose,
      updateParentTaskStatusRecursively,
      isBulkMode,
    ],
  );

  const handleClose = useCallback(() => {
    if (!loading) {
      setError(null);
      onClose();
    }
  }, [loading, onClose, setError]);

  const handleErrorDismiss = useCallback(() => {
    setError(null);
  }, [setError]);

  const modalTitle = useMemo(() => {
    if (mode === "bulk") return t("taskForm.modalTitle.bulkCreate");
    if (task) return t("taskForm.modalTitle.edit");
    if (parentTaskId) return t("taskForm.modalTitle.createSub");
    return t("visions.vision.actions.createRootTask");
  }, [mode, task, parentTaskId, t]);

  const canChangeVision = useMemo(() => {
    if (visionLocked) return false;
    if (!task) return true;
    return task.parent_task_id === null;
  }, [task, visionLocked]);

  return {
    formData,
    loading,
    error,
    modalTitle,
    canChangeVision,
    filteredTasksForParent,
    excludedParentTaskIds,
    visionStatusFilter,
    taskStatusFilter,
    focusTrigger,
    handlers: {
      handleVisionChange,
      handleParentTaskChange,
      handleContentChange,
      handlePriorityChange,
      handlePersonChange,
      handlePlanningTypeChange,
      handlePlanningStartDateChange,
      handlePlanningNoPreset,
      handlePlanningToday,
      handlePlanningTomorrow,
      handlePlanningThisWeek,
      handlePlanningThisMonth,
      handleSubmit,
      handleClose,
      handleErrorDismiss,
    },
  };
}
