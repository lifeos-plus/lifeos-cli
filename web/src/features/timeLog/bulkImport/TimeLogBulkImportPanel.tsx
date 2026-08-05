import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import Container from "@/layouts/Container";
import { TextInput } from "@/components/forms";
import TextArea from "@/components/forms/TextArea";
import ActionButton from "@/components/ActionButton";
import ConfirmDialog from "@/components/ConfirmDialog";
import TimeEntriesTable from "@/components/TimeEntriesTable";
import TimeEntryModal from "@/components/TimeEntryModal";
import {
  parseDateKey,
  parseDateOnlyToLocalDate,
  resolvePreferredTimezone,
  zonedDateTimeToUtc,
} from "@/utils/datetime";
import {
  parseBulkTimelogInput,
  BULK_IMPORT_MAX_ENTRIES,
  BULK_IMPORT_MAX_DAYS,
  type BulkImportRow,
  type BulkImportMessage,
  type BulkImportRowErrorCode,
  type BulkImportWarningCode,
  type BulkImportGlobalErrorCode,
} from "./parseBulkTimelogInput";
import {
  formatDateToken,
  formatTimeToken,
  resolveBulkImportDefaultStart,
  toDateInputValue,
} from "./bulkImportDefaults";
import type { ProcessedEntry } from "@/utils/datetime";
import type { UUID } from "@/types/primitive";
import { UNKNOWN_AREA_COLOR } from "@/utils/areaColors";
import type { TaskWithSubtasks } from "@/services/api";
import type {
  Timelog,
  TimelogCreate,
  TimelogTaskSummary,
} from "@/services/api/timelogs";
import type { PersonSummary } from "@/services/api/types/common";
import { useTimelogMutations } from "@/hooks/useTimelogMutations";
import { useToast } from "@/contexts/ToastContext";
import { usePersonsList } from "@/hooks/queries/usePersonsList";

interface TimeLogBulkImportPanelProps {
  selectedDate: Date;
  timezone?: string | null;
  latestTimelogEndTime?: string | null;
  areaMap: Map<UUID, { name: string; color?: string | null }>;
  preloadedTasks: TaskWithSubtasks[];
  onCancel: () => void;
  onImported: () => void;
}

interface EditableRow extends BulkImportRow {
  isManualEdit?: boolean;
}

const MIN_TEXTAREA_HEIGHT = 200;
const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const TIME_REGEX = /^\d{2}:\d{2}$/;
const MS_PER_DAY = 24 * 60 * 60 * 1000;

const rowErrorKeys: Record<BulkImportRowErrorCode, string> = {
  line_unrecognized: "timeLog.bulkImport.errors.lineUnrecognized",
  missing_description: "timeLog.bulkImport.errors.missingDescription",
  start_missing: "timeLog.bulkImport.errors.startMissing",
  start_invalid: "timeLog.bulkImport.errors.startInvalid",
  end_invalid: "timeLog.bulkImport.errors.endInvalid",
  time_parse_failure: "timeLog.bulkImport.errors.timeParseFailure",
  cross_day_limit: "timeLog.bulkImport.errors.crossDayLimit",
  duration_invalid: "timeLog.bulkImport.errors.durationInvalid",
};

const warningKeys: Record<BulkImportWarningCode, string> = {
  auto_shift_start: "timeLog.bulkImport.warnings.autoShiftStart",
  auto_cross_midnight_end: "timeLog.bulkImport.warnings.autoCrossMidnightEnd",
  auto_cross_midnight_range:
    "timeLog.bulkImport.warnings.autoCrossMidnightRange",
};

const globalErrorKeys: Record<BulkImportGlobalErrorCode, string> = {
  too_many_lines: "timeLog.bulkImport.errors.tooManyLines",
};

const mapMessage = (
  t: TFunction,
  type: "error" | "warning" | "global",
  message: BulkImportMessage,
): string => {
  const key =
    type === "warning"
      ? warningKeys[message.code as BulkImportWarningCode]
      : type === "global"
        ? globalErrorKeys[message.code as BulkImportGlobalErrorCode]
        : rowErrorKeys[message.code as BulkImportRowErrorCode];
  if (!key) return message.code;
  return t(key, message.meta);
};

