import { useTranslation } from "react-i18next";

import NoteItem from "./NoteItem";
import EmptyState from "@/components/EmptyState";
import Surface from "@/layouts/Surface";
import ActionButton from "@/components/ActionButton";
import { Icon } from "@/components/icons";
import type { Note } from "@/types/newNotes";
import type { Tag, PersonSummary } from "@/services/api";
import type { UUID } from "@/types/primitive";

interface NotesListProps {
  notes: Note[];
  selectedFilterTag: Tag | null;
  selectedFilterPerson: PersonSummary | null;
  selectedFilterTaskId?: UUID | null;
  hasMore: boolean;
  isLoadingMore: boolean;
  onEdit: (note: Note) => void;
  onDelete: (noteId: UUID) => void;
  onTagClick: (tag: Tag) => void;
  onPersonClick: (person: PersonSummary) => void;
  onTaskClick: (taskId: UUID) => void;
  onLoadMore: () => void;
  isSelectMode?: boolean;
  selectedNoteIds?: Set<UUID>;
  onSelectChange?: (noteId: UUID, checked: boolean) => void;
  minCollapsedLines?: number;
  timezone?: string;
}

export function NotesList({
  notes,
  selectedFilterTag,
  selectedFilterPerson,
  selectedFilterTaskId,
  hasMore,
  isLoadingMore,
  onEdit,
  onDelete,
  onTagClick,
  onPersonClick,
  onTaskClick,
  onLoadMore,
  isSelectMode = false,
  selectedNoteIds,
  onSelectChange,
  minCollapsedLines,
  timezone,
}: NotesListProps) {
  const { t } = useTranslation();

  if (notes.length === 0) {
    return (
      <EmptyState
        icon={<Icon name="tag" size={48} aria-hidden />}
        title={
          selectedFilterTag
            ? t("notes.noNotesWithFilter", { tagName: selectedFilterTag.name })
            : selectedFilterPerson
              ? t("notes.noNotesWithPerson", {
                  personName: selectedFilterPerson.display_name,
                })
              : t("notes.noNotes")
        }
        description={
          selectedFilterTag || selectedFilterPerson
            ? t("notes.noNotesWithFilterDescription")
            : t("notes.noNotesDescription")
        }
      />
    );
  }

  return (
    <div className="space-y-2">
      {notes.map((note) => (
        <Surface
          key={note.id}
          padding="responsive"
          border="subtle"
          elevation="subtle"
          interactive
          className="group"
        >
          <NoteItem
            note={note}
            selectedFilterTag={selectedFilterTag}
            selectedFilterPerson={selectedFilterPerson}
            selectedFilterTaskId={selectedFilterTaskId ?? null}
            onEdit={onEdit}
            onDelete={onDelete}
            onTagClick={onTagClick}
            onPersonClick={onPersonClick}
            onTaskClick={onTaskClick}
            isSelectMode={isSelectMode}
            isSelected={selectedNoteIds ? selectedNoteIds.has(note.id) : false}
            onSelectChange={onSelectChange}
            minCollapsedLines={minCollapsedLines}
            timezone={timezone}
          />
        </Surface>
      ))}

      {hasMore &&
        !selectedFilterTag &&
        !selectedFilterPerson &&
        !selectedFilterTaskId && (
          <div className="mt-6 text-center">
            <ActionButton
              label={isLoadingMore ? t("common.loading") : t("notes.loadMore")}
              onClick={onLoadMore}
              disabled={isLoadingMore}
              color="neutral"
              variant="outline"
              className="w-full sm:w-auto"
            />
          </div>
        )}

      {notes.length > 0 && (
        <div className="mt-8 text-center text-base text-base-content/60">
          {t("notes.totalNotes", { count: notes.length })}
          {selectedFilterTag && (
            <span className="ml-2 text-primary">
              ({t("notes.taggedWith", { tagName: selectedFilterTag.name })})
            </span>
          )}
          {selectedFilterPerson && (
            <span className="ml-2 text-success">
              (
              {t("notes.associatedWith", {
                personName: selectedFilterPerson.display_name,
              })}
              )
            </span>
          )}
        </div>
      )}
    </div>
  );
}
