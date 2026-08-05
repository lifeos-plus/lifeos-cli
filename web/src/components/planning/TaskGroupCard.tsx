import React from "react";
import type { PlanningGroup, PlanningViewType } from "@/utils/calendar";
import type { TaskWithSubtasks, Vision } from "@/services/api";
import type { HabitActionWithHabit } from "@/services/api/habits";
import type { UUID } from "@/types/primitive";
import type {
  PlanningTaskGroupHandlers,
  StatusFilterOption,
} from "@/hooks/planning/usePlanningTaskGroup";
import { TaskGroupHeader } from "./TaskGroupHeader";
import { TaskCreationPanel } from "./TaskCreationPanel";
import { TaskSelectorPanel } from "./TaskSelectorPanel";
import { CarryForwardPanel } from "./CarryForwardPanel";
import { HabitActionsCard } from "./HabitActionsCard";
import { TaskListSection } from "./TaskListSection";

interface TaskGroupCardProps {
  group: PlanningGroup;
  visions: Vision[];
  planningCycleType?: PlanningViewType;
  statusFilter: string;
  statusFilterOptions: StatusFilterOption[];
  visionFilter: string;
  visionFilterOptions: StatusFilterOption[];
  selectedVisionFilterName: string;
  totalTimeSpent: string;
  canCreateTask: boolean;
  canAddTask: boolean;
  isCreatingTask: boolean;
  isAddingTask: boolean;
  isCarryingForward: boolean;
  carryForwardCount: number;
  showCreateTask: boolean;
  showTaskSelector: boolean;
  showCarryForwardConfirm: boolean;
  showHabitActionsCard: boolean;
  newTaskContent: string;
  selectedVisionId: UUID | null;
  selectedTaskId: UUID | null;
  filteredTasks: TaskWithSubtasks[];
  sortedTasks: TaskWithSubtasks[];
  habitActions: HabitActionWithHabit[];
  carryForwardableTasks: TaskWithSubtasks[];
  handlers: PlanningTaskGroupHandlers;
  onTaskUpdate?: () => void;
  onTaskStatusUpdate?: (taskId: UUID, newStatus: string) => Promise<void>;
  getExpandedTasks: (groupId: string) => Set<UUID>;
  toggleTaskExpansion: (groupId: string, taskId: string) => void;
  planningTaskFilterStatus: readonly string[];
  periodRangeLabel?: string;
}

export const TaskGroupCard: React.FC<TaskGroupCardProps> = ({
  group,
  visions,
  planningCycleType,
  statusFilter,
  statusFilterOptions,
  visionFilter,
  visionFilterOptions,
  selectedVisionFilterName,
  totalTimeSpent,
  canCreateTask,
  canAddTask,
  isCreatingTask,
  isAddingTask,
  isCarryingForward,
  carryForwardCount,
  showCreateTask,
  showTaskSelector,
  showCarryForwardConfirm,
  showHabitActionsCard,
  newTaskContent,
  selectedVisionId,
  selectedTaskId,
  filteredTasks,
  sortedTasks,
  habitActions,
  carryForwardableTasks,
  handlers,
  onTaskUpdate,
  onTaskStatusUpdate,
  getExpandedTasks,
  toggleTaskExpansion,
  planningTaskFilterStatus,
  periodRangeLabel,
}) => {
  return (
    <div>
      <div className="mb-3">
        <TaskGroupHeader
          groupId={group.id}
          groupLabel={group.label}
          periodRangeLabel={periodRangeLabel}
          planningCycleType={planningCycleType}
          totalTimeSpent={totalTimeSpent}
          statusFilter={statusFilter}
          statusFilterOptions={statusFilterOptions}
          visionFilter={visionFilter}
          visionFilterOptions={visionFilterOptions}
          onStatusFilterChange={handlers.handleStatusFilterChange}
          onVisionFilterChange={handlers.handleVisionFilterChange}
          canCreateTask={canCreateTask}
          canAddTask={canAddTask}
          isCreatingTask={isCreatingTask}
          isAddingTask={isAddingTask}
          isCarryingForward={isCarryingForward}
          carryForwardCount={carryForwardCount}
          onCreateTaskClick={handlers.handleCreateTaskClick}
          onAddTaskClick={handlers.handleAddTaskClick}
          onCarryForwardClick={handlers.handleCarryForwardClick}
        />
      </div>

      {showCreateTask && (
        <TaskCreationPanel
          groupId={group.id}
          groupLabel={group.label}
          selectedVisionId={selectedVisionId}
          onVisionChange={handlers.handleVisionChange}
          isCreatingTask={isCreatingTask}
          newTaskContent={newTaskContent}
          onTaskContentChange={handlers.handleTaskContentChange}
          onSubmit={handlers.handleCreateTask}
          onCancel={handlers.handleCancelCreateTask}
        />
      )}

      {showTaskSelector && (
        <TaskSelectorPanel
          groupId={group.id}
          groupLabel={group.label}
          selectedTaskId={selectedTaskId}
          onTaskSelectorChange={handlers.handleTaskSelectorChange}
          onSubmit={() => handlers.handleTaskSelect(selectedTaskId)}
          onCancel={handlers.handleCancelTaskSelect}
          isAddingTask={isAddingTask}
          planningTaskFilterStatus={planningTaskFilterStatus}
        />
      )}

      {showCarryForwardConfirm && (
        <CarryForwardPanel
          tasks={carryForwardableTasks}
          isCarryingForward={isCarryingForward}
          onSubmit={handlers.handleCarryForwardTasks}
          onCancel={handlers.handleCancelCarryForward}
        />
      )}

      <TaskListSection
        groupId={group.id}
        visions={visions}
        filteredTasks={filteredTasks}
        sortedTasks={sortedTasks}
        statusFilter={statusFilter}
        visionFilter={visionFilter}
        selectedVisionFilterName={selectedVisionFilterName}
        onTaskUpdate={onTaskUpdate}
        onTaskStatusUpdate={onTaskStatusUpdate}
        getExpandedTasks={getExpandedTasks}
        toggleTaskExpansion={toggleTaskExpansion}
      />

      {showHabitActionsCard && (
        <HabitActionsCard
          habitActions={habitActions}
          onStatusChange={handlers.handleHabitActionStatusUpdate}
          onNotesChanged={handlers.handleHabitActionNotesChanged}
        />
      )}
    </div>
  );
};