const convertToUtcIso = (
  dateString: string,
  timeString: string,
  timezone: string,
): string => {
  const [year, month, day] = dateString
    .split("-")
    .map((token) => Number(token));
  const [hour, minute] = timeString.split(":").map((token) => Number(token));
  return zonedDateTimeToUtc(
    year,
    month,
    day,
    hour,
    minute,
    0,
    0,
    timezone,
  ).toISOString();
};

const buildProcessedEntry = (
  row: EditableRow,
  timezone: string,
  taskLookup: Map<UUID, TimelogTaskSummary>,
  personLookup: Map<UUID, PersonSummary>,
): ProcessedEntry => {
  const startIso = convertToUtcIso(row.date, row.startTime, timezone);
  const endIso = convertToUtcIso(row.endDate, row.endTime, timezone);
  const people = row.personIds.map((id) => {
    const uuid = id as UUID;
    return (
      personLookup.get(uuid) || {
        id: uuid,
        display_name: uuid,
        primary_nickname: "",
        name: "",
        tags: [],
      }
    );
  });
  const task =
    row.taskId && taskLookup.get(row.taskId as UUID)
      ? taskLookup.get(row.taskId as UUID)!
      : row.taskId
        ? {
            id: row.taskId as UUID,
            content: row.taskId,
            vision_id: null,
            vision_summary: null,
          }
        : null;
  return {
    id: row.id as UUID,
    title: row.description,
    start_time: startIso,
    end_time: endIso,
    area_id: (row.areaId as UUID) ?? null,
    tracking_method: "manual",
    location: null,
    energy_level: row.energyLevel ?? null,
    notes: row.notes || null,
    tags: [],
    extra_data: { sourceLine: row.sourceLineNumber },
    created_at: startIso,
    updated_at: endIso,
    people,
    task,
    linked_notes: [],
    validationResult: {
      isValid: row.errors.length === 0,
      hasNegativeDuration: false,
      hasOverlaps: false,
      overlappingEntries: [],
    },
  } as ProcessedEntry;
};

const computeDayOffset = (baseDate: string, target: string): number | null => {
  if (!DATE_REGEX.test(baseDate) || !DATE_REGEX.test(target)) return null;
  const base = parseDateOnlyToLocalDate(baseDate);
  const targetDate = parseDateOnlyToLocalDate(target);
  if (!base || !targetDate) return null;
  return Math.floor((targetDate.getTime() - base.getTime()) / MS_PER_DAY);
};

const validateRowFields = (
  row: EditableRow,
  baseDate: string,
  timezone: string,
): BulkImportMessage[] => {
  const errors: BulkImportMessage[] = [];
  if (!DATE_REGEX.test(row.date) || !DATE_REGEX.test(row.endDate)) {
    errors.push({ code: "time_parse_failure" });
    return errors;
  }
  if (!TIME_REGEX.test(row.startTime)) {
    errors.push({ code: "start_invalid" });
  }
  if (!TIME_REGEX.test(row.endTime)) {
    errors.push({ code: "end_invalid" });
  }
  if (errors.length) return errors;

  const startIso = convertToUtcIso(row.date, row.startTime, timezone);
  const endIso = convertToUtcIso(row.endDate, row.endTime, timezone);

  if (new Date(endIso).getTime() <= new Date(startIso).getTime()) {
    errors.push({ code: "duration_invalid" });
  }

  const startOffset = computeDayOffset(baseDate, row.date);
  const endOffset = computeDayOffset(baseDate, row.endDate);
  if (
    startOffset === null ||
    endOffset === null ||
    startOffset >= BULK_IMPORT_MAX_DAYS ||
    endOffset >= BULK_IMPORT_MAX_DAYS ||
    startOffset < 0
  ) {
    errors.push({
      code: "cross_day_limit",
      meta: { maxDays: BULK_IMPORT_MAX_DAYS },
    });
  }

  return errors;
};

