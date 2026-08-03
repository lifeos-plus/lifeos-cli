import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ModalBase from "@/layouts/ModalBase";
import CreateNoteModal from "./CreateNoteModal";
import Badge from "@/components/common/Badge";
import type { TaskWithSubtasks } from "@/services/api";
import type { Timelog } from "@/services/api/timelogs";
import type {
  Note,
  NoteHabitActionSummary,
  NoteTimelogSummary,
} from "@/services/api/notes";
import { formatDate, formatTime } from "@/utils/datetime";
import { deriveNoteAssociationDefaults } from "@/utils/notes";
import ActionButton from "./ActionButton";
import type { UUID } from "@/types/primitive";
import NoteCardLayout, {
  type NoteCardAssociation,
} from "./notes/NoteCardLayout";
import { useNoteCollapsePreference } from "@/hooks/notes/useNoteCollapsePreference";
import { Icon } from "./icons";
import { useAssociatedNotesController } from "@/features/notes/controller/useAssociatedNotesController";
import ConfirmDialog from "./ConfirmDialog";
import { notesApi } from "@/services/api/notes";
import { useToast } from "@/contexts/ToastContext";

type SharedProps = {
  isOpen: boolean;
  onClose: () => void;
  defaultCreateOpen?: boolean;
  timezone?: string;
  onNotesChanged?: () => void;
};

type TaskContextProps = SharedProps & {
  entityType?: "task";
  task: TaskWithSubtasks | null;
};

type TimelogContextProps = SharedProps & {
  entityType: "timelog";
  timelog: Timelog | null;
};

type HabitActionContextProps = SharedProps & {
  entityType: "habit_action";
  habitAction: NoteHabitActionSummary | null;
};

type TaskNotesModalProps =
  | TaskContextProps
  | TimelogContextProps
  | HabitActionContextProps;

