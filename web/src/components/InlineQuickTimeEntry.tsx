import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useTranslation } from "react-i18next";
import type {
  TimelogCreate,
  TimelogWithEnergyResponse,
  TaskWithSubtasks,
  Vision,
  PersonSummary,
} from "@/services/api";
import type { Task as ApiTask } from "@/services/api/tasks";
import { tasksApi } from "@/services/api/tasks";
import { visionsApi } from "@/services/api/visions";
import type { Area as ApiArea } from "@/services/api/areas";
import { useTimelogMutations } from "@/hooks/useTimelogMutations";
import { useTasksMutations } from "@/hooks/useTasksMutations";
import { logger } from "@/utils/core";
import {
  ACTIVE_TASK_STATUSES,
  QUICK_TIME_ENTRY_MAX_DURATION_MINUTES,
} from "@/utils/constants";
import { useAreas } from "@/hooks/queries/useAreas";
import { usePreferenceWithBootstrap } from "@/hooks/queries/usePreferenceWithBootstrap";
import { UNKNOWN_AREA_COLOR } from "@/utils/areaColors";
import ActionButton, { FormActions } from "./ActionButton";
import { Icon } from "./icons";
import TaskSelector from "./selects/TaskSelector";
import { TextInput } from "./forms";
import { FORM_LABEL_COMPACT_CLASS } from "./forms/styles";
import {
  getNearestFiveMinuteTime,
  hhmmOnDateToISO,
  formatDate,
  formatTime,
  formatDuration,
  addMinutesToIso,
} from "@/utils/datetime";
import QuickTemplatesManagerModal from "./QuickTemplatesManagerModal";
import AreaSelect from "./selects/AreaSelect";
import PersonSelector from "./selects/PersonSelector";
import { useToast } from "@/contexts/ToastContext";
import type { UUID } from "@/types/primitive";
import { useTimelogTemplates } from "@/hooks/queries/useTimelogTemplates";
import type { TimelogTemplate } from "@/services/api/timelogTemplates";

const sortTemplates = (input: TimelogTemplate[]): TimelogTemplate[] => {
  const templates = Array.isArray(input) ? input : [];
  return [...templates].sort((a, b) => {
    const ua = a.usage_count || 0;
    const ub = b.usage_count || 0;
    if (ub !== ua) return ub - ua;
    const la = a.last_used_at ? new Date(a.last_used_at).getTime() : 0;
    const lb = b.last_used_at ? new Date(b.last_used_at).getTime() : 0;
    if (lb !== la) return lb - la;
    const ca = a.created_at ? new Date(a.created_at).getTime() : 0;
    const cb = b.created_at ? new Date(b.created_at).getTime() : 0;
    return ca - cb;
  });
};

const extractUniquePersonIds = (persons?: PersonSummary[]): UUID[] => {
  if (!persons || persons.length === 0) return [];
  const ids = persons
    .map((person) => person.id)
    .filter((id): id is UUID => typeof id === "string" && id.length > 0);
  if (ids.length === 0) return [];
  return Array.from(new Set(ids));
};

const DURATION_MIN_MINUTES = 0;

const clampDurationMinutes = (value: number): number =>
  Math.max(
    DURATION_MIN_MINUTES,
    Math.min(QUICK_TIME_ENTRY_MAX_DURATION_MINUTES, Math.round(value)),
  );

const computeDurationMinutes = (
  startIso?: string | null,
  endIso?: string | null,
): number | null => {
  if (!startIso || !endIso) return null;
  const startDate = new Date(startIso);
  const endDate = new Date(endIso);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime()))
    return null;
  const diffMs = endDate.getTime() - startDate.getTime();
  const diffMinutes = Math.round(diffMs / (1000 * 60));
  if (!Number.isFinite(diffMinutes)) return null;
  return Math.max(0, diffMinutes);
};

const parseDurationValue = (value: string): number | null => {
  if (value === "") return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || Number.isNaN(parsed)) return null;
  return clampDurationMinutes(parsed);
};