const buildDraftTimelog = (
  row: EditableRow,
  timezone: string,
  taskLookup: Map<UUID, TimelogTaskSummary>,
  personLookup: Map<UUID, PersonSummary>,
): Timelog => {
  const startIso = convertToUtcIso(row.date, row.startTime, timezone);
  const endIso = convertToUtcIso(row.endDate, row.endTime, timezone);
  const nowIso = new Date().toISOString();
  const people = row.personIds.map((id) => {
    const uuid = id as UUID;
    return (
      personLookup.get(uuid) || {
        id: uuid,
        display_name: uuid,
        primary_nickname: "",
        name: "",
        tags: [],
      }
    );
  });
  const task =
    row.taskId && taskLookup.get(row.taskId as UUID)
      ? taskLookup.get(row.taskId as UUID)!
      : row.taskId
        ? {
            id: row.taskId as UUID,
            content: row.taskId,
            vision_id: null,
            vision_summary: null,
          }
        : null;
  return {
    id: row.id as UUID,
    title: row.description,
    start_time: startIso,
    end_time: endIso,
    area_id: (row.areaId as UUID) ?? null,
    area_summary: null,
    tracking_method: "manual",
    location: null,
    energy_level: row.energyLevel ?? null,
    notes: row.notes || null,
    tags: [],
    extra_data: { sourceLine: row.sourceLineNumber },
    created_at: nowIso,
    updated_at: nowIso,
    people,
    task,
    linked_notes: [],
  };
};

