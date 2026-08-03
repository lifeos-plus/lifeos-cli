import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ActionButton from "@/components/ActionButton";
import { FormField, TextArea } from "@/components/forms";
import PersonSelector from "@/components/selects/PersonSelector";
import TagSelector from "@/components/selects/TagSelector";
import TaskSelector from "@/components/selects/TaskSelector";
import NoteCardLayout from "./NoteCardLayout";
import { Icon } from "@/components/icons";
import type { Tag } from "@/services/api";
import type { UUID } from "@/types/primitive";
import { useToast } from "@/contexts/ToastContext";
import {
  createPreviewNoteId,
  joinBulkNotes,
  splitBulkNoteInput,
} from "@/utils/notes";
import {
  MAX_BULK_NOTES_PER_REQUEST,
  type BulkNoteDraft,
  useBulkNoteImport,
} from "@/features/notes/useBulkNoteImport";
import { ACTIVE_TASK_STATUSES } from "@/utils/constants";
import Surface from "@/layouts/Surface";
import Badge, { type BadgeTone } from "@/components/common/Badge";

type PreviewStatus = "idle" | "pending" | "success" | "error";

interface PreviewNote {
  id: string;
  content: string;
  status: PreviewStatus;
  errorMessage?: string;
}

interface NotesBulkImportPanelProps {
  availableNoteTags: Tag[];
  onCreateTag: (tagName: string) => Promise<Tag>;
  onComplete?: (result: { createdCount: number; failedCount: number }) => void;
}

