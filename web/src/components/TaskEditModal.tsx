import React, { useCallback } from "react";
import type { TaskWithSubtasks, Vision } from "@/services/api";
import type { UUID } from "@/types/primitive";
import {
  useTaskEditor,
  type TaskEditResultPayload,
} from "@/hooks/tasks/useTaskEditor";
import { TaskEditModalView } from "./tasks/TaskEditModalView";

export interface TaskEditModalCloseContext {
  sessionId: string;
}

export type TaskEditModalSaveResult = TaskEditResultPayload & {
  sessionId: string;
};

interface TaskEditModalProps {
  isOpen: boolean;
  onClose: (context?: TaskEditModalCloseContext) => void;
  onSave: (result?: TaskEditModalSaveResult) => void;
  task?: TaskWithSubtasks | null;
  visionId: UUID | null;
  parentTaskId?: UUID | null;
  allTasks: TaskWithSubtasks[];
  allVisions?: Vision[];
  mode?: "single" | "bulk";
  visionLocked?: boolean;
  inheritPlanningFromParent?: boolean;
  sessionId: string;
  onRequestDelete?: (task: TaskWithSubtasks) => void;
}

const TaskEditModal: React.FC<TaskEditModalProps> = ({
  isOpen,
  onClose,
  onSave,
  sessionId,
  task,
  visionId,
  parentTaskId,
  allTasks,
  allVisions,
  mode = "single",
  visionLocked = false,
  inheritPlanningFromParent = true,
  onRequestDelete,
}) => {
  const sessionAwareClose = useCallback(() => {
    onClose({ sessionId });
  }, [onClose, sessionId]);

  const sessionAwareSave = useCallback(
    (result?: TaskEditResultPayload) => {
      if (!onSave) {
        return;
      }
      if (result) {
        onSave({ ...result, sessionId });
        return;
      }
      onSave({ sessionId });
    },
    [onSave, sessionId],
  );

  const editor = useTaskEditor({
    isOpen,
    task,
    visionId,
    parentTaskId,
    allTasks,
    allVisions,
    onSave: sessionAwareSave,
    onClose: sessionAwareClose,
    mode,
    visionLocked,
    inheritPlanningFromParent,
  });

  return (
    <TaskEditModalView
      isOpen={isOpen}
      loading={editor.loading}
      error={editor.error}
      modalTitle={editor.modalTitle}
      canChangeVision={editor.canChangeVision}
      formData={editor.formData}
      handlers={editor.handlers}
      filteredTasksForParent={editor.filteredTasksForParent}
      excludedParentTaskIds={editor.excludedParentTaskIds}
      taskStatusFilter={editor.taskStatusFilter}
      visionStatusFilter={editor.visionStatusFilter}
      focusTrigger={editor.focusTrigger}
      task={task}
      allTasks={allTasks}
      visionId={visionId}
      mode={mode}
      visionLocked={visionLocked}
      onRequestDelete={onRequestDelete}
    />
  );
};

export default TaskEditModal;
