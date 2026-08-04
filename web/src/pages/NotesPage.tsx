import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { usePageHeader } from "@/contexts/PageHeaderContext";
import PageLayout from "@/layouts/PageLayout";
import type { Person, PersonSummary, Tag } from "@/services/api";
import PersonDetailModal from "@/components/PersonDetailModal";
import PersonFormModal from "@/components/PersonFormModal";
import ErrorDisplay from "@/components/ErrorDisplay";
import LoadingSpinner from "@/components/LoadingSpinner";
import ActionButton from "@/components/ActionButton";
import { personsApi } from "@/services/api/persons";
import { useTagSelectorSource } from "@/hooks/selectors/useTagSelectorSource";
import TagManager from "@/components/TagManagerModal";

import { useToast } from "@/contexts/ToastContext";
// Inline editing is replaced by CreateNoteModal

// Note components
import { NoteInputForm } from "@/components/notes/NoteInputForm";
import { NotesList } from "@/components/notes/NotesList";
import { NotesSidebar } from "@/components/notes/NotesSidebar";
import { FilterStatus } from "@/components/notes/FilterStatus";
import NotesAdvancedSearchPanel, {
  type NotesAdvancedSearchFormState,
} from "@/components/notes/NotesAdvancedSearchPanel";
import NotesBatchEditModal from "@/components/notes/NotesBatchEditModal";
import ConfirmDialog from "@/components/ConfirmDialog";
import type { UUID } from "@/types/primitive";
import CreateNoteModal from "@/components/CreateNoteModal";
import { type Note as ApiNote } from "@/services/api/notes";
import { createDateBoundaries } from "@/utils/datetime";
import {
  useNotesPageData,
  NOTES_ADVANCED_PAGE_SIZE,
} from "@/features/notes/controller/useNotesPageData";
import { useNotesAdvancedSelection } from "@/features/notes/controller/useNotesAdvancedSelection";
import { useQueryMode } from "@/hooks/useQueryMode";
import { arraysEqual } from "@/utils/core";
import { NotesBulkImportPanel } from "@/components/notes/NotesBulkImportPanel";
import { NotesModeBanner } from "@/components/notes/NotesModeBanner";

/**
 * NotesPage component for LifeOS Web UI.
 *
 * This component implements the Quick Notes feature with:
 * - Instant response for note creation
 * - Background synchronization with backend
 * - Clean, minimalist interface focused on speed
 * - Tag support for better organization
 * - REFACTORED: Uses custom hooks for better separation of concerns
 */