export function NotesBulkImportPanel({
  availableNoteTags,
  onCreateTag,
  onComplete,
}: NotesBulkImportPanelProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const { submitBulkNotes, isSubmitting } = useBulkNoteImport();

  const [inputValue, setInputValue] = useState("");
  const [selectedPersonIds, setSelectedPersonIds] = useState<UUID[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<UUID[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<UUID | null>(null);
  const [previewNotes, setPreviewNotes] = useState<PreviewNote[]>([]);
  const [isPreviewStale, setIsPreviewStale] = useState(true);
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingDraft, setEditingDraft] = useState("");

  const hasPreview = previewNotes.length > 0;
  const taskFilterStatus = useMemo(() => ACTIVE_TASK_STATUSES, []);

  const previewDrafts: BulkNoteDraft[] = useMemo(
    () => previewNotes.map((note) => ({ id: note.id, content: note.content })),
    [previewNotes],
  );

  const handleInputChange = (value: string) => {
    setInputValue(value);
    setIsPreviewStale(true);
  };

  const handlePreview = useCallback(() => {
    const parsed = splitBulkNoteInput(inputValue);
    if (!parsed.length) {
      toast.showInfo(
        t("notes.bulkImport.previewEmptyTitle"),
        t("notes.bulkImport.previewEmptyDescription"),
      );
      setPreviewNotes([]);
      setIsPreviewStale(true);
      return;
    }

    setPreviewNotes(
      parsed.map((content) => ({
        id: createPreviewNoteId(),
        content,
        status: "idle",
      })),
    );
    setEditingNoteId(null);
    setEditingDraft("");
    setIsPreviewStale(false);
  }, [inputValue, t, toast]);

  const handleEditStart = (noteId: string) => {
    const target = previewNotes.find((note) => note.id === noteId);
    if (!target) return;
    setEditingNoteId(noteId);
    setEditingDraft(target.content);
  };

  const handleEditSave = () => {
    if (!editingNoteId) return;
    const trimmed = editingDraft.trim();
    if (!trimmed) {
      toast.showError(
        t("notes.bulkImport.editEmptyTitle"),
        t("notes.bulkImport.editEmptyDescription"),
      );
      return;
    }
    let nextNotes: PreviewNote[] = [];
    setPreviewNotes((notes) => {
      nextNotes = notes.map((note) =>
        note.id === editingNoteId
          ? {
              ...note,
              content: trimmed,
              status: "idle",
              errorMessage: undefined,
            }
          : note,
      );
      return nextNotes;
    });
    setInputValue(joinBulkNotes(nextNotes.map((note) => note.content)));
    setEditingNoteId(null);
    setEditingDraft("");
  };

  const handleEditCancel = () => {
    setEditingNoteId(null);
    setEditingDraft("");
  };

  const handleRemoveNote = (noteId: string) => {
    let nextNotes: PreviewNote[] = [];
    setPreviewNotes((notes) => {
      nextNotes = notes.filter((note) => note.id !== noteId);
      return nextNotes;
    });
    setInputValue(joinBulkNotes(nextNotes.map((note) => note.content)));
    if (nextNotes.length === 0) {
      setIsPreviewStale(true);
    }
  };

  const handleSubmit = useCallback(async () => {
    if (!previewNotes.length || isPreviewStale) {
      toast.showInfo(
        t("notes.bulkImport.previewRequiredTitle"),
        t("notes.bulkImport.previewRequiredDescription"),
      );
      return;
    }

    setPreviewNotes((notes) =>
      notes.map((note) => ({
        ...note,
        status: "pending",
        errorMessage: undefined,
      })),
    );

    try {
      const result = await submitBulkNotes({
        drafts: previewDrafts,
        personIds: selectedPersonIds,
        tagIds: selectedTagIds,
        taskId: selectedTaskId,
      });

      setPreviewNotes((notes) =>
        notes.map((note) => {
          const statusResult = result.statusById[note.id];
          if (!statusResult) return note;
          return {
            ...note,
            status: statusResult.status,
            errorMessage: statusResult.error,
          };
        }),
      );

      if (result.failedCount === 0) {
        toast.showSuccess(
          t("notes.bulkImport.toast.success", { count: result.createdCount }),
        );
        setInputValue("");
        setPreviewNotes([]);
        setIsPreviewStale(true);
        onComplete?.(result);
      } else {
        toast.showWarning(
          t("notes.bulkImport.toast.partialTitle"),
          t("notes.bulkImport.toast.partialDescription", {
            created: result.createdCount,
            failed: result.failedCount,
          }),
        );
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast.showError(t("notes.bulkImport.toast.error"), message);
    }
  }, [
    previewNotes.length,
    isPreviewStale,
    toast,
    t,
    submitBulkNotes,
    previewDrafts,
    selectedPersonIds,
    selectedTagIds,
    selectedTaskId,
    onComplete,
  ]);

  const statusMeta: Record<
    PreviewStatus,
    { label: string; tone: BadgeTone }
  > = {
    idle: {
      label: t("notes.bulkImport.status.idle"),
      tone: "neutral",
    },
    pending: {
      label: t("notes.bulkImport.status.pending"),
      tone: "info",
    },
    success: {
      label: t("notes.bulkImport.status.success"),
      tone: "success",
    },
    error: {
      label: t("notes.bulkImport.status.error"),
      tone: "error",
    },
  };

  return (
    <Surface padding="responsive" border="none" elevation="moderate" className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold text-base-content">
          {t("notes.bulkImport.sectionTitle")}
        </h2>
        <p className="text-base-content/70">
          {t("notes.bulkImport.sectionDescription")}
        </p>
        <p className="text-sm text-base-content/60">
          {t("notes.bulkImport.limitNotice", {
            limit: MAX_BULK_NOTES_PER_REQUEST,
          })}
        </p>
      </div>

      <div className="space-y-4">
        <FormField
          label={t("notes.bulkImport.inputLabel")}
          htmlFor="bulk-note-input"
          description={t("notes.bulkImport.separatorHint")}
        >
          <TextArea
            id="bulk-note-input"
            rows={8}
            value={inputValue}
            placeholder={t("notes.bulkImport.placeholder")}
            onChange={(event) => handleInputChange(event.target.value)}
          />
        </FormField>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          <PersonSelector
            selectedPersonIds={selectedPersonIds}
            onSelectionChange={setSelectedPersonIds}
            placeholder={t("person.selectPersonPlaceholder")}
            multiple
            idPrefix="bulk-person"
          />
          <TagSelector
            availableTags={availableNoteTags}
            selectedTagIds={selectedTagIds}
            onTagsChange={setSelectedTagIds}
            onCreateTag={onCreateTag}
            disabled={false}
            idPrefix="bulk-tag"
          />
          <TaskSelector
            value={selectedTaskId}
            onChange={(id) => setSelectedTaskId(id || null)}
            disabled={false}
            filterStatus={taskFilterStatus}
            idPrefix="bulk-task"
          />
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="text-sm text-base-content/70">
            {isPreviewStale && hasPreview
              ? t("notes.bulkImport.previewStale")
              : t("notes.bulkImport.instructions")}
          </div>
          <div className="flex flex-wrap gap-2">
            <ActionButton
              label={t("notes.bulkImport.previewButton")}
              iconName="eye"
              color="primary"
              variant="outline"
              onClick={handlePreview}
              disabled={isSubmitting}
            />
            <ActionButton
              label={t("notes.bulkImport.submitButton")}
              iconName="check"
              color="success"
              onClick={handleSubmit}
              disabled={!hasPreview || isPreviewStale || isSubmitting}
            />
          </div>
        </div>
      </div>

      <div>
        {hasPreview ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">
                {t("notes.bulkImport.previewTitle", {
                  count: previewNotes.length,
                })}
              </h3>
              {isSubmitting && (
                <span className="text-sm text-info flex items-center gap-1">
                  <Icon name="refresh" className="animate-spin" />
                  {t("common.submitting")}
                </span>
              )}
            </div>
            {previewNotes.map((note, index) => {
              const status = statusMeta[note.status];
              const isEditing = editingNoteId === note.id;
              return (
                <Surface
                  key={note.id}
                  border="subtle"
                  elevation="subtle"
                  className="flex flex-col gap-3 p-3 lg:p-4"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm text-base-content/70">
                      {t("notes.bulkImport.previewItemLabel", {
                        index: index + 1,
                      })}
                    </div>
                    <Badge tone={status.tone} size="sm">
                      {status.label}
                    </Badge>
                  </div>
                  <NoteCardLayout
                    content={note.content}
                    contentNode={
                      isEditing ? (
                        <TextArea
                          value={editingDraft}
                          onChange={(event) =>
                            setEditingDraft(event.target.value)
                          }
                          rows={4}
                        />
                      ) : undefined
                    }
                    createdAt={new Date().toISOString()}
                    collapsible={false}
                    actions={
                      isEditing ? (
                        <div className="flex gap-2">
                          <ActionButton
                            label={t("notes.bulkImport.saveLabel")}
                            iconName="check"
                            color="success"
                            onClick={handleEditSave}
                          />
                          <ActionButton
                            label={t("notes.bulkImport.cancelLabel")}
                            iconName="x-mark"
                            color="neutral"
                            variant="ghost"
                            onClick={handleEditCancel}
                          />
                        </div>
                      ) : (
                        <div className="flex gap-2">
                          <ActionButton
                            label={t("notes.bulkImport.editLabel")}
                            iconName="edit"
                            color="primary"
                            variant="ghost"
                            onClick={() => handleEditStart(note.id)}
                          />
                          <ActionButton
                            label={t("notes.bulkImport.removeLabel")}
                            iconName="trash"
                            color="error"
                            variant="ghost"
                            onClick={() => handleRemoveNote(note.id)}
                          />
                        </div>
                      )
                    }
                    actionsVisibility="always"
                  />
                  {note.status === "error" && note.errorMessage && (
                    <div className="text-sm text-error/80">
                      {note.errorMessage}
                    </div>
                  )}
                </Surface>
              );
            })}
          </div>
        ) : (
          <div className="text-base-content/60 text-sm">
            {t("notes.bulkImport.previewEmptyDescription")}
          </div>
        )}
      </div>
    </Surface>
  );
}
