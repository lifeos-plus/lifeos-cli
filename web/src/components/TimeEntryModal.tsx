import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import type {
  Timelog,
  TimelogCreate,
  TimelogWithEnergyResponse,
  TaskWithSubtasks,
} from "@/services/api";
import { tasksApi } from "@/services/api/tasks";
import PersonSelector from "./selects/PersonSelector";
import TaskSelector from "./selects/TaskSelector";
import {
  addMinutesToIso,
  formatDate,
  formatTime,
  getNearestFiveMinuteTime,
  hhmmOnDateToISO,
} from "@/utils/datetime";
import { logger } from "@/utils/core";
import ModalBase from "@/layouts/ModalBase";
import { FormActions } from "./ActionButton";
import AreaSelect from "./selects/AreaSelect";
import { TextInput } from "./forms";
import { FORM_LABEL_SPACED_CLASS } from "./forms/styles";
import { useModalState } from "@/hooks/useModalState";
import { useToast } from "@/contexts/ToastContext";
import { usePreferenceWithBootstrap } from "@/hooks/queries/usePreferenceWithBootstrap";
import { ALL_TASK_STATUSES } from "@/utils/constants";
import type { UUID } from "@/types/primitive";
import { useTimelogMutations } from "@/hooks/useTimelogMutations";
import { useSystemTimezone } from "@/hooks/useSystemTimezone";

interface TimeEntryModalProps {
  isOpen: boolean;
  onClose: (context?: { sessionId: string }) => void;
  onSave: (
    result: Timelog | TimelogWithEnergyResponse,
    context: { sessionId: string },
  ) => void;
  entry?: Timelog | null;
  selectedDate: Date;
  preloadedTasks?: TaskWithSubtasks[]; // 添加预加载任务支持
  mode?: "default" | "draft";
  onDraftSubmit?: (payload: TimelogCreate) => void | Promise<void>;
  sessionId: string;
  onRequestDelete?: (entry: Timelog) => void;
}

