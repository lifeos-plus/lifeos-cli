import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import AsyncEntitySelect, {
  type EntityOption,
  type SelectSize,
} from "./AsyncEntitySelect";
import {
  SelectorSpecialValue,
  asSelectorString,
  type SelectorValue,
} from "./selectorTypes";
import type { Task, TaskWithSubtasks, Vision } from "@/services/api";
import { useVisions } from "@/hooks/queries/useVisions";
import { tasksApi } from "@/services/api/tasks";
import { tasksKeys } from "@/services/api/queryKeys";
import { ACTIVE_TASK_STATUSES } from "@/utils/constants";
import { SELECT_LABEL_TEXT_CLASS } from "@/components/forms/styles";
import type { UUID } from "@/types/primitive";
import { logger } from "@/utils/core";

interface TaskSelectorProps {
  value: UUID | null;
  onChange: (taskId: UUID | null) => void;
  placeholder?: string;
  size?: SelectSize;
  disabled?: boolean;
  className?: string;
  filterStatus?: readonly string[];
  allowedTaskIds?: UUID[];
  excludeTaskIds?: UUID[];
  overrideOptions?: { id: UUID; label: string }[];
  preloadedTasks?: Task[];
  deferRemoteLoad?: boolean;
  expandFilterForSelected?: boolean;
  visionId?: UUID | null;
  onTaskSelect?: (
    task: TaskWithSubtasks | null,
    vision?: Vision | null,
  ) => void;
  idPrefix?: string;
  label?: string;
  showLabel?: boolean;
  usePortal?: boolean;
  showSpecialOptions?: boolean;
  showNoTaskOption?: boolean;
  clearBehavior?: "none" | "all";
}

type TaskOptionMeta =
  | { kind: "task"; task: TaskWithSubtasks }
  | { kind: "special"; type: "none" | "has" | "all" };

type TaskEntityOption = EntityOption & { data: TaskOptionMeta };

const SPECIAL_HAS_ID = SelectorSpecialValue.Has as unknown as UUID;
const SPECIAL_ALL_ID = SelectorSpecialValue.All as unknown as UUID;
const TASK_SELECTOR_PAGE_SIZE = 50;
const TASK_SELECTOR_SEARCH_DEBOUNCE_MS = 250;
const SPECIAL_TASK_SELECTOR_VALUES = new Set<string>([
  SelectorSpecialValue.None,
  SelectorSpecialValue.Has,
  SelectorSpecialValue.All,
]);

const isSpecialTaskSelectorValue = (value: UUID | null): boolean =>
  value !== null && SPECIAL_TASK_SELECTOR_VALUES.has(String(value));

const TaskSelector: React.FC<TaskSelectorProps> = (props) => {
  if (props.overrideOptions && props.overrideOptions.length > 0) {
    return <TaskSelectorOverride {...props} />;
  }
  return <TaskSelectorManaged {...props} />;
};

const TaskSelectorOverride: React.FC<TaskSelectorProps> = ({
  value,
  onChange,
  onTaskSelect,
  placeholder,
  size = "sm",
  disabled = false,
  className = "",
  idPrefix = "task-selector",
  label,
  showLabel = true,
  usePortal = false,
  overrideOptions = [],
}) => {
  const { t } = useTranslation();

  const options = useMemo<EntityOption[]>(
    () =>
      overrideOptions.map((opt) => ({
        id: String(opt.id),
        label: opt.label,
      })),
    [overrideOptions],
  );

  const normalizedValue = useMemo<SelectorValue>(() => {
    if (value === null) {
      return undefined;
    }
    return value as SelectorValue;
  }, [value]);

  const handleChange = useCallback(
    (selected: SelectorValue) => {
      const normalized = asSelectorString(selected);
      if (!normalized) {
        onChange(null);
        onTaskSelect?.(null, undefined);
        return;
      }
      onChange(normalized as UUID);
      onTaskSelect?.(null, undefined);
    },
    [onChange, onTaskSelect],
  );

  const effectiveLabel = label ?? t("target.tasks.label");
  const effectivePlaceholder = placeholder ?? t("taskSelector.placeholder");

  return (
    <div className={`relative form-control ${className}`}>
      {showLabel && effectiveLabel && (
        <label htmlFor={`${idPrefix}-override`} className="label">
          <span className={SELECT_LABEL_TEXT_CLASS}>{effectiveLabel}</span>
        </label>
      )}

      <AsyncEntitySelect
        value={normalizedValue}
        onChange={handleChange}
        options={options}
        placeholder={effectivePlaceholder}
        disabled={disabled}
        size={size}
        id={idPrefix ? `${idPrefix}-override` : undefined}
        usePortal={usePortal}
        dropdownMinWidth={280}
        dropdownMaxWidth={320}
        dropdownPreferredWidth={(rect) => Math.max(rect.width, 280)}
      />
    </div>
  );
};

