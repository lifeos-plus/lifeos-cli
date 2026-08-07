import React, {
  useState,
  useCallback,
  useMemo,
  type MouseEvent as ReactMouseEvent,
  type FocusEvent as ReactFocusEvent,
} from "react";
import { useTranslation } from "react-i18next";
import ActionButton, {
  ActionButtonGroup,
  EditButton,
  DeleteButton,
  ExpandButton,
} from "./ActionButton";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { TaskWithSubtasks } from "@/services/api";
import type { Habit } from "@/services/api/habits";
import type { Vision } from "@/services/api/visions";
import { logger } from "@/utils/core";
import { formatDuration, formatDateTime, formatDate } from "@/utils/datetime";
import PersonsList from "./PersonsList";
import { tasksApi } from "@/services/api/tasks";
import EnumSelect from "./selects/EnumSelect";
import {
  TASK_STATUS_LABELS,
  getTaskStatusStyling,
  PRIORITY,
} from "@/utils/constants";
import type { UUID } from "@/types/primitive";
import HoverTooltipOverlay from "./HoverTooltipOverlay";
import { TaskTooltipContent } from "./tooltips";
import { useHoverTooltip } from "@/hooks/useHoverTooltip";
import { Icon } from "./icons";

// Types
interface DraggableTaskListProps {
  tasks: TaskWithSubtasks[];
  onEditTask: (task: TaskWithSubtasks) => void;
  onDeleteTask: (task: TaskWithSubtasks) => void;
  onStatusUpdate: (task: TaskWithSubtasks, newStatus: string) => void;
  onAddSubtask: (parentId?: UUID | null) => void;
  onViewTimeRecords: (task: TaskWithSubtasks) => void;
  onCreateNote: (task: TaskWithSubtasks) => void;
  onViewNotes: (task: TaskWithSubtasks) => void;
  onCreateTimeRecord: (task: TaskWithSubtasks) => void;
  expandedTasks?: Set<UUID>;
  onToggleExpansion?: (taskId: UUID) => void;
  onTasksReorder?: (reorderedTasks: TaskWithSubtasks[]) => void | Promise<void>;
  habitTaskAssociations?: Record<UUID, Habit[]>;
  // Vision information for planning page
  visions?: Vision[];
  showVisionInfo?: boolean;
  // Context for different pages
  isPlanningPage?: boolean;
}

interface SortableTaskItemProps {
  task: TaskWithSubtasks;
  depth: number;
  isExpanded: boolean;
  hasSubtasks: boolean;
  parentTask?: TaskWithSubtasks | null;
  onEditTask: (task: TaskWithSubtasks) => void;
  onDeleteTask: (task: TaskWithSubtasks) => void;
  onStatusUpdate: (task: TaskWithSubtasks, newStatus: string) => void;
  onAddSubtask: (parentId?: UUID | null) => void;
  onViewTimeRecords: (task: TaskWithSubtasks) => void;
  onCreateNote: (task: TaskWithSubtasks) => void;
  onViewNotes: (task: TaskWithSubtasks) => void;
  onCreateTimeRecord: (task: TaskWithSubtasks) => void;
  onToggleExpansion: (taskId: UUID) => void;
  habitTaskAssociations?: Record<UUID, Habit[]>;
  // Vision information for planning page
  visions?: Vision[];
  showVisionInfo?: boolean;
  // Context for different pages
  isPlanningPage?: boolean;
}

interface TaskDragInfo {
  task: TaskWithSubtasks;
  parentId: UUID | null;
  level: number;
}

const readTaskRelationshipCount = (
  task: TaskWithSubtasks,
  keys: string[],
): number => {
  const taskRecord = task as unknown as Record<string, unknown>;
  let count = 0;
  for (const key of keys) {
    const value = taskRecord[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      count = Math.max(count, value);
    }
    if (typeof value === "string" && value.trim() !== "") {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        count = Math.max(count, parsed);
      }
    }
  }
  return count;
};

// Task hierarchy utilities
class TaskHierarchyManager {
  private taskMap = new Map<UUID, TaskDragInfo>();
  private rootTasks: TaskWithSubtasks[] = [];

  constructor(tasks: TaskWithSubtasks[]) {
    this.rootTasks = tasks;
    this.buildTaskMap(tasks);
  }

