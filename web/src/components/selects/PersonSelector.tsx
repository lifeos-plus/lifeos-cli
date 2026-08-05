import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import AsyncEntityMultiSelect, {
  type MultiSelectOption,
} from "./AsyncEntityMultiSelect";
import { personsApi } from "@/services/api/persons";
import { usePersonsList as usePersons } from "@/hooks/queries/usePersonsList";
import type { PersonSummary } from "@/services/api";
import { logger } from "@/utils/core";
import type { UUID } from "@/types/primitive";
import { Icon } from "@/components/icons";

interface PersonSelectorProps {
  selectedPersonIds: UUID[];
  onSelectionChange: (personIds: UUID[]) => void;
  placeholder?: string;
  size?: "sm" | "md" | "lg";
  multiple?: boolean;
  disabled?: boolean;
  className?: string;
  variant?: "compact" | "detailed";
  usePortal?: boolean;
  menuMaxHeight?: number;
  idPrefix?: string;
  label?: string;
  showLabel?: boolean;
  showNoPersonOption?: boolean;
  selectedListMaxHeight?: number;
  selectedPlacement?: "inline" | "below";
}

const filterValidUUIDs = (ids: UUID[]): UUID[] =>
  ids.filter((id) => id && id.trim() && id !== "");

const matchesPerson = (person: PersonSummary, query: string) => {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  if ((person.display_name ?? person.name ?? "").toLowerCase().includes(normalized)) return true;
  if (person.primary_nickname?.toLowerCase().includes(normalized)) return true;
  return (person.tags ?? []).some((tag) =>
    tag.name.toLowerCase().includes(normalized),
  );
};