const TaskSelectorManaged: React.FC<TaskSelectorProps> = ({
  value,
  onChange,
  onTaskSelect,
  placeholder,
  size = "sm",
  disabled = false,
  className = "",
  filterStatus = ACTIVE_TASK_STATUSES,
  allowedTaskIds,
  excludeTaskIds,
  preloadedTasks,
  deferRemoteLoad = true,
  expandFilterForSelected = true,
  visionId,
  idPrefix = "task-selector",
  label,
  showLabel = true,
  usePortal = true,
  showSpecialOptions = false,
  showNoTaskOption = true,
  clearBehavior = "none",
}) => {
  const { t } = useTranslation();
  const { visions } = useVisions();

  const {
    options,
    optionLookup,
    isLoading,
    hasMoreOptions,
    isLoadingMore,
    onInteract,
    onLoadMore,
    onSearchQueryChange,
  } = useTaskSelectorOptions({
    value,
    filterStatus,
    allowedTaskIds,
    excludeTaskIds,
    preloadedTasks,
    deferRemoteLoad,
    expandFilterForSelected,
    showSpecialOptions,
    showNoTaskOption,
    visionId,
    translator: t,
  });

  const visionMap = useMemo(() => {
    return new Map<UUID, Vision>(visions.map((vision) => [vision.id, vision]));
  }, [visions]);

  const selectValue = useMemo<SelectorValue>(() => {
    if (value === null) {
      return showNoTaskOption ? SelectorSpecialValue.None : undefined;
    }
    return value as SelectorValue;
  }, [value, showNoTaskOption]);

  const handleSelectChange = useCallback(
    (selected: SelectorValue) => {
      const normalized = asSelectorString(selected);
      if (!normalized) {
        if (clearBehavior === "all") {
          onChange(SPECIAL_ALL_ID);
          onTaskSelect?.(null, undefined);
          return;
        }
        onChange(null);
        onTaskSelect?.(null, undefined);
        return;
      }

      if (normalized === SelectorSpecialValue.None) {
        onChange(null);
        onTaskSelect?.(null, undefined);
        return;
      }

      if (normalized === SelectorSpecialValue.Has) {
        onChange(SPECIAL_HAS_ID);
        onTaskSelect?.(null, undefined);
        return;
      }

      if (normalized === SelectorSpecialValue.All) {
        onChange(SPECIAL_ALL_ID);
        onTaskSelect?.(null, undefined);
        return;
      }

      const meta = optionLookup.get(normalized);
      if (meta?.kind === "task") {
        onChange(meta.task.id);
        const vision = meta.task.vision_id
          ? (visionMap.get(meta.task.vision_id) ?? null)
          : null;
        onTaskSelect?.(meta.task, vision ?? undefined);
        return;
      }

      onChange(normalized as UUID);
      onTaskSelect?.(null, undefined);
    },
    [clearBehavior, onChange, onTaskSelect, optionLookup, visionMap],
  );

  const renderOption = useCallback(
    ({
      option,
      isActive,
      isSelected,
      select,
      highlight,
    }: {
      option: EntityOption;
      index: number;
      isActive: boolean;
      isSelected: boolean;
      select: () => void;
      highlight: () => void;
    }) => {
      const meta = optionLookup.get(option.id);
      const depth = meta?.kind === "task" ? (meta.task.depth ?? 0) : 0;
      const paddingLeft = 12 + depth * 16;

      const optionClasses = [
        "w-full",
        "px-3",
        "py-2",
        "text-left",
        "text-base",
        "transition-colors",
        "focus:outline-none",
        meta?.kind === "special" ? "font-medium" : "",
        isSelected
          ? "bg-primary text-primary-content"
          : isActive
            ? "bg-base-200"
            : "hover:bg-base-200",
      ]
        .filter(Boolean)
        .join(" ");

      return (
        <button
          key={option.id}
          type="button"
          className={optionClasses}
          style={{ paddingLeft }}
          onMouseEnter={highlight}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => select()}
        >
          <span className="block truncate">{option.label}</span>
        </button>
      );
    },
    [optionLookup],
  );

  const effectiveLabel = label ?? t("target.tasks.label");
  const effectivePlaceholder = isLoading
    ? t("common.loading")
    : (placeholder ?? t("taskSelector.placeholder"));
  const disabledState = disabled || isLoading;

  return (
    <div className={`relative form-control ${className}`}>
      {showLabel && effectiveLabel && (
        <label htmlFor={`${idPrefix}-input`} className="label">
          <span className={SELECT_LABEL_TEXT_CLASS}>{effectiveLabel}</span>
        </label>
      )}

      <AsyncEntitySelect
        value={selectValue}
        onChange={handleSelectChange}
        options={options}
        placeholder={effectivePlaceholder}
        disabled={disabledState}
        size={size}
        id={idPrefix ? `${idPrefix}-input` : undefined}
        usePortal={usePortal}
        onFocus={onInteract}
        onClick={onInteract}
        dropdownClassName="max-h-96"
        dropdownMinWidth={480}
        dropdownMaxWidth={800}
        dropdownPreferredWidth={(rect) => Math.max(rect.width, 640)}
        dropdownOffset={4}
        isLoading={isLoading}
        hasMoreOptions={options.length > 0 && hasMoreOptions}
        isLoadingMore={isLoadingMore}
        loadMoreLabel={t("taskSelector.loadMore")}
        onLoadMore={onLoadMore}
        onSearchQueryChange={onSearchQueryChange}
        renderOption={renderOption}
        renderEmpty={(query) => (
          <div className="p-3 text-center text-base-content/60">
            {query ? t("taskSelector.noResults") : t("taskSelector.searchHint")}
          </div>
        )}
        renderLoading={() => (
          <div className="p-3 text-center text-base-content/60">
            <span
              className="loading loading-spinner loading-xs text-primary mr-2"
              aria-hidden="true"
            ></span>
            {t("common.loading")}
          </div>
        )}
      />
    </div>
  );
};

