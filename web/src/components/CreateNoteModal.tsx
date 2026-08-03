import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
  useMemo,
} from "react";
import { useTranslation } from "react-i18next";
import ModalBase from "@/layouts/ModalBase";
import PersonSelector from "./selects/PersonSelector";
import TagSelector from "./selects/TagSelector";
import TaskSelector from "./selects/TaskSelector";
import { FormActions } from "./ActionButton";
import { tasksApi } from "@/services/api/tasks";
import { FormField, TextArea } from "./forms";
import type {
  Note,
  NoteHabitActionSummary,
  NoteTimelogSummary,
} from "@/services/api/notes";
import { ACTIVE_TASK_STATUSES } from "@/utils/constants";
import type { UUID } from "@/types/primitive";
import { Icon } from "./icons";
import { formatDate, formatTime } from "@/utils/datetime";
import { useCreateNoteModalController } from "@/features/notes/controller/useCreateNoteModalController";

type TimelogPreview = Pick<
  NoteTimelogSummary,
  "id" | "title" | "start_time" | "end_time"
>;

type HabitActionPreview = Pick<
  NoteHabitActionSummary,
  "id" | "habit_id" | "habit_title" | "action_date" | "status"
>;

const uniqueUuidList = (ids?: UUID[] | null): UUID[] => {
  if (!ids || ids.length === 0) return [];
  const filtered = ids.filter(
    (id): id is UUID => typeof id === "string" && id.length > 0,
  );
  if (filtered.length === 0) return [];
  return Array.from(new Set(filtered));
};

interface CreateNoteModalProps {
  isOpen: boolean;
  onClose: () => void;
  preSelectedTaskId?: UUID;
  preSelectedTaskTitle?: string;
  preSelectedTimelogId?: UUID;
  preSelectedTimelog?: TimelogPreview | null;
  preSelectedHabitActionId?: UUID;
  preSelectedHabitAction?: HabitActionPreview | null;
  preSelectedPersonIds?: UUID[];
  preSelectedTagIds?: UUID[];
  lockTaskSelection?: boolean;
  lockPersonSelection?: boolean;
  lockTagSelection?: boolean;
  onNoteCreated?: (note?: Note) => void;
  mode?: "create" | "edit";
  existingNote?: Note;
  timezone?: string;
  onRequestDelete?: (note: Note) => void;
}