export default function TaskNotesModal(props: TaskNotesModalProps) {
  const { isOpen, onClose } = props;
  const onNotesChanged = props.onNotesChanged;
  const timezone = props.timezone;
  const entityType = props.entityType ?? "task";
  const defaultCreateOpen = props.defaultCreateOpen ?? false;
  const task = entityType === "task" ? (props as TaskContextProps).task : null;
  const timelog =
    entityType === "timelog"
      ? ((props as TimelogContextProps).timelog ?? null)
      : null;
  const habitAction =
    entityType === "habit_action"
      ? ((props as HabitActionContextProps).habitAction ?? null)
      : null;
  const entityId: UUID | null =
    entityType === "task"
      ? task
        ? task.id
        : null
      : entityType === "timelog"
        ? timelog
          ? timelog.id
          : null
        : habitAction
          ? habitAction.id
          : null;

  const { t } = useTranslation();
  const toast = useToast();
  const noteCollapsePreference = useNoteCollapsePreference();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingNote, setEditingNote] = useState<Note | null>(null);
  const [deletingNote, setDeletingNote] = useState<Note | null>(null);
  const createModalNoteDefaults = useMemo(() => {
    if (entityType === "task" && task) {
      return deriveNoteAssociationDefaults({
        task,
        people: task.people,
      });
    }
    if (entityType === "timelog" && timelog) {
      return deriveNoteAssociationDefaults({
        task: timelog.task,
        people: timelog.people,
      });
    }
    return null;
  }, [entityType, task, timelog]);

  const listFilters = useMemo(() => {
    if (entityType === "task") {
      return { task_id: task?.id } as const;
    }
    if (entityType === "timelog") {
      return { timelog_id: timelog?.id } as const;
    }
    return { habit_action_id: habitAction?.id } as const;
  }, [entityType, habitAction?.id, task?.id, timelog?.id]);

  const { notes, isLoading, error, refetch } = useAssociatedNotesController({
    isOpen,
    enabledId: entityId,
    listFilters,
  });

  useEffect(() => {
    if (!isOpen) {
      setEditingNote(null);
      setDeletingNote(null);
      setShowCreateModal(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && defaultCreateOpen) {
      setShowCreateModal(true);
    }
  }, [isOpen, defaultCreateOpen]);

  const handleEditNote = (note: Note) => {
    setEditingNote(note);
  };

  const handleEditComplete = () => {
    setEditingNote(null);
    refetch();
    onNotesChanged?.();
  };

  const confirmDeleteNote = async () => {
    if (!deletingNote) return;
    try {
      await notesApi.delete(deletingNote.id);
      setDeletingNote(null);
      await refetch();
      onNotesChanged?.();
    } catch (error) {
      toast.showError(
        t("common.operationFailed"),
        error instanceof Error ? error.message : t("common.unknown_error"),
      );
    }
  };

  const formatFirstTimelogLabel = (
    timelog?: NoteTimelogSummary | null,
  ): string | null => {
    if (!timelog) {
      return null;
    }

    if (timelog.title && timelog.title.trim().length > 0) {
      return timelog.title.trim();
    }

    const start = timelog.start_time
      ? formatTime(timelog.start_time, timezone)
      : "";
    const end = timelog.end_time ? formatTime(timelog.end_time, timezone) : "";

    if (start && end) {
      return `${start}-${end}`;
    }
    if (start) {
      return start;
    }
    if (end) {
      return end;
    }

    return t("notes.timelogChipDefault");
  };

  const formatHabitActionLabel = (
    action?: NoteHabitActionSummary | null,
  ): string | null => {
    if (!action) {
      return null;
    }
    const habitLabel =
      action.habit_title?.trim() ||
      t("createNoteModal.habitActionHeader.fallbackTitle");
    return `${habitLabel} · ${formatDate(action.action_date, timezone)} (${action.status})`;
  };

  if (
    (entityType === "task" && !task) ||
    (entityType === "timelog" && !timelog) ||
    (entityType === "habit_action" && !habitAction)
  ) {
    return null;
  }

  const headerTitle =
    entityType === "task"
      ? t("taskNotes.title")
      : entityType === "timelog"
        ? t("timelogNotes.title")
        : t("habitActionNotes.title");

  const emptyStateTitle =
    entityType === "task"
      ? t("taskNotes.emptyState.title")
      : entityType === "timelog"
        ? t("timelogNotes.emptyState.title")
        : t("habitActionNotes.emptyState.title");
  const emptyStateDescription =
    entityType === "task"
      ? t("taskNotes.emptyState.description")
      : entityType === "timelog"
        ? t("timelogNotes.emptyState.description")
        : t("habitActionNotes.emptyState.description");
  const habitActionLabel = formatHabitActionLabel(habitAction);

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={onClose}
      header={headerTitle}
      showCloseButton={true}
      size="xl"
      loading={isLoading}
      error={error?.message}
      onErrorDismiss={() => refetch()}
      showLoadingSpinner={true}
      loadingSpinnerSize="md"
      errorDisplayMode="inline"
    >
      {entityType === "task" && task && (
        <p className="text-base text-base-content mb-4">
          {t("taskNotes.taskLabel")}
          {task.content}
        </p>
      )}
      {entityType === "habit_action" && habitActionLabel && (
        <p className="text-base text-base-content mb-4">
          {t("habitActionNotes.actionLabel")}
          {habitActionLabel}
        </p>
      )}

      <div className="flex justify-center items-center gap-4 mb-8">
        <ActionButton
          label={t("createNoteModal.submitText")}
          onClick={() => setShowCreateModal(true)}
          color="primary"
          variant="solid"
          iconName="plus"
          disabled={!entityId}
        />
        {notes.length > 0 && (
          <Badge tone="primary" variant="outline">
            {t("filterStatus.notesCount", { count: notes.length })}
          </Badge>
        )}
      </div>

      {!isLoading && !error && notes.length === 0 && (
        <div className="flex items-center justify-center py-16">
          <div className="text-center max-w-md">
            <Icon
              name="document-text"
              size={48}
              className="mb-6 opacity-60"
              aria-hidden
            />
            <h3 className="text-lg font-semibold text-base-content mb-3">
              {emptyStateTitle}
            </h3>
            <p className="text-base-content/80 mb-6 leading-relaxed">
              {emptyStateDescription}
            </p>
          </div>
        </div>
      )}

      {!isLoading && !error && notes.length > 0 && (
        <div className="space-y-4">
          {notes.map((note) => {
            const associations: NoteCardAssociation[] = [];

            if (note.people && note.people.length > 0) {
              associations.push(
                ...note.people.map((person) => ({
                  id: `person-${person.id}`,
                  type: "person" as const,
                  label: `@${person.display_name ?? person.name}`,
                  icon: (
                    <Icon
                      name="people"
                      size={16}
                      className="text-success"
                      aria-hidden
                    />
                  ),
                  title: person.display_name
                    ? t("notesSidebar.filterPerson", {
                        name: person.display_name,
                      })
                    : undefined,
                  disabled: true,
                })),
              );
            }

            if (note.tags && note.tags.length > 0) {
              associations.push(
                ...note.tags.map((tag) => ({
                  id: `tag-${tag.id}`,
                  type: "tag" as const,
                  label: `#${tag.name}`,
                  icon: (
                    <Icon
                      name="tag"
                      size={16}
                      className="text-primary"
                      aria-hidden
                    />
                  ),
                  title: undefined,
                  disabled: true,
                })),
              );
            }

            if (note.task) {
              associations.push({
                id: `task-${note.task.id}`,
                type: "task",
                label: `${note.task.content} (${note.task.status})`,
                icon: (
                  <Icon
                    name="clipboard"
                    size={16}
                    className="text-secondary"
                    aria-hidden
                  />
                ),
                title: undefined,
                disabled: true,
              });
            }

            const firstTimelog = note.timelogs?.[0] ?? null;
            const timelogLabel = formatFirstTimelogLabel(firstTimelog);
            if (timelogLabel) {
              associations.push({
                id: `timelog-${firstTimelog?.id ?? `${note.id}-timelog`}`,
                type: "timelog",
                label: timelogLabel,
                icon: (
                  <Icon
                    name="timer"
                    size={16}
                    className="text-info"
                    aria-hidden
                  />
                ),
                title: t("notes.timelogChipTooltip", { label: timelogLabel }),
                disabled: true,
              });
            }

            const firstHabitAction = note.habit_actions?.[0] ?? null;
            const habitActionNoteLabel = formatHabitActionLabel(firstHabitAction);
            if (habitActionNoteLabel) {
              associations.push({
                id: `habit-action-${firstHabitAction?.id ?? `${note.id}-habit-action`}`,
                type: "habit_action",
                label: habitActionNoteLabel,
                icon: (
                  <Icon
                    name="repeat"
                    size={16}
                    className="text-accent"
                    aria-hidden
                  />
                ),
                title: habitActionNoteLabel,
                disabled: true,
              });
            }

            const actions = (
              <ActionButton
                label={t("common.edit")}
                iconName="edit"
                iconOnly
                color="primary"
                onClick={() => handleEditNote(note)}
                ariaLabel={t("common.edit")}
              />
            );

            return (
              <div
                key={note.id}
                className="bg-base-100 rounded-lg shadow-sm border border-base-200 p-3 lg:p-4 hover:shadow-md transition-shadow"
              >
                <NoteCardLayout
                  content={note.content}
                  associations={associations}
                  createdAt={note.created_at}
                  actions={actions}
                  actionsVisibility="hover"
                  minCollapsedLines={noteCollapsePreference.value}
                />
              </div>
            );
          })}
        </div>
      )}

      {showCreateModal && (
        <CreateNoteModal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          preSelectedTaskId={
            createModalNoteDefaults?.preSelectedTaskId ??
            (entityType === "task" ? task?.id : undefined)
          }
          preSelectedTaskTitle={
            createModalNoteDefaults?.preSelectedTaskTitle ??
            (entityType === "task" ? task?.content : undefined)
          }
          preSelectedTimelogId={
            entityType === "timelog" ? timelog?.id : undefined
          }
          preSelectedTimelog={
            entityType === "timelog" && timelog
              ? {
                  id: timelog.id,
                  title: timelog.title,
                  start_time: timelog.start_time,
                  end_time: timelog.end_time,
                }
              : undefined
          }
          preSelectedHabitActionId={
            entityType === "habit_action" ? habitAction?.id : undefined
          }
          preSelectedHabitAction={
            entityType === "habit_action" && habitAction
              ? habitAction
              : undefined
          }
          preSelectedPersonIds={createModalNoteDefaults?.preSelectedPersonIds}
          lockTaskSelection={
            createModalNoteDefaults?.lockTaskSelection ??
            (entityType === "task" ? true : false)
          }
          lockPersonSelection={
            createModalNoteDefaults?.lockPersonSelection ?? false
          }
          onNoteCreated={() => {
            refetch();
            onNotesChanged?.();
          }}
          timezone={timezone}
        />
      )}

      {editingNote && (
        <CreateNoteModal
          isOpen={!!editingNote}
          onClose={() => setEditingNote(null)}
          mode="edit"
          existingNote={editingNote}
          onNoteCreated={handleEditComplete}
          onRequestDelete={(note) => setDeletingNote(note)}
          timezone={timezone}
        />
      )}

      {deletingNote && (
        <ConfirmDialog
          isOpen={!!deletingNote}
          title={t("common.delete")}
          message={`${t("common.confirm")}${t("common.delete")}: ${deletingNote.content}`}
          confirmText={t("common.delete")}
          onConfirm={confirmDeleteNote}
          onCancel={() => setDeletingNote(null)}
        />
      )}
    </ModalBase>
  );
}