const PersonSelector: React.FC<PersonSelectorProps> = ({
  selectedPersonIds,
  onSelectionChange,
  placeholder,
  size = "sm",
  multiple = true,
  disabled = false,
  className = "",
  variant = "compact",
  usePortal = true,
  menuMaxHeight = 240,
  label,
  showLabel = true,
  showNoPersonOption = true,
  selectedListMaxHeight,
  selectedPlacement = "inline",
}) => {
  const { t } = useTranslation();
  const defaultPlaceholder = placeholder ?? t("common.please_select");
  const effectiveLabel = label ?? t("target.persons.label");

  const [searchTerm, setSearchTerm] = useState("");
  const [remotePersons, setRemotePersons] = useState<PersonSummary[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  const { persons: personsFromCache, loading: personsLoading } = usePersons();

  const sanitizedSelectedIds = useMemo(
    () => filterValidUUIDs(selectedPersonIds),
    [selectedPersonIds],
  );

  useEffect(() => {
    if (sanitizedSelectedIds.length !== selectedPersonIds.length) {
      onSelectionChange(sanitizedSelectedIds);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!searchTerm.trim()) {
      setRemotePersons([]);
      setSearchLoading(false);
      return;
    }

    let cancelled = false;
    setSearchLoading(true);
    const handler = window.setTimeout(async () => {
      try {
        const data = await personsApi.getAll(1, 100, searchTerm.trim());
        if (!cancelled) {
          setRemotePersons(Array.isArray(data.items) ? data.items : []);
        }
      } catch (error) {
        if (!cancelled) {
          logger.error("Failed to search persons:", error);
        }
      } finally {
        if (!cancelled) {
          setSearchLoading(false);
        }
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(handler);
    };
  }, [searchTerm]);

  const availablePersons: PersonSummary[] = useMemo(() => {
    const query = searchTerm.trim();
    if (query) {
      if (remotePersons.length > 0) {
        return remotePersons;
      }
      const base = personsFromCache ?? [];
      return base.filter((person) => matchesPerson(person, query));
    }
    if (personsFromCache && personsFromCache.length > 0) {
      return personsFromCache;
    }
    return remotePersons;
  }, [personsFromCache, remotePersons, searchTerm]);

  const knownPersonsMap = useMemo(() => {
    const map = new Map<UUID, PersonSummary>();
    (personsFromCache ?? []).forEach((person) => map.set(person.id, person));
    remotePersons.forEach((person) => map.set(person.id, person));
    availablePersons.forEach((person) => map.set(person.id, person));
    return map;
  }, [availablePersons, personsFromCache, remotePersons]);

  const options: MultiSelectOption[] = useMemo(() => {
    const unique = new Map<UUID, PersonSummary>();
    availablePersons.forEach((person) => unique.set(person.id, person));
    sanitizedSelectedIds.forEach((id) => {
      if (!unique.has(id)) {
        const existing = knownPersonsMap.get(id);
        if (existing) unique.set(id, existing);
      }
    });
    return Array.from(unique.values()).map((person) => ({
      id: person.id,
      label: person.display_name ?? person.name ?? "",
      data: person,
    }));
  }, [availablePersons, knownPersonsMap, sanitizedSelectedIds]);

  const filterOptions = useCallback(
    (items: MultiSelectOption[], query: string) => {
      const normalized = query.trim().toLowerCase();
      if (!normalized) return items;
      return items.filter((option) => {
        const person = option.data as PersonSummary | undefined;
        if (option.label.toLowerCase().includes(normalized)) return true;
        if (person?.primary_nickname?.toLowerCase().includes(normalized)) {
          return true;
        }
        return person?.tags?.some((tag) =>
          tag.name.toLowerCase().includes(normalized),
        );
      });
    },
    [],
  );

  const renderOption = useCallback(
    ({
      option,
      isSelected,
      select,
      highlight,
    }: {
      option: MultiSelectOption;
      index: number;
      isActive: boolean;
      isSelected: boolean;
      select: () => void;
      highlight: () => void;
    }) => {
      const person = option.data as PersonSummary | undefined;
      const displayName = person?.display_name ?? option.label;
      const nickname = person?.primary_nickname;
      const tags = person?.tags ?? [];

      return (
        <button
          key={option.id}
          type="button"
          onMouseEnter={highlight}
          onMouseDown={(event) => event.preventDefault()}
          onClick={select}
          className={`w-full px-3 ${
            variant === "compact" ? "py-1.5" : "py-2"
          } text-left text-base transition-colors flex items-center justify-between ${
            isSelected
              ? "bg-primary text-primary-content"
              : "hover:bg-base-200 text-base-content"
          }`}
        >
          <div className="flex-1 min-w-0">
            <div className="font-medium truncate">{displayName}</div>
            {variant === "detailed" && nickname && nickname !== displayName && (
              <div className="text-sm opacity-80 truncate">{nickname}</div>
            )}
            {variant === "detailed" && tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {tags.slice(0, 4).map((tag) => (
                  <span
                    key={tag.id}
                    className="inline-block px-1 py-0.5 bg-primary/10 text-primary text-sm rounded border border-primary/20"
                  >
                    {tag.name}
                  </span>
                ))}
                {tags.length > 4 && (
                  <span className="text-sm text-base-content/50">
                    +{tags.length - 4}
                  </span>
                )}
              </div>
            )}
          </div>
          {isSelected && (
            <Icon name="check" size={16} aria-hidden className="ml-2" />
          )}
        </button>
      );
    },
    [variant],
  );

  const renderTag = useCallback(
    ({ option, remove }: { option: MultiSelectOption; remove: () => void }) => {
      const person = option.data as PersonSummary | undefined;
      const labelText = person?.display_name ?? option.label;
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 bg-primary/15 text-primary text-sm rounded-md border border-primary/30">
          <span className="truncate max-w-[8rem]">{labelText}</span>
          {!disabled && (
            <button
              type="button"
              className="text-primary hover:text-primary/80"
              onClick={(event) => {
                event.stopPropagation();
                remove();
              }}
            >
              ×
            </button>
          )}
        </span>
      );
    },
    [disabled],
  );

  const handleSelectionChange = useCallback(
    (ids: string[]) => {
      const normalized = filterValidUUIDs(ids as UUID[]);
      if (multiple) {
        onSelectionChange(normalized);
      } else {
        onSelectionChange(normalized.slice(-1));
      }
    },
    [multiple, onSelectionChange],
  );

  const effectiveSelectedIds = multiple
    ? sanitizedSelectedIds
    : sanitizedSelectedIds.slice(-1);

  return (
    <AsyncEntityMultiSelect
      selectedIds={effectiveSelectedIds}
      onSelectionChange={handleSelectionChange}
      options={options}
      placeholder={defaultPlaceholder}
      size={size}
      className={className}
      multiple={multiple}
      disabled={disabled}
      label={showLabel ? effectiveLabel : undefined}
      showLabel={showLabel}
      usePortal={usePortal}
      dropdownMaxHeight={menuMaxHeight}
      isLoading={personsLoading || searchLoading}
      renderOption={renderOption}
      renderTag={renderTag}
      renderEmpty={(query) => (
        <div className="p-3 text-center text-base-content/60">
          {query ? t("common.no_options") : t("common.no_data")}
        </div>
      )}
      searchValue={searchTerm}
      onSearchChange={setSearchTerm}
      filterOptions={filterOptions}
      showClearOption={showNoPersonOption}
      clearOptionLabel={t("common.none")}
      selectedContainerMaxHeight={selectedListMaxHeight}
      selectedPlacement={selectedPlacement}
    />
  );
};

export default PersonSelector;
