import React, { useEffect, useId, useRef } from "react";
import { useTranslation } from "react-i18next";
import ModalBase from "@/layouts/ModalBase";
import VisionSelector from "@/components/selects/VisionSelector";
import TaskSelector from "@/components/selects/TaskSelector";
import EnumSelect from "@/components/selects/EnumSelect";
import PersonSelector from "@/components/selects/PersonSelector";
import { FormField, TextArea, TextInput } from "@/components/forms";
import { FORM_LABEL_COMPACT_CLASS } from "@/components/forms/styles";
import ActionButton, {
  ActionButtonGroup,
  FormActions,
} from "@/components/ActionButton";
import { PlanningCycleDateInput } from "@/components/PlanningCycleDateInput";
import type { TaskCreate, TaskWithSubtasks } from "@/services/api";
import type { UUID } from "@/types/primitive";
import { PRIORITY } from "@/utils/constants";
import type { UseTaskEditorHandlers } from "@/hooks/tasks/useTaskEditor";
import { usePlanningCycle } from "@/hooks/useCalendarAdapter";
import { Icon } from "@/components/icons";

interface TaskEditModalViewProps {
  isOpen: boolean;
  loading: boolean;
  error: string | null;
  modalTitle: string;
  canChangeVision: boolean;
  formData: TaskCreate;
  handlers: UseTaskEditorHandlers;
  filteredTasksForParent: TaskWithSubtasks[];
  excludedParentTaskIds: UUID[];
  taskStatusFilter: readonly string[];
  visionStatusFilter: readonly string[];
  focusTrigger: number;
  task?: TaskWithSubtasks | null;
  allTasks: TaskWithSubtasks[];
  visionId: UUID | null;
  mode?: "single" | "bulk";
  visionLocked?: boolean;
  onRequestDelete?: (task: TaskWithSubtasks) => void;
}