interface UseTaskSelectorOptionsArgs {
  value: UUID | null;
  filterStatus: readonly string[];
  allowedTaskIds?: UUID[];
  excludeTaskIds?: UUID[];
  preloadedTasks?: Task[];
  deferRemoteLoad: boolean;
  expandFilterForSelected: boolean;
  showSpecialOptions: boolean;
  showNoTaskOption: boolean;
  visionId?: UUID | null;
  translator: (key: string, options?: Record<string, unknown>) => string;
}

interface UseTaskSelectorOptionsResult {
  options: TaskEntityOption[];
  optionLookup: Map<string, TaskOptionMeta>;
  isLoading: boolean;
  hasMoreOptions: boolean;
  isLoadingMore: boolean;
  onInteract: () => void;
  onLoadMore: () => void;
  onSearchQueryChange: (query: string) => void;
}

const useTaskSelectorOptions = (
  args: UseTaskSelectorOptionsArgs,
): UseTaskSelectorOptionsResult => {
  const {
    value,
    filterStatus,
    allowedTaskIds,
    excludeTaskIds,
    preloadedTasks,
    deferRemoteLoad,
    expandFilterForSelected,
    showSpecialOptions,
    showNoTaskOption,
    visionId,
    translator,
  } = args;

  const [hasInteracted, setHasInteracted] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [extraTasks, setExtraTasks] = useState<Task[]>([]);
  const shouldRemoteLoad = !deferRemoteLoad || hasInteracted || !!value;

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearchQuery(searchQuery.trim());
    }, TASK_SELECTOR_SEARCH_DEBOUNCE_MS);

    return () => window.clearTimeout(timer);
  }, [searchQuery]);

  const statusIn = useMemo(
    () => (filterStatus.length > 0 ? [...filterStatus] : undefined),
    [filterStatus],
  );

  const selectorQuery = useInfiniteQuery({
    queryKey: tasksKeys.selectorSearch({
      visionId,
      query: debouncedSearchQuery,
      statusIn,
    }),
    queryFn: ({ pageParam }) =>
      tasksApi.searchSelectorPage({
        visionId,
        query: debouncedSearchQuery,
        statusIn,
        page: pageParam,
        pageSize: TASK_SELECTOR_PAGE_SIZE,
        fields: "basic",
      }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const currentPage = lastPage.pagination?.page ?? 1;
      const totalPages = lastPage.pagination?.pages ?? 0;
      return currentPage < totalPages ? currentPage + 1 : undefined;
    },
    enabled: shouldRemoteLoad,
  });

  const remoteTasks = useMemo(
    () =>
      (selectorQuery.data?.pages.flatMap((page) => page.items) ?? []).filter(
        (task) => !(task as { deleted_at?: string | null }).deleted_at,
      ),
    [selectorQuery.data],
  );

  const sanitizedPreloaded = useMemo(
    () =>
      (preloadedTasks ?? []).filter(
        (task) => !(task as { deleted_at?: string | null }).deleted_at,
      ),
    [preloadedTasks],
  );

  const baseTasks = useMemo(() => {
    const map = new Map<UUID, Task>();
    const addTasks = (tasks?: Task[]) => {
      tasks?.forEach((task) => {
        if (!task) return;
        if ((task as { deleted_at?: string | null }).deleted_at) return;
        if (!map.has(task.id)) {
          map.set(task.id, task);
        }
      });
    };

    addTasks(sanitizedPreloaded as Task[]);
    addTasks(remoteTasks);
    addTasks(extraTasks);

    return Array.from(map.values());
  }, [sanitizedPreloaded, remoteTasks, extraTasks]);

  const selectedTaskId = useMemo<UUID | null>(() => {
    if (!value) return null;
    if (isSpecialTaskSelectorValue(value)) {
      return null;
    }
    return value;
  }, [value]);

  useEffect(() => {
    if (!selectedTaskId) return;
    const exists = baseTasks.some((task) => task.id === selectedTaskId);
    if (exists) return;

    let cancelled = false;
    (async () => {
      try {
        const fetched = await tasksApi.getById(selectedTaskId);
        if (!cancelled) {
          setExtraTasks((prev) => {
            if (prev.some((task) => task.id === fetched.id)) {
              return prev;
            }
            return [...prev, fetched];
          });
        }
      } catch (error) {
        if (!cancelled) {
          logger.warn("Failed to fetch selected task for TaskSelector", error);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedTaskId, baseTasks]);

  const statusFilteredTasks = useMemo(() => {
    if (!filterStatus || filterStatus.length === 0) {
      return baseTasks;
    }
    const allowedStatuses = new Set(filterStatus);
    if (expandFilterForSelected && selectedTaskId) {
      const selected = baseTasks.find((task) => task.id === selectedTaskId);
      if (selected && !allowedStatuses.has(selected.status)) {
        allowedStatuses.add(selected.status);
      }
    }
    return baseTasks.filter((task) => allowedStatuses.has(task.status));
  }, [baseTasks, filterStatus, expandFilterForSelected, selectedTaskId]);

  const allowedFilteredTasks = useMemo(() => {
    if (!allowedTaskIds || allowedTaskIds.length === 0) {
      return statusFilteredTasks;
    }
    const allow = new Set(allowedTaskIds);
    return statusFilteredTasks.filter((task) => allow.has(task.id));
  }, [statusFilteredTasks, allowedTaskIds]);

  const excludedFilteredTasks = useMemo(() => {
    if (!excludeTaskIds || excludeTaskIds.length === 0) {
      return allowedFilteredTasks;
    }
    const excluded = new Set(excludeTaskIds);
    return allowedFilteredTasks.filter((task) => !excluded.has(task.id));
  }, [allowedFilteredTasks, excludeTaskIds]);

  const visionFilteredTasks = useMemo(() => {
    if (visionId === undefined || visionId === null) {
      return excludedFilteredTasks;
    }
    return excludedFilteredTasks.filter((task) => task.vision_id === visionId);
  }, [excludedFilteredTasks, visionId]);

  const hierarchy = useMemo(
    () => buildTaskHierarchy(visionFilteredTasks),
    [visionFilteredTasks],
  );

  const flattenedTasks = useMemo(
    () => flattenTaskHierarchy(hierarchy),
    [hierarchy],
  );

  const options = useMemo<TaskEntityOption[]>(() => {
    const entries: TaskEntityOption[] = [];
    const ensureOption = (id: string, label: string, meta: TaskOptionMeta) => {
      if (!entries.some((existing) => existing.id === id)) {
        entries.push({ id, label, data: meta });
      }
    };

    if (showNoTaskOption) {
      ensureOption(
        SelectorSpecialValue.None,
        translator("timeLog.searchResults.noTask"),
        {
          kind: "special",
          type: "none",
        },
      );
    }

    if (showSpecialOptions) {
      ensureOption(
        SelectorSpecialValue.None,
        translator("timeLog.searchResults.noTask"),
        {
          kind: "special",
          type: "none",
        },
      );
      ensureOption(
        SelectorSpecialValue.All,
        translator("taskSelector.specialOptions.allTasks"),
        {
          kind: "special",
          type: "all",
        },
      );
      ensureOption(
        SelectorSpecialValue.Has,
        translator("taskSelector.specialOptions.hasTask"),
        {
          kind: "special",
          type: "has",
        },
      );
    }

    flattenedTasks.forEach((task) => {
      entries.push({
        id: task.id,
        label: task.content,
        data: { kind: "task", task },
      });
    });

    return entries;
  }, [flattenedTasks, showNoTaskOption, showSpecialOptions, translator]);

  const optionLookup = useMemo(() => {
    return new Map<string, TaskOptionMeta>(
      options.map((option) => [option.id, option.data]),
    );
  }, [options]);

  const hasPreloaded = sanitizedPreloaded.length > 0;
  const shouldShowLoading =
    (!deferRemoteLoad || baseTasks.length === 0) &&
    selectorQuery.isLoading &&
    !hasPreloaded;

  return {
    options,
    optionLookup,
    isLoading: shouldShowLoading,
    hasMoreOptions: Boolean(selectorQuery.hasNextPage),
    isLoadingMore: selectorQuery.isFetchingNextPage,
    onInteract: () => setHasInteracted(true),
    onLoadMore: () => {
      if (selectorQuery.hasNextPage && !selectorQuery.isFetchingNextPage) {
        void selectorQuery.fetchNextPage();
      }
    },
    onSearchQueryChange: setSearchQuery,
  };
};

const buildTaskHierarchy = (flatTasks: Task[]): TaskWithSubtasks[] => {
  const taskMap = new Map<UUID, TaskWithSubtasks>();
  const rootTasks: TaskWithSubtasks[] = [];

  flatTasks.forEach((task) => {
    taskMap.set(task.id, {
      ...task,
      subtasks: [],
      completion_percentage:
        (task as TaskWithSubtasks).completion_percentage ?? 0,
      depth: 0,
    });
  });

  flatTasks.forEach((task) => {
    const current = taskMap.get(task.id);
    if (!current) return;

    const parentId = task.parent_task_id ?? null;
    if (parentId) {
      const parent = taskMap.get(parentId);
      if (parent) {
        current.depth = parent.depth + 1;
        parent.subtasks.push(current);
        return;
      }
    }

    rootTasks.push(current);
  });

  return rootTasks;
};

const flattenTaskHierarchy = (
  tasks: TaskWithSubtasks[],
): TaskWithSubtasks[] => {
  const result: TaskWithSubtasks[] = [];
  const traverse = (task: TaskWithSubtasks, depth: number) => {
    const clone: TaskWithSubtasks = {
      ...task,
      depth,
      subtasks: task.subtasks ?? [],
    };
    result.push(clone);
    (task.subtasks ?? []).forEach((child) => traverse(child, depth + 1));
  };

  tasks.forEach((task) => traverse(task, task.depth ?? 0));
  return result;
};

export default TaskSelector;
