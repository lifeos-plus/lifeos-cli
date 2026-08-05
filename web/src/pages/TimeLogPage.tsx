import { useState, useEffect, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type {
  Timelog,
  TimelogWithEnergyResponse,
} from "@/services/api";
import TimeEntryModal from "@/components/TimeEntryModal";
import TimeProgressBar from "@/components/TimeProgressBar";
import AreaManagerModal from "@/components/AreaManagerModal";
import QuickTemplatesManagerModal from "@/components/QuickTemplatesManagerModal";
import ErrorDisplay from "@/components/ErrorDisplay";
import ConfirmDialog from "@/components/ConfirmDialog";
import LoadingSpinner from "@/components/LoadingSpinner";
import { usePageHeader } from "@/contexts/PageHeaderContext";
import PageLayout from "@/layouts/PageLayout";
import ActionButton from "@/components/ActionButton";
import { useTimeLogUIState } from "@/features/timeLog/controller/useTimeLogUIState";
import type { TaskWithSubtasks } from "@/services/api";
import TimeLogToolbar from "@/components/TimeLogToolbar";
import AdvancedSearchPanel from "@/components/AdvancedSearchPanel";
import TimeEntriesTable from "@/components/TimeEntriesTable";
import TaskNotesModal from "@/components/TaskNotesModal";
import CreateNoteModal from "@/components/CreateNoteModal";
import { useToast } from "@/contexts/ToastContext";
import { formatDate, formatDateInTimezone } from "@/utils/datetime";
import { deriveNoteAssociationDefaults } from "@/utils/notes";
import Container from "@/layouts/Container";
import { TextInput } from "@/components/forms";
import type { UUID } from "@/types/primitive";
import type { ProcessedEntry } from "@/utils/datetime";
import { useTimeLogPageData } from "@/features/timeLog/controller/useTimeLogPageData";
import { useTimeLogAdvancedInteractions } from "@/features/timeLog/controller/useTimeLogAdvancedInteractions";
import { useQueryMode } from "@/hooks/useQueryMode";
import TimeLogBulkImportPanel from "@/features/timeLog/bulkImport/TimeLogBulkImportPanel";
import { createModalSessionId } from "@/utils/session";
import { SelectorSpecialValue } from "@/components/selects/selectorTypes";
import { timelogsApi } from "@/services/api/timelogs";
import { timelogsKeys } from "@/services/api/queryKeys";

const TimeLogPage = () => {
  const { t } = useTranslation();
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());

  // Areas are provided via shared cache (areaMap and list)
  const {
    sortOrder,
    setSortOrder,
    selectedAreaId,
    setSelectedAreaId,
    saveScrollPosition,
    scrollPosition,
    clearScrollPosition,
  } = useTimeLogUIState();

  const { queryMode, setQueryMode } = useQueryMode("single");

  const {
    activeTimezone,
    processedEntries,
    loading,
    error,
    selectedEntryIds,
    isSelectMode,
    deletingEntryId,
    deletingEntryCount,
    requestDeleteEntry,
    confirmDeleteEntry,
    cancelDeleteEntry,
    requestBatchDelete,
    confirmBatchDelete,
    cancelBatchDelete,
    setIsSelectMode,
    setAdvancedSearchResultsFromHook,
    selectionHandlers,
    advancedSearchParams,
    setAdvancedSearchParams,
    advancedSearch,
    tasksForAdvancedSearch,
    allFlatTasks,
    areasFromCache,
    areaMap,
  } = useTimeLogPageData({
    selectedDate,
    sortOrder,
    queryMode,
    saveScrollPosition,
  });

  // Modal states
  const [showEntryModal, setShowEntryModal] = useState(false);
  const [editingEntry, setEditingEntry] = useState<Timelog | null>(null);
  const [entryModalSessionId, setEntryModalSessionId] = useState<string | null>(
    null,
  );

  // Scroll position persistence handled by useTimeLogUIState

  // Area manager modal state
  const [showAreaManager, setShowAreaManager] = useState(false);
  const [showQuickTemplatesManager, setShowQuickTemplatesManager] =
    useState(false);

  const [activeTimelogForNotes, setActiveTimelogForNotes] =
    useState<ProcessedEntry | null>(null);
  const [isNotesModalOpen, setIsNotesModalOpen] = useState(false);
  const [isCreateNoteModalOpen, setIsCreateNoteModalOpen] = useState(false);
  const [openNotesAfterCreate, setOpenNotesAfterCreate] = useState(false);

  const activeTimelogNoteDefaults = useMemo(() => {
    if (!activeTimelogForNotes) return null;
    return deriveNoteAssociationDefaults({
      task: activeTimelogForNotes.task,
      people: activeTimelogForNotes.people,
    });
  }, [activeTimelogForNotes]);

  const latestTimelogEndTimeQuery = useQuery({
    queryKey: timelogsKeys.latestEndTime(),
    queryFn: () => timelogsApi.fetchLatestEndTime(),
    staleTime: 30 * 1000,
  });

  const currentEntriesLatestEndTime = useMemo(() => {
    let latestMs = Number.NEGATIVE_INFINITY;
    let latestEnd: string | null = null;

    processedEntries.forEach((entry) => {
      if (entry.isPlaceholder || !entry.end_time) return;
      const endMs = new Date(entry.end_time).getTime();
      if (Number.isNaN(endMs)) return;
      if (endMs > latestMs) {
        latestMs = endMs;
        latestEnd = entry.end_time;
      }
    });

    return latestEnd;
  }, [processedEntries]);

  const latestTimelogEndTime =
    latestTimelogEndTimeQuery.data?.end_time ?? currentEntriesLatestEndTime;

  // Request concurrency guards - removed as it's now handled in the hook

  // Advanced search states
  const { showError, showInfo } = useToast();
  const { setHeader } = usePageHeader();

  useEffect(() => {
    setHeader({
      actions: (
        <div className="flex gap-2">
          <ActionButton
            label={t("timeLog.actions.manageAreas")}
            iconName="settings"
            color="primary"
            variant="solid"
            ariaLabel="Open area manager"
            onClick={() => setShowAreaManager(true)}
          />
        </div>
      ),
    });
    return () => setHeader({ actions: undefined });
  }, [setHeader, t]);

  const openEntryModal = useCallback((entry: Timelog | null) => {
    setEditingEntry(entry);
    setEntryModalSessionId(createModalSessionId());
    setShowEntryModal(true);
  }, []);

  const handleEdit = useCallback(
    (entry: Timelog) => {
      openEntryModal(entry);
    },
    [openEntryModal],
  );

  const handleModalClose = useCallback(
    (context?: { sessionId?: string }) => {
      if (
        entryModalSessionId &&
        context?.sessionId &&
        context.sessionId !== entryModalSessionId
      ) {
        return;
      }

      setShowEntryModal(false);
      setEditingEntry(null);
      setEntryModalSessionId(null);
    },
    [entryModalSessionId],
  );

  const handleEntrySaved = useCallback(
    (
      _result: Timelog | TimelogWithEnergyResponse,
      context: { sessionId: string },
    ) => {
      if (entryModalSessionId && context.sessionId !== entryModalSessionId) {
        return;
      }

      // Save current scroll position before reloading
      saveScrollPosition(window.scrollY);
      setShowEntryModal(false);
      setEditingEntry(null);
      setEntryModalSessionId(null);

      // Data refresh is now handled automatically by TanStack Query
      // when mutations invalidate the cache
    },
    [entryModalSessionId, saveScrollPosition],
  );

  const handleOpenTimelogNotes = useCallback(
    (entry: ProcessedEntry, mode: "view" | "create") => {
      setActiveTimelogForNotes(entry);
      setOpenNotesAfterCreate(false);
      if (mode === "create") {
        setIsCreateNoteModalOpen(true);
        setIsNotesModalOpen(false);
      } else {
        setIsNotesModalOpen(true);
      }
    },
    [],
  );

  const handleCloseTimelogNotes = useCallback(() => {
    setIsNotesModalOpen(false);
    setActiveTimelogForNotes(null);
  }, []);

  const handleCloseCreateNoteModal = useCallback(() => {
    setIsCreateNoteModalOpen(false);
    if (openNotesAfterCreate) {
      setIsNotesModalOpen(true);
      setOpenNotesAfterCreate(false);
    } else {
      setActiveTimelogForNotes(null);
    }
  }, [openNotesAfterCreate]);

  const handleAreaManagerClose = () => {
    setShowAreaManager(false);
    // Areas are served via shared cache; rely on TTL or expose refresh in useAreas if needed
  };

  const {
    switchToAdvancedMode,
    switchToSingleMode,
    resetAdvancedSearch,
    handleAdvancedSearch,
    filteredEntries,
  } = useTimeLogAdvancedInteractions({
    queryMode,
    setQueryMode,
    advancedSearchParams,
    setAdvancedSearchParams,
    advancedSearch,
    areasFromCache,
    sortOrder,
    setAdvancedSearchResultsFromHook,
    showError,
    showInfo,
    t,
    processedEntries,
    selectedAreaId,
    activeTimezone,
  });

  const handleConfirmBatchDelete = useCallback(async () => {
    await confirmBatchDelete();

    if (queryMode === "advanced") {
      handleAdvancedSearch();
    }
  }, [confirmBatchDelete, handleAdvancedSearch, queryMode]);

  const advancedSearchMetadata =
    queryMode === "advanced" ? advancedSearch.metadata : null;

  // areaMap from useAreas

  // name/color lookup handled by AreaBadge via areaMap

  // Derived: filtered entries (memoized)
  // Unified loading flag for table rendering
  const isTableLoading = useMemo(
    () => (queryMode === "advanced" ? advancedSearch.isLoading : loading),
    [queryMode, advancedSearch.isLoading, loading],
  );

  // Handle area filter change
  const handleAreaFilterChange = (
    areaId: UUID | null | undefined,
  ) => {
    // Area filter changes are disabled while advanced search is active.
    if (queryMode === "advanced") return;

    if (areaId === undefined) {
      setSelectedAreaId("");
      return;
    }

    if (areaId === null) {
      setSelectedAreaId(SelectorSpecialValue.None);
      return;
    }

    setSelectedAreaId(areaId);
  };

  // no-op: filteredEntries derived by useMemo

  // Restore scroll position after entries are loaded
  useEffect(() => {
    if (scrollPosition > 0 && !loading) {
      window.scrollTo({ top: scrollPosition, behavior: "auto" });
      clearScrollPosition();
    }
  }, [processedEntries, loading, scrollPosition, clearScrollPosition]);

  return (
    <PageLayout>
      {/* Date selector and toolbar */}

      <div className="w-full">
        <TimeLogToolbar
          queryMode={queryMode}
          selectedDate={selectedDate}
          timezone={activeTimezone}
          onDateChange={setSelectedDate}
          onQueryModeChange={(mode) => {
            if (mode === "advanced") {
              switchToAdvancedMode();
            } else if (mode === "single") {
              switchToSingleMode();
            } else {
              setQueryMode("import");
            }
          }}
        />
      </div>

      {queryMode === "import" ? (
        <TimeLogBulkImportPanel
          selectedDate={selectedDate}
          timezone={activeTimezone}
          latestTimelogEndTime={latestTimelogEndTime}
          areaMap={areaMap}
          preloadedTasks={allFlatTasks as unknown as TaskWithSubtasks[]}
          onCancel={() => switchToSingleMode()}
          onImported={() => {
            switchToSingleMode();
          }}
        />
      ) : (
        <>
          {/* Advanced Search Panel */}
          {queryMode === "advanced" && (
            <div className="w-full">
              <AdvancedSearchPanel
                params={{
                  start_date: new Date(advancedSearchParams.start_date),
                  end_date: new Date(advancedSearchParams.end_date),
                  area_id: advancedSearchParams.area_id,
                  description_keyword: advancedSearchParams.description_keyword,
                  task_id: advancedSearchParams.task_id,
                  with_task: advancedSearchParams.with_task,
                }}
                onParamsChange={(params) => {
                  setAdvancedSearchParams({
                    start_date: params.start_date.toISOString(),
                    end_date: params.end_date.toISOString(),
                    area_id: params.area_id,
                    area_name:
                      params.area_id === null
                        ? t("common.noArea")
                        : params.area_id
                          ? areasFromCache?.find(
                              (d) => d.id === params.area_id,
                            )?.name || null
                          : null,
                    description_keyword: params.description_keyword,
                    task_id: params.task_id,
                    with_task: params.with_task,
                  });
                }}
                onSearch={handleAdvancedSearch}
                onReset={resetAdvancedSearch}
                tasks={tasksForAdvancedSearch}
                isSelectMode={isSelectMode}
                onSelectModeToggle={setIsSelectMode}
                selectedEntryIds={selectedEntryIds}
                onSelectAll={() => selectionHandlers.handleSelectAll()}
                onSelectInverse={() => selectionHandlers.handleSelectInverse()}
                onClearSelection={() =>
                  selectionHandlers.handleClearSelection()
                }
                filteredEntriesCount={
                  queryMode === "advanced"
                    ? advancedSearch.totalCount
                    : processedEntries.filter((entry) => !entry.isPlaceholder)
                        .length
                }
                onBatchEditSuccess={() => {
                  if (queryMode === "advanced") {
                    advancedSearch.refetch();
                    handleAdvancedSearch();
                  }
                  selectionHandlers.handleClearSelection();
                  setIsSelectMode(false);
                }}
                onBatchDelete={requestBatchDelete}
                timezone={activeTimezone}
              />
            </div>
          )}

          {queryMode === "advanced" && advancedSearchMetadata && (
            <div
              className={`alert mb-4 text-sm ${
                advancedSearchMetadata.truncated
                  ? "alert-warning"
                  : "alert-info"
              }`}
            >
              <div className="flex flex-col">
                <div>
                  {t("timeLog.messages.foundRecords", {
                    count: advancedSearchMetadata.total_count ?? 0,
                  })}
                </div>
                {advancedSearchMetadata.truncated && (
                  <div className="mt-1">
                    {t("timeLog.messages.searchTruncatedDescription", {
                      limit: advancedSearchMetadata.limit,
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Pagination for Advanced Search */}
          {queryMode === "advanced" && advancedSearch.data.length > 0 && (
            <Container className="mb-4">
              <div className="w-full flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="text-base">
                    {t("timeLog.pagination.showing", {
                      start:
                        advancedSearch.data.length > 0
                          ? (advancedSearch.currentPage - 1) * 100 + 1
                          : 0,
                      end: Math.min(
                        advancedSearch.currentPage * 100,
                        advancedSearch.totalCount,
                      ),
                      total: advancedSearch.totalCount,
                    })}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <ActionButton
                    label={t("timeLog.pagination.previousPage")}
                    size="sm"
                    variant="ghost"
                    onClick={() => advancedSearch.previousPage()}
                    disabled={!advancedSearch.hasPreviousPage}
                  />
                  <div className="flex items-center gap-2">
                    <span className="text-base">
                      {t("timeLog.pagination.page", {
                        page: advancedSearch.currentPage,
                        totalPages: advancedSearch.totalPages,
                      })}
                    </span>
                    <div className="flex items-center gap-1">
                      <span className="text-base">
                        {t("timeLog.pagination.jumpTo")}
                      </span>
                      <TextInput
                        id="advanced-search-page-jump"
                        name="advanced-search-page-jump"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        value={String(advancedSearch.currentPage)}
                        onChange={(e) => {
                          const raw = e.target.value.trim();
                          if (raw === "") return;
                          const page = parseInt(raw, 10);
                          if (
                            Number.isFinite(page) &&
                            page >= 1 &&
                            page <= advancedSearch.totalPages
                          ) {
                            advancedSearch.goToPage(page);
                          }
                        }}
                        className="input-xs w-16 text-center"
                      />
                      <span className="text-base">
                        {t("timeLog.pagination.pageSuffix")}
                      </span>
                    </div>
                  </div>
                  <ActionButton
                    label={t("timeLog.pagination.nextPage")}
                    size="sm"
                    variant="ghost"
                    onClick={() => advancedSearch.nextPage()}
                    disabled={!advancedSearch.hasNextPage}
                  />
                </div>
              </div>
            </Container>
          )}

          {/* Error Message */}
          <ErrorDisplay error={error} className="mb-4" />

          {isTableLoading && (
            <div className="sr-only">
              <LoadingSpinner message={t("timeLog.messages.loadingTimeLogs")} />
            </div>
          )}

          {/* Time Progress Bar (persistent to avoid layout shift) */}
          <div className="w-full">
            <TimeProgressBar
              entries={processedEntries}
              areas={areasFromCache}
              localDateISO={
                queryMode === "single"
                  ? formatDateInTimezone(selectedDate, activeTimezone)
                  : undefined
              }
              timezone={activeTimezone}
              isLoading={loading}
            />
          </div>

          {/* Entries Table */}
          <div className="w-full">
            {queryMode === "advanced" &&
              advancedSearch.data.length > 0 &&
              !isTableLoading && (
                <div className="w-full px-4 py-3 bg-primary/10 border-b border-primary/20">
                  <div className="w-full flex items-center justify-between">
                    <div className="text-base text-primary">
                      <span className="font-medium">
                        {t("timeLog.searchResults.title")}
                      </span>
                      {t("timeLog.searchResults.from", {
                        startDate: formatDate(
                          advancedSearchParams.start_date,
                          activeTimezone,
                        ),
                      })}
                      {advancedSearchParams.end_date &&
                        advancedSearchParams.end_date !==
                          advancedSearchParams.start_date &&
                        ` ${t("timeLog.searchResults.to", {
                          endDate: formatDate(
                            advancedSearchParams.end_date,
                            activeTimezone,
                          ),
                        })}`}
                      {advancedSearchParams.area_name &&
                        ` | ${t("timeLog.searchResults.area", {
                          area: advancedSearchParams.area_name,
                        })}`}
                      {advancedSearchParams.description_keyword &&
                        ` | ${t("timeLog.searchResults.keyword", {
                          keyword: advancedSearchParams.description_keyword,
                        })}`}
                      {advancedSearchParams.task_id !== undefined &&
                        (advancedSearchParams.task_id === null
                          ? ` | ${t("timeLog.searchResults.task", {
                              task: t("timeLog.searchResults.noTask"),
                            })}`
                          : ` | ${t("timeLog.searchResults.task", {
                              task:
                                allFlatTasks.find(
                                  (t) => t.id === advancedSearchParams.task_id,
                                )?.content ||
                                t("timeLog.searchResults.unknownTask"),
                            })}`)}
                      {advancedSearchParams.with_task &&
                        ` | ${t("timeLog.searchResults.task", {
                          task: t("taskSelector.specialOptions.hasTask"),
                        })}`}
                    </div>
                    <div className="text-base text-primary">
                      {t("timeLog.searchResults.foundRecords", {
                        count: advancedSearch.totalCount,
                      })}
                    </div>
                  </div>
                </div>
              )}

            <TimeEntriesTable
              entries={filteredEntries}
              isLoading={isTableLoading}
              isSelectMode={isSelectMode}
              selectedEntryIds={selectedEntryIds}
              onSelectChange={selectionHandlers.handleSelectEntry}
              onEdit={(entry) => handleEdit(entry as Timelog)}
              onDelete={requestDeleteEntry}
              onPlaceholderClick={(_placeholder) => {
                // Handle placeholder click - the TimeEntriesTable will handle expansion internally
                // This callback can be used for additional logic if needed in the future
              }}
              onEntrySaved={() => {
                // Data refresh is now handled automatically by TanStack Query
                // when mutations invalidate the cache
              }}
              sortOrder={sortOrder}
              onSortChange={setSortOrder}
              selectedDate={selectedDate}
              timezone={activeTimezone}
              queryMode={queryMode}
              areaMap={areaMap}
              preloadedTasks={allFlatTasks as unknown as TaskWithSubtasks[]}
              disableQuickEntry={showEntryModal || queryMode === "advanced"}
              selectedAreaId={
                queryMode === "advanced" ? null : selectedAreaId
              }
              onAreaChange={handleAreaFilterChange}
              onCreateNoteForEntry={(entry) =>
                handleOpenTimelogNotes(entry, "create")
              }
              onViewNotesForEntry={(entry) =>
                handleOpenTimelogNotes(entry, "view")
              }
            />
          </div>
        </>
      )}

      {/* Time Entry Modal */}
      {showEntryModal && entryModalSessionId && (
        <TimeEntryModal
          isOpen={showEntryModal}
          onClose={handleModalClose}
          onSave={handleEntrySaved}
          onRequestDelete={(entry) => requestDeleteEntry(entry.id)}
          entry={editingEntry}
          selectedDate={selectedDate}
          preloadedTasks={(() => {
            return allFlatTasks as unknown as TaskWithSubtasks[];
          })()}
          sessionId={entryModalSessionId}
        />
      )}

      <AreaManagerModal
        isOpen={showAreaManager}
        onClose={handleAreaManagerClose}
      />

      {isNotesModalOpen && activeTimelogForNotes && (
        <TaskNotesModal
          isOpen={isNotesModalOpen}
          onClose={handleCloseTimelogNotes}
          entityType="timelog"
          timelog={activeTimelogForNotes as unknown as Timelog}
          timezone={activeTimezone}
        />
      )}

      {isCreateNoteModalOpen && activeTimelogForNotes && (
        <CreateNoteModal
          isOpen={isCreateNoteModalOpen}
          onClose={handleCloseCreateNoteModal}
          preSelectedTaskId={activeTimelogNoteDefaults?.preSelectedTaskId}
          preSelectedTaskTitle={activeTimelogNoteDefaults?.preSelectedTaskTitle}
          preSelectedTimelogId={activeTimelogForNotes.id as unknown as UUID}
          preSelectedTimelog={{
            id: activeTimelogForNotes.id as unknown as UUID,
            title: activeTimelogForNotes.title,
            start_time: activeTimelogForNotes.start_time,
            end_time: activeTimelogForNotes.end_time,
          }}
          preSelectedPersonIds={activeTimelogNoteDefaults?.preSelectedPersonIds}
          lockTaskSelection={
            activeTimelogNoteDefaults?.lockTaskSelection ?? false
          }
          lockPersonSelection={
            activeTimelogNoteDefaults?.lockPersonSelection ?? false
          }
          onNoteCreated={() => {
            setOpenNotesAfterCreate(true);
          }}
          timezone={activeTimezone}
        />
      )}

      {showQuickTemplatesManager && (
        <QuickTemplatesManagerModal
          isOpen={showQuickTemplatesManager}
          onClose={() => setShowQuickTemplatesManager(false)}
        />
      )}

      {/* Confirmation Dialogs */}
      {deletingEntryId && (
        <ConfirmDialog
          isOpen={!!deletingEntryId}
          title={t("common.delete")}
          message={t("timeLog.messages.deleteConfirmation")}
          confirmText={t("common.delete")}
          onConfirm={confirmDeleteEntry}
          onCancel={cancelDeleteEntry}
        />
      )}
      {deletingEntryCount > 0 && (
        <ConfirmDialog
          isOpen={deletingEntryCount > 0}
          title={t("common.delete")}
          message={t("timeLog.messages.batchDeleteConfirmation", {
            count: deletingEntryCount,
          })}
          confirmText={t("common.delete")}
          onConfirm={handleConfirmBatchDelete}
          onCancel={cancelBatchDelete}
        />
      )}
    </PageLayout>
  );
};

export default TimeLogPage;