export default function CreateNoteModal({
  isOpen,
  onClose,
  preSelectedTaskId,
  preSelectedTaskTitle,
  preSelectedTimelogId,
  preSelectedTimelog,
  preSelectedHabitActionId,
  preSelectedHabitAction,
  preSelectedPersonIds,
  preSelectedTagIds,
  lockTaskSelection,
  lockPersonSelection,
  lockTagSelection,
  onNoteCreated,
  mode = "create",
  existingNote,
  timezone,
  onRequestDelete,
}: CreateNoteModalProps) {
  const { t } = useTranslation();
  const formRef = useRef<HTMLFormElement | null>(null);
  const [content, setContent] = useState("");
  const [selectedPersonIds, setSelectedPersonIds] = useState<UUID[]>(() =>
    uniqueUuidList(preSelectedPersonIds),
  );
  const normalizedPreSelectedTagIds = useMemo(
    () => uniqueUuidList(preSelectedTagIds),
    [preSelectedTagIds],
  );
  const [selectedTagIds, setSelectedTagIds] = useState<UUID[]>(() => {
    if (mode === "edit" && existingNote) {
      const noteTags = existingNote.tags?.map((tag) => tag.id) ?? [];
      return uniqueUuidList([...normalizedPreSelectedTagIds, ...noteTags]);
    }
    return [...normalizedPreSelectedTagIds];
  });
  const [selectedTaskId, setSelectedTaskId] = useState<UUID | null>(
    preSelectedTaskId ?? null,
  );
  const [lockedTaskLabel, setLockedTaskLabel] = useState<string | null>(
    preSelectedTaskTitle ?? null,
  );
  const isTaskSelectionLocked = lockTaskSelection ?? Boolean(preSelectedTaskId);
  const isPersonSelectionLocked =
    lockPersonSelection ?? Boolean(preSelectedPersonIds?.length);
  const isTagSelectionLocked = lockTagSelection ?? false;
  const lockedTagIds = useMemo(
    () =>
      isTagSelectionLocked ? uniqueUuidList(normalizedPreSelectedTagIds) : [],
    [isTagSelectionLocked, normalizedPreSelectedTagIds],
  );
  const initialTimelogId = useMemo(
    () => preSelectedTimelog?.id ?? preSelectedTimelogId ?? null,
    [preSelectedTimelog?.id, preSelectedTimelogId],
  );
  const initialHabitActionId = useMemo(
    () => preSelectedHabitAction?.id ?? preSelectedHabitActionId ?? null,
    [preSelectedHabitAction?.id, preSelectedHabitActionId],
  );

  const [selectedTimelogIds, setSelectedTimelogIds] = useState<UUID[]>(
    initialTimelogId ? [initialTimelogId] : [],
  );
  const [selectedHabitActionIds, setSelectedHabitActionIds] = useState<UUID[]>(
    initialHabitActionId ? [initialHabitActionId] : [],
  );

  const lockedTaskOptionId: UUID | null =
    selectedTaskId ?? preSelectedTaskId ?? null;

  const lockedTaskOverrideOptions = useMemo(() => {
    if (!isTaskSelectionLocked) return undefined;
    if (!lockedTaskOptionId) return undefined;
    const label =
      lockedTaskLabel ??
      (typeof lockedTaskOptionId === "string" && lockedTaskOptionId.length > 0
        ? `#${lockedTaskOptionId}`
        : t("createNoteModal.relatedTaskLocked"));
    return [
      {
        id: lockedTaskOptionId,
        label,
      },
    ];
  }, [isTaskSelectionLocked, lockedTaskOptionId, lockedTaskLabel, t]);

  // 编辑模式下初始化表单数据
  useEffect(() => {
    if (mode === "edit" && existingNote) {
      setContent(existingNote.content);
      setSelectedPersonIds(existingNote.people?.map((person) => person.id) || []);
      setSelectedTagIds(
        uniqueUuidList([
          ...normalizedPreSelectedTagIds,
          ...(existingNote.tags?.map((t) => t.id) || []),
        ]),
      );
      setSelectedTaskId(existingNote.task?.id || null);
      if (existingNote.task?.content) {
        setLockedTaskLabel(existingNote.task.content);
      }
      setSelectedTimelogIds(
        existingNote.timelogs?.map((timelog) => timelog.id) || [],
      );
      setSelectedHabitActionIds(
        existingNote.habit_actions?.map((habitAction) => habitAction.id) || [],
      );
    }
  }, [mode, existingNote, normalizedPreSelectedTagIds]);

  useEffect(() => {
    if (!isOpen) return;
    if (mode === "edit") return;
    setSelectedTimelogIds(
      initialTimelogId ? [initialTimelogId] : [],
    );
    setSelectedHabitActionIds(
      initialHabitActionId ? [initialHabitActionId] : [],
    );
  }, [isOpen, initialHabitActionId, initialTimelogId, mode]);

  useEffect(() => {
    if (!isOpen) return;
    if (mode === "edit") return;
    setSelectedPersonIds(uniqueUuidList(preSelectedPersonIds));
    setSelectedTaskId(preSelectedTaskId ?? null);
    setSelectedTagIds([...normalizedPreSelectedTagIds]);
    setSelectedHabitActionIds(
      initialHabitActionId ? [initialHabitActionId] : [],
    );
  }, [
    initialHabitActionId,
    isOpen,
    mode,
    preSelectedPersonIds,
    preSelectedTaskId,
    normalizedPreSelectedTagIds,
  ]);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // 重置表单状态
  const resetForm = useCallback(() => {
    setContent("");
    setSelectedPersonIds(uniqueUuidList(preSelectedPersonIds));
    setSelectedTagIds([...normalizedPreSelectedTagIds]);
    setSelectedTaskId(preSelectedTaskId ?? null);
    setLockedTaskLabel(preSelectedTaskTitle ?? null);
    setSelectedTimelogIds(
      initialTimelogId ? [initialTimelogId] : [],
    );
    setSelectedHabitActionIds(
      initialHabitActionId ? [initialHabitActionId] : [],
    );
  }, [
    initialHabitActionId,
    initialTimelogId,
    preSelectedPersonIds,
    preSelectedTaskId,
    preSelectedTaskTitle,
    normalizedPreSelectedTagIds,
  ]);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [resetForm, onClose]);

  const { availableNoteTags, handleCreateTag, submitNote, isSubmitting } =
    useCreateNoteModalController({
      mode,
      existingNote,
      onCompleted: handleClose,
      onNoteCreated,
    });

  // Stable filter status for TaskSelector to avoid re-triggering effects
  const taskFilterStatus = useMemo(() => ACTIVE_TASK_STATUSES, []);

  // 当模态框打开时，聚焦到文本区域
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // 如果未传入标题且有任务ID，则拉取一次任务内容作为展示文案
  useEffect(() => {
    const loadTaskTitle = async () => {
      if (!isOpen) return;
      if (!preSelectedTaskId) return; // 仅在锁定任务场景加载标题
      if (!selectedTaskId) return;
      if (lockedTaskLabel) return;
      try {
        const task = await tasksApi.getById(selectedTaskId);
        if (task?.content) setLockedTaskLabel(task.content);
      } catch {
        setLockedTaskLabel(`#${selectedTaskId}`);
      }
    };
    void loadTaskTitle();
  }, [isOpen, preSelectedTaskId, selectedTaskId, lockedTaskLabel]);

  const handleTagsChange = useCallback(
    (ids: UUID[]) => {
      if (!isTagSelectionLocked) {
        setSelectedTagIds(ids);
        return;
      }
      const merged = new Set<UUID>([...lockedTagIds, ...ids]);
      setSelectedTagIds(Array.from(merged));
    },
    [isTagSelectionLocked, lockedTagIds],
  );

  // 处理表单提交
  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();

      if (!content.trim()) return;

      const mergedTagIds = isTagSelectionLocked
        ? Array.from(new Set<UUID>([...lockedTagIds, ...selectedTagIds]))
        : selectedTagIds;

      submitNote({
        content,
        selectedPersonIds,
        selectedTagIds: mergedTagIds,
        lockedTagIds,
        isTagSelectionLocked,
        selectedTaskId,
        selectedTimelogIds,
        selectedHabitActionIds,
      });
    },
    [
      content,
      selectedPersonIds,
      selectedTagIds,
      selectedTaskId,
      selectedTimelogIds,
      selectedHabitActionIds,
      isTagSelectionLocked,
      lockedTagIds,
      submitNote,
    ],
  );

  // 处理键盘快捷键
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        // 触发表单提交
        formRef.current?.requestSubmit();
      }
    },
    [],
  );

  const isLoading = isSubmitting;
  const modalTitle =
    mode === "edit" ? t("createNoteModal.editTitle") : t("createNoteModal.title");
  const modalDescription = null;
  const submitText =
    mode === "edit"
      ? t("createNoteModal.updateText")
      : t("createNoteModal.submitText");
  const modalSize = mode === "edit" ? "xl" : "2xl";

  const timelogPreview = useMemo<TimelogPreview | null>(() => {
    if (mode === "edit" && existingNote?.timelogs?.length) {
      return existingNote.timelogs[0];
    }
    if (preSelectedTimelog) {
      return preSelectedTimelog;
    }
    return null;
  }, [mode, existingNote, preSelectedTimelog]);

  const timelogTimes = useMemo(() => {
    if (!timelogPreview)
      return { start: null as string | null, end: null as string | null };
    const start = timelogPreview.start_time
      ? formatTime(timelogPreview.start_time, timezone)
      : null;
    const end = timelogPreview.end_time
      ? formatTime(timelogPreview.end_time, timezone)
      : null;
    return { start, end };
  }, [timelogPreview, timezone]);

  const timelogRangeLabel = useMemo(() => {
    if (!timelogPreview) return null;
    const { start, end } = timelogTimes;
    if (start && end) {
      return t("createNoteModal.timelogHeader.range", { start, end });
    }
    if (start) return start;
    if (end) return end;
    return null;
  }, [timelogPreview, timelogTimes, t]);

  const timelogPrimaryLabel = useMemo(() => {
    if (!timelogPreview) return null;
    const trimmedTitle = timelogPreview.title?.trim();
    if (trimmedTitle) return trimmedTitle;
    if (timelogRangeLabel) return timelogRangeLabel;
    return t("createNoteModal.timelogHeader.fallbackTitle");
  }, [timelogPreview, timelogRangeLabel, t]);

  const habitActionPreview = useMemo<HabitActionPreview | null>(() => {
    if (mode === "edit" && existingNote?.habit_actions?.length) {
      return existingNote.habit_actions[0];
    }
    if (preSelectedHabitAction) {
      return preSelectedHabitAction;
    }
    return null;
  }, [mode, existingNote, preSelectedHabitAction]);

  const habitActionPrimaryLabel = useMemo(() => {
    if (!habitActionPreview) return null;
    const habitLabel =
      habitActionPreview.habit_title?.trim() ||
      t("createNoteModal.habitActionHeader.fallbackTitle");
    return `${habitLabel} · ${formatDate(habitActionPreview.action_date, timezone)} (${habitActionPreview.status})`;
  }, [habitActionPreview, t, timezone]);

  const modalHeader = (
    <div className="flex flex-col gap-2">
      <span className="text-lg font-semibold text-base-content">
        {modalTitle}
      </span>
      {modalDescription ? (
        <p className="text-sm text-base-content/70">{modalDescription}</p>
      ) : null}
      {timelogPrimaryLabel ? (
        <div className="flex items-start gap-2 rounded-xl border border-info/40 bg-info/10 px-3 py-2 text-sm">
          <Icon
            name="timer"
            size={18}
            aria-hidden
            className="mt-0.5 text-info"
          />
          <div className="min-w-0">
            <div className="font-medium text-info">
              {t("createNoteModal.timelogHeader.label")}
            </div>
            <div className="text-base-content/90 font-medium">
              {timelogPrimaryLabel}
            </div>
            {timelogRangeLabel && timelogPrimaryLabel !== timelogRangeLabel ? (
              <div className="text-xs text-base-content/70">
                {timelogRangeLabel}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
      {habitActionPrimaryLabel ? (
        <div className="alert alert-info items-start gap-2 px-3 py-2 text-sm">
          <Icon
            name="repeat"
            size={18}
            aria-hidden
            className="mt-0.5 text-info-content"
          />
          <div className="min-w-0">
            <div className="font-medium text-info-content">
              {t("createNoteModal.habitActionHeader.label")}
            </div>
            <div className="font-medium text-info-content">
              {habitActionPrimaryLabel}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={handleClose}
      header={modalHeader}
      loading={isLoading}
      showLoadingOverlay={false}
      showLoadingSpinner={true}
      loadingSpinnerSize="lg"
      showCloseButton={true}
      size={modalSize}
      footer={
        <div className="w-full lg:w-auto">
          <FormActions
            loading={isLoading}
            onCancel={handleClose}
            onSubmit={() => formRef.current?.requestSubmit()}
            onDelete={
              mode === "edit" && existingNote && onRequestDelete
                ? () => {
                    handleClose();
                    onRequestDelete(existingNote);
                  }
                : undefined
            }
            //disabled={!content.trim()}
            submitText={submitText}
            cancelText={t("common.cancel")}
          />
        </div>
      }
    >
      <form
        ref={formRef}
        onSubmit={handleSubmit}
        className="space-y-6 max-h-[85vh] overflow-auto"
      >
        {/* 笔记内容 */}
        <FormField label={""} htmlFor="note-content" required>
          <TextArea
            id="note-content"
            name="note-content"
            ref={textareaRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("createNoteModal.contentPlaceholder")}
            resize="y"
            className="min-h-48 lg:min-h-64 max-h-[75vh]"
            autoFocus
            required
            rows={8}
          />
        </FormField>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* 人员选择器 */}
          <div>
            <PersonSelector
              selectedPersonIds={selectedPersonIds}
              onSelectionChange={setSelectedPersonIds}
              placeholder={t("common.none")}
              multiple={true}
              disabled={isPersonSelectionLocked}
              idPrefix="create-note-person"
              selectedPlacement="below"
            />
          </div>

          {/* 标签选择器 */}
          <div>
            <TagSelector
              availableTags={availableNoteTags}
              selectedTagIds={selectedTagIds}
              onTagsChange={handleTagsChange}
              onCreateTag={handleCreateTag}
              lockedTagIds={lockedTagIds}
              disabled={false}
              idPrefix="create-note-tag"
              selectedPlacement="below"
            />
          </div>

          {/* 任务选择：支持锁定或自由选择 */}
          <div>
            <TaskSelector
              value={selectedTaskId ?? null}
              onChange={(id) => {
                if (isTaskSelectionLocked) return;
                setSelectedTaskId(id || null);
              }}
              placeholder={
                isTaskSelectionLocked
                  ? t("createNoteModal.relatedTaskLocked")
                  : t("createNoteModal.relatedTaskOptional")
              }
              disabled={isTaskSelectionLocked}
              filterStatus={taskFilterStatus}
              deferRemoteLoad={true}
              overrideOptions={lockedTaskOverrideOptions}
              idPrefix="create-note-task"
            />
          </div>
        </div>
      </form>
    </ModalBase>
  );
}