  private buildTaskMap(
    tasks: TaskWithSubtasks[],
    parentId: UUID | null = null,
    level: number = 0,
  ) {
    tasks.forEach((task) => {
      this.taskMap.set(task.id, { task, parentId, level });
      if (task.subtasks?.length) {
        this.buildTaskMap(task.subtasks, task.id, level + 1);
      }
    });
  }

  getTaskInfo(taskId: UUID): TaskDragInfo | undefined {
    return this.taskMap.get(taskId);
  }

  getSiblings(taskId: UUID): TaskWithSubtasks[] {
    const info = this.taskMap.get(taskId);
    if (!info) return [];

    if (info.parentId === null) {
      // Root level - return root tasks
      return this.rootTasks;
    } else {
      // Find parent and return its subtasks
      const parentInfo = this.taskMap.get(info.parentId);
      return parentInfo?.task.subtasks || [];
    }
  }

  updateTaskOrder(
    tasks: TaskWithSubtasks[],
    reorderedSiblings: TaskWithSubtasks[],
    parentId: UUID | null,
  ): TaskWithSubtasks[] {
    if (parentId === null) {
      // Root level reordering
      return reorderedSiblings;
    }

    return this.updateTaskInHierarchy(tasks, parentId, reorderedSiblings);
  }

  private updateTaskInHierarchy(
    tasks: TaskWithSubtasks[],
    parentId: UUID,
    newSubtasks: TaskWithSubtasks[],
  ): TaskWithSubtasks[] {
    return tasks.map((task) => {
      if (task.id === parentId) {
        return { ...task, subtasks: newSubtasks };
      }
      if (task.subtasks?.length) {
        return {
          ...task,
          subtasks: this.updateTaskInHierarchy(
            task.subtasks,
            parentId,
            newSubtasks,
          ),
        };
      }
      return task;
    });
  }
}

