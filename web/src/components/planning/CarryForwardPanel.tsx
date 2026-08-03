import React from "react";
import { useTranslation } from "react-i18next";
import { FormActions } from "@/components/ActionButton";
import type { TaskWithSubtasks } from "@/services/api";
import PlanningActionPanel from "./PlanningActionPanel";

interface CarryForwardPanelProps {
  tasks: TaskWithSubtasks[];
  isCarryingForward: boolean;
  onSubmit: () => Promise<void>;
  onCancel: () => void;
}

export const CarryForwardPanel: React.FC<CarryForwardPanelProps> = ({
  tasks,
  isCarryingForward,
  onSubmit,
  onCancel,
}) => {
  const { t } = useTranslation();

  return (
    <PlanningActionPanel
      title={t("planning.carryForward.title")}
      closeLabel={t("common.cancel")}
      onClose={onCancel}
      tone="warning"
    >
      <div className="mb-4">
        <p className="text-base text-warning mb-2">
          {t("planning.carryForward.message", { count: tasks.length })}
        </p>
        <div className="max-h-32 overflow-y-auto bg-base-100 border border-warning/30 rounded p-2">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="text-sm py-1 px-2 hover:bg-base-200 rounded transition-colors"
            >
              • {task.content}
            </div>
          ))}
        </div>
      </div>

      <FormActions
        loading={isCarryingForward}
        disabled={isCarryingForward}
        submitText={
          isCarryingForward
            ? t("planning.carryForward.carryingText")
            : t("planning.carryForward.submitText")
        }
        cancelText={t("common.cancel")}
        submitColor="warning"
        onSubmit={() => {
          void onSubmit();
        }}
        onCancel={onCancel}
      />
    </PlanningActionPanel>
  );
};
