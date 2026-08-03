import React from "react";
import { useTranslation } from "react-i18next";
import VisionSelector from "@/components/selects/VisionSelector";
import { TextInput } from "@/components/forms";
import { FormActions } from "@/components/ActionButton";
import type { UUID } from "@/types/primitive";
import PlanningActionPanel from "./PlanningActionPanel";

interface TaskCreationPanelProps {
  groupId: string;
  groupLabel: string;
  selectedVisionId: UUID | null;
  onVisionChange: (visionId: UUID | null) => void;
  isCreatingTask: boolean;
  newTaskContent: string;
  onTaskContentChange: (value: string) => void;
  onSubmit: () => Promise<void>;
  onCancel: () => void;
}

export const TaskCreationPanel: React.FC<TaskCreationPanelProps> = ({
  groupId,
  groupLabel,
  selectedVisionId,
  onVisionChange,
  isCreatingTask,
  newTaskContent,
  onTaskContentChange,
  onSubmit,
  onCancel,
}) => {
  const { t } = useTranslation();

  return (
    <PlanningActionPanel
      title={t("planning.taskActions.createTask", { period: groupLabel })}
      closeLabel={t("common.cancel")}
      onClose={onCancel}
    >
      <div className="grid grid-cols-1 md:grid-cols-10 gap-3">
        <div className="md:col-span-3">
          <VisionSelector
            value={selectedVisionId}
            onChange={onVisionChange}
            placeholder={t("planning.createTask.visionPlaceholder")}
            disabled={isCreatingTask}
            showDefaultOption
            defaultToInboxVision
            idPrefix={`create-task-vision-${groupId}`}
            className="w-full"
          />
        </div>

        <div className="md:col-span-7">
          <TextInput
            id={`new-task-content-${groupId}`}
            name="new-task-content"
            value={newTaskContent}
            onChange={(event) => onTaskContentChange(event.target.value)}
            placeholder={t("planning.createTask.contentPlaceholder")}
            disabled={isCreatingTask}
            className="text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void onSubmit();
              }
            }}
            autoFocus
          />
        </div>
      </div>

      <div className="mt-3">
        <FormActions
          loading={isCreatingTask}
          disabled={
            !newTaskContent.trim() || !selectedVisionId || isCreatingTask
          }
          submitText={
            isCreatingTask
              ? t("tagManager.actions.creating")
              : t("planning.createTask.submitText")
          }
          cancelText={t("common.cancel")}
          submitColor="success"
          onSubmit={() => {
            void onSubmit();
          }}
          onCancel={onCancel}
        />
      </div>
    </PlanningActionPanel>
  );
};
