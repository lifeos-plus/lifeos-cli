import { useState, useCallback, useRef, useMemo } from "react";
import { useTranslation } from "react-i18next";
import PersonSelector from "@/components/selects/PersonSelector";
import TagSelector from "@/components/selects/TagSelector";
import TaskSelector from "@/components/selects/TaskSelector";
import ActionButton from "@/components/ActionButton";
import { FormField, TextArea } from "@/components/forms";
import type { Tag } from "@/services/api";
import { ACTIVE_TASK_STATUSES } from "@/utils/constants";
import type { UUID } from "@/types/primitive";
import Surface from "@/layouts/Surface";

interface NoteInputFormProps {
  onCreateNote: (
    content: string,
    personIds: UUID[],
    tagIds: UUID[],
    taskId?: UUID,
  ) => Promise<void>;
  availableNoteTags: Tag[];
  onCreateTag: (tagName: string) => Promise<Tag>;
}

export function NoteInputForm({
  onCreateNote,
  availableNoteTags,
  onCreateTag,
}: NoteInputFormProps) {
  const { t } = useTranslation();
  const [content, setContent] = useState("");
  const [selectedPersonIds, setSelectedPersonIds] = useState<UUID[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<UUID[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<UUID | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Memoize filterStatus to prevent unnecessary re-renders
  const taskFilterStatus = useMemo(() => ACTIVE_TASK_STATUSES, []);

  const handleReset = useCallback(() => {
    setContent("");
    setSelectedPersonIds([]);
    setSelectedTagIds([]);
    setSelectedTaskId(null);
    textareaRef.current?.focus();
  }, []);

  /**
   * Handle form submission
   */
  const handleSubmit = useCallback(async () => {
    if (!content.trim()) return;

    try {
      await onCreateNote(
        content.trim(),
        selectedPersonIds,
        selectedTagIds,
        selectedTaskId !== null ? selectedTaskId : undefined,
      );

      // Clear form after successful creation
      handleReset();
    } catch (error) {
      // Error handling is done by the parent component
      console.error("Failed to create note:", error);
    }
  }, [
    content,
    selectedPersonIds,
    selectedTagIds,
    selectedTaskId,
    onCreateNote,
    handleReset,
  ]);

  /**
   * Handle Enter key press for quick note creation
   */
  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  /**
   * Handle creating new note tag
   */
  const handleCreateNoteTag = useCallback(
    async (tagName: string): Promise<Tag> => {
      return await onCreateTag(tagName);
    },
    [onCreateTag],
  );

  const hasContent = content.trim().length > 0;
  const hasSelections =
    selectedPersonIds.length > 0 ||
    selectedTagIds.length > 0 ||
    selectedTaskId !== null;
  const isResetDisabled = !hasContent && !hasSelections;

  return (
    <Surface
      padding="responsive"
      elevation="moderate"
      className="mb-6 sm:mb-8"
    >
      <div className="space-y-4">
        <FormField
          label={t("createNoteModal.title")}
          htmlFor="new-note-content"
        >
          <TextArea
            id="new-note-content"
            name="new-note-content"
            ref={textareaRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={t("createNoteModal.contentPlaceholder")}
            autoFocus
            rows={4}
          />
        </FormField>

        {/* Person, Tag, and Task Selectors */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {/* Person Selector */}
          <div>
            <PersonSelector
              selectedPersonIds={selectedPersonIds}
              onSelectionChange={setSelectedPersonIds}
              placeholder={t("person.selectPersonPlaceholder")}
              multiple={true}
              idPrefix="new-person"
              selectedPlacement="below"
            />
          </div>

          {/* Tag Selector */}
          <div>
            <TagSelector
              availableTags={availableNoteTags}
              selectedTagIds={selectedTagIds}
              onTagsChange={setSelectedTagIds}
              onCreateTag={handleCreateNoteTag}
              disabled={false}
              idPrefix="new-tag"
              selectedPlacement="below"
            />
          </div>

          {/* Task Selector */}
          <div>
            <TaskSelector
              value={selectedTaskId || null}
              onChange={(id) => setSelectedTaskId(id || null)}
              disabled={false}
              filterStatus={taskFilterStatus}
              idPrefix="new-task"
            />
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-3">
          <ActionButton
            label={t("noteInputForm.resetLabel")}
            iconName="sparkles"
            onClick={handleReset}
            disabled={isResetDisabled}
            color="neutral"
            variant="outline"
            className="w-full sm:w-auto order-2 sm:order-1"
          />
          <ActionButton
            label={t("noteInputForm.submitLabel")}
            iconName="document-plus"
            onClick={handleSubmit}
            disabled={!hasContent}
            color="primary"
            variant="solid"
            className="w-full sm:w-auto order-1 sm:order-2"
          />
        </div>
      </div>
    </Surface>
  );
}
