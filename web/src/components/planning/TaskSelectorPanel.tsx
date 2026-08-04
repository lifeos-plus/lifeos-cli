import React from "react";
import { useTranslation } from "react-i18next";
import TaskSelector from "@/components/selects/TaskSelector";
import { FormActions } from "@/components/ActionButton";
import type { UUID } from "@/types/primitive";
import PlanningActionPanel from "./PlanningActionPanel";

interface TaskSelectorPanelProps {
  groupId: string;
  groupLabel: string;
  selectedTaskId: UUID | null;
  onTaskSelectorChange: (taskId: UUID | null) => void;
  onSubmit: () => Promise<void>;
  onCancel: () => void;
  isAddingTask: boolean;
  planningTaskFilterStatus: readonly string[];
}

export const TaskSelectorPanel: React.FC<TaskSelectorPanelProps> = ({
  groupId,
  groupLabel,
  selectedTaskId,
  onTaskSelectorChange,
  onSubmit,
  onCancel,
  isAddingTask,
  planningTaskFilterStatus,
}) => {
  const { t } = useTranslation();

  return (
    <PlanningActionPanel
      title={t("planning.taskActions.addTask", { period: groupLabel })}
      closeLabel={t("common.cancel")}
      onClose={onCancel}
      tone="primary"
    >
      <TaskSelector
        value={selectedTaskId}
        onChange={onTaskSelectorChange}
        disabled={isAddingTask}
        filterStatus={planningTaskFilterStatus}
        idPrefix={`planning-task-selector-${groupId}`}
        className="mb-3"
      />

      <div className="mt-3">
        <FormActions
          loading={isAddingTask}
          disabled={!selectedTaskId || isAddingTask}
          submitText={
            isAddingTask
              ? t("planning.addTask.addingText")
              : t("planning.addTask.submitText")
          }
          cancelText={t("common.cancel")}
          submitColor="primary"
          onSubmit={() => {
            void onSubmit();
          }}
          onCancel={onCancel}
        />
      </div>
    </PlanningActionPanel>
  );
};