export const TaskEditModalView: React.FC<TaskEditModalViewProps> = ({
  isOpen,
  loading,
  error,
  modalTitle,
  canChangeVision,
  formData,
  handlers,
  filteredTasksForParent,
  excludedParentTaskIds,
  taskStatusFilter,
  visionStatusFilter,
  focusTrigger,
  task,
  allTasks,
  visionId,
  mode = "single",
  visionLocked = false,
  onRequestDelete,
}) => {
  const { t } = useTranslation();
  const { adapter } = usePlanningCycle();
  const uniqueId = useId();
  const taskContentId = `task-content-${uniqueId}`;
  const planningCycleYearId = `planning-cycle-year-${uniqueId}`;
  const planningCycleStartDateId = `planning-cycle-start-date-${uniqueId}`;

  const formRef = useRef<HTMLFormElement>(null);
  const textInputRef = useRef<HTMLInputElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  const isBulkMode = mode === "bulk";

  useEffect(() => {
    if (!isOpen) return;
    const timer = setTimeout(() => {
      if (isBulkMode) {
        textAreaRef.current?.focus();
        return;
      }
      textInputRef.current?.focus();
    }, 100);
    return () => clearTimeout(timer);
  }, [focusTrigger, isOpen, isBulkMode]);

  const selectedParentTask = formData.parent_task_id
    ? allTasks.find((candidate) => candidate.id === formData.parent_task_id)
    : null;
  const isMonthlyPlanning = formData.planning_cycle_type === "month";

  const handlePlanningMonthYearChange = (yearStartDate?: string) => {
    if (!yearStartDate) {
      handlers.handlePlanningStartDateChange(undefined);
      return;
    }
    const selectedYearStart = new Date(`${yearStartDate}T00:00:00`);
    const currentMonthIndex = formData.planning_cycle_start_date
      ? adapter.getMonthInfo(new Date(`${formData.planning_cycle_start_date}T00:00:00`))
          .monthIndex
      : adapter.getMonthInfo(new Date()).monthIndex;
    if (!currentMonthIndex || Number.isNaN(selectedYearStart.getTime())) {
      handlers.handlePlanningStartDateChange(yearStartDate);
      return;
    }
    const monthStart = adapter.getMonthStart(selectedYearStart, currentMonthIndex);
    handlers.handlePlanningStartDateChange(monthStart.toLocaleDateString("en-CA"));
  };

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={handlers.handleClose}
      closeDisabled={loading}
      header={modalTitle}
      loading={loading}
      error={error}
      onErrorDismiss={handlers.handleErrorDismiss}
      showLoadingOverlay={false}
      showLoadingSpinner
      loadingSpinnerSize="md"
      showCloseButton
      errorDisplayMode="inline"
      footer={
        <FormActions
          loading={loading}
          onCancel={handlers.handleClose}
          onSubmit={() => formRef.current?.requestSubmit()}
          onDelete={
            task && !isBulkMode && onRequestDelete
              ? () => {
                  handlers.handleClose();
                  onRequestDelete(task);
                }
              : undefined
          }
        />
      }
    >
      <form
        ref={formRef}
        onSubmit={handlers.handleSubmit}
        className="space-y-3 sm:space-y-4 lg:space-y-5"
      >
        <div className="w-full">
          <VisionSelector
            value={formData.vision_id}
            onChange={handlers.handleVisionChange}
            placeholder={t("planning.createTask.visionPlaceholder")}
            disabled={loading || !canChangeVision}
            idPrefix="vision-select"
            label={t("taskForm.fields.vision")}
            showLabel
            showDefaultOption={false}
            defaultToInboxVision={false}
            filterStatus={[...visionStatusFilter]}
            showStatus
          />
          <p className="text-xs sm:text-sm mt-1 text-base-content/40">
            {visionLocked
              ? t("taskForm.tips.visionLocked")
              : canChangeVision
                ? t("taskForm.tips.visionChangeAllowed")
                : t("taskForm.tips.visionChangeRootOnly")}
          </p>
        </div>

        <div>
          <div className="text-sm sm:text-base">
            <TaskSelector
              value={formData.parent_task_id ?? null}
              onChange={(taskId) => handlers.handleParentTaskChange(taskId)}
              placeholder={
                formData.vision_id === visionId
                  ? t("taskForm.placeholders.parentNoneRoot")
                  : t("taskForm.placeholders.selectVisionFirst")
              }
              disabled={loading || formData.vision_id !== visionId}
              className="w-full"
              idPrefix="parent-task-selector"
              label={t("taskForm.fields.parent")}
              usePortal
              visionId={
                formData.vision_id === visionId ? formData.vision_id : undefined
              }
              preloadedTasks={filteredTasksForParent}
              excludeTaskIds={excludedParentTaskIds}
              deferRemoteLoad={true}
              expandFilterForSelected
              filterStatus={[...taskStatusFilter]}
            />
          </div>
          <p className="text-xs sm:text-sm mt-1 text-base-content/40">
            {formData.vision_id === visionId
              ? t("taskForm.tips.parentReady")
              : t("taskForm.tips.parentSelectVisionFirst")}
          </p>
          {selectedParentTask && selectedParentTask.status === "done" && (
            <div className="mt-2 p-2 bg-primary/10 border border-primary/30 rounded-md">
              <p className="text-xs sm:text-sm text-primary">
                <span className="inline-flex items-center gap-1">
                  <Icon name="sparkles" size={16} aria-hidden />
                  <strong>{t("common.info")}</strong>
                </span>
                {t("taskForm.tips.parentDoneAutoUpdate")}
              </p>
            </div>
          )}
        </div>

        <FormField
          label={t("taskForm.fields.content")}
          htmlFor={taskContentId}
          required
          labelClassName="text-sm sm:text-sm mb-1 sm:mb-1"
          description={
            isBulkMode ? t("taskForm.tips.bulkContentDescription") : undefined
          }
        >
          {isBulkMode ? (
            <>
              <TextArea
                id={taskContentId}
                name="task-content"
                ref={textAreaRef}
                value={formData.content}
                onChange={(event) =>
                  handlers.handleContentChange(event.target.value)
                }
                placeholder={t("taskForm.placeholders.bulkContent")}
                disabled={loading}
                rows={8}
                resize="vertical"
                className="text-sm sm:text-sm"
              />
              <p className="text-xs sm:text-sm mt-2 text-primary font-medium">
                {t("taskForm.tips.bulkContentHelper")}
              </p>
            </>
          ) : (
            <TextInput
              id={taskContentId}
              name="task-content"
              ref={textInputRef}
              type="text"
              value={formData.content}
              onChange={(event) =>
                handlers.handleContentChange(event.target.value)
              }
              placeholder={t("taskForm.placeholders.content")}
              required
              disabled={loading}
              size="sm"
              className="text-sm"
            />
          )}
        </FormField>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4 pt-2 sm:pt-3 pb-2 sm:pb-3">
          <div>
            <EnumSelect
              value={String(formData.priority)}
              onChange={(value) => {
                const resolved =
                  typeof value === "number" ? value : Number(value ?? 0);
                handlers.handlePriorityChange(resolved);
              }}
              options={PRIORITY.map((item) => ({
                value: item.value,
                label: item.label,
              }))}
              disabled={loading}
              id="task-edit-modal-priority-select"
              placeholder={t("target.priority")}
              label={t("target.priority")}
            />
          </div>

          <div>
            <PersonSelector
              selectedPersonIds={formData.person_ids || []}
              onSelectionChange={(personIds) =>
                handlers.handlePersonChange(personIds)
              }
              multiple
              disabled={loading}
              idPrefix="person-selector"
            />
          </div>
        </div>

        <div className="space-y-2 sm:space-y-3 pt-2 sm:pt-3 pb-2 sm:pb-3">
          <div className="flex justify-between items-center">
            <h3 className="text-sm sm:text-base font-semibold">
              {t("taskForm.planning.title")}
            </h3>
          </div>
          <div className="flex justify-end">
            <ActionButtonGroup gap="sm" align="end">
              <ActionButton
                label={t("planning.presets.none")}
                size="xs"
                variant="ghost"
                onClick={handlers.handlePlanningNoPreset}
                disabled={loading}
              />
              <ActionButton
                label={t("planning.presets.today")}
                size="xs"
                variant="ghost"
                onClick={handlers.handlePlanningToday}
                disabled={loading}
              />
              <ActionButton
                label={t("planning.presets.tomorrow")}
                size="xs"
                variant="ghost"
                onClick={handlers.handlePlanningTomorrow}
                disabled={loading}
              />
              <ActionButton
                label={t("planning.presets.this_week")}
                size="xs"
                variant="ghost"
                onClick={handlers.handlePlanningThisWeek}
                disabled={loading}
              />
              <ActionButton
                label={t("planning.presets.this_month")}
                size="xs"
                variant="ghost"
                onClick={handlers.handlePlanningThisMonth}
                disabled={loading}
              />
            </ActionButtonGroup>
          </div>

          <div
            className={
              isMonthlyPlanning
                ? "grid grid-cols-1 sm:grid-cols-3 gap-3"
                : "grid grid-cols-1 sm:grid-cols-2 gap-3"
            }
          >
            <div>
              <EnumSelect
                value={formData.planning_cycle_type || ""}
                onChange={(value) =>
                  handlers.handlePlanningTypeChange(
                    value === "" ? undefined : String(value),
                  )
                }
                options={[
                  { value: "", label: t("common.none") },
                  { value: "day", label: t("target.day") },
                  { value: "week", label: t("target.week") },
                  {
                    value: "month",
                    label: t("taskForm.planning.cycleTypes.month"),
                  },
                  {
                    value: "year",
                    label: t("taskForm.planning.cycleTypes.year"),
                  },
                  { value: "7years", label: t("target.sevenYears") },
                ]}
                disabled={loading}
                id="planning-cycle-type-select"
                label={t("target.type")}
              />
            </div>

            {isMonthlyPlanning && (
              <div className="mt-0 sm:mt-2">
                <label
                  htmlFor={planningCycleYearId}
                  className={FORM_LABEL_COMPACT_CLASS}
                >
                  {t("taskForm.planning.startLabels.year")}
                </label>
                <PlanningCycleDateInput
                  cycleType="year"
                  startDate={formData.planning_cycle_start_date}
                  id={planningCycleYearId}
                  name="planning_cycle_start_year"
                  className="input-sm"
                  onStartDateChange={handlePlanningMonthYearChange}
                  disabled={loading}
                />
              </div>
            )}

            {formData.planning_cycle_type &&
              formData.planning_cycle_type !== "" && (
                <div className="mt-0 sm:mt-2">
                  <label
                    htmlFor={planningCycleStartDateId}
                    className={FORM_LABEL_COMPACT_CLASS}
                  >
                    {formData.planning_cycle_type === "year" &&
                      t("taskForm.planning.startLabels.year")}
                    {formData.planning_cycle_type === "7years" &&
                      t("taskForm.planning.startLabels.sevenYears")}
                    {formData.planning_cycle_type === "month" &&
                      t("taskForm.planning.startLabels.month")}
                    {formData.planning_cycle_type === "week" &&
                      t("taskForm.planning.startLabels.week")}
                    {formData.planning_cycle_type === "day" &&
                      t("taskForm.planning.startLabels.day")}
                  </label>
                  <PlanningCycleDateInput
                    cycleType={formData.planning_cycle_type || ""}
                    startDate={formData.planning_cycle_start_date}
                    id={planningCycleStartDateId}
                    name="planning_cycle_start_date"
                    className="input-sm"
                    onStartDateChange={(startDate) =>
                      handlers.handlePlanningStartDateChange(startDate)
                    }
                    disabled={loading}
                  />
                </div>
              )}
          </div>
          <p className="text-xs sm:text-sm text-base-content/40">
            {t("taskForm.planning.description")}
          </p>
        </div>

        {task && <div className="mt-4" />}
      </form>
    </ModalBase>
  );
};
