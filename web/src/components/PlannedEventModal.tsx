// src/components/PlannedEventModal.tsx
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import type {
  PlannedEvent,
  PlannedEventCreate,
  PlannedEventUpdate,
  TaskWithSubtasks,
  Vision,
  Task as ApiTask,
} from "@/services/api";

import { plannedEventsApi } from "@/services/api/plannedEvents";
import ModalBase from "@/layouts/ModalBase";
import RecurrenceSelector from "./RecurrenceSelector";
import { FormField, TextInput, Checkbox, RadioGroup } from "./forms";
import { FORM_LABEL_SPACED_CLASS } from "./forms/styles";
import DateTimeSelector from "./forms/DateTimeSelector";

import TaskSelector from "./selects/TaskSelector";
import { DeleteButton, FormActions } from "./ActionButton";
import { useAreas } from "@/hooks/queries/useAreas";
import AreaSelect from "./selects/AreaSelect";
import { useModalState } from "@/hooks/useModalState";
import { useToast } from "@/contexts/ToastContext";
import { ACTIVE_TASK_STATUSES } from "@/utils/constants";
import type { UUID } from "@/types/primitive";
import { normalizeTimezone } from "@/utils/datetime";
import { formatDateTime } from "@/utils/datetime";
import {
  buildPlannedEventFormData,
  buildPlannedEventUpdatePayload,
  createEmptyPlannedEventFormData,
} from "./plannedEventModalUtils";

interface PlannedEventModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: () => void;
  plannedEvent?: PlannedEvent | null;
  initialDateInfo?: {
    start: Date;
    end: Date;
    allDay: boolean;
  } | null;
  /** Optional: provide preloaded flat tasks to avoid internal fetching */
  preloadedTasks?: ApiTask[];
  /** Optional: provide visions to avoid internal fetching */
  visions?: Vision[];
  /** Optional: timezone identifier to align selectors */
  timezone?: string;
}