const TimeEntryModal = ({
  isOpen,
  onClose,
  onSave,
  sessionId,
  entry,
  selectedDate,
  preloadedTasks,
  mode = "default",
  onDraftSubmit,
  onRequestDelete,
}: TimeEntryModalProps) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<TimelogCreate>({
    title: "",
    start_time: "",
    end_time: "",
    area_id: null,
    notes: "",
    energy_level: 3,
    task_id: undefined,
    person_ids: [],
    tracking_method: "manual",
  });

  const modalStateRaw = useModalState();

  // Memoize modal state to prevent unnecessary re-renders
  const { loading, error, setError, withLoading } = useMemo(
    () => modalStateRaw,
    [modalStateRaw],
  );

  const toastRaw = useToast();

  // Memoize toast object to prevent unnecessary re-renders
  const toast = useMemo(() => toastRaw, [toastRaw]);

  // User preference: whether to auto-set task planning when linking tasks to Timelog
  const { value: autoSetTaskPlanning } = usePreferenceWithBootstrap<boolean>({
    key: "timeLog.auto_set_task_planning",
    defaultValue: false,
    module: "timeLog",
    validator: (value) => {
      if (typeof value === "boolean") return true;
      if (typeof value === "number") return value === 0 || value === 1;
      if (typeof value === "string")
        return value === "true" || value === "false";
      return false;
    },
  });
  const timezonePreference = useSystemTimezone();
  const activeTimezone = timezonePreference.timezone;

  // Ref for auto-focusing title input
  const titleInputRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  // Initialize form data when modal opens
  useEffect(() => {
    if (isOpen) {
      if (entry) {
        // Edit mode - populate form with existing data
        setFormData({
          title: entry.title,
          start_time: entry.start_time || "",
          end_time: entry.end_time || "",
          area_id: entry.area_id,
          notes: entry.notes || "",
          energy_level: entry.energy_level || 3,
          task_id: entry.task?.id ?? entry.task_id ?? null,
          person_ids: entry.people?.map((person) => person.id) || [],
          tracking_method: "manual",
        });
      } else {
        // Create mode - initialize with defaults
        const currentTime = getNearestFiveMinuteTime(
          new Date(),
          activeTimezone,
        );
        const defaultEndTime = hhmmOnDateToISO(
          selectedDate,
          currentTime,
          activeTimezone,
        );

        setFormData({
          title: "",
          start_time: addMinutesToIso(defaultEndTime, -60),
          end_time: defaultEndTime,
          area_id: null,
          notes: "",
          energy_level: 3,
          task_id: undefined,
          person_ids: [],
          tracking_method: "manual",
        });
      }

      // Auto-focus title input after a short delay to ensure modal is rendered
      setTimeout(() => {
        titleInputRef.current?.focus();
      }, 100);
    }
  }, [
    activeTimezone,
    entry,
    isOpen,
    preloadedTasks,
    selectedDate,
  ]);

  // Removed user-edited flag effect

  // persons are selected via PersonSelector; no extra reference load here

  // Optimize input change handler with useCallback
  const handleInputChange = useCallback(
    (field: string, value: string | number | number[]) => {
      setFormData((prev) => ({
        ...prev,
        [field]: value,
      }));
    },
    [],
  );

  // 自动设置任务规划为今天的辅助函数
  const autoSetTaskPlanningToday = useCallback(
    async (taskId: UUID, entryTime: string): Promise<boolean> => {
      try {
        const existing = await tasksApi.getById(taskId);
        if (
          existing?.planning_cycle_type &&
          existing?.planning_cycle_start_date
        ) {
          logger.debug(
            `Skipping auto-set planning for task ${taskId} because planning cycle already exists.`,
          );
          return false;
        }

        // 使用时间日志的 entryTime 来获取本地日期
        const dateString = formatDate(entryTime, activeTimezone);

        const updateData = {
          planning_cycle_type: "day",
          planning_cycle_days: 1,
          planning_cycle_start_date: dateString,
        };

        await tasksApi.update(taskId, updateData);
        return true;
      } catch (err) {
        logger.error(`Failed to auto-set task ${taskId} planning:`, err);
        // 不抛出错误，避免影响时间日志保存
        return false;
      }
    },
    [activeTimezone],
  );

  // 检查时间是否在24小时内的辅助函数
  const isWithin24Hours = useCallback((timeString: string) => {
    const now = new Date();
    const entryTime = new Date(timeString);
    const timeDiff = Math.abs(now.getTime() - entryTime.getTime());
    const hoursDiff = timeDiff / (1000 * 60 * 60);
    return hoursDiff <= 24;
  }, []);

  const { createTimelogAsync, updateTimelogAsync } =
    useTimelogMutations();

  // Optimize submit handler with useCallback
  const sessionAwareClose = useCallback(() => {
    onClose({ sessionId });
  }, [onClose, sessionId]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!formData.title.trim()) {
        setError(t("timeLog.modal.activityRequired"));
        return;
      }

      if (!formData.end_time) {
        setError(t("timeLog.modal.endTimeRequired"));
        return;
      }

      const prepared: TimelogCreate = {
        ...formData,
        start_time: formData.start_time || formData.end_time || "",
      };

      if (mode === "draft" && onDraftSubmit) {
        try {
          await onDraftSubmit(prepared);
          setError(null);
          sessionAwareClose();
        } catch (err) {
          const errorMessage =
            err instanceof Error ? err.message : t("common.error");
          setError(errorMessage);
        }
        return;
      }

      try {
        await withLoading(async () => {
          let result: Timelog | TimelogWithEnergyResponse;

          let autoPlanningApplied = false;

          if (entry) {
            result = await updateTimelogAsync({
              id: entry.id,
              data: prepared,
            });
          } else {
            result = await createTimelogAsync(prepared);
          }

          if (
            autoSetTaskPlanning &&
            formData.task_id !== undefined &&
            formData.task_id !== null &&
            (formData.start_time || formData.end_time)
          ) {
            const entryTime = formData.start_time || formData.end_time;
            const within24Hours = entryTime && isWithin24Hours(entryTime);

            if (entryTime && within24Hours) {
              autoPlanningApplied = await autoSetTaskPlanningToday(
                formData.task_id,
                entryTime,
              );
            }
          }

          if (autoPlanningApplied) {
            toast.showInfo(
              entry
                ? t("timeLog.messages.timeLogUpdated")
                : t("timeLog.messages.timeLogCreated"),
              entry
                ? t("timeLog.messages.timeLogUpdatedWithTask", {
                    title: formData.title,
                  })
                : t("timeLog.messages.timeLogCreatedWithTask", {
                    title: formData.title,
                  }),
            );
          }

          onSave(result, { sessionId });
        });
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : t("common.error");
        logger.error("Failed to save entry:", err);
        setError(errorMessage);
      }
    },
    [
      formData,
      entry,
      setError,
      withLoading,
      toast,
      onSave,
      t,
      autoSetTaskPlanningToday,
      isWithin24Hours,
      autoSetTaskPlanning,
      createTimelogAsync,
      updateTimelogAsync,
      mode,
      onDraftSubmit,
      sessionAwareClose,
      sessionId,
    ],
  );

  // Removed dirty-state JSON calculations

  const attemptClose = useCallback(() => {
    if (!loading) {
      setError(null);
      sessionAwareClose();
    }
  }, [loading, sessionAwareClose, setError]);

  // Optimize close handler with useCallback
  const handleClose = useCallback(() => {
    if (!loading) attemptClose();
  }, [loading, attemptClose]);

  // Optimize time change handlers with useCallback
  const handleStartTimeChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setFormData((prev) => ({
        ...prev,
        start_time: hhmmOnDateToISO(
          selectedDate,
          e.target.value,
          activeTimezone,
        ),
      }));
    },
    [activeTimezone, selectedDate],
  );

  const handleEndTimeChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newEndIso = hhmmOnDateToISO(
        selectedDate,
        e.target.value,
        activeTimezone,
      );
      // handle cross-day if needed
      const start = new Date(formData.start_time);
      const end = new Date(newEndIso);
      if (end < start) {
        end.setDate(end.getDate() + 1);
      }
      setFormData((prev) => ({
        ...prev,
        end_time: end.toISOString(),
      }));
    },
    [activeTimezone, selectedDate, formData.start_time],
  );

  // Optimize area change handler with useCallback
  const handleAreaChange = useCallback((v: UUID | null | undefined) => {
    setFormData((prev) => ({
      ...prev,
      area_id: v ?? "",
    }));
  }, []);

  // Optimize person selection change handler with useCallback
  const handlePersonSelectionChange = useCallback((personIds: UUID[]) => {
    setFormData((prev) => ({ ...prev, person_ids: personIds }));
  }, []);

  // Optimize task selection change handler with useCallback
  const handleTaskSelectionChange = useCallback((taskId: UUID | null) => {
    setFormData((prev) => ({
      ...prev,
      task_id: taskId, // 直接使用 taskId，包括 null（符合空值语义）
    }));
  }, []);

  // Optimize title change handler with useCallback
  const handleTitleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      handleInputChange("title", e.target.value);
    },
    [handleInputChange],
  );

  // Memoize TaskSelector props to prevent unnecessary re-renders
  const stableFilterStatus = useMemo(() => [...ALL_TASK_STATUSES], []);
  const stablePreloadedTasks = useMemo(() => preloadedTasks, [preloadedTasks]);

  const taskSelectorProps = useMemo(() => {
    return {
      value: formData.task_id === undefined ? null : formData.task_id,
      placeholder: t("task.selectTaskPlaceholder"),
      disabled: loading,
      filterStatus: stableFilterStatus,
      deferRemoteLoad: true,
      expandFilterForSelected: true,
      preloadedTasks: stablePreloadedTasks,
    };
  }, [formData.task_id, loading, stablePreloadedTasks, stableFilterStatus, t]);

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={handleClose}
      closeDisabled={loading}
      ariaLabelledBy="time-entry-modal-title"
      loading={loading}
      error={error}
      onErrorDismiss={() => setError(null)}
      showLoadingOverlay={false}
      showLoadingSpinner={true}
      loadingSpinnerSize="md"
      showCloseButton={true}
      errorDisplayMode="inline"
      header={
        entry ? t("timeLog.modal.editTimeLog") : t("timeLog.modal.addTimeLog")
      }
      footer={
        <FormActions
          loading={loading}
          onCancel={attemptClose}
          onSubmit={() => formRef.current?.requestSubmit()}
          onDelete={
            entry && mode === "default" && onRequestDelete
              ? () => {
                  attemptClose();
                  onRequestDelete(entry);
                }
              : undefined
          }
        />
      }
    >
      <form ref={formRef} onSubmit={handleSubmit} className="space-y-4">
        {/* Title */}
        <div className="mb-4">
          <label
            htmlFor="title"
            className={FORM_LABEL_SPACED_CLASS}
          >
            {t("timeLog.modal.activity")} *
          </label>
          <TextInput
            id="title"
            name="title"
            ref={titleInputRef}
            type="text"
            value={formData.title}
            onChange={handleTitleChange}
            placeholder={t("timeLog.modal.activityPlaceholder")}
            disabled={loading}
          />
        </div>

        {/* Time Range */}
        <div className="mb-4 grid grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="start_time"
              className={FORM_LABEL_SPACED_CLASS}
            >
              {t("eventModal.fields.startTime")}
            </label>
            <TextInput
              id="start_time"
              name="start_time"
              type="time"
              step="300"
              value={formatTime(formData.start_time || "", activeTimezone)}
              onChange={handleStartTimeChange}
              disabled={loading}
            />
          </div>
          <div>
            <label
              htmlFor="end_time"
              className={FORM_LABEL_SPACED_CLASS}
            >
              {t("timeLog.modal.endTimeRequired")}
            </label>
            <TextInput
              id="end_time"
              name="end_time"
              type="time"
              step="300"
              value={formatTime(formData.end_time || "", activeTimezone)}
              onChange={handleEndTimeChange}
              disabled={loading}
            />
          </div>
        </div>

        {/* Area */}
        <div className="mb-4">
          <div className="flex items-center gap-2">
            <AreaSelect
              value={formData.area_id || null}
              onChange={handleAreaChange}
              disabled={loading}
              id="time-entry-area"
              placeholder={t("common.please_select")}
            />
          </div>
        </div>

        {/* Associated Persons */}
        <div className="mb-4">
          <PersonSelector
            selectedPersonIds={formData.person_ids || ([] as UUID[])}
            onSelectionChange={handlePersonSelectionChange}
            placeholder={t("common.none")}
            multiple={true}
            idPrefix="time-entry-person-selector"
          />
        </div>

        {/* Related Task */}
        <div className="mb-4">
          <TaskSelector
            {...taskSelectorProps}
            onChange={handleTaskSelectionChange}
            idPrefix="time-entry-task-selector"
          />
        </div>
      </form>
    </ModalBase>
  );
};

export default TimeEntryModal;