interface InlineQuickTimeEntryProps {
  selectedDate: Date;
  startTime: string;
  endTime: string;
  onEntryCreated: (
    result: TimelogWithEnergyResponse,
    context: { sessionId: string },
  ) => void;
  onError: (error: string) => void;
  onCancel: (context?: { sessionId: string }) => void;
  /**
   * Visual variant. "accent" shows blue accent background and borders (default).
   * "plain" renders without decorative wrappers, suitable for embedding
   * inside already-styled containers (e.g., Focus page panels).
   */
  variant?: "accent" | "plain";
  /** Optional restriction: only allow selecting from these task IDs */
  allowedTaskIds?: string[];
  /** Optional preselect task id */
  preselectedTaskId?: UUID | null;
  /** Optional: provide preloaded flat tasks to avoid internal fetching */
  preloadedTasks?: ApiTask[];
  /** Prefix for generating unique IDs */
  idPrefix?: string;
  sessionId: string;
  timezone?: string;
  blankInitialEndTime?: boolean;
}

export default function InlineQuickTimeEntry({
  selectedDate,
  startTime: initialStartTime,
  endTime: initialEndTime,
  onEntryCreated,
  onError,
  onCancel,
  allowedTaskIds,
  preselectedTaskId,
  preloadedTasks,
  idPrefix = "quick-time",
  sessionId,
  timezone,
  blankInitialEndTime = false,
}: InlineQuickTimeEntryProps) {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<TimelogCreate>({
    title: "",
    start_time: "",
    end_time: "",
    area_id: null,
    task_id: undefined,
    person_ids: [],
    tracking_method: "manual",
  });
  const [selectedTaskId, setSelectedTaskId] = useState<UUID | null>(
    preselectedTaskId || null,
  );

  const sessionIdRef = useRef(sessionId);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const sessionAwareCancel = useCallback(() => {
    onCancel({ sessionId: sessionIdRef.current });
  }, [onCancel]);

  const toast = useToast();

  // TanStack Query mutations
  const { createTimelogAsync } = useTimelogMutations();
  const { updateTaskAsync: updateTaskPlanningAsync } = useTasksMutations();

  // Sync external preselected task id to local state
  useEffect(() => {
    setSelectedTaskId(preselectedTaskId || null);
  }, [preselectedTaskId]);

  // Autofill when a task is preselected externally
  useEffect(() => {
    const run = async () => {
      if (!preselectedTaskId || preselectedTaskId === null) return;
      try {
        // Note: We still need to fetch task and vision data for autofill
        // This could be optimized by using a query hook, but for now we keep the direct calls
        // since this is a one-time autofill operation and not part of the main data flow
        const task = await tasksApi.getById(preselectedTaskId);
        let vision: Vision | null = null;
        try {
          if (task.vision_id) {
            vision = await visionsApi.getById(task.vision_id);
          }
        } catch {
          // Vision not found or other error, continue without vision data
        }

        // Use extracted helper functions
        autoFillTitle(task);
        autoFillArea(vision);
        applyTaskPersons(task.people);
      } catch {
        // ignore autofill errors
      }
    };
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preselectedTaskId]);
  const [selectedPersonIds, setSelectedPersonIds] = useState<UUID[]>([]);
  const lastAutoTitleRef = useRef<string>("");
  const lastAutoPersonIdsRef = useRef<UUID[] | null>(null);
  const [durationMinutes, setDurationMinutes] = useState<string>("");
  const durationBeforeFocusRef = useRef<string>("");

  const getEffectiveDurationMinutes = useCallback((): number | null => {
    const parsed = parseDurationValue(durationMinutes);
    if (parsed !== null) return parsed;
    const fallback = parseDurationValue(durationBeforeFocusRef.current);
    return fallback;
  }, [durationMinutes]);

  const syncDurationWithTimes = useCallback(
    (next: TimelogCreate): TimelogCreate => {
      if (next.start_time && next.end_time) {
        const rawMinutes = computeDurationMinutes(
          next.start_time,
          next.end_time,
        );
        if (rawMinutes !== null) {
          const bounded = clampDurationMinutes(rawMinutes);
          if (bounded !== rawMinutes) {
            const adjustedEnd = addMinutesToIso(next.start_time, bounded);
            setDurationMinutes(String(bounded));
            return {
              ...next,
              end_time: adjustedEnd,
            };
          }
          setDurationMinutes(String(bounded));
          return next;
        }
      }
      return next;
    },
    [setDurationMinutes],
  );

  const setFormDataWithSync = useCallback(
    (updater: (prev: TimelogCreate) => TimelogCreate) => {
      setFormData((prev) => {
        const next = updater(prev);
        const synced = syncDurationWithTimes(next);
        if (synced !== next) {
          const minutes = computeDurationMinutes(
            synced.start_time,
            synced.end_time,
          );
          if (minutes !== null) {
            setDurationMinutes(String(clampDurationMinutes(minutes)));
          }
        }
        return synced;
      });
    },
    [setFormData, syncDurationWithTimes],
  );

  const applyTaskPersons = (persons?: PersonSummary[]) => {
    const ids = extractUniquePersonIds(persons);
    lastAutoPersonIdsRef.current = ids;
    setSelectedPersonIds(ids);
  };

  const clearAutoPersonsIfAutoApplied = () => {
    if (lastAutoPersonIdsRef.current !== null) {
      lastAutoPersonIdsRef.current = null;
      setSelectedPersonIds([]);
    }
  };

  const handlePersonSelectionChange = (ids: UUID[]) => {
    lastAutoPersonIdsRef.current = null;
    setSelectedPersonIds(ids);
  };
  const handleDurationInputChange = (value: string) => {
    if (value === "") {
      setDurationMinutes("");
      return;
    }
    if (!/^\d+$/.test(value)) return;
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return;
    const bounded = clampDurationMinutes(numeric);
    const normalizedValue = String(bounded);
    setDurationMinutes(normalizedValue);
    durationBeforeFocusRef.current = normalizedValue;
    setFormDataWithSync((prev) => {
      if (!prev.start_time) return prev;
      const endIso = addMinutesToIso(prev.start_time, bounded);
      return {
        ...prev,
        end_time: endIso,
      };
    });
  };

  const handleDurationInputFocus = () => {
    durationBeforeFocusRef.current = durationMinutes;
    setDurationMinutes("");
  };

  const handleDurationInputBlur = () => {
    if (durationMinutes === "") {
      setDurationMinutes(durationBeforeFocusRef.current);
    } else {
      durationBeforeFocusRef.current = durationMinutes;
    }
  };

  const handleStartTimeChange = (value: string) => {
    const nextStartIso = hhmmToISO(selectedDate, value);
    const parsedDuration = getEffectiveDurationMinutes();
    setFormDataWithSync((prev) => {
      const minutes = parsedDuration ?? 0;
      const endIso = addMinutesToIso(nextStartIso, minutes);
      return {
        ...prev,
        start_time: nextStartIso,
        end_time: endIso,
      };
    });
  };

  const handleEndTimeChange = (value: string) => {
    setFormDataWithSync((prev) => {
      const baseEnd = new Date(hhmmToISO(selectedDate, value));
      if (!prev.start_time) {
        return {
          ...prev,
          end_time: baseEnd.toISOString(),
        };
      }
      const startDate = new Date(prev.start_time);
      if (baseEnd < startDate) {
        baseEnd.setDate(baseEnd.getDate() + 1);
      }
      return {
        ...prev,
        end_time: baseEnd.toISOString(),
      };
    });
  };
  const [areas, setAreas] = useState<ApiArea[]>([]);
  // Removed internal tasks loading; TaskSelector will handle via shared cache
  // const [selectedTask, setSelectedTask] = useState<TaskWithSubtasks | null>(null);
  const [loading, setLoading] = useState(false);
  const [showTemplateManager, setShowTemplateManager] = useState(false);
  // Flag to track if we should use props for time initialization
  const [shouldInitializeFromProps, setShouldInitializeFromProps] =
    useState(true);
  // removed duplicate state declarations for areas

  // Refs for keyboard navigation
  const formRef = useRef<HTMLFormElement | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const areaRef = useRef<HTMLInputElement>(null);

  // Load reference data on component mount
  // Use cached reference data where possible
  const { areas: areasFromCache } = useAreas();

  // Time log task planning settings
  const { value: autoSetTaskPlanning } = usePreferenceWithBootstrap<boolean>({
    key: "timeLog.auto_set_task_planning",
    defaultValue: false,
    module: "timeLog",
    validator: (value) => {
      if (typeof value === "boolean") return true;
      if (typeof value === "number") return value === 0 || value === 1;
      if (typeof value === "string")
        return value === "true" || value === "false";
      return false;
    },
  });

  useEffect(() => {
    let cancelled = false;
    const loadReferenceData = async () => {
      try {
        if (!cancelled) {
          setAreas(areasFromCache as ApiArea[]);
        }

        // visions/tasks are now globally cached elsewhere via TaskSelector; skip here to avoid duplication
      } catch {
        if (cancelled) return;
      }
    };
    loadReferenceData();
    return () => {
      cancelled = true;
    };
  }, [areasFromCache]);

  const {
    templates,
    bumpTemplateUsage,
    loading: templatesLoading,
  } = useTimelogTemplates();
  const sortedTemplates = useMemo(() => sortTemplates(templates), [templates]);

  const hhmmToISO = useCallback(
    (baseDate: Date, hhmm: string): string =>
      hhmmOnDateToISO(baseDate, hhmm, timezone),
    [timezone],
  );

  // Human readable duration label
  const formStartTime = formData.start_time;
  const formEndTime = formData.end_time;

  const durationDisplay = useMemo(() => {
    const minutes = computeDurationMinutes(formStartTime, formEndTime);
    if (minutes === null) return "--";
    return formatDuration(clampDurationMinutes(minutes));
  }, [formStartTime, formEndTime]);

  // Initialize form times from props
  useEffect(() => {
    if (!shouldInitializeFromProps) return;

    // If start time is empty, use current time
    const effectiveStartTime =
      initialStartTime || getNearestFiveMinuteTime(selectedDate);

    const normalizedEnd =
      initialEndTime === "23:59"
        ? getNearestFiveMinuteTime(selectedDate)
        : initialEndTime;

    const startISO = hhmmToISO(selectedDate, effectiveStartTime);
    const shouldBlankEndTime = blankInitialEndTime && !initialEndTime;
    let endISO = shouldBlankEndTime ? "" : hhmmToISO(selectedDate, normalizedEnd);

    // Cross-day: if end before start, roll to next day
    if (endISO && new Date(endISO) < new Date(startISO)) {
      const tmp = new Date(endISO);
      tmp.setDate(tmp.getDate() + 1);
      endISO = tmp.toISOString();
    }

    setFormDataWithSync((prev) => ({
      ...prev,
      start_time: startISO,
      end_time: endISO,
    }));
  }, [
    selectedDate,
    initialStartTime,
    initialEndTime,
    blankInitialEndTime,
    shouldInitializeFromProps,
    setFormDataWithSync,
    hhmmToISO,
  ]);

  // Focus title input when component mounts
  useEffect(() => {
    setTimeout(() => {
      titleRef.current?.focus();
    }, 100);
  }, []);

  // Preview removed: duration calculation no longer needed

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await saveEntry();
  };

  const saveEntry = async () => {
    // Validation
    if (!formData.title.trim()) {
      onError(t("quickTimeEntry.validation.titleRequired"));
      titleRef.current?.focus();
      return;
    }

    // area_id is now optional, no validation needed

    if (!formData.start_time) {
      onError(t("quickTimeEntry.validation.startTimeRequired"));
      return;
    }

    if (!formData.end_time) {
      onError(t("quickTimeEntry.validation.endTimeRequired"));
      return;
    }

    const preparedPersonIds = Array.from(
      new Set(
        selectedPersonIds.filter(
          (id): id is UUID => typeof id === "string" && id.length > 0,
        ),
      ),
    );

    setLoading(true);

    const requestSessionId = sessionIdRef.current;

    try {
      // Create start and end datetime objects
      const prepared: TimelogCreate = {
        ...formData,
        task_id: selectedTaskId !== null ? selectedTaskId : undefined,
        person_ids: preparedPersonIds,
      };

      const result = await createTimelogAsync(prepared);

      // Check if auto-set task planning to today is needed (based on user settings)
      let autoPlanningApplied = false;
      if (
        autoSetTaskPlanning &&
        selectedTaskId &&
        selectedTaskId !== null &&
        (formData.start_time || formData.end_time)
      ) {
        const entryTime = formData.start_time || formData.end_time;
        const within24Hours = entryTime && isWithin24Hours(entryTime);

        if (entryTime && within24Hours) {
          await autoSetTaskPlanningToday(selectedTaskId, entryTime);
          autoPlanningApplied = true;
        }
      }

      // Success message is handled by the mutation hook
      // Additional success message for task planning if applied
      if (autoPlanningApplied) {
        toast.showSuccess(
          t("quickTimeEntry.messages.saveSuccessWithTask"),
          t("quickTimeEntry.messages.saveSuccessWithTaskMessage", {
            title: formData.title,
          }),
        );
      }

      const isLatestSession = sessionIdRef.current === requestSessionId;

      if (isLatestSession) {
        // Reset form state for next entry
        const now = new Date();
        const currentTime = getNearestFiveMinuteTime(now);
        const startISO = hhmmToISO(selectedDate, currentTime);
        const parsedDuration = getEffectiveDurationMinutes();
        const resetEndIso = addMinutesToIso(startISO, parsedDuration ?? 0);

        // Disable props-based initialization to prevent override
        setShouldInitializeFromProps(false);

        setFormDataWithSync(() => ({
          title: "",
          start_time: startISO,
          end_time: resetEndIso,
          area_id: "",
          task_id: undefined,
          person_ids: [],
          tracking_method: "manual",
        }));
        setSelectedTaskId(null);
        setSelectedPersonIds([]);
        lastAutoTitleRef.current = "";
        lastAutoPersonIdsRef.current = null;
      }

      // Notify parent regardless of session match
      onEntryCreated(result, { sessionId: requestSessionId });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : t("common.error");
      onError(errorMessage);
      // Error message is handled by the mutation hook
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      saveEntry();
    } else if (e.key === "Escape") {
      e.preventDefault();
      sessionAwareCancel();
    }
  };

  // Handle task selection with auto-fill title and area inherited from vision
  const handleTaskSelect = (
    task: TaskWithSubtasks | null,
    vision?: Vision | null,
  ) => {
    // Initialize lastAutoTitleRef if not set
    if (!lastAutoTitleRef.current) {
      lastAutoTitleRef.current = "";
    }

    if (task) {
      // Use extracted helper functions for auto-fill
      autoFillTitle(task);
      autoFillArea(vision);
      if (task.people && task.people.length > 0) {
        applyTaskPersons(task.people);
      } else {
        clearAutoPersonsIfAutoApplied();
      }
    } else {
      // Deselect task - clear only if previously auto-filled
      const wasAutoFilled = formData.title === lastAutoTitleRef.current;
      if (wasAutoFilled) {
        lastAutoTitleRef.current = "";
        setFormData((prev) => ({ ...prev, title: "" }));
      }
      clearAutoPersonsIfAutoApplied();
    }
  };

  // When external task id changes, trigger autofill via TaskSelector callback path
  useEffect(() => {
    if (!selectedTaskId) return;
    // We don't have the full task object here; rely on vision-based autofill via AreaSelect if available.
    // Minimal behavior: clear lastAutoTitleRef to allow title autofill on next onTaskSelect.
    lastAutoTitleRef.current = "";
  }, [selectedTaskId]);

  // Helpers kept for potential future preview UI; not used now after preview removal

  // Helper function to auto-set task planning to today
  const autoSetTaskPlanningToday = async (taskId: UUID, entryTime: string) => {
    try {
      const dateString = formatDate(entryTime, timezone);

      const updateData = {
        planning_cycle_type: "day",
        planning_cycle_days: 1,
        planning_cycle_start_date: dateString,
      };

      await updateTaskPlanningAsync({ id: taskId, data: updateData });
    } catch (err) {
      logger.error(
        `InlineQuickTimeEntry: Failed to auto-set task ${taskId} planning:`,
        err,
      );
      // Don't throw error to avoid affecting time log saving
    }
  };

  // Helper function to check if time is within 24 hours
  const isWithin24Hours = (timeString: string) => {
    const now = new Date();
    const entryTime = new Date(timeString);
    const timeDiff = Math.abs(now.getTime() - entryTime.getTime());
    const hoursDiff = timeDiff / (1000 * 60 * 60);
    return hoursDiff <= 24;
  };

  // Helper functions for auto-fill logic
  const autoFillTitle = (task: TaskWithSubtasks | ApiTask) => {
    const isEmpty = !formData.title.trim();
    const wasAutoFilled = formData.title === lastAutoTitleRef.current;

    if (isEmpty || wasAutoFilled) {
      const autoTitle = task.content;
      lastAutoTitleRef.current = autoTitle;
      setFormData((prev) => ({ ...prev, title: autoTitle }));
    }
  };

  const autoFillArea = (vision?: Vision | null) => {
    if (
      vision &&
      typeof vision.area_id === "string" &&
      vision.area_id > ""
    ) {
      setFormData((prev) =>
        prev.area_id && prev.area_id > ""
          ? prev
          : { ...prev, area_id: vision.area_id as UUID },
      );
    }
  };

  const resolveAreaIdByName = (name?: string): UUID => {
    if (!name) return "";
    const found = areas.find((d) => d.name === name);
    return found ? found.id : "";
  };

  const applyTemplate = async (tpl: TimelogTemplate) => {
    try {
      await bumpTemplateUsage(tpl.id);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err ?? "");
      toast.showError(
        t("quickTemplatesManager.messages.actionFailed"),
        message,
      );
    }

    const templateDuration =
      typeof tpl.default_duration_minutes === "number"
        ? clampDurationMinutes(tpl.default_duration_minutes)
        : null;

    if (templateDuration !== null) {
      setDurationMinutes(String(templateDuration));
    }

    setFormDataWithSync((prev) => {
      const resolvedAreaId = tpl.area_id
        ? tpl.area_id
        : tpl.area_name
          ? resolveAreaIdByName(tpl.area_name)
          : null;
      let next: TimelogCreate = {
        ...prev,
        title: tpl.title,
        area_id: resolvedAreaId,
      };
      if (templateDuration !== null && prev.start_time) {
        next = {
          ...next,
          end_time: addMinutesToIso(prev.start_time, templateDuration),
        };
      }
      return next;
    });
    const templatePersonIds =
      tpl.person_ids && tpl.person_ids.length > 0
        ? tpl.person_ids
        : (tpl.people?.map((person) => person.id) ?? []);
    handlePersonSelectionChange(templatePersonIds);
  };

  return (
    <div className="min-w-0 max-w-full rounded-lg border border-primary/30 bg-base-100 p-4 shadow-sm">
      <div className="mb-3">
        <h4 className="text-lg font-semibold text-base-content flex items-center justify-between">
          <span className="inline-flex items-center gap-2">
            <Icon name="bolt" size={20} aria-hidden />
            {t("quickTimeEntry.title")}
          </span>
        </h4>
      </div>

      {/* Task single-select (left) + Templates (right) */}
      <div className="mt-1 mb-5 flex min-w-0 flex-col items-start justify-between gap-3 lg:flex-row">
        {/* Left: inline compact TaskSelector */}
        <div className="w-full lg:w-56">
          <TaskSelector
            value={selectedTaskId}
            onChange={setSelectedTaskId}
            disabled={loading}
            className="text-base"
            filterStatus={useMemo(() => ACTIVE_TASK_STATUSES, [])}
            allowedTaskIds={allowedTaskIds}
            onTaskSelect={handleTaskSelect}
            preloadedTasks={preloadedTasks as unknown as TaskWithSubtasks[]}
            deferRemoteLoad={true}
            idPrefix={`${idPrefix}-task-selector`}
          />
        </div>

        {/* Right: templates */}
        <div className="min-w-0 flex-1 w-full lg:w-auto">
          <div className="flex items-center gap-2 mb-2 justify-start lg:justify-end">
            <ActionButton
              label={t("quickTimeEntry.templates.manage")}
              iconName="settings"
              color="primary"
              ariaLabel={t("quickTimeEntry.templates.manageTitle")}
              onClick={() => setShowTemplateManager(true)}
            />
          </div>
          {templatesLoading ? (
            <div className="text-base bg-base-100 border border-base-200 rounded px-3 py-2 text-right">
              {t("common.loading")}
            </div>
          ) : sortedTemplates.length === 0 ? (
            <div className="text-sm bg-base-100  px-3 py-2 text-right">
              {t("quickTimeEntry.templates.noTemplates")}
            </div>
          ) : (
            <div className="flex flex-wrap gap-1.5 justify-start lg:justify-end">
              {sortedTemplates.map((tpl) => (
                <button
                  key={tpl.id}
                  type="button"
                  onClick={() => void applyTemplate(tpl)}
                  className="px-2 py-0.5 text-xs rounded-md bg-base-200/70 hover:bg-base-200 transition inline-flex items-center gap-1 text-left"
                  title={(() => {
                    const areaLabel = tpl.area_id
                      ? (areas.find((d) => d.id === tpl.area_id)
                          ?.name ??
                        tpl.area_name ??
                        "?")
                      : tpl.area_name || "?";
                    if (tpl.default_duration_minutes) {
                      return `${tpl.title}（领域: ${areaLabel}，时长: ${tpl.default_duration_minutes} 分钟）`;
                    }
                    return `${tpl.title}（领域: ${areaLabel}）`;
                  })()}
                >
                  {/* area color dot */}
                  {(() => {
                    const areaById = tpl.area_id
                      ? areas.find((d) => d.id === tpl.area_id)
                      : null;
                    const areaByName =
                      !areaById && tpl.area_name
                        ? areas.find((d) => d.name === tpl.area_name)
                        : null;
                    const color =
                      areaById?.color ||
                      areaByName?.color ||
                      tpl.area_color ||
                      UNKNOWN_AREA_COLOR;
                    return (
                      <span
                        className="inline-block w-1.5 h-1.5 rounded-full"
                        style={{ backgroundColor: color }}
                      />
                    );
                  })()}
                  {tpl.title}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <form ref={formRef} onSubmit={handleSubmit} className="space-y-4">
        {/* Quick input row */}
        <div className="flex min-w-0 flex-col items-start gap-3 lg:flex-row lg:items-center">
          {/* Start Time */}
          <div className="flex-shrink-0 w-full lg:w-auto mt-4">
            <label
              htmlFor={`${idPrefix}-start-time`}
              className={FORM_LABEL_COMPACT_CLASS}
            >
              {t("eventModal.fields.startTime")}
            </label>
            <TextInput
              id={`${idPrefix}-start-time`}
              name={`${idPrefix}-start-time`}
              type="time"
              step="300"
              value={formatTime(formData.start_time || "", timezone)}
              onChange={(e) => handleStartTimeChange(e.target.value)}
              onKeyDown={handleKeyDown}
              size="sm"
              className="lg:w-30"
              disabled={loading}
            />
          </div>

          {/* End Time */}
          <div className="flex-shrink-0 w-full lg:w-auto  mt-4">
            <label
              htmlFor={`${idPrefix}-end-time`}
              className={FORM_LABEL_COMPACT_CLASS}
            >
              {t("eventModal.fields.endTime")}
            </label>
            <TextInput
              id={`${idPrefix}-end-time`}
              name={`${idPrefix}-end-time`}
              type="time"
              step="300"
              value={formatTime(formData.end_time || "", timezone)}
              onChange={(e) => handleEndTimeChange(e.target.value)}
              onKeyDown={handleKeyDown}
              size="sm"
              className="lg:w-30"
              disabled={loading}
            />
          </div>

          {/* Duration (minutes) */}
          <div className="flex-shrink-0 w-full lg:w-auto  mt-4">
            <label
              htmlFor={`${idPrefix}-duration`}
              className={`${FORM_LABEL_COMPACT_CLASS} flex items-center justify-between gap-2`}
            >
              <span>{t("timeLog.table.duration")}</span>
              <span className="text-sm text-base-content/70 whitespace-nowrap">
                {durationDisplay}
              </span>
            </label>
            <TextInput
              id={`${idPrefix}-duration`}
              name={`${idPrefix}-duration`}
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={4}
              value={durationMinutes}
              onChange={(e) => handleDurationInputChange(e.target.value)}
              onFocus={handleDurationInputFocus}
              onBlur={handleDurationInputBlur}
              onKeyDown={handleKeyDown}
              placeholder="hhmm"
              size="sm"
              className="lg:w-24"
              disabled={loading}
            />
          </div>

          {/* Task Title */}
          <div className="mt-4 min-w-0 flex-1">
            <label
              htmlFor={`${idPrefix}-title`}
              className={FORM_LABEL_COMPACT_CLASS}
            >
              {t("quickTimeEntry.activity.label")}
            </label>
            <TextInput
              ref={titleRef}
              id={`${idPrefix}-title`}
              name={`${idPrefix}-title`}
              type="text"
              value={formData.title}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, title: e.target.value }))
              }
              onKeyDown={handleKeyDown}
              placeholder={t("quickTimeEntry.activity.placeholder")}
              size="sm"
              disabled={loading}
            />
          </div>

          {/* Area */}
          <div className="flex-shrink-0 w-22 mt-2">
            <AreaSelect
              ref={areaRef}
              value={formData.area_id || null}
              onChange={(v) =>
                setFormData((prev) => ({
                  ...prev,
                  area_id: v ?? null,
                }))
              }
              disabled={loading}
              placeholder={t("common.please_select")}
              id={`${idPrefix}-area`}
            />
          </div>

          {/* Tasks field removed as per new compact picker above */}
          {/* Persons */}
          <div className="flex-shrink-0 w-28 mt-2">
            <PersonSelector
              selectedPersonIds={selectedPersonIds}
              onSelectionChange={handlePersonSelectionChange}
              multiple={true}
              variant="compact"
              disabled={loading}
              className="text-base"
              idPrefix={`${idPrefix}-persons`}
              placeholder={t("common.none")}
              selectedListMaxHeight={120}
            />
          </div>
        </div>

        {/* Bottom action buttons */}
        <div className="pt-2">
          <FormActions
            loading={loading}
            onCancel={sessionAwareCancel}
            onSubmit={() => formRef.current?.requestSubmit()}
            disabled={
              !formData.title.trim() ||
              formData.area_id === "" ||
              !formData.start_time ||
              !formData.end_time
            }
          />
        </div>
      </form>

      {/* Manager Modal */}
      {showTemplateManager && (
        <QuickTemplatesManagerModal
          isOpen={showTemplateManager}
          onClose={() => setShowTemplateManager(false)}
        />
      )}
    </div>
  );
}
