import React from "react";
import type { Vision } from "@/services/api";
import type {
  CalendarAdapter,
  PlanningGroup,
  PlanningViewType,
} from "@/utils/calendar";
import type { UUID } from "@/types/primitive";
import { usePlanningTaskGroup } from "@/hooks/planning/usePlanningTaskGroup";
import { TaskGroupCard } from "./planning/TaskGroupCard";

interface PlanningTaskListProps {
  group: PlanningGroup;
  visions: Vision[];
  onTaskUpdate?: () => void;
  onTaskStatusUpdate?: (taskId: UUID, newStatus: string) => Promise<void>;
  planningCycleType?: PlanningViewType;
  calendarAdapter?: CalendarAdapter;
}

const PlanningTaskList: React.FC<PlanningTaskListProps> = (props) => {
  const {
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
    getExpandedTasks,
    toggleTaskExpansion,
    planningTaskFilterStatus,
    periodRangeLabel,
  } = usePlanningTaskGroup({
    group: props.group,
    visions: props.visions,
    onTaskUpdate: props.onTaskUpdate,
    planningCycleType: props.planningCycleType,
    calendarAdapter: props.calendarAdapter,
  });

  return (
    <TaskGroupCard
      group={props.group}
      visions={props.visions}
      planningCycleType={props.planningCycleType}
      statusFilter={statusFilter}
      statusFilterOptions={statusFilterOptions}
      visionFilter={visionFilter}
      visionFilterOptions={visionFilterOptions}
      selectedVisionFilterName={selectedVisionFilterName}
      totalTimeSpent={totalTimeSpent}
      canCreateTask={canCreateTask}
      canAddTask={canAddTask}
      isCreatingTask={isCreatingTask}
      isAddingTask={isAddingTask}
      isCarryingForward={isCarryingForward}
      carryForwardCount={carryForwardCount}
      showCreateTask={showCreateTask}
      showTaskSelector={showTaskSelector}
      showCarryForwardConfirm={showCarryForwardConfirm}
      showHabitActionsCard={showHabitActionsCard}
      newTaskContent={newTaskContent}
      selectedVisionId={selectedVisionId}
      selectedTaskId={selectedTaskId}
      filteredTasks={filteredTasks}
      sortedTasks={sortedTasks}
      habitActions={habitActions}
      carryForwardableTasks={carryForwardableTasks}
      handlers={handlers}
      onTaskUpdate={props.onTaskUpdate}
      onTaskStatusUpdate={props.onTaskStatusUpdate}
      getExpandedTasks={getExpandedTasks}
      toggleTaskExpansion={toggleTaskExpansion}
      planningTaskFilterStatus={planningTaskFilterStatus}
      periodRangeLabel={periodRangeLabel}
    />
  );
};

export default PlanningTaskList;
