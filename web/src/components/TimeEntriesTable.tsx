import React, { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import type { ProcessedEntry, PlaceholderEntry } from "@/utils/datetime";
import EntryRow from "./EntryRow";
import InlineQuickTimeEntry from "./InlineQuickTimeEntry";
import EmptyState from "./EmptyState";
import ActionButton from "./ActionButton";
import AreaSelect from "./selects/AreaSelect";
import Checkbox from "./forms/Checkbox";
import type {
  TaskWithSubtasks,
  Timelog,
  TimelogWithEnergyResponse,
} from "@/services/api";
import { formatTime } from "@/utils/datetime";
import Container from "@/layouts/Container";
import type { UUID } from "@/types/primitive";
import type { QueryMode } from "@/hooks/useQueryMode";
import HoverTooltipOverlay, {
  type HoverTooltipOverlayPosition,
} from "./HoverTooltipOverlay";
import { TimelogTooltipContent } from "./tooltips";
import { useHoverTooltip } from "@/hooks/useHoverTooltip";
import { Icon } from "./icons";
import { createModalSessionId } from "@/utils/session";
import { SelectorSpecialValue } from "./selects/selectorTypes";

interface TimeEntriesTableProps {
  entries: ProcessedEntry[];
  isLoading?: boolean;
  isSelectMode: boolean;
  selectedEntryIds: Set<UUID>;
  onSelectChange: (entryId: UUID, checked: boolean) => void;
  onEdit: (entry: ProcessedEntry) => void;
  onDelete: (entryId: UUID) => void;
  onPlaceholderClick?: (_placeholder: PlaceholderEntry) => void;
  onEntrySaved?: () => void; // Callback to notify parent to refresh data
  sortOrder: "asc" | "desc";
  onSortChange: (order: "asc" | "desc") => void;
  selectedDate: Date;
  timezone?: string;
  queryMode: QueryMode;
  areaMap: Map<UUID, { name: string; color: string }>;
  preloadedTasks: TaskWithSubtasks[];
  /** 是否禁用快捷添加功能，通常在编辑模式下使用 */
  disableQuickEntry?: boolean;
  /** 领域筛选相关属性 */
  selectedAreaId: UUID | null | "" | typeof SelectorSpecialValue.None;
  onAreaChange: (areaId: UUID | null | undefined) => void;
  onCreateNoteForEntry?: (entry: ProcessedEntry) => void;
  onViewNotesForEntry?: (entry: ProcessedEntry) => void;
}

const TimeEntriesTable: React.FC<TimeEntriesTableProps> = ({
  entries,
  isLoading = false,
  isSelectMode,
  selectedEntryIds,
  onSelectChange,
  onEdit,
  onDelete,
  onPlaceholderClick: _onPlaceholderClick,
  onEntrySaved,
  sortOrder,
  onSortChange,
  selectedDate,
  timezone,
  queryMode,
  areaMap,
  preloadedTasks,
  disableQuickEntry = false,
  selectedAreaId,
  onAreaChange,
  onCreateNoteForEntry,
  onViewNotesForEntry,
}) => {
  const { t } = useTranslation();
  // Inline quick entry states
  const [expandedTimeRange, setExpandedTimeRange] = useState<string | null>(
    null,
  );
  const [inlineStartTime, setInlineStartTime] = useState<string>("");
  const [inlineEndTime, setInlineEndTime] = useState<string>("");
  const [justSubmitted, setJustSubmitted] = useState<boolean>(false);
  const [inlineSessionId, setInlineSessionId] = useState<string | null>(null);

  const {
    tooltipState: hoveredEntryTooltip,
    showTooltip,
    schedulePositionUpdate,
    hideTooltip,
    showTooltipForElement,
  } = useHoverTooltip<ProcessedEntry>({
    defaultOffset: { x: 16, y: -12 },
    focusOffset: (rect) => ({ x: -rect.width / 2, y: -16 }),
  });

  // Unified function to update inline times
  const updateInlineTimes = useCallback(
    (startTime: string, endTime: string) => {
      setInlineStartTime(startTime);
      setInlineEndTime(endTime);
    },
    [],
  );

  const resolveInlineStartTime = useCallback(
    (placeholder: Pick<ProcessedEntry, "start_time"> | null) => {
      const targetMs = placeholder?.start_time
        ? new Date(placeholder.start_time).getTime()
        : null;
      let bestEndMs = Number.NEGATIVE_INFINITY;
      let bestEndIso: string | null = null;

      for (const entry of entries) {
        if (entry.isPlaceholder) continue;
        if (!entry.end_time) continue;
        const endMs = new Date(entry.end_time).getTime();
        if (Number.isNaN(endMs)) continue;

        if (targetMs !== null) {
          if (endMs <= targetMs && endMs > bestEndMs) {
            bestEndMs = endMs;
            bestEndIso = entry.end_time;
          }
        } else if (endMs > bestEndMs) {
          bestEndMs = endMs;
          bestEndIso = entry.end_time;
        }
      }

      if (bestEndIso) {
        return formatTime(bestEndIso, timezone);
      }

      if (placeholder?.start_time) {
        return formatTime(placeholder.start_time, timezone);
      }

      return "";
    },
    [entries, timezone],
  );

  useEffect(() => {
    if (isSelectMode) {
      hideTooltip();
    }
  }, [hideTooltip, isSelectMode]);

  const hoveredEntry = hoveredEntryTooltip?.payload ?? null;
  const tooltipPosition = hoveredEntryTooltip?.position ?? null;

  const handleHoverMove = useCallback(
    (entry: ProcessedEntry, position: HoverTooltipOverlayPosition) => {
      if (!hoveredEntry || hoveredEntry.id !== entry.id) {
        showTooltip({ payload: entry, position });
        return;
      }

      schedulePositionUpdate(position);
    },
    [hoveredEntry, schedulePositionUpdate, showTooltip],
  );

  const handleHoverStart = useCallback(
    (entry: ProcessedEntry, position: HoverTooltipOverlayPosition) => {
      showTooltip({ payload: entry, position });
    },
    [showTooltip],
  );

  const handleFocusTooltip = useCallback(
    (entry: ProcessedEntry, element: HTMLElement) => {
      showTooltipForElement(entry, element);
    },
    [showTooltipForElement],
  );

  const handleHoverLeave = useCallback(() => {
    hideTooltip();
  }, [hideTooltip]);

  const handleBlurTooltip = useCallback(() => {
    hideTooltip();
  }, [hideTooltip]);

  const tooltipContent = hoveredEntry ? (
    <TimelogTooltipContent
      entry={hoveredEntry}
      areaMap={areaMap}
      timezone={timezone}
    />
  ) : null;

  // Auto-expand the first placeholder when entries are loaded
  useEffect(() => {
    if (isSelectMode) {
      return;
    }

    // 在禁用快捷添加模式下，不自动展开
    if (disableQuickEntry) {
      return;
    }

    // 如果刚刚提交了时间日志，不要覆盖用户设置的时间
    if (justSubmitted) {
      setJustSubmitted(false);
      return;
    }

    const autoExpandEntry = entries.find(
      (entry) =>
        entry.isPlaceholder &&
        entry.start_time &&
        new Date(entry.start_time).toDateString() ===
          selectedDate.toDateString(),
    );

    if (autoExpandEntry) {
      const rangeStartTimeStr = formatTime(autoExpandEntry.start_time, timezone);
      const endTimeStr = autoExpandEntry.end_time
        ? formatTime(autoExpandEntry.end_time, timezone)
        : "";
      const timeRange = `${rangeStartTimeStr}-${endTimeStr}`;
      const startTimeStr =
        resolveInlineStartTime(autoExpandEntry) || rangeStartTimeStr;
      setExpandedTimeRange(timeRange);
      updateInlineTimes(startTimeStr, endTimeStr);
      setInlineSessionId((prev) => prev ?? createModalSessionId());
    }
  }, [
    entries,
    selectedDate,
    isSelectMode,
    disableQuickEntry,
    justSubmitted,
    resolveInlineStartTime,
    timezone,
    updateInlineTimes,
  ]);

  const handleInlineQuickEntrySaved = useCallback(
    (
      _entry: Timelog | TimelogWithEnergyResponse,
      context: { sessionId: string },
    ) => {
      if (!inlineSessionId || context.sessionId !== inlineSessionId) {
        return;
      }

      // Keep the form open for continued entry, but reset form data
      const now = new Date();
      const startTimeStr = formatTime(now.toISOString(), timezone).slice(0, 5);
      const endTimeStr = "23:59"; // Special flag for "now"

      updateInlineTimes(startTimeStr, endTimeStr);
      setJustSubmitted(true);
      setInlineSessionId(createModalSessionId());

      if (onEntrySaved) {
        onEntrySaved();
      }
    },
    [inlineSessionId, onEntrySaved, timezone, updateInlineTimes],
  );

  const handleInlineQuickEntryError = (errorMessage: string) => {
    console.error("Inline quick entry error:", errorMessage);
  };

  const handleInlineQuickEntryCancel = useCallback(
    (context?: { sessionId?: string }) => {
      if (
        inlineSessionId &&
        context?.sessionId &&
        context.sessionId !== inlineSessionId
      ) {
        return;
      }

      setExpandedTimeRange(null);
      updateInlineTimes("", "");
      setInlineSessionId(null);
    },
    [inlineSessionId, updateInlineTimes],
  );

  const handlePlaceholderClick = (placeholder: PlaceholderEntry) => {
    // 在批量操作模式下，不允许展开快速添加记录
    if (isSelectMode) {
      return;
    }

    // 在禁用快捷添加模式下，不允许展开
    if (disableQuickEntry) {
      return;
    }

    // Create stable time range identifier and set form state
    const rangeStartTimeStr = formatTime(placeholder.start_time, timezone);
    const endTimeStr = placeholder.end_time
      ? formatTime(placeholder.end_time, timezone)
      : "";
    const timeRange = `${rangeStartTimeStr}-${endTimeStr}`;
    const startTimeStr =
      resolveInlineStartTime(placeholder) || rangeStartTimeStr;

    updateInlineTimes(startTimeStr, endTimeStr);
    setExpandedTimeRange(timeRange);
    setInlineSessionId(createModalSessionId());

    // Call the parent's onPlaceholderClick if provided
    if (_onPlaceholderClick) {
      _onPlaceholderClick(placeholder);
    }
  };

  const handleSelectAll = () => {
    const allEntryIds = entries
      .filter((entry) => !entry.isPlaceholder)
      .map((entry) => entry.id as UUID);

    allEntryIds.forEach((id) => {
      if (!selectedEntryIds.has(id)) {
        onSelectChange(id, true);
      }
    });
  };

  const handleClearSelection = () => {
    selectedEntryIds.forEach((id) => {
      onSelectChange(id, false);
    });
  };

  if (isLoading) {
    return (
      <Container className="h-fit min-h-[420px]">
        <div role="status" className="sr-only">
          {t("timeLog.messages.loadingTimeLogs")}
        </div>
        <div className="space-y-4 py-6" aria-hidden="true">
          <div className="flex items-center justify-between px-4">
            <div className="h-6 w-32 rounded bg-base-300 animate-pulse" />
            <div className="h-6 w-24 rounded bg-base-300 animate-pulse" />
          </div>
          <div className="space-y-3 px-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="h-16 w-full rounded-lg bg-base-200 animate-pulse"
              />
            ))}
          </div>
        </div>
      </Container>
    );
  }

  return (
    <Container className="h-fit min-w-0 max-w-full" overflow="hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-base-100  border-b border-base-200">
            <tr>
              {isSelectMode && (
                <th className="px-4 py-3 text-center text-base font-medium text-base-content uppercase tracking-wider w-12">
                  <Checkbox
                    id="select-all"
                    name="select-all"
                    checked={
                      entries.filter((entry) => !entry.isPlaceholder).length >
                        0 &&
                      entries
                        .filter((entry) => !entry.isPlaceholder)
                        .every((entry) =>
                          selectedEntryIds.has(entry.id as UUID),
                        )
                    }
                    indeterminate={
                      selectedEntryIds.size > 0 &&
                      selectedEntryIds.size <
                        entries.filter((entry) => !entry.isPlaceholder).length
                    }
                    onCheckedChange={(checked) => {
                      if (checked) {
                        handleSelectAll();
                      } else {
                        handleClearSelection();
                      }
                    }}
                    variant="primary"
                    size="sm"
                    aria-label={t("timeLog.table.selectAllRecords")}
                  />
                </th>
              )}
              <th className="px-4 py-3 text-left text-base font-medium text-base-content uppercase tracking-wider w-24">
                {t("timeLog.table.date")}
              </th>
              <th className="px-4 py-3 text-left text-base font-medium text-base-content uppercase tracking-wider w-32">
                <div className="flex items-center gap-2">
                  <ActionButton
                    label={t("timeLog.table.timeRange")}
                    iconName={sortOrder === "asc" ? "arrow-down" : "arrow-up"}
                    color="primary"
                    variant="ghost"
                    ariaLabel={t(
                      sortOrder === "asc"
                        ? "timeLog.table.sortAscTooltip"
                        : "timeLog.table.sortDescTooltip",
                    )}
                    onClick={() =>
                      onSortChange(sortOrder === "asc" ? "desc" : "asc")
                    }
                    title={t(
                      sortOrder === "asc"
                        ? "timeLog.table.sortAscTooltip"
                        : "timeLog.table.sortDescTooltip",
                    )}
                  />
                </div>
              </th>
              <th className="px-4 py-3 text-left text-base font-medium text-base-content uppercase tracking-wider w-20">
                {t("timeLog.table.duration")}
              </th>
              <th className="px-4 py-3 text-left text-base font-medium text-base-content uppercase tracking-wider w-28">
                {queryMode === "single" ? (
                  <AreaSelect
                    value={
                      selectedAreaId === SelectorSpecialValue.None
                        ? null
                        : (selectedAreaId ?? undefined)
                    }
                    onChange={(v) => onAreaChange(v)}
                    id="table-area-filter"
                    placeholder={t("common.all")}
                    showAllOption={true}
                    showNoneOption={true}
                    noneLabel={t("common.noArea")}
                    showLabel={false}
                  />
                ) : (
                  t("target.area")
                )}
              </th>
              <th className="px-4 py-3 text-left text-base font-medium text-base-content uppercase tracking-wider">
                {t("timeLog.table.description")}
              </th>
              <th className="px-4 py-3 text-left text-base font-medium text-base-content uppercase tracking-wider w-24">
                {t("batchEdit.editType.task")}
              </th>
              <th className="px-4 py-3 text-left text-base font-medium text-base-content uppercase tracking-wider w-20">
                {t("timeLog.table.relatedPerson")}
              </th>
              <th className="px-4 py-3 text-center text-base font-medium text-base-content uppercase tracking-wider w-28">
                {t("common.actions")}
              </th>
            </tr>
          </thead>
          <tbody className="bg-base-100 divide-y divide-base-300">
            {entries.length === 0 ? (
              <tr>
                <td
                  colSpan={isSelectMode ? 9 : 8}
                  className="px-4 py-12 text-center bg-base-100"
                >
                  <EmptyState
                    icon={
                      <Icon
                        name="timer"
                        size={40}
                        className="text-primary"
                        aria-hidden
                      />
                    }
                    title={t("timeLog.table.noTimeLogs")}
                    description={t("timeLog.table.noRecordsInFilter")}
                    actionText={t("timeLog.table.clearFilter")}
                    onAction={() => {
                      // Note: This will be handled by the parent component
                    }}
                    className="py-0"
                  />
                </td>
              </tr>
            ) : (
              <>
                {entries.map((entry, index) => {
                  // Use time range for stable expansion state
                  let isExpanded = false;
                  if (entry.isPlaceholder) {
                    const startTimeStr = formatTime(entry.start_time, timezone);
                    const endTimeStr = entry.end_time
                      ? formatTime(entry.end_time, timezone)
                      : "";
                    const timeRange = `${startTimeStr}-${endTimeStr}`;
                    isExpanded = expandedTimeRange === timeRange;
                  }

                  const key = entry.isPlaceholder
                    ? (entry as unknown as PlaceholderEntry).id
                    : entry.id;

                  return (
                    <React.Fragment key={key}>
                      <EntryRow
                        entry={entry}
                        index={index}
                        isSelectMode={isSelectMode}
                        selected={selectedEntryIds.has(entry.id as UUID)}
                        onSelectChange={onSelectChange}
                        onEdit={onEdit}
                        onDelete={onDelete}
                        onPlaceholderClick={handlePlaceholderClick}
                        onCreateNote={onCreateNoteForEntry}
                        onViewNotes={onViewNotesForEntry}
                        areaMap={areaMap}
                        selectedDate={selectedDate}
                        timezone={timezone}
                        queryMode={queryMode}
                        onHoverTooltip={handleHoverStart}
                        onHoverMove={handleHoverMove}
                        onHoverLeave={handleHoverLeave}
                        onFocusTooltip={handleFocusTooltip}
                        onBlurTooltip={handleBlurTooltip}
                      />
                      {isExpanded &&
                        !isSelectMode &&
                        !disableQuickEntry &&
                        inlineSessionId && (
                          <tr>
                            <td colSpan={isSelectMode ? 9 : 8} className="p-0">
                              <div className="bg-primary/10 p-4 animate-in slide-in-from-top-2 duration-200">
                                <InlineQuickTimeEntry
                                  selectedDate={selectedDate}
                                  startTime={inlineStartTime}
                                  endTime={inlineEndTime}
                                  onEntryCreated={handleInlineQuickEntrySaved}
                                  onError={handleInlineQuickEntryError}
                                  onCancel={handleInlineQuickEntryCancel}
                                  preloadedTasks={preloadedTasks}
                                  idPrefix="timelog-inline"
                                  sessionId={inlineSessionId}
                                  timezone={timezone}
                                />
                              </div>
                            </td>
                          </tr>
                        )}
                    </React.Fragment>
                  );
                })}
              </>
            )}
          </tbody>
        </table>
      </div>
      <HoverTooltipOverlay
        visible={Boolean(hoveredEntry) && Boolean(tooltipPosition)}
        position={tooltipPosition}
        offset={hoveredEntryTooltip?.offset}
        className="text-sm leading-relaxed max-w-xs"
      >
        {tooltipContent}
      </HoverTooltipOverlay>
    </Container>
  );
};

export default TimeEntriesTable;
