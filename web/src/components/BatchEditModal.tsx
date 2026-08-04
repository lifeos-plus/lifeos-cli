import React, { useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import ModalBase from "@/layouts/ModalBase";
import ActionButton, { ActionButtonGroup } from "./ActionButton";
import PersonSelector from "./selects/PersonSelector";
import AreaSelect from "./selects/AreaSelect";
import { timelogsApi } from "@/services/api/timelogs";
import {
  invalidateTimelogLists,
  invalidateTimelogsAdvancedSearch,
} from "@/services/api/cacheInvalidation/timelogs";
import { useToast } from "@/contexts/ToastContext";
import TaskSelector from "./selects/TaskSelector";
import { ALL_TASK_STATUSES } from "@/utils/constants";
import { FormField, TextInput } from "./forms";
import { FORM_LABEL_CLASS } from "./forms/styles";
import type { UUID } from "@/types/primitive";

interface BatchEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedEntryIds: Set<UUID>;
  onSuccess: () => void | Promise<void>;
}

type EditMode = "people" | "title" | "task" | "area";

const BatchEditModal: React.FC<BatchEditModalProps> = ({
  isOpen,
  onClose,
  selectedEntryIds,
  onSuccess,
}) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editMode, setEditMode] = useState<EditMode>("people");
  const [loading, setLoading] = useState(false);
  const [personMode, setPersonMode] = useState<"add" | "replace" | "clear">(
    "replace",
  );
  const [selectedPersonIds, setSelectedPersonIds] = useState<UUID[]>([]);
  const [titleMode, setTitleMode] = useState<"replace" | "find_replace">(
    "replace",
  );
  const [titleValue, setTitleValue] = useState("");
  const [findText, setFindText] = useState("");
  const [taskMode, setTaskMode] = useState<"replace" | "clear">("replace");
  const [selectedTaskId, setSelectedTaskId] = useState<UUID | null>(null);
  const [areaMode, setAreaMode] = useState<"replace" | "clear">(
    "replace",
  );
  const [selectedAreaId, setSelectedAreaId] = useState<UUID | null>(
    null,
  );

  const { showSuccess, showError, showInfo } = useToast();

  // Local toggle button to unify active/inactive styles with ActionButton
  function ToggleButton({
    active,
    label,
    onClick,
    size = "sm",
    className = "",
  }: {
    active: boolean;
    label: string;
    onClick: () => void;
    size?: "sm" | "md" | "lg";
    className?: string;
  }) {
    return (
      <ActionButton
        label={label}
        onClick={onClick}
        size={size}
        color={active ? "primary" : "neutral"}
        variant={active ? "outline" : "ghost"}
        className={className}
      />
    );
  }

  const handleSubmit = useCallback(async () => {
    if (selectedEntryIds.size === 0) {
      showError(t("batchEdit.title"), t("batchEdit.errors.noEntriesSelected"));
      return;
    }

    setLoading(true);
    try {
      const eventIds = Array.from(selectedEntryIds);
      const batchSize = 100; // 每批最多100条记录
      const totalBatches = Math.ceil(eventIds.length / batchSize);

      let totalUpdated = 0;
      let totalFailed = 0;
      const allFailedIds: UUID[] = [];
      const allErrors: string[] = [];

      // 分批处理
      for (let i = 0; i < totalBatches; i++) {
        const startIndex = i * batchSize;
        const endIndex = Math.min(startIndex + batchSize, eventIds.length);
        const batchIds = eventIds.slice(startIndex, endIndex);

        // 显示进度信息
        if (totalBatches > 1) {
          showInfo(
            t("batchEdit.title"),
            t("batchEdit.progress.batchProcessing", {
              current: i + 1,
              total: totalBatches,
              count: batchIds.length,
            }),
          );
        }

        const updateParams: {
          timelog_ids: UUID[];
          update_type: EditMode;
          people?: { mode: "add" | "replace" | "clear"; person_ids: UUID[] };
          title?: {
            mode: "replace" | "find_replace";
            value: string;
            find?: string;
          };
          task?: { mode: "replace" | "clear"; task_id?: UUID };
          area?: { area_id: UUID | null };
        } = {
          timelog_ids: batchIds,
          update_type: editMode,
        };

        if (editMode === "people") {
          if (personMode === "clear") {
            updateParams.people = { mode: "clear", person_ids: [] };
          } else if (selectedPersonIds.length === 0) {
            showError(
              t("batchEdit.title"),
              t("batchEdit.errors.noPersonsSelected"),
            );
            setLoading(false);
            return;
          } else {
            updateParams.people = {
              mode: personMode,
              person_ids: selectedPersonIds,
            };
          }
        } else if (editMode === "title") {
          if (!titleValue.trim()) {
            showError(t("batchEdit.title"), t("batchEdit.errors.noTitleValue"));
            setLoading(false);
            return;
          }
          if (titleMode === "find_replace" && !findText.trim()) {
            showError(t("batchEdit.title"), t("batchEdit.errors.noFindText"));
            setLoading(false);
            return;
          }
          updateParams.title = {
            mode: titleMode,
            value: titleValue.trim(),
            ...(titleMode === "find_replace" && { find: findText.trim() }),
          };
        } else if (editMode === "task") {
          if (taskMode === "replace" && selectedTaskId === null) {
            showError(
              t("batchEdit.title"),
              t("batchEdit.errors.noTaskSelected"),
            );
            setLoading(false);
            return;
          }
          updateParams.task = {
            mode: taskMode,
            ...(taskMode === "replace" && {
              task_id: selectedTaskId || undefined,
            }),
          };
        } else if (editMode === "area") {
          if (areaMode === "replace") {
            if (selectedAreaId === null) {
              showError(
                t("batchEdit.title"),
                t("batchEdit.errors.noAreaSelected"),
              );
              setLoading(false);
              return;
            }
            updateParams.area = {
              area_id: selectedAreaId,
            };
          } else {
            updateParams.area = {
              area_id: null,
            };
          }
        }

        try {
          const response = await timelogsApi.batchUpdate(updateParams);

          totalUpdated += response.updated_count;
          totalFailed += response.failed_ids.length;
          allFailedIds.push(...response.failed_ids);
          allErrors.push(...response.errors);
        } catch (error) {
          const errorMessage =
            error instanceof Error ? error.message : t("common.requestFailed");
          allErrors.push(
            t("batchEdit.errors.batchFailed", {
              batch: i + 1,
              error: errorMessage,
            }),
          );
          totalFailed += batchIds.length;
        }
      }

      // 显示最终结果
      if (totalUpdated > 0) {
        const successTitle = t("batchEdit.success.title");
        const successMessage =
          totalFailed > 0
            ? t("batchEdit.success.messageWithFailed", {
                updated: totalUpdated,
                failed: totalFailed,
              })
            : t("batchEdit.success.message", { updated: totalUpdated });

        showSuccess(successTitle, successMessage);

        if (allFailedIds.length > 0) {
          const hasMore = allFailedIds.length > 20;
          const idsForDisplay = hasMore
            ? allFailedIds.slice(0, 20).join(", ")
            : allFailedIds.join(", ");
          const failedIdsMessage = hasMore
            ? t("batchEdit.success.failedIdsMore", {
                ids: idsForDisplay,
                total: allFailedIds.length,
              })
            : t("batchEdit.success.failedIds", { ids: idsForDisplay });

          showInfo(t("batchEdit.title"), failedIdsMessage);
        }

        if (allErrors.length > 0) {
          console.warn(t("batchEdit.errors.details"), allErrors);
        }

        await Promise.all([
          invalidateTimelogLists(queryClient),
          invalidateTimelogsAdvancedSearch(queryClient),
        ]);
        await onSuccess();
        onClose();
      } else {
        showError(t("batchEdit.title"), t("batchEdit.errors.noRecordsUpdated"));
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : t("common.operationFailed");
      showError(t("batchEdit.errors.title"), errorMessage);
    } finally {
      setLoading(false);
    }
  }, [
    selectedEntryIds,
    editMode,
    personMode,
    selectedPersonIds,
    titleMode,
    titleValue,
    findText,
    taskMode,
    selectedTaskId,
    areaMode,
    selectedAreaId,
    onSuccess,
    onClose,
    queryClient,
    showSuccess,
    showError,
    showInfo,
    t,
  ]);

  const handleClose = useCallback(() => {
    if (!loading) {
      setEditMode("people");
      setPersonMode("replace");
      setSelectedPersonIds([]);
      setTitleMode("replace");
      setTitleValue("");
      setFindText("");
      setTaskMode("replace");
      setSelectedTaskId(null);
      setAreaMode("replace");
      setSelectedAreaId(null);
      onClose();
    }
  }, [loading, onClose]);

  const getModalTitle = () => {
    const count = selectedEntryIds.size;
    return t("batchEdit.modalTitle", { count });
  };

  return (
    <ModalBase isOpen={isOpen} onClose={handleClose}>
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg font-bold text-base-content">
          {getModalTitle()}
        </h2>
        <p className="text-base mt-1">{t("batchEdit.description")}</p>
        {selectedEntryIds.size > 100 && (
          <div className="mt-3 p-3 bg-primary/10 rounded-lg">
            <div className="flex items-start gap-2">
              <svg
                className="w-5 h-5 text-primary mt-0.5 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-base text-primary">
                {t("batchEdit.warning.largeBatch", {
                  count: selectedEntryIds.size,
                  batchSize: 100,
                })}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Edit Mode Selection */}
      <div className="mb-6">
        <label className={`${FORM_LABEL_CLASS} mb-3`}>
          {t("batchEdit.editType.label")}
        </label>
        <div className="flex gap-2">
          <ToggleButton
            label={t("batchEdit.editType.persons")}
            active={editMode === "people"}
            onClick={() => setEditMode("people")}
          />
          <ToggleButton
            label={t("batchEdit.editType.title")}
            active={editMode === "title"}
            onClick={() => setEditMode("title")}
          />
          <ToggleButton
            label={t("batchEdit.editType.task")}
            active={editMode === "task"}
            onClick={() => setEditMode("task")}
          />
          <ToggleButton
            label={t("target.area")}
            active={editMode === "area"}
            onClick={() => setEditMode("area")}
          />
        </div>
      </div>

      {/* Content Section */}
      <div className="bg-base-100 rounded-lg p-4 mb-6 ">
        {/* Persons Edit Mode */}
        {editMode === "people" && (
          <div className="space-y-4">
            <div>
              <label className={`${FORM_LABEL_CLASS} mb-2`}>
                {t("batchEdit.modes.label")}
              </label>
              <div className="flex gap-2">
                <ToggleButton
                  label={t("common.replace")}
                  active={personMode === "replace"}
                  onClick={() => setPersonMode("replace")}
                />
                <ToggleButton
                  label={t("common.add")}
                  active={personMode === "add"}
                  onClick={() => setPersonMode("add")}
                />
                <ToggleButton
                  label={t("common.clear")}
                  active={personMode === "clear"}
                  onClick={() => setPersonMode("clear")}
                />
              </div>
            </div>
            {personMode !== "clear" && (
              <div>
                <PersonSelector
                  selectedPersonIds={selectedPersonIds}
                  onSelectionChange={setSelectedPersonIds}
                  multiple={true}
                  idPrefix="batch-edit-persons"
                />
                <p className="text-sm mt-1">
                  {personMode === "replace" &&
                    t("batchEdit.persons.replaceDescription")}
                  {personMode === "add" &&
                    t("batchEdit.persons.addDescription")}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Title Edit Mode */}
        {editMode === "title" && (
          <div className="space-y-4">
            <div>
              <label className={`${FORM_LABEL_CLASS} mb-2`}>
                {t("batchEdit.modes.label")}
              </label>
              <div className="flex gap-2">
                <ToggleButton
                  label={t("common.replace")}
                  active={titleMode === "replace"}
                  onClick={() => setTitleMode("replace")}
                />
                <ToggleButton
                  label={t("common.findReplace")}
                  active={titleMode === "find_replace"}
                  onClick={() => setTitleMode("find_replace")}
                />
              </div>
            </div>

            {titleMode === "find_replace" && (
              <FormField
                label={t("batchEdit.subtitle.findTextLabel")}
                htmlFor="find-text"
              >
                <TextInput
                  id="find-text"
                  name="find-text"
                  type="text"
                  value={findText}
                  onChange={(e) => setFindText(e.target.value)}
                  placeholder={t("batchEdit.subtitle.findTextPlaceholder")}
                  size="sm"
                />
              </FormField>
            )}

            <FormField
              label={
                titleMode === "replace"
                  ? t("batchEdit.subtitle.newTitleLabel")
                  : t("batchEdit.subtitle.replaceWithLabel")
              }
              htmlFor="title-value"
            >
              <TextInput
                id="title-value"
                name="title-value"
                type="text"
                value={titleValue}
                onChange={(e) => setTitleValue(e.target.value)}
                placeholder={
                  titleMode === "replace"
                    ? t("batchEdit.subtitle.newTitlePlaceholder")
                    : t("batchEdit.subtitle.replaceWithPlaceholder")
                }
                size="sm"
              />
            </FormField>
          </div>
        )}

        {/* Task Edit Mode */}
        {editMode === "task" && (
          <div className="space-y-4">
            <div>
              <label className={`${FORM_LABEL_CLASS} mb-2`}>
                {t("batchEdit.modes.label")}
              </label>
              <div className="flex gap-2">
                <ToggleButton
                  label={t("common.replace")}
                  active={taskMode === "replace"}
                  onClick={() => setTaskMode("replace")}
                />
                <ToggleButton
                  label={t("common.clear")}
                  active={taskMode === "clear"}
                  onClick={() => setTaskMode("clear")}
                />
              </div>
            </div>

            {taskMode === "replace" && (
              <div>
                <TaskSelector
                  value={selectedTaskId || null}
                  onChange={(id) => setSelectedTaskId(id || null)}
                  disabled={loading}
                  filterStatus={ALL_TASK_STATUSES}
                  deferRemoteLoad={true}
                  expandFilterForSelected={true}
                  idPrefix="batch-edit-task"
                />
                <p className="text-sm mt-1">
                  {t("batchEdit.task.description")}
                </p>
              </div>
            )}

            {taskMode === "clear" && (
              <div className="text-sm">
                {t("batchEdit.task.clearDescription")}
              </div>
            )}
          </div>
        )}

        {/* Area Edit Mode */}
        {editMode === "area" && (
          <div className="space-y-4">
            <div>
              <label className={`${FORM_LABEL_CLASS} mb-2`}>
                {t("batchEdit.modes.label")}
              </label>
              <div className="flex gap-2">
                <ToggleButton
                  label={t("common.replace")}
                  active={areaMode === "replace"}
                  onClick={() => setAreaMode("replace")}
                />
                <ToggleButton
                  label={t("common.clear")}
                  active={areaMode === "clear"}
                  onClick={() => {
                    setAreaMode("clear");
                    setSelectedAreaId(null);
                  }}
                />
              </div>
            </div>

            {areaMode === "replace" ? (
              <div>
                <AreaSelect
                  value={selectedAreaId || undefined}
                  onChange={(value) => setSelectedAreaId(value || null)}
                  id="batch-edit-area"
                  placeholder={t("common.please_select")}
                />
                <p className="text-sm mt-1">
                  {t("batchEdit.area.description")}
                </p>
              </div>
            ) : (
              <div className="text-sm">
                {t("batchEdit.area.description")}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="pt-4 border-t border-base-200">
        <ActionButtonGroup splitOpposite>
          <ActionButton
            label={t("common.cancel")}
            color="neutral"
            size="md"
            onClick={handleClose}
            disabled={loading}
          />
          <ActionButton
            label={loading ? t("batchEdit.confirmEditing") : t("common.edit")}
            color="primary"
            size="md"
            onClick={handleSubmit}
            disabled={selectedEntryIds.size === 0 || loading}
          />
        </ActionButtonGroup>
      </div>
    </ModalBase>
  );
};

export default BatchEditModal;