// Task Item Component
const SortableTaskItem: React.FC<SortableTaskItemProps> = ({
  task,
  depth,
  isExpanded,
  hasSubtasks,
  parentTask,
  onEditTask,
  onDeleteTask,
  onStatusUpdate,
  onAddSubtask,
  onViewTimeRecords,
  onCreateNote,
  onViewNotes,
  onCreateTimeRecord,
  onToggleExpansion,
  habitTaskAssociations,
  visions,
  showVisionInfo,
  isPlanningPage,
}) => {
  const { t } = useTranslation();
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id });

  const style: React.CSSProperties = {
    transform: transform ? CSS.Transform.toString(transform) : undefined,
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  // Get associated habit for this task
  const associatedHabits = habitTaskAssociations?.[task.id] ?? [];
  const hasAssociatedHabits = associatedHabits.length > 0;

  // Get associated vision for this task (for planning page)
  const associatedVision =
    showVisionInfo && visions
      ? visions.find((vision) => vision.id === task.vision_id)
      : null;

  // Get task status styling configuration (currently not used for visual styling)
  const statusStyling = getTaskStatusStyling(task.status);
  const priorityIndex = Number.isFinite(task.priority)
    ? Math.max(0, Math.min(PRIORITY.length - 1, Number(task.priority ?? 0)))
    : 0;
  const priorityInfo = PRIORITY[priorityIndex] ?? PRIORITY[0];
  const hasNotes =
    readTaskRelationshipCount(task, [
      "notes_count",
      "note_count",
      "linked_notes_count",
    ]) > 0;
  const hasTimeLogs =
    readTaskRelationshipCount(task, [
      "timelogs_count",
      "timelog_count",
      "actual_effort_self",
    ]) > 0;
  const subduedClass = "opacity-40 hover:opacity-60 transition-opacity";
  const noteButtonClass = hasNotes ? undefined : subduedClass;
  const timeLogButtonClass = hasTimeLogs ? undefined : subduedClass;

  const {
    tooltipState: taskTooltipState,
    showTooltip: showTaskTooltip,
    schedulePositionUpdate: updateTaskTooltipPosition,
    hideTooltip: hideTaskTooltip,
    showTooltipForElement: showTaskTooltipForElement,
  } = useHoverTooltip<null>({
    defaultOffset: { x: 16, y: -12 },
    focusOffset: (rect) => ({ x: -rect.width / 2, y: -16 }),
  });

  const tooltipContent = useMemo(() => {
    const noneLabel = t("draggableTaskList.tooltip.none");
    const priorityIndex = Math.max(
      0,
      Math.min(
        PRIORITY.length - 1,
        Number.isFinite(task.priority) ? task.priority : 0,
      ),
    );
    const priorityInfo = PRIORITY[priorityIndex] ?? PRIORITY[0];
    const statusLabel =
      TASK_STATUS_LABELS[task.status as keyof typeof TASK_STATUS_LABELS] ??
      task.status;

    const planningCycleValue = (() => {
      if (!task.planning_cycle_type) return null;
      const cycleTypeMap: Record<string, string> = {
        day: t("draggableTaskList.planningCycle.day"),
        week: t("draggableTaskList.planningCycle.week"),
        month: t("draggableTaskList.planningCycle.month"),
        year: t("draggableTaskList.planningCycle.year"),
        "7years": t("draggableTaskList.planningCycle.7years"),
      };
      const periodText =
        cycleTypeMap[task.planning_cycle_type] || task.planning_cycle_type;
      if (task.planning_cycle_start_date) {
        const formattedStart = formatDate(task.planning_cycle_start_date);
        return t("draggableTaskList.tooltip.planningCycleValueWithDate", {
          period: periodText,
          date: formattedStart,
        });
      }
      return periodText;
    })();

    const totalEffort = formatDuration(task.actual_effort_total ?? 0);
    const selfEffort = formatDuration(task.actual_effort_self ?? 0);
    const createdAt = formatDateTime(task.created_at ?? "") || noneLabel;
    const updatedAt = formatDateTime(task.updated_at ?? "") || noneLabel;

    const lines = [
      t("draggableTaskList.tooltip.vision", {
        vision: associatedVision?.name ?? noneLabel,
      }),
      t("draggableTaskList.tooltip.parent", {
        parent: parentTask?.content ?? noneLabel,
      }),
      t("draggableTaskList.tooltip.priority", {
        priority: priorityInfo.label,
      }),
      t("draggableTaskList.tooltip.status", { status: statusLabel }),
      t("draggableTaskList.tooltip.planningCycle", {
        planning: planningCycleValue ?? noneLabel,
      }),
      t("draggableTaskList.tooltip.totalEffort", { duration: totalEffort }),
      t("draggableTaskList.tooltip.selfEffort", { duration: selfEffort }),
      t("draggableTaskList.tooltip.createdAt", { date: createdAt }),
      t("draggableTaskList.tooltip.updatedAt", { date: updatedAt }),
    ];

    return {
      title: t("draggableTaskList.tooltip.title", { name: task.content }),
      lines,
      visionName: associatedVision?.name ?? null,
      parentName: parentTask?.content ?? null,
    };
  }, [
    t,
    task.priority,
    task.status,
    task.planning_cycle_type,
    task.planning_cycle_start_date,
    task.actual_effort_total,
    task.actual_effort_self,
    task.created_at,
    task.updated_at,
    task.content,
    associatedVision,
    parentTask,
  ]);

  const handleTaskMouseEnter = useCallback(
    (event: ReactMouseEvent<HTMLElement>) => {
      if (!tooltipContent) return;
      showTaskTooltip({
        payload: null,
        position: { x: event.clientX, y: event.clientY },
      });
    },
    [showTaskTooltip, tooltipContent],
  );

  const handleTaskMouseMove = useCallback(
    (event: ReactMouseEvent<HTMLElement>) => {
      if (!taskTooltipState) {
        showTaskTooltip({
          payload: null,
          position: { x: event.clientX, y: event.clientY },
        });
        return;
      }
      updateTaskTooltipPosition({ x: event.clientX, y: event.clientY });
    },
    [showTaskTooltip, taskTooltipState, updateTaskTooltipPosition],
  );

  const handleTaskMouseLeave = useCallback(() => {
    hideTaskTooltip();
  }, [hideTaskTooltip]);

  const handleTaskFocus = useCallback(
    (event: ReactFocusEvent<HTMLElement>) => {
      if (!tooltipContent) return;
      showTaskTooltipForElement(null, event.currentTarget);
    },
    [showTaskTooltipForElement, tooltipContent],
  );

  const handleTaskBlur = useCallback(() => {
    hideTaskTooltip();
  }, [hideTaskTooltip]);

  return (
    <>
      <div
        ref={setNodeRef}
        style={{
          ...style,
          paddingLeft: `min(${depth * 16}px, 15vw)`,
        }}
        className="dnd-sortable-item group flex w-full min-w-0 max-w-full items-start"
      >
        {/* Expand/Collapse Button */}
        <div className="mr-1 mt-2 flex-shrink-0 sm:mr-2 sm:mt-3">
          <ExpandButton
            isExpanded={isExpanded}
            onClick={() => hasSubtasks && onToggleExpansion(task.id)}
            disabled={!hasSubtasks}
            className={
              hasSubtasks
                ? "cursor-pointer transition-colors hover:bg-primary/20 hover:shadow-sm"
                : ""
            }
            ariaLabel={
              hasSubtasks
                ? isExpanded
                  ? t("draggableTaskList.expandButton.collapse")
                  : t("draggableTaskList.expandButton.expand")
                : t("draggableTaskList.expandButton.noSubtasks")
            }
            expandedLabel={t("draggableTaskList.expandButton.collapse")}
            collapsedLabel={t("draggableTaskList.expandButton.expand")}
          />
        </div>

        {/* Task Card */}
        <div className="flex-1 w-full min-w-0 max-w-full overflow-hidden">
          <div
            className={`w-full min-w-0 max-w-full overflow-hidden rounded-lg p-2 transition-all duration-200 ease-in-out sm:p-3 ${statusStyling.bgColor} ${statusStyling.hoverColor}`}
          >
            <div
              data-testid="draggable-task-layout"
              className="grid w-full min-w-0 grid-cols-1 items-stretch gap-2 2xl:grid-cols-[minmax(0,1fr)_auto] 2xl:items-center"
            >
              {/* Draggable Task Info */}
              <div
                {...attributes}
                {...listeners}
                className="flex w-full min-w-0 cursor-move flex-wrap items-start gap-2 overflow-hidden sm:flex-nowrap sm:items-center sm:gap-3"
              >
                <span className="text-base-content text-lg flex-shrink-0">
                  {priorityInfo.iconName ? (
                    <Icon name={priorityInfo.iconName} size={18} aria-hidden />
                  ) : null}
                </span>

                {/* Vision Badge for Planning Page */}
                {associatedVision && (
                  <span
                    className="inline-flex max-w-[min(12rem,60vw)] flex-shrink-0 items-center rounded-full border border-primary/30 bg-primary/10 px-2 py-1 text-base font-medium text-primary"
                    title={`${t("draggableTaskList.vision.label")}: ${associatedVision.name}`}
                  >
                    <Icon
                      name="sparkles"
                      size={16}
                      className="mr-1"
                      aria-hidden
                    />
                    <span className="truncate">{associatedVision.name}</span>
                  </span>
                )}

                <div className="flex min-w-0 max-w-full basis-full flex-col overflow-hidden sm:basis-auto sm:flex-1 sm:flex-row sm:items-center">
                  <h4
                    className="w-full min-w-0 flex-1 overflow-hidden text-base font-medium text-base-content"
                    onMouseEnter={handleTaskMouseEnter}
                    onMouseMove={handleTaskMouseMove}
                    onMouseLeave={handleTaskMouseLeave}
                    onFocus={handleTaskFocus}
                    onBlur={handleTaskBlur}
                    tabIndex={0}
                    aria-label={`${tooltipContent.title} ${tooltipContent.lines.join(" ")}`}
                  >
                    <span className="truncate block w-full">
                      {task.content}
                    </span>
                  </h4>

                  {/* Task metadata wraps responsively. */}
                  <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-sm text-base-content/50 mt-1 sm:mt-0 sm:ml-3">
                    <span
                      className="flex-shrink-0 inline-flex items-center gap-1"
                      title={t("draggableTaskList.meta.totalEffort")}
                    >
                      <Icon name="timer" size={16} aria-hidden />
                      {formatDuration(task.actual_effort_total ?? 0)}
                    </span>
                    {/* Planning cycle information - hide in planning page to save space, and hide in small/medium screens */}
                    {!isPlanningPage && task.planning_cycle_type && (
                      <span
                        className="hidden lg:inline flex-shrink-0"
                        title={t("draggableTaskList.meta.plannedActions")}
                      >
                        <Icon
                          name="calendar"
                          size={16}
                          className="mr-1"
                          aria-hidden
                        />
                        {(() => {
                          const cycleTypeMap: Record<string, string> = {
                            day: t("draggableTaskList.planningCycle.day"),
                            week: t("draggableTaskList.planningCycle.week"),
                            month: t("draggableTaskList.planningCycle.month"),
                            year: t("draggableTaskList.planningCycle.year"),
                            "7years": t(
                              "draggableTaskList.planningCycle.7years",
                            ),
                          };

                          if (task.planning_cycle_start_date) {
                            const startDate = formatDate(
                              task.planning_cycle_start_date,
                            );
                            const cycleTypeText =
                              cycleTypeMap[task.planning_cycle_type] ||
                              task.planning_cycle_type;
                            return `${t("draggableTaskList.planningCycle.from", { date: startDate })} 1${cycleTypeText}${t("draggableTaskList.planningCycle.within")}`;
                          }

                          // Fallback if no start date
                          const cycleTypeText =
                            cycleTypeMap[task.planning_cycle_type] ||
                            task.planning_cycle_type;
                          return cycleTypeText;
                        })()}
                      </span>
                    )}
                    {/* Area badge if task inherits vision area (optional) */}
                  </div>
                </div>

                {/* Associated Persons */}
                {task.people && task.people.length > 0 && (
                  <PersonsList
                    people={task.people}
                    inline
                    max={3}
                    className="min-w-0 max-w-full overflow-hidden"
                  />
                )}
              </div>

              {/* Action Buttons - Always visible with ultra-compact design */}
              <div
                data-testid="draggable-task-actions"
                className="flex w-full min-w-0 flex-wrap items-center justify-end gap-1 2xl:ml-2 2xl:w-auto 2xl:flex-nowrap"
              >
                <div className="w-28 min-w-0 sm:w-32 lg:w-24">
                  <EnumSelect
                    value={task.status}
                    onChange={(v) =>
                      onStatusUpdate(task, String(v ?? task.status))
                    }
                    options={Object.entries(TASK_STATUS_LABELS).map(
                      ([value, label]) => ({ value, label }),
                    )}
                    id={`task-status-${task.id}`}
                  />
                </div>

                <ActionButtonGroup
                  gap="sm"
                  align="end"
                  className="flex-wrap gap-1"
                >
                  <EditButton onClick={() => onEditTask(task)} size="sm" />
                  <ActionButton
                    label=""
                    iconName="plus"
                    color="primary"
                    onClick={() => onAddSubtask(task.id)}
                  />
                  <ActionButton
                    label=""
                    iconName="document-plus"
                    color="primary"
                    onClick={() => onCreateNote(task)}
                  />
                  <ActionButton
                    label=""
                    iconName="book-open"
                    color={hasNotes ? "primary" : "neutral"}
                    className={noteButtonClass}
                    onClick={() => onViewNotes(task)}
                  />
                  <ActionButton
                    label=""
                    iconName="bolt"
                    color="primary"
                    onClick={() => onCreateTimeRecord(task)}
                  />
                  {/* View time records button - only show in vision page */}
                  <ActionButton
                    label=""
                    iconName="timer"
                    color={hasTimeLogs ? "primary" : "neutral"}
                    className={timeLogButtonClass}
                    onClick={() => onViewTimeRecords(task)}
                  />
                  {/* Delete button - only show in vision page */}
                  {!isPlanningPage && (
                    <DeleteButton
                      onClick={() => onDeleteTask(task)}
                      size="sm"
                    />
                  )}
                </ActionButtonGroup>
              </div>
            </div>

            {/* Habit Information - Show when task has associated habit */}
            {hasAssociatedHabits && (
              <div className="mt-3 p-3 bg-base-100/50 rounded-r-lg">
                <div className="flex items-start space-x-2">
                  <div className="flex-shrink-0">
                    <Icon
                      name="refresh"
                      size={20}
                      className="text-primary"
                      aria-hidden
                    />
                  </div>
                  <div className="flex-1 min-w-0 space-y-4">
                    {associatedHabits.map((habit) => (
                      <div key={habit.id} className="space-y-2">
                        <div className="flex items-center space-x-2">
                          <h5 className="text-base font-medium text-primary">
                            {habit.title}
                          </h5>
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-base font-medium bg-primary/10 text-primary">
                            {habit.status}
                          </span>
                        </div>
                        {habit.description && (
                          <p className="text-base text-primary">
                            {habit.description}
                          </p>
                        )}
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-base text-primary">
                          <span className="inline-flex items-center gap-1">
                            <Icon name="calendar" size={16} aria-hidden />
                            {t("draggableTaskList.habit.start")}:{" "}
                            {formatDate(habit.start_date)}
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <Icon name="timer" size={16} aria-hidden />
                            {t("draggableTaskList.habit.duration")}:{" "}
                            {habit.duration_days}{" "}
                            {t("draggableTaskList.habit.days")}
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <Icon name="chart" size={16} aria-hidden />
                            {t("draggableTaskList.habit.status")}:{" "}
                            {habit.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      <HoverTooltipOverlay
        visible={Boolean(taskTooltipState)}
        position={taskTooltipState?.position ?? null}
        offset={taskTooltipState?.offset}
        className="text-sm leading-relaxed max-w-sm"
      >
        <TaskTooltipContent
          task={task}
          visionName={tooltipContent.visionName}
          parentTaskName={tooltipContent.parentName}
        />
      </HoverTooltipOverlay>
    </>
  );
};

// Main Component
const DraggableTaskList: React.FC<DraggableTaskListProps> = ({
  tasks,
  onEditTask,
  onDeleteTask,
  onStatusUpdate,
  onAddSubtask,
  onViewTimeRecords,
  onCreateNote,
  onViewNotes,
  onCreateTimeRecord,
  expandedTasks: externalExpandedTasks,
  onToggleExpansion: externalOnToggleExpansion,
  onTasksReorder,
  habitTaskAssociations,
  visions,
  showVisionInfo,
  isPlanningPage,
}) => {
  const { t } = useTranslation();
  // State management
  const [internalExpandedTasks, setInternalExpandedTasks] = useState<Set<UUID>>(
    new Set(),
  );
  const expandedTasks = externalExpandedTasks ?? internalExpandedTasks;

  // Memoized hierarchy manager
  const hierarchyManager = useMemo(
    () => new TaskHierarchyManager(tasks),
    [tasks],
  );

  // Sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  // Expansion state management
  const setExpandedTasks = useCallback(
    (taskId: UUID) => {
      if (externalOnToggleExpansion) {
        externalOnToggleExpansion(taskId);
      } else {
        setInternalExpandedTasks((prev) => {
          const newExpanded = new Set(prev);
          if (newExpanded.has(taskId)) {
            newExpanded.delete(taskId);
          } else {
            newExpanded.add(taskId);
          }
          return newExpanded;
        });
      }
    },
    [externalOnToggleExpansion],
  );

  // Same level reordering
  const handleSameLevelReorder = useCallback(
    async (activeInfo: TaskDragInfo, overInfo: TaskDragInfo) => {
      const siblings = hierarchyManager.getSiblings(activeInfo.task.id);

      if (siblings.length === 0) {
        return;
      }

      const oldIndex = siblings.findIndex(
        (task) => task.id === activeInfo.task.id,
      );
      const newIndex = siblings.findIndex(
        (task) => task.id === overInfo.task.id,
      );

      if (oldIndex === -1 || newIndex === -1) {
        return;
      }

      const reorderedSiblings = arrayMove(siblings, oldIndex, newIndex);

      if (onTasksReorder) {
        const updatedTasks = hierarchyManager.updateTaskOrder(
          tasks,
          reorderedSiblings,
          activeInfo.parentId,
        );
        await onTasksReorder(updatedTasks);
      }
    },
    [hierarchyManager, onTasksReorder, tasks],
  );

  // Cross-level movement
  const handleCrossLevelMove = useCallback(
    async (activeInfo: TaskDragInfo, overInfo: TaskDragInfo) => {
      try {
        // Move the active task to become a child of the over task
        // The API expects: move(taskId, oldParentTaskId, newParentTaskId, newVisionId, newDisplayOrder)
        await tasksApi.move(
          activeInfo.task.id, // taskId
          activeInfo.parentId ?? undefined, // oldParentTaskId - current parent (required for effort recalculation)
          overInfo.task.id, // newParentTaskId - make it a child of overTask
          undefined, // newVisionId - keep same vision
          0, // newDisplayOrder - add at the beginning
        );

        // Notify parent component to reload tasks
        if (onTasksReorder) {
          // For cross-level moves, we need to reload the entire task tree
          // since the structure has changed significantly
          // Send a special signal to indicate cross-level move
          await onTasksReorder([]); // Empty array signals cross-level move
        }
      } catch (error) {
        logger.error("Failed to move task:", error);
        // Even if the move fails, we should still request a reload to ensure UI consistency
        if (onTasksReorder) {
          await onTasksReorder([]);
        }
      }
    },
    [onTasksReorder],
  );

  // Drag end handler
  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      const { active, over } = event;

      if (active.id === over?.id) return;

      const activeInfo = hierarchyManager.getTaskInfo(active.id as UUID);
      const overInfo = hierarchyManager.getTaskInfo(over?.id as UUID);

      if (!activeInfo || !overInfo) return;

      // Same level operations - need to distinguish between reordering and making child
      if (activeInfo.parentId === overInfo.parentId) {
        if (activeInfo.task.id !== overInfo.task.id) {
          // Check if target has subtasks and is expanded
          const targetTask = overInfo.task;
          const isTargetExpanded = expandedTasks.has(targetTask.id);
          const hasSubtasks =
            targetTask.subtasks && targetTask.subtasks.length > 0;

          if (hasSubtasks && isTargetExpanded) {
            // Target has subtasks and is expanded - make it a child
            await handleCrossLevelMove(activeInfo, overInfo);
          } else {
            // Target has no subtasks or is not expanded - do reordering
            await handleSameLevelReorder(activeInfo, overInfo);
          }
        } else {
          // Dragging onto itself - ignore
          return;
        }
      } else {
        // Cross-level movement
        await handleCrossLevelMove(activeInfo, overInfo);
      }
    },
    [
      hierarchyManager,
      expandedTasks,
      handleCrossLevelMove,
      handleSameLevelReorder,
    ],
  );

  // Render task node recursively
  const renderTaskNode = useCallback(
    (
      task: TaskWithSubtasks,
      depth: number = 0,
      parent: TaskWithSubtasks | null = null,
    ) => {
      const hasSubtasks = task.subtasks?.length > 0;
      const isExpanded = expandedTasks.has(task.id);

      return (
        <div key={task.id} className="relative">
          <SortableTaskItem
            task={task}
            depth={depth}
            isExpanded={isExpanded}
            hasSubtasks={hasSubtasks}
            parentTask={parent}
            onEditTask={onEditTask}
            onDeleteTask={onDeleteTask}
            onStatusUpdate={onStatusUpdate}
            onAddSubtask={onAddSubtask}
            onViewTimeRecords={onViewTimeRecords}
            onCreateNote={onCreateNote}
            onViewNotes={onViewNotes}
            onCreateTimeRecord={onCreateTimeRecord}
            onToggleExpansion={setExpandedTasks}
            habitTaskAssociations={habitTaskAssociations}
            visions={visions}
            showVisionInfo={showVisionInfo}
            isPlanningPage={isPlanningPage}
          />

          {/* Subtasks */}
          {hasSubtasks && isExpanded && (
            <div className="mt-1 relative">
              <SortableContext
                items={task.subtasks.map((subtask) => subtask.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-2">
                  {task.subtasks.map((subtask) => (
                    <div key={subtask.id} className="relative">
                      {renderTaskNode(subtask, depth + 1, task)}
                    </div>
                  ))}
                </div>
              </SortableContext>
            </div>
          )}
        </div>
      );
    },
    [
      expandedTasks,
      setExpandedTasks,
      onEditTask,
      onDeleteTask,
      onStatusUpdate,
      onAddSubtask,
      onViewTimeRecords,
      onCreateNote,
      onViewNotes,
      onCreateTimeRecord,
      habitTaskAssociations,
      isPlanningPage,
      showVisionInfo,
      visions,
    ],
  );

  // Empty state
  if (tasks.length === 0) {
    return (
      <div className="text-center py-8 text-base-content/70">
        <Icon
          name="sparkles"
          size={36}
          className="text-primary mb-2"
          aria-hidden
        />
        <h3 className="text-lg font-bold font-medium mb-1 text-base-content">
          {t("draggableTaskList.empty.title")}
        </h3>
        <p className="text-base text-base-content">
          {t("draggableTaskList.empty.description")}
        </p>
      </div>
    );
  }

  // Main render
  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <div
        className="w-full rounded min-w-0 max-w-full overflow-hidden"
        style={{ maxWidth: "100%" }}
      >
        <SortableContext
          items={tasks.map((task) => task.id)}
          strategy={verticalListSortingStrategy}
        >
          <div
            className="w-full space-y-2 min-w-0 max-w-full overflow-hidden"
            style={{ maxWidth: "100%" }}
          >
            {tasks.map((task) => (
              <div
                key={`${task.id}-${expandedTasks.has(task.id)}`}
                className="relative"
              >
                <div className="relative">{renderTaskNode(task, 0)}</div>
              </div>
            ))}
          </div>
        </SortableContext>
      </div>
    </DndContext>
  );
};

export default DraggableTaskList;