function NotesPage() {
  const { t } = useTranslation();

  const { showSuccess, showError, showInfo } = useToast();
  const { queryMode, setQueryMode } = useQueryMode("single");

  const {
    notes,
    isLoading,
    error,
    hasMore,
    isLoadingMore,
    isLoadingStats,
    createNote,
    deleteNote,
    loadMoreNotes,
    activeTimezone,
    noteCollapsePreference,
    noteFilters,
    tasksForAdvancedSearch,
    notesAdvancedSearch,
    notesAdvancedSearchRef,
    advancedSearchParams,
    setAdvancedSearchParams,
    advancedFormState,
    advancedNotes,
    canCopyAdvancedResults,
  } = useNotesPageData({ queryMode });
  const [showBatchEditModal, setShowBatchEditModal] = useState(false);
  const {
    isSelectMode,
    toggleSelectMode,
    selectedNoteIds,
    handleSelectNote,
    handleSelectAll,
    handleSelectInverse,
    clearSelection,
    loadAdvancedSearchResults,
    handleAdvancedReset,
    isBatchDeleteConfirmOpen,
    openBatchDeleteConfirm,
    closeBatchDeleteConfirm,
    handleBatchDeleteConfirm,
    handleBatchEditSuccess,
  } = useNotesAdvancedSelection({
    queryMode,
    notesAdvancedSearch,
    notesAdvancedSearchRef,
    advancedSearchParams,
    setAdvancedSearchParams,
    advancedNotes,
    showSuccess,
    showError,
    showInfo,
    t,
  });
  const {
    filteredNotes: displayNotes,
    selectedFilterTag,
    selectedFilterPerson,
    selectedFilterTaskId,
    selectedFilterTags,
    selectedFilterPersons,
    searchKeyword,
    isSearchApplied,
    showUntaggedOnly,
    tagUsageStats,
    personUsageStats,
    uniquePersons,
    handleTagClick,
    handlePersonClick,
    handleTaskClick,
    handleUntaggedToggle,
    applyTextSearch,
    clearAllFilters,
    setSearchKeyword,
  } = noteFilters;

  // Create person lookup map for efficient access
  const handleAdvancedParamsChange = useCallback(
    (next: NotesAdvancedSearchFormState) => {
      let nextStartIso: string | null = null;
      if (next.start_date) {
        const { startOfDay } = createDateBoundaries(
          next.start_date,
          activeTimezone,
        );
        nextStartIso = startOfDay.toISOString();
      }

      let nextEndIso: string | null = null;
      if (next.end_date) {
        const { endOfDay } = createDateBoundaries(
          next.end_date,
          activeTimezone,
        );
        nextEndIso = endOfDay.toISOString();
      }

      const nextTagIds = next.tag_mode === "none" ? [] : next.tag_ids;
      const nextPersonIds = next.person_mode === "none" ? [] : next.person_ids;
      const nextKeyword = next.keyword ? next.keyword.trim() || null : null;
      const nextTaskId =
        next.task_filter === "specific" ? (next.task_id ?? null) : null;

      setAdvancedSearchParams((prev) => {
        if (
          prev.start_date === nextStartIso &&
          prev.end_date === nextEndIso &&
          prev.tag_mode === next.tag_mode &&
          arraysEqual(prev.tag_ids, nextTagIds) &&
          prev.person_mode === next.person_mode &&
          arraysEqual(prev.person_ids, nextPersonIds) &&
          prev.task_filter === next.task_filter &&
          prev.task_id === nextTaskId &&
          prev.keyword === nextKeyword &&
          prev.sort_order === next.sort_order
        ) {
          return prev;
        }

        return {
          ...prev,
          start_date: nextStartIso,
          end_date: nextEndIso,
          tag_mode: next.tag_mode,
          tag_ids: nextTagIds,
          person_mode: next.person_mode,
          person_ids: nextPersonIds,
          task_filter: next.task_filter,
          task_id: nextTaskId,
          keyword: nextKeyword,
          sort_order: next.sort_order,
        };
      });
    },
    [activeTimezone, setAdvancedSearchParams],
  );

  const isAdvancedMode = queryMode === "advanced";
  const isImportMode = queryMode === "import";
  const isStandardMode = queryMode === "single";
  const notesToDisplay = isAdvancedMode ? advancedNotes : displayNotes;

  const mainColumnClass = isAdvancedMode
    ? "flex-1 min-w-0"
    : isImportMode
      ? "flex-1 min-w-0"
      : "flex-1 min-w-0 lg:basis-[80%]";
  const layoutClass =
    isAdvancedMode || isImportMode
      ? "flex flex-col gap-6"
      : "flex flex-col lg:flex-row gap-6";

  const advancedLoading = notesAdvancedSearch.isLoading;
  const advancedErrorMessage = notesAdvancedSearch.isError
    ? (notesAdvancedSearch.error?.message ??
      t("notes.messages.searchFailedTitle"))
    : null;

  const advancedTotalCount = notesAdvancedSearch.totalCount;
  const advancedRangeStart =
    advancedTotalCount === 0
      ? 0
      : (notesAdvancedSearch.currentPage - 1) * NOTES_ADVANCED_PAGE_SIZE + 1;
  const advancedRangeEnd =
    advancedTotalCount === 0
      ? 0
      : Math.min(
          notesAdvancedSearch.currentPage * NOTES_ADVANCED_PAGE_SIZE,
          advancedTotalCount,
        );

  // Edit via CreateNoteModal state (replaces inline editing)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [modalEditingNote, setModalEditingNote] = useState<ApiNote | null>(
    null,
  );

  const mapDbNoteToApiNote = useCallback(
    (n: {
      id?: UUID;
      content: string;
      createdAt: Date;
      people?: PersonSummary[];
      tags?: Tag[];
      task?: ApiNote["task"];
      timelogs?: ApiNote["timelogs"];
      habit_actions?: ApiNote["habit_actions"];
    }): ApiNote | null => {
      if (!n.id) return null;
      return {
        id: n.id,
        content: n.content,
        created_at: n.createdAt.toISOString(),
        updated_at: n.createdAt.toISOString(),
        people: n.people,
        tags: n.tags,
        task: n.task,
        timelogs: n.timelogs,
        habit_actions: n.habit_actions,
      };
    },
    [],
  );

  const openEditModal = useCallback(
    (note: {
      id?: UUID;
      content: string;
      createdAt: Date;
      people?: PersonSummary[];
      tags?: Tag[];
      task?: ApiNote["task"];
      timelogs?: ApiNote["timelogs"];
      habit_actions?: ApiNote["habit_actions"];
    }) => {
      const mapped = mapDbNoteToApiNote(note);
      if (!mapped) return;
      setModalEditingNote(mapped);
      setIsEditModalOpen(true);
    },
    [mapDbNoteToApiNote],
  );

  const closeEditModal = useCallback(() => {
    setIsEditModalOpen(false);
    setModalEditingNote(null);
  }, []);

  // Note deletion state
  const [deletingNoteId, setDeletingNoteId] = useState<UUID | null>(null);

  // Person detail modal state
  const [selectedPersonForDetail, setSelectedPersonForDetail] =
    useState<PersonSummary | null>(null);

  // Person form modal state
  const [showPersonFormModal, setShowPersonFormModal] =
    useState<boolean>(false);
  const [editingPerson, setEditingPerson] = useState<Person | null>(null);
  const [deletingPerson, setDeletingPerson] = useState<Person | null>(null);
  const {
    tags: availableNoteTags,
    refresh: refreshNoteTags,
    createTag: createNoteTag,
  } = useTagSelectorSource({ entityType: "note" });

  // Tag management modal state
  const [showTagManager, setShowTagManager] = useState(false);
  // Page header via context
  const { setHeader } = usePageHeader();

  useEffect(() => {
    setHeader({
      actions: (
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4">
          <ActionButton
            label={t("notes.noteTagManager")}
            iconName="tag"
            color="primary"
            variant="solid"
            onClick={() => setShowTagManager(true)}
          />
        </div>
      ),
    });
    return () => setHeader({ actions: undefined });
  }, [setHeader, t]);

  /**
   * Load person tags for the form modal
   */
  // Person tags via shared cache
  // Note tags 现在通过 useTagSelectorSource 自动加载，无需手动加载

  /**
   * Handle note deletion with confirmation
   */
  const handleDeleteNote = useCallback(async (noteId: UUID) => {
    setDeletingNoteId(noteId);
  }, []);

  const confirmDeleteNote = useCallback(async () => {
    if (!deletingNoteId) return;
    try {
      await deleteNote(deletingNoteId);
    } catch (error) {
      // Error handling is done by the useNotes hook
      console.error("Failed to delete note:", error);
    } finally {
      setDeletingNoteId(null);
    }
  }, [deletingNoteId, deleteNote]);

  /**
   * Handle person edit from detail modal
   */
  const handlePersonEdit = useCallback(
    async (person: PersonSummary | Person) => {
      try {
        // Fetch full person details for editing
        const fullPerson = await personsApi.getById(person.id);
        setEditingPerson(fullPerson);
        setShowPersonFormModal(true);
      } catch (err) {
        console.error("Failed to load person for editing:", err);
        // You might want to show an error toast here
      }
    },
    [],
  );

  /**
   * Handle person form modal success
   */
  const handlePersonFormSuccess = useCallback(() => {
    setShowPersonFormModal(false);
    setEditingPerson(null);
    // Refresh notes to update any person information that might have changed
    // This could be optimized by only refreshing if necessary
  }, []);

  const handleRequestDeletePerson = useCallback((person: Person) => {
    setShowPersonFormModal(false);
    setEditingPerson(null);
    setDeletingPerson(person);
  }, []);

  const confirmDeletePerson = useCallback(async () => {
    if (!deletingPerson) return;
    try {
      await personsApi.delete(deletingPerson.id);
      setSelectedPersonForDetail(null);
      showSuccess(t("common.delete"), deletingPerson.display_name);
    } catch (error) {
      showError(
        t("common.operationFailed"),
        error instanceof Error ? error.message : t("common.unknown_error"),
      );
    } finally {
      setDeletingPerson(null);
    }
  }, [deletingPerson, showError, showSuccess, t]);

  /**
   * Handle creating new note tag
   */
  const handleCreateNoteTag = useCallback(
    async (tagName: string): Promise<Tag> => {
      try {
        const newTag = await createNoteTag(tagName);
        await refreshNoteTags();
        return newTag;
      } catch (error) {
        throw new Error(t("notes.messages.createTagFailed", { error }));
      }
    },
    [createNoteTag, refreshNoteTags, t],
  );

  /**
   * Handle tag management modal
   */

  // const handleOpenPersonsPage = useCallback(() => {
  //   window.open("/people", "_blank");
  // }, []);

  const handleClosePersonDetail = useCallback(() => {
    setSelectedPersonForDetail(null);
  }, []);

  const handleClosePersonForm = useCallback(() => {
    setShowPersonFormModal(false);
  }, []);

  const handleCloseTagManager = useCallback(() => {
    setShowTagManager(false);
  }, []);

  // 不再整页切换 Loading，保持页面结构不变，列表区用 isLoading/isLoadingMore 展示局部加载

  return (
    <PageLayout>
      {isStandardMode && (
        <div className="flex justify-end mb-4">
          <div className="flex gap-2 flex-wrap">
            <ActionButton
              label={t("notes.queryMode.import")}
              color="neutral"
              variant="outline"
              onClick={() => setQueryMode("import")}
            />
            <ActionButton
              label={t("notes.queryMode.advanced")}
              color="neutral"
              variant="outline"
              onClick={() => setQueryMode("advanced")}
            />
          </div>
        </div>
      )}

      {isImportMode && (
        <NotesModeBanner
          iconName="document-plus"
          title={t("notes.bulkImport.banner.message")}
          description={t("notes.bulkImport.banner.hint")}
          exitLabel={t("notes.bulkImport.exit")}
          onExit={() => setQueryMode("single")}
        />
      )}

      {isAdvancedMode && (
        <NotesModeBanner
          iconName="search"
          title={t("notes.advancedSearch.banner.message")}
          description={t("notes.advancedSearch.banner.hint")}
          exitLabel={t("notes.advancedSearch.exit")}
          onExit={() => setQueryMode("single")}
        />
      )}

      {isAdvancedMode && (
        <div className="mb-6">
          <NotesAdvancedSearchPanel
            params={advancedFormState}
            onParamsChange={handleAdvancedParamsChange}
            onSearch={loadAdvancedSearchResults}
            onReset={handleAdvancedReset}
            availableTags={availableNoteTags}
            onCreateTag={handleCreateNoteTag}
            availableTasks={tasksForAdvancedSearch}
            isSelectMode={isSelectMode}
            onSelectModeToggle={toggleSelectMode}
            selectedNoteIds={selectedNoteIds}
            onSelectAll={handleSelectAll}
            onSelectInverse={handleSelectInverse}
            onClearSelection={clearSelection}
            onOpenBatchEdit={() => setShowBatchEditModal(true)}
            onBatchDelete={openBatchDeleteConfirm}
            totalResults={advancedTotalCount}
            timezone={activeTimezone}
            isLoading={advancedLoading}
            canCopyResults={canCopyAdvancedResults}
          />
        </div>
      )}

      {isStandardMode && (
        <FilterStatus
          selectedFilterTags={selectedFilterTags}
          selectedFilterPersons={selectedFilterPersons}
          searchKeyword={searchKeyword}
          isSearchApplied={isSearchApplied}
          filteredNotesCount={displayNotes.length}
          onClearFilters={clearAllFilters}
        />
      )}

      <div className={layoutClass}>
        <div className={mainColumnClass}>
          {isImportMode ? (
            <NotesBulkImportPanel
              availableNoteTags={availableNoteTags}
              onCreateTag={handleCreateNoteTag}
            />
          ) : (
            <>
              {isStandardMode && (
                <NoteInputForm
                  onCreateNote={async (content, personIds, tagIds, taskId) => {
                    createNote({
                      content,
                      person_ids: personIds,
                      tag_ids: tagIds,
                      task_id: taskId,
                    });
                  }}
                  availableNoteTags={availableNoteTags}
                  onCreateTag={handleCreateNoteTag}
                />
              )}

              {isAdvancedMode ? (
                advancedErrorMessage ? (
                  <ErrorDisplay error={advancedErrorMessage} className="mb-4" />
                ) : null
              ) : (
                <ErrorDisplay error={error?.message || null} className="mb-4" />
              )}

              {isAdvancedMode
                ? advancedLoading && (
                    <div className="mb-4">
                      <LoadingSpinner message={t("notes.loadingAdvanced")} />
                    </div>
                  )
                : isLoading &&
                  notes.length === 0 && (
                    <div className="mb-4">
                      <LoadingSpinner message={t("notes.loadingNotes")} />
                    </div>
                  )}

              <NotesList
                notes={notesToDisplay}
                selectedFilterTag={isAdvancedMode ? null : selectedFilterTag}
                selectedFilterPerson={
                  isAdvancedMode ? null : selectedFilterPerson
                }
                selectedFilterTaskId={
                  isAdvancedMode ? null : selectedFilterTaskId
                }
                hasMore={isAdvancedMode ? false : hasMore}
                isLoadingMore={isAdvancedMode ? false : isLoadingMore}
                onEdit={openEditModal}
                onDelete={handleDeleteNote}
                onTagClick={handleTagClick}
                onPersonClick={handlePersonClick}
                onTaskClick={handleTaskClick}
                onLoadMore={isAdvancedMode ? () => {} : loadMoreNotes}
                isSelectMode={isAdvancedMode ? isSelectMode : false}
                selectedNoteIds={isAdvancedMode ? selectedNoteIds : undefined}
                onSelectChange={isAdvancedMode ? handleSelectNote : undefined}
                minCollapsedLines={noteCollapsePreference.value}
                timezone={activeTimezone}
              />

              {isAdvancedMode && advancedTotalCount > 0 && (
                <div className="mt-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div className="text-base text-base-content/70">
                    {t("notes.advancedSearch.paginationSummary", {
                      start: advancedRangeStart,
                      end: advancedRangeEnd,
                      total: advancedTotalCount,
                    })}
                  </div>
                  <div className="flex items-center gap-2">
                    <ActionButton
                      label={t("notes.advancedSearch.previousPage")}
                      iconName="chevron-left"
                      onClick={notesAdvancedSearch.previousPage}
                      color="neutral"
                      variant="outline"
                      disabled={
                        !notesAdvancedSearch.hasPreviousPage || advancedLoading
                      }
                    />
                    <span className="text-base text-base-content/80">
                      {t("notes.advancedSearch.pageIndicator", {
                        page: notesAdvancedSearch.currentPage,
                        total: notesAdvancedSearch.totalPages,
                      })}
                    </span>
                    <ActionButton
                      label={t("notes.advancedSearch.nextPage")}
                      iconName="chevron-right"
                      onClick={notesAdvancedSearch.nextPage}
                      color="neutral"
                      variant="outline"
                      disabled={
                        !notesAdvancedSearch.hasNextPage || advancedLoading
                      }
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {!isAdvancedMode && !isImportMode && (
          <div className="lg:basis-[20%] min-w-0 max-w-full">
            <NotesSidebar
              uniquePersons={uniquePersons}
              availableNoteTags={availableNoteTags}
              tagUsageStats={tagUsageStats}
              personUsageStats={personUsageStats}
              selectedFilterTags={selectedFilterTags}
              selectedFilterPersons={selectedFilterPersons}
              searchKeyword={searchKeyword}
              showUntaggedOnly={showUntaggedOnly}
              onTagToggle={handleTagClick}
              onPersonToggle={handlePersonClick}
              onSearchKeywordChange={setSearchKeyword}
              onApplyFilters={applyTextSearch}
              onUntaggedToggle={handleUntaggedToggle}
              isLoadingStats={isLoadingStats}
            />
          </div>
        )}
      </div>

      <PersonDetailModal
        person={selectedPersonForDetail}
        isOpen={!!selectedPersonForDetail}
        onClose={handleClosePersonDetail}
        onEdit={handlePersonEdit}
      />

      <PersonFormModal
        isOpen={showPersonFormModal}
        onClose={handleClosePersonForm}
        onSuccess={handlePersonFormSuccess}
        editingPerson={editingPerson}
        onRequestDelete={handleRequestDeletePerson}
      />

      {deletingPerson && (
        <ConfirmDialog
          isOpen={!!deletingPerson}
          title={t("common.delete")}
          message={t("personManager.deleteConfirmMessage", {
            name: deletingPerson.display_name,
          })}
          confirmText={t("common.delete")}
          onConfirm={confirmDeletePerson}
          onCancel={() => setDeletingPerson(null)}
        />
      )}

      <TagManager
        isOpen={showTagManager}
        onClose={handleCloseTagManager}
        title={t("notes.noteTagManager")}
        entityTypeScope="note"
        onTagCreated={async () => {
          await refreshNoteTags();
        }}
        onTagUpdated={async () => {
          await refreshNoteTags();
        }}
      />

      <NotesBatchEditModal
        isOpen={showBatchEditModal}
        onClose={() => setShowBatchEditModal(false)}
        selectedNoteIds={selectedNoteIds}
        onSuccess={handleBatchEditSuccess}
        availableTags={availableNoteTags}
        onCreateTag={handleCreateNoteTag}
        availableTasks={tasksForAdvancedSearch}
      />

      {isBatchDeleteConfirmOpen && (
        <ConfirmDialog
          isOpen={isBatchDeleteConfirmOpen}
          title={t("notes.batchDelete.confirmTitle")}
          message={t("notes.batchDelete.confirmMessage", {
            count: selectedNoteIds.size,
          })}
          confirmText={t("notes.batchDelete.confirmButton")}
          onConfirm={handleBatchDeleteConfirm}
          onCancel={closeBatchDeleteConfirm}
        />
      )}

      {deletingNoteId && (
        <ConfirmDialog
          isOpen={!!deletingNoteId}
          title={t("common.delete")}
          message={(() => {
            const note =
              notesToDisplay.find((n) => n.id === deletingNoteId) ||
              notes.find((n) => n.id === deletingNoteId);
            return note
              ? `${t("common.confirm")}${t("common.delete")}: ${note.content}`
              : t("common.confirm");
          })()}
          confirmText={t("common.delete")}
          onConfirm={confirmDeleteNote}
          onCancel={() => setDeletingNoteId(null)}
        />
      )}

      <CreateNoteModal
        isOpen={isEditModalOpen}
        onClose={closeEditModal}
        mode={"edit"}
        existingNote={modalEditingNote ?? undefined}
        onRequestDelete={(note) => handleDeleteNote(note.id)}
      />
    </PageLayout>
  );
}

export default NotesPage;