const TimeLogBulkImportPanel: React.FC<TimeLogBulkImportPanelProps> = ({
  selectedDate,
  timezone,
  latestTimelogEndTime,
  areaMap,
  preloadedTasks,
  onCancel,
  onImported,
}) => {
  const { t } = useTranslation();
  const toast = useToast();
  const { batchCreateTimelogsAsync } = useTimelogMutations();
  const { persons: knownPersons } = usePersonsList();

  const [startDateInput, setStartDateInput] = useState(
    () =>
      resolveBulkImportDefaultStart(
        selectedDate,
        resolvePreferredTimezone(timezone),
        latestTimelogEndTime,
      ).date,
  );
  const [firstStartTime, setFirstStartTime] = useState(
    () =>
      resolveBulkImportDefaultStart(
        selectedDate,
        resolvePreferredTimezone(timezone),
        latestTimelogEndTime,
      ).time,
  );
  const [isStartDateCustomized, setIsStartDateCustomized] = useState(false);
  const [isFirstStartTimeCustomized, setIsFirstStartTimeCustomized] =
    useState(false);
  const [rawInput, setRawInput] = useState("");
  const [rows, setRows] = useState<EditableRow[]>([]);
  const [globalErrors, setGlobalErrors] = useState<BulkImportMessage[]>([]);
  const [hasManualEdits, setHasManualEdits] = useState(false);
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [editingRowId, setEditingRowId] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [manualEditsConfirmOpen, setManualEditsConfirmOpen] = useState(false);

  const effectiveTimezone = useMemo(
    () => resolvePreferredTimezone(timezone),
    [timezone],
  );
  const defaultStart = useMemo(
    () =>
      resolveBulkImportDefaultStart(
        selectedDate,
        effectiveTimezone,
        latestTimelogEndTime,
      ),
    [effectiveTimezone, latestTimelogEndTime, selectedDate],
  );

  useEffect(() => {
    if (!isStartDateCustomized) {
      setStartDateInput(defaultStart.date);
    }
    if (!isFirstStartTimeCustomized) {
      setFirstStartTime(defaultStart.time);
    }
  }, [defaultStart, isFirstStartTimeCustomized, isStartDateCustomized]);

  const baseDateString = useMemo(
    () =>
      DATE_REGEX.test(startDateInput)
        ? startDateInput
        : toDateInputValue(selectedDate),
    [startDateInput, selectedDate],
  );

  const parseDate = useMemo(
    () => parseDateKey(baseDateString),
    [baseDateString],
  );

  const taskSummaryLookup = useMemo(() => {
    const map = new Map<UUID, TimelogTaskSummary>();
    preloadedTasks.forEach((task) => {
      map.set(task.id, {
        id: task.id,
        content: task.content,
        vision_id: task.vision_id,
        status: task.status,
        vision_summary: null,
      });
    });
    return map;
  }, [preloadedTasks]);

  const personLookup = useMemo(() => {
    const map = new Map<UUID, PersonSummary>();
    knownPersons.forEach((person) => map.set(person.id, person));
    return map;
  }, [knownPersons]);

  const emptySelection = useMemo(() => new Set<UUID>(), []);

  const executeParse = useCallback(() => {
    setIsParsing(true);
    try {
      const result = parseBulkTimelogInput(rawInput, {
        startDate: parseDate,
        defaultFirstStartTime: firstStartTime || "00:00",
        maxEntries: BULK_IMPORT_MAX_ENTRIES,
      });
      setRows(result.rows);
      setGlobalErrors(result.globalErrors);
      setHasManualEdits(false);
      setEditingRowId(null);
    } finally {
      setIsParsing(false);
    }
  }, [rawInput, parseDate, firstStartTime]);

  const handleParse = useCallback(() => {
    if (!rawInput.trim()) {
      toast.showInfo(
        t("timeLog.bulkImport.parseEmptyTitle"),
        t("timeLog.bulkImport.parseEmptyMessage"),
      );
      return;
    }

    if (hasManualEdits) {
      setManualEditsConfirmOpen(true);
      return;
    }

    executeParse();
  }, [rawInput, hasManualEdits, t, toast, executeParse]);

  const handleConfirmReparse = useCallback(() => {
    setManualEditsConfirmOpen(false);
    executeParse();
  }, [executeParse]);

  const normalizedAreaMap = useMemo(() => {
    const normalized = new Map<UUID, { name: string; color: string }>();
    areaMap.forEach((value, key) => {
      normalized.set(key, {
        name: value.name,
        color: value.color ?? UNKNOWN_AREA_COLOR,
      });
    });
    return normalized;
  }, [areaMap]);

  const previewEntries = useMemo<ProcessedEntry[]>(() => {
    const mapped = rows.map((row) =>
      buildProcessedEntry(
        row,
        effectiveTimezone,
        taskSummaryLookup,
        personLookup,
      ),
    );
    if (sortOrder === "desc") {
      return [...mapped].sort(
        (a, b) =>
          new Date(b.start_time ?? 0).getTime() -
          new Date(a.start_time ?? 0).getTime(),
      );
    }
    return mapped.sort(
      (a, b) =>
        new Date(a.start_time ?? 0).getTime() -
        new Date(b.start_time ?? 0).getTime(),
    );
  }, [rows, effectiveTimezone, sortOrder, taskSummaryLookup, personLookup]);

  const handleDeleteRow = (rowId: UUID) => {
    const idString = String(rowId);
    setRows((prev) => prev.filter((row) => row.id !== idString));
    setHasManualEdits(true);
    if (editingRowId === idString) {
      setEditingRowId(null);
    }
  };

  const handleImport = async () => {
    const validRows = rows.filter((row) => row.errors.length === 0);
    if (validRows.length === 0) {
      toast.showError(
        t("timeLog.bulkImport.submit"),
        t("timeLog.bulkImport.parseEmptyMessage"),
      );
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: TimelogCreate[] = validRows.map((row) => {
        const startIso = convertToUtcIso(
          row.date,
          row.startTime,
          effectiveTimezone,
        );
        const endIso = convertToUtcIso(
          row.endDate,
          row.endTime,
          effectiveTimezone,
        );
        const eventData: TimelogCreate = {
          title: row.description,
          start_time: startIso,
          end_time: endIso,
          area_id: (row.areaId as UUID) ?? null,
          tracking_method: "manual",
        };
        if (row.taskId) {
          eventData.task_id = row.taskId as UUID;
        }
        if (row.personIds.length > 0) {
          eventData.person_ids = row.personIds as UUID[];
        }
        if (row.notes) {
          eventData.notes = row.notes;
        }
        if (typeof row.energyLevel === "number") {
          eventData.energy_level = row.energyLevel;
        }
        return eventData;
      });
      await batchCreateTimelogsAsync(payload);
      setRows([]);
      setRawInput("");
      setEditingRowId(null);
      setHasManualEdits(false);
      onImported();
    } catch (error) {
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeRow = useMemo(
    () => rows.find((row) => row.id === editingRowId) || null,
    [rows, editingRowId],
  );

  const editingEntry = useMemo(
    () =>
      activeRow
        ? buildDraftTimelog(
            activeRow,
            effectiveTimezone,
            taskSummaryLookup,
            personLookup,
          )
        : null,
    [activeRow, effectiveTimezone, taskSummaryLookup, personLookup],
  );

  const editingSelectedDate = useMemo(
    () => (activeRow ? parseDateKey(activeRow.date) : selectedDate),
    [activeRow, selectedDate],
  );

  const handleDraftSubmit = useCallback(
    async (payload: TimelogCreate) => {
      if (!activeRow) return;
      const startIso = payload.start_time || payload.end_time;
      const endIso = payload.end_time || payload.start_time;
      if (!startIso || !endIso) return;

      setRows((prev) =>
        prev.map((row) => {
          if (row.id !== activeRow.id) return row;
          const next: EditableRow = {
            ...row,
            description: payload.title,
            date: formatDateToken(startIso, effectiveTimezone),
            startTime: formatTimeToken(startIso, effectiveTimezone),
            endDate: formatDateToken(endIso, effectiveTimezone),
            endTime: formatTimeToken(endIso, effectiveTimezone),
            areaId: (payload.area_id as string | null) ?? null,
            taskId: (payload.task_id as string | null) ?? null,
            personIds: (payload.person_ids as string[] | undefined) ?? [],
            notes: payload.notes ?? "",
            energyLevel:
              typeof payload.energy_level === "number"
                ? payload.energy_level
                : null,
            isManualEdit: true,
            autoInferredStart: false,
          };
          next.errors = validateRowFields(
            next,
            baseDateString,
            effectiveTimezone,
          );
          next.warnings = [];
          return next;
        }),
      );
      setHasManualEdits(true);
      setEditingRowId(null);
    },
    [activeRow, baseDateString, effectiveTimezone],
  );

  const renderMessages = (
    messages: BulkImportMessage[],
    type: "error" | "warning" | "global" = "error",
  ) =>
    messages.length > 0 && (
      <ul className="mt-2 space-y-1 text-sm">
        {messages.map((msg, idx) => (
          <li
            key={`${msg.code}-${idx}`}
            className={type === "warning" ? "text-warning" : "text-error"}
          >
            {mapMessage(t, type, msg)}
          </li>
        ))}
      </ul>
    );

  const validCount = rows.filter((row) => row.errors.length === 0).length;

  return (
    <div className="space-y-4">
      <Container padding="lg" borderVariant="subtle" shadow="md">
        <div className="mb-4">
          <div>
            <h2 className="text-xl font-semibold">
              {t("timeLog.bulkImport.modalTitle")}
            </h2>
            <p className="text-sm text-base-content/70">
              {t("timeLog.bulkImport.tip", {
                max: BULK_IMPORT_MAX_ENTRIES,
              })}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              {t("timeLog.bulkImport.startDateLabel")}
            </label>
            <TextInput
              type="date"
              value={startDateInput}
              onChange={(event) => {
                setIsStartDateCustomized(true);
                setStartDateInput(event.target.value);
              }}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              {t("timeLog.bulkImport.firstStartLabel")}
            </label>
            <TextInput
              type="time"
              value={firstStartTime}
              onChange={(event) => {
                setIsFirstStartTimeCustomized(true);
                setFirstStartTime(event.target.value);
              }}
            />
          </div>
        </div>
        <div className="mt-4">
          <label className="block text-sm font-medium mb-1">
            {t("timeLog.bulkImport.inputLabel")}
          </label>
          <TextArea
            value={rawInput}
            onChange={(event) => setRawInput(event.target.value)}
            resize="vertical"
            rows={6}
            style={{ minHeight: MIN_TEXTAREA_HEIGHT }}
            placeholder={t("timeLog.bulkImport.inputPlaceholder")}
          />
          {globalErrors.length > 0 && renderMessages(globalErrors, "global")}
          <div className="mt-3 flex flex-wrap gap-2">
            <ActionButton
              label={t("timeLog.bulkImport.parseButton")}
              color="primary"
              variant="solid"
              size="md"
              onClick={handleParse}
              disabled={isParsing}
            />
            <ActionButton
              label={t("common.clear")}
              variant="outline"
              size="md"
              onClick={() => {
                setRows([]);
                setRawInput("");
                setGlobalErrors([]);
                setHasManualEdits(false);
                setEditingRowId(null);
              }}
            />
          </div>
        </div>
      </Container>

      <Container padding="lg" borderVariant="subtle" shadow="md">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold">
              {t("timeLog.bulkImport.previewTitle", {
                count: rows.length,
              })}
            </h3>
            <p className="text-sm text-base-content/60">
              {t("timeLog.bulkImport.summary", {
                total: rows.length,
                valid: validCount,
              })}
            </p>
          </div>
          <div className="flex gap-2">
            <ActionButton
              label={t("timeLog.bulkImport.submit")}
              color="primary"
              variant="solid"
              size="md"
              onClick={handleImport}
              disabled={validCount === 0 || isSubmitting}
            />
            <ActionButton
              label={t("common.cancel")}
              variant="outline"
              size="md"
              onClick={onCancel}
            />
          </div>
        </div>
        {rows.length === 0 ? (
          <p className="text-base text-base-content/70">
            {t("timeLog.bulkImport.emptyPreview")}
          </p>
        ) : (
          <TimeEntriesTable
            entries={previewEntries}
            isLoading={false}
            isSelectMode={false}
            selectedEntryIds={emptySelection}
            onSelectChange={() => {}}
            onEdit={(entry) => setEditingRowId(entry.id as string)}
            onDelete={(id) => handleDeleteRow(id)}
            onPlaceholderClick={() => {}}
            onEntrySaved={() => {}}
            sortOrder={sortOrder}
            onSortChange={setSortOrder}
            selectedDate={selectedDate}
            queryMode="import"
            areaMap={normalizedAreaMap}
            preloadedTasks={preloadedTasks}
            disableQuickEntry
            selectedAreaId={null}
            onAreaChange={() => {}}
          />
        )}
        {rows.some((row) => row.errors.length > 0) && (
          <div className="mt-6 border-t border-base-300 pt-4">
            <h4 className="font-semibold text-base">
              {t("timeLog.bulkImport.errorListTitle")}
            </h4>
            <ul className="mt-2 space-y-1 text-sm text-error">
              {rows
                .filter((row) => row.errors.length > 0)
                .map((row) =>
                  row.errors.map((msg, idx) => (
                    <li key={`${row.id}-error-${idx}`}>
                      {t("timeLog.bulkImport.errorListItem", {
                        line: row.sourceLineNumber,
                        message: mapMessage(t, "error", msg),
                      })}
                    </li>
                  )),
                )}
            </ul>
          </div>
        )}
        {activeRow && editingEntry && (
          <TimeEntryModal
            isOpen
            mode="draft"
            entry={editingEntry}
            selectedDate={editingSelectedDate}
            onClose={(_context) => setEditingRowId(null)}
            onSave={(_result, _meta) => {}}
            onDraftSubmit={handleDraftSubmit}
            preloadedTasks={preloadedTasks}
            sessionId={activeRow.id}
          />
        )}
      </Container>

      <ConfirmDialog
        isOpen={manualEditsConfirmOpen}
        title={t("common.confirm")}
        message={t("timeLog.bulkImport.manualEditsReset")}
        confirmText={t("timeLog.bulkImport.reparseButton")}
        cancelText={t("common.cancel")}
        onConfirm={handleConfirmReparse}
        onCancel={() => setManualEditsConfirmOpen(false)}
      />
    </div>
  );
};

export default TimeLogBulkImportPanel;