export default function PlannedEventModal({
  isOpen,
  onClose,
  onSave,
  plannedEvent,
  initialDateInfo,
  preloadedTasks,
  visions,
  timezone,
}: PlannedEventModalProps) {
  const { t } = useTranslation();
  const resolvedTimezone = useMemo(
    () => normalizeTimezone(timezone),
    [timezone],
  );
  const [formData, setFormData] = useState<PlannedEventCreate>(() =>
    createEmptyPlannedEventFormData(),
  );

  const modalStateRaw = useModalState();

  // Memoize modal state to prevent unnecessary re-renders
  const { loading, error, setError, withLoading } = useMemo(
    () => modalStateRaw,
    [modalStateRaw],
  );
  const [selectedTaskId, setSelectedTaskId] = useState<UUID | null>(
    null, // Start with null to avoid placeholder selection
  );

  // Delete related states
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteType, setDeleteType] = useState<"single" | "all_future" | "all">(
    "single",
  );
  const [editScope, setEditScope] = useState<"single" | "all_future" | "all">(
    "all",
  );

  // Shared areas via hook
  const areasRaw = useAreas();

  // Memoize areas to prevent unnecessary re-renders
  const { areas: areasFromCache } = useMemo(
    () => areasRaw,
    [areasRaw],
  );
  const allowScopedEditing = Boolean(
    plannedEvent?.is_recurring && plannedEvent?.is_instance,
  );
  const effectiveScope = allowScopedEditing ? editScope : "all";

  // Toast notifications
  const toastRaw = useToast();

  // Memoize toast object to prevent unnecessary re-renders
  const toast = useMemo(() => toastRaw, [toastRaw]);

  // Run initialization only once per open to avoid wiping first user selection
  const initializedRef = useRef(false);
  const initialFormDataRef = useRef<PlannedEventCreate | null>(null);

  // Initialize form data when modal opens (once per open)
  useEffect(() => {
    if (!isOpen) {
      initializedRef.current = false;
      initialFormDataRef.current = null;
      return;
    }
    if (initializedRef.current) return;

    setError(null);

    const nextFormData = buildPlannedEventFormData({
      plannedEvent,
      initialDateInfo,
    });
    initialFormDataRef.current = nextFormData;
    setFormData(nextFormData);

    if (plannedEvent) {
      setSelectedTaskId(plannedEvent.task_id || null);
    } else {
      setSelectedTaskId(null);
    }

    if (plannedEvent?.is_recurring && plannedEvent?.is_instance) {
      setEditScope("single");
    } else {
      setEditScope("all");
    }

    initializedRef.current = true;
  }, [isOpen, areasFromCache, plannedEvent, initialDateInfo, setError]);

  // Memoize preloadedTasks to prevent unnecessary re-renders
  const stablePreloadedTasks = useMemo(
    () => preloadedTasks || [],
    [preloadedTasks],
  );
  const stableVisions = useMemo(() => visions, [visions]);
  // Only show actionable tasks for scheduling: todo/in_progress/paused
  const stableFilterStatus = useMemo(() => ACTIVE_TASK_STATUSES, []);

  // Memoize TaskSelector props to prevent unnecessary re-renders
  const taskSelectorProps = useMemo(
    () => ({
      value: selectedTaskId || null,
      placeholder: t("common.none"),
      disabled: loading,
      filterStatus: stableFilterStatus,
      preloadedTasks: stablePreloadedTasks as unknown as TaskWithSubtasks[],
      // Allow remote load when no valid preloaded tasks provided
      deferRemoteLoad: true,
    }),
    [selectedTaskId, loading, stablePreloadedTasks, stableFilterStatus, t],
  );

  const occurrenceDateLabel = useMemo(() => {
    if (!plannedEvent?.start_time) return "";
    return formatDateTime(plannedEvent.start_time, resolvedTimezone);
  }, [plannedEvent?.start_time, resolvedTimezone]);

  /**
   * Handle form input changes
   */
  const handleInputChange = useCallback(
    (
      e: React.ChangeEvent<
        HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
      >,
    ) => {
      const { name, value, type } = e.target;

      if (type === "checkbox") {
        const checked = (e.target as HTMLInputElement).checked;
        setFormData((prev) => ({
          ...prev,
          [name]: checked,
        }));
      } else if (type === "number" || name === "area_id") {
        setFormData((prev) => ({
          ...prev,
          [name]: parseInt(value) || "",
        }));
      } else {
        setFormData((prev) => ({
          ...prev,
          [name]: value,
        }));
      }
    },
    [],
  );

  // Optimize task selection handler with useCallback to prevent unnecessary re-renders
  const handleTaskSelect = useCallback(
    (taskId: UUID | null) => {
      const taskIdValue = taskId && taskId !== null ? taskId : null;

      // Handle task selection directly here instead of through useEffect
      setFormData((prev) => {
        const newState = {
          ...prev,
          task_id: taskIdValue !== null ? taskIdValue : null,
        };

        // Auto-fill title and area if it's empty and we have task data
        if (
          taskIdValue !== null &&
          Array.isArray(stablePreloadedTasks) &&
          stablePreloadedTasks.length > 0
        ) {
          const picked = stablePreloadedTasks.find((t) => t.id === taskIdValue);
          if (picked) {
            const v = Array.isArray(stableVisions)
              ? (stableVisions as Vision[]).find(
                  (vv) => vv.id === picked.vision_id,
                )
              : undefined;

            // Auto-fill title if empty
            if (!prev.title.trim()) {
              const combinedTitle = v
                ? `${v.name} - ${picked.content}`
                : picked.content;
              newState.title = combinedTitle;
            }

            // Auto-fill area if not set and vision has area
            if (
              (!prev.area_id || prev.area_id === null) &&
              v?.area_id
            ) {
              // 确保 area_id 始终是字符串类型，null 转换为 null
              newState.area_id = v.area_id || null;
            }
          }
        }

        return newState;
      });

      // Also update selectedTaskId for consistency
      setSelectedTaskId(taskIdValue);
    },
    [stablePreloadedTasks, stableVisions],
  );

  // New handlers for separated date/time controls
  const handleStartTimeSelect = useCallback((isoString: string) => {
    setFormData((prev) => ({
      ...prev,
      start_time: isoString,
    }));
  }, []);

  const handleEndTimeSelect = useCallback(
    (isoString: string) => {
      if (!isoString) {
        setFormData((prev) => ({
          ...prev,
          end_time: "",
        }));
        return;
      }

      // Handle cross-day logic: if end time is before start time, assume next day
      const newEndTime = new Date(isoString);
      const startTime = formData.start_time
        ? new Date(formData.start_time)
        : null;

      if (startTime && newEndTime < startTime) {
        // Move end time to next day
        newEndTime.setDate(newEndTime.getDate() + 1);
      }

      setFormData((prev) => ({
        ...prev,
        end_time: newEndTime.toISOString(),
      }));
    },
    [formData.start_time],
  );

  // Tags UI removed; keeping data field for compatibility.

  /**
   * Handle recurrence rule changes
   */
  const handleRecurrenceChange = useCallback((rrule: string) => {
    setFormData((prev) => ({
      ...prev,
      rrule_string: rrule,
      is_recurring: rrule !== "",
    }));
  }, []);

  // Optimize area change handler
  const handleAreaChange = useCallback((v: UUID | null | undefined) => {
    setFormData((prev) => ({
      ...prev,
      area_id: v ?? null,
    }));
  }, []);

  /**
   * Handle form submission
   */
  const handleSubmit = useCallback(
    async (formEvent: React.FormEvent) => {
      formEvent.preventDefault();

      if (!formData.title.trim()) {
        setError(t("eventModal.errors.titleRequired"));
        return;
      }

      if (!formData.start_time) {
        setError(t("eventModal.errors.startTimeRequired"));
        return;
      }

      // area_id is now optional, no validation needed

      try {
        await withLoading(async () => {
          if (plannedEvent) {
            const payload: PlannedEventUpdate = buildPlannedEventUpdatePayload(
              initialFormDataRef.current ?? createEmptyPlannedEventFormData(),
              formData,
            );
            if (allowScopedEditing && effectiveScope === "single") {
              delete payload.rrule_string;
              delete payload.recurrence_pattern;
              delete payload.is_recurring;
            }

            if (Object.keys(payload).length === 0) {
              onSave();
              return;
            }

            await plannedEventsApi.update(
              plannedEvent.id,
              payload,
              plannedEvent.is_recurring
                ? {
                    updateType: effectiveScope,
                    instanceId:
                      allowScopedEditing && effectiveScope !== "all"
                        ? (plannedEvent.instance_id ?? undefined)
                        : undefined,
                    instanceStart:
                      allowScopedEditing && effectiveScope !== "all"
                        ? plannedEvent.start_time
                        : undefined,
                  }
                : undefined,
            );

            // 显示成功提示
            toast.showSuccess(
              t("eventModal.success.updateTitle"),
              t("eventModal.success.updateMessage", { title: formData.title }),
            );
          } else {
            await plannedEventsApi.create(formData);

            // 显示成功提示
            toast.showSuccess(
              t("eventModal.success.createTitle"),
              t("eventModal.success.createMessage", { title: formData.title }),
            );
          }

          onSave();
        });
      } catch (err) {
        const errorMessage =
          err instanceof Error
            ? err.message
            : t("eventModal.errors.saveFailed");
        setError(errorMessage);

        // 显示错误提示
        toast.showError(
          t("eventModal.errors.saveTitle"),
          t("eventModal.errors.saveMessage", { error: errorMessage }),
        );
      }
    },
    [
      formData,
      plannedEvent,
      withLoading,
      toast,
      onSave,
      setError,
      t,
      allowScopedEditing,
      effectiveScope,
    ],
  );

  /**
   * Handle actual deletion
   */
  const handleDelete = useCallback(
    async (type: "single" | "all_future" | "all") => {
      if (!plannedEvent) return;

      try {
        await withLoading(async () => {
          // Call delete API with delete type
          const requiresInstanceContext =
            plannedEvent.is_recurring && type !== "all";
          await plannedEventsApi.delete(plannedEvent.id, {
            deleteType: type,
            instanceId:
              requiresInstanceContext && plannedEvent.is_instance
                ? (plannedEvent.instance_id ?? undefined)
                : undefined,
            instanceStart: requiresInstanceContext
              ? plannedEvent.start_time
              : undefined,
          });

          // 显示成功提示
          const deleteTypeText = {
            single: t("eventModal.deleteTypes.single"),
            all_future: t("eventModal.deleteTypes.allFuture"),
            all: t("eventModal.deleteTypes.all"),
          }[type];

          toast.showSuccess(
            t("eventModal.success.deleteTitle"),
            t("eventModal.success.deleteMessage", {
              type: deleteTypeText,
              title: plannedEvent.title,
            }),
          );

          onSave(); // Refresh the parent component
          onClose(); // Close the modal
        });
      } catch (err) {
        const errorMessage =
          err instanceof Error
            ? err.message
            : t("eventModal.errors.deleteFailed");
        setError(errorMessage);

        // 显示错误提示
        toast.showError(
          t("eventModal.errors.deleteTitle"),
          t("eventModal.errors.saveMessage", { error: errorMessage }),
        );
      } finally {
        setShowDeleteConfirm(false);
      }
    },
    [plannedEvent, withLoading, onSave, onClose, toast, setError, t],
  );

  /**
   * Handle delete button click
   */
  const handleDeleteClick = useCallback(() => {
    if (!plannedEvent) return;

    if (plannedEvent.is_recurring) {
      setShowDeleteConfirm(true);
    } else {
      handleDelete("single");
    }
  }, [plannedEvent, handleDelete]);

  // Optimize delete button click handler for delete confirm
  const handleDeleteConfirm = useCallback(() => {
    handleDelete(deleteType);
  }, [handleDelete, deleteType]);

  const attemptClose = useCallback(() => {
    if (!loading) {
      setError(null);
      onClose();
    }
  }, [loading, onClose, setError]);

  // Optimize error dismiss handler
  const handleErrorDismiss = useCallback(() => {
    setError(null);
  }, [setError]);

  // Optimize delete confirm close handler
  const handleDeleteConfirmClose = useCallback(() => {
    setShowDeleteConfirm(false);
  }, []);

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={attemptClose}
      closeDisabled={loading}
      header={plannedEvent ? t("common.edit") : t("eventModal.title.create")}
      loading={loading}
      error={error}
      onErrorDismiss={handleErrorDismiss}
      showLoadingOverlay={false}
      showLoadingSpinner={true}
      loadingSpinnerSize="md"
      showCloseButton={true}
      errorDisplayMode="inline"
      footer={
        <FormActions
          loading={loading}
          onCancel={onClose}
          onSubmit={() => document.querySelector("form")?.requestSubmit()}
          leftSlot={
            plannedEvent ? (
              <DeleteButton onClick={handleDeleteClick} disabled={loading} />
            ) : undefined
          }
        />
      }
    >
      {/* Form */}
      <form
        onSubmit={handleSubmit}
        className="space-y-3 sm:space-y-4 lg:space-y-5"
      >
        {/* 1. 关联任务 - 放在最上方 */}
        <div>
          <TaskSelector
            {...taskSelectorProps}
            onChange={handleTaskSelect}
            idPrefix="task-selector-eventmodal"
          />
        </div>

        {/* 2. 标题 + 领域 - 响应式排列 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {/* Title - 移动端全宽，平板占1/2，桌面占2/3 */}
          <div className="sm:col-span-2 lg:col-span-2">
            <FormField
              label={t("eventModal.fields.title")}
              htmlFor="title"
              required
            >
              <TextInput
                id="title"
                name="title"
                type="text"
                value={formData.title}
                onChange={handleInputChange}
                placeholder={t("eventModal.fields.titlePlaceholder")}
                required
              />
            </FormField>
          </div>

          {/* Area - 移动端全宽，平板和桌面占1/3 */}
          <div className="sm:col-span-2 lg:col-span-1">
            <AreaSelect
              value={formData.area_id ?? null}
              onChange={handleAreaChange}
              id="planned-event-modal-area"
              showNoneOption
              clearBehavior="none"
            />
            {/* area_id is now optional, no error message needed */}
          </div>
        </div>

        {/* 3. 时间设置 */}
        <div className="bg-base-200 rounded-lg p-3 sm:p-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            {/* All day toggle */}
            <div className="sm:col-span-2">
              <Checkbox
                id="is_all_day"
                name="is_all_day"
                checked={formData.is_all_day}
                onCheckedChange={(checked) => {
                  const syntheticEvent = {
                    target: {
                      name: "is_all_day",
                      value: checked,
                      checked,
                      type: "checkbox",
                    },
                  } as unknown as React.ChangeEvent<HTMLInputElement>;
                  handleInputChange(syntheticEvent);
                }}
                label={t("eventModal.fields.allDay")}
                variant="primary"
                size="md"
              />
            </div>

            {/* Start time */}
            <div>
              <label
                htmlFor="start-time-selector"
                className={FORM_LABEL_SPACED_CLASS}
              >
                {t("eventModal.fields.startTime")}{" "}
                <span className="text-error">*</span>
              </label>
              <DateTimeSelector
                dateId="start-date"
                timeId="start-time"
                value={formData.start_time}
                isAllDay={formData.is_all_day}
                disabled={loading}
                onChange={handleStartTimeSelect}
                className="text-sm"
                quickTimeOptions={[
                  "06:00",
                  "08:00",
                  "09:00",
                  "12:00",
                  "14:00",
                  "17:00",
                  "18:00",
                  "20:00",
                  "22:00",
                ]}
                timezone={resolvedTimezone}
              />
            </div>

            {/* End time */}
            {!formData.is_all_day && (
              <div>
                <label
                  htmlFor="end-time-selector"
                  className={FORM_LABEL_SPACED_CLASS}
                >
                  {t("eventModal.fields.endTime")}
                </label>
                <DateTimeSelector
                  dateId="end-date"
                  timeId="end-time"
                  value={formData.end_time || ""}
                  isAllDay={false}
                  disabled={loading}
                  onChange={handleEndTimeSelect}
                  className="text-sm"
                  quickTimeOptions={[
                    "06:00",
                    "08:00",
                    "09:00",
                    "12:00",
                    "14:00",
                    "17:00",
                    "18:00",
                    "20:00",
                    "22:00",
                  ]}
                  timezone={resolvedTimezone}
                />
              </div>
            )}
          </div>
        </div>

        {/* 4. 循环设置 */}
        {allowScopedEditing && (
          <div className="bg-base-200 rounded-lg p-3 sm:p-4 space-y-3">
            <div className="text-sm sm:text-base font-semibold text-base-content">
              {t("eventModal.editScope.title")}
            </div>
            <RadioGroup
              variant="card"
              value={editScope}
              options={[
                {
                  value: "single",
                  label: t("eventModal.editScope.options.single.title"),
                  description: t(
                    "eventModal.editScope.options.single.description",
                  ),
                },
                {
                  value: "all_future",
                  label: t("eventModal.editScope.options.allFuture.title"),
                  description: t(
                    "eventModal.editScope.options.allFuture.description",
                  ),
                },
                {
                  value: "all",
                  label: t("eventModal.editScope.options.all.title"),
                  description: t(
                    "eventModal.editScope.options.all.description",
                  ),
                },
              ]}
              onChange={(nextValue) =>
                setEditScope(nextValue as "single" | "all_future" | "all")
              }
            />
            <p className="text-xs sm:text-sm text-base-content/60">
              {t(`eventModal.editScope.notice.${effectiveScope}`, {
                date:
                  occurrenceDateLabel || t("eventModal.editScope.fallbackDate"),
              })}
            </p>
          </div>
        )}

        <div>
          <RecurrenceSelector
            value={formData.rrule_string ?? undefined}
            onChange={handleRecurrenceChange}
            startDate={
              formData.start_time ? new Date(formData.start_time) : undefined
            }
          />
        </div>
      </form>

      {/* Delete confirmation dialog for recurring events */}
      {showDeleteConfirm && (
        <ModalBase
          isOpen={showDeleteConfirm}
          onClose={handleDeleteConfirmClose}
          role="alertdialog"
          overlayClosable={false}
          title={t("eventModal.deleteConfirm.title")}
          footer={
            <FormActions
              onCancel={handleDeleteConfirmClose}
              onSubmit={handleDeleteConfirm}
              submitText={t("common.delete")}
              submitColor="error"
              cancelColor="neutral"
            />
          }
        >
          <p className="text-sm sm:text-base leading-relaxed mb-3 sm:mb-4">
            {t("eventModal.deleteConfirm.description", {
              title: plannedEvent?.title,
            })}
          </p>

          <div className="space-y-2 sm:space-y-3">
            <RadioGroup
              variant="card"
              value={deleteType}
              options={[
                {
                  value: "single",
                  label: t("eventModal.deleteConfirm.options.single.title"),
                  description: t(
                    "eventModal.deleteConfirm.options.single.description",
                  ),
                },
                {
                  value: "all_future",
                  label: t("eventModal.deleteConfirm.options.allFuture.title"),
                  description: t(
                    "eventModal.deleteConfirm.options.allFuture.description",
                  ),
                },
                {
                  value: "all",
                  label: t("eventModal.deleteConfirm.options.all.title"),
                  description: t(
                    "eventModal.deleteConfirm.options.all.description",
                  ),
                },
              ]}
              onChange={(nextValue) =>
                setDeleteType(nextValue as "single" | "all_future" | "all")
              }
            />
          </div>
        </ModalBase>
      )}
    </ModalBase>
  );
}
