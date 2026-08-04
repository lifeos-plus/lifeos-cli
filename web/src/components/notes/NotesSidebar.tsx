import { useCallback } from "react";
import type { MouseEvent } from "react";
import { useTranslation } from "react-i18next";
import type { PersonSummary, Tag } from "@/services/api";
import ActionButton from "@/components/ActionButton";
import { Icon } from "@/components/icons";
import type { IconName } from "@/components/icons";
import Badge from "@/components/common/Badge";
import Card from "@/layouts/Card";
import ExpandableCard from "@/components/ExpandableCard";
import { TextInput } from "@/components/forms";
import type { UUID } from "@/types/primitive";
import { usePersistentState } from "@/hooks/usePersistentState";

interface NotesSidebarProps {
  uniquePersons: PersonSummary[];
  availableNoteTags: Tag[];
  tagUsageStats: { [key: UUID]: number };
  personUsageStats: { [key: UUID]: number };
  selectedFilterTags: Tag[];
  selectedFilterPersons: PersonSummary[];
  searchKeyword: string;
  showUntaggedOnly: boolean;
  onTagToggle: (tag: Tag) => void;
  onPersonToggle: (person: PersonSummary) => void;
  onSearchKeywordChange: (keyword: string) => void;
  onApplyFilters: () => void;
  onUntaggedToggle: () => void;
  isLoadingStats?: boolean;
}

interface NotesFilterOptionProps {
  label: string;
  countLabel: string;
  iconName: IconName;
  selected: boolean;
  onClick: (event: MouseEvent<HTMLButtonElement>) => void;
}

function NotesFilterOption({
  label,
  countLabel,
  iconName,
  selected,
  onClick,
}: NotesFilterOptionProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center justify-between rounded-lg p-1.5 transition-colors ${
        selected
          ? "bg-primary/10 text-primary"
          : "bg-base-100 hover:bg-primary/10"
      }`}
    >
      <span
        className={`flex items-center gap-1 text-sm font-medium ${
          selected ? "text-primary" : "text-base-content"
        }`}
      >
        <Icon name={iconName} size={16} className="text-primary" aria-hidden />
        {label}
      </span>
      <Badge
        tone={selected ? "primary" : "ghost"}
        size="xs"
        className="flex-shrink-0"
      >
        {countLabel}
      </Badge>
    </button>
  );
}

export function NotesSidebar({
  uniquePersons,
  availableNoteTags,
  tagUsageStats,
  personUsageStats,
  selectedFilterTags,
  selectedFilterPersons,
  searchKeyword,
  showUntaggedOnly,
  onTagToggle,
  onPersonToggle,
  onSearchKeywordChange,
  onApplyFilters,
  onUntaggedToggle,
  isLoadingStats = false,
}: NotesSidebarProps) {
  const { t } = useTranslation();
  // Section expansion state with persistence to avoid collapse on remount
  const STORAGE_KEY = "notesSidebar.expandedSections";
  const { state: expandedSections, setState: setExpandedSections } =
    usePersistentState<{ tags: boolean; persons: boolean }>({
      key: STORAGE_KEY,
      defaultValue: { tags: true, persons: false },
      expireInHours: 0,
    });

  /**
   * Toggle section expansion
   */
  const toggleSection = useCallback(
    (section: "tags" | "persons") => {
      setExpandedSections((prev) => ({
        ...prev,
        [section]: !prev[section],
      }));
    },
    [setExpandedSections],
  );

  return (
    <div className="w-full max-w-full flex-shrink-0 space-y-4">
      {/* Search Section */}
      <Card title={t("notesSidebar.searchContent")} className="h-auto mb-0">
        <div className="space-y-3">
          <div>
            <TextInput
              id="note-search"
              name="note-search"
              type="text"
              value={searchKeyword}
              onChange={(e) => onSearchKeywordChange(e.target.value)}
              placeholder={t("notesSidebar.searchPlaceholder")}
              className="text-sm"
            />
          </div>
          <div className="flex gap-2">
            <ActionButton
              label={t("notesSidebar.search")}
              onClick={onApplyFilters}
              color="primary"
              variant="solid"
              className="flex-1"
            />
          </div>
        </div>
      </Card>

      {/* Persons Section */}
      <ExpandableCard
        isExpanded={expandedSections.persons}
        onToggleExpansion={() => toggleSection("persons")}
        title={
          <h3 className="text-base font-semibold text-base-content">
            {t("notesSidebar.relatedPersons")}
          </h3>
        }
        elevation="subtle"
      >
        <div className="px-4 pb-4 max-h-[40vh] overflow-y-auto">
          {(() => {
            if (isLoadingStats) {
              return (
                <p className="text-base text-base-content">
                  {t("common.loading")}
                </p>
              );
            }

            if (uniquePersons.length === 0) {
              return (
                <p className="text-base text-base-content">
                  {t("notesSidebar.noRelatedPersons")}
                </p>
              );
            }

            return (
              <div className="space-y-1">
                {uniquePersons.map((person) => {
                  const usageCount = personUsageStats[person.id] || 0;
                  const isSelected = selectedFilterPersons.some(
                    (p) => p.id === person.id,
                  );
                  return (
                    <NotesFilterOption
                      key={person.id}
                      label={`@${person.display_name}`}
                      countLabel={`(${usageCount})`}
                      iconName="people"
                      selected={isSelected}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onPersonToggle(person);
                        // keep section expanded
                        setExpandedSections((prev) => ({
                          ...prev,
                          persons: true,
                        }));
                      }}
                    />
                  );
                })}
              </div>
            );
          })()}
        </div>
      </ExpandableCard>

      {/* Tags Section */}
      <ExpandableCard
        isExpanded={expandedSections.tags}
        onToggleExpansion={() => toggleSection("tags")}
        title={
          <h3 className="text-base font-semibold text-base-content">
            {t("target.tag")}
          </h3>
        }
        elevation="subtle"
      >
        <div className="px-4 pb-4 max-h-[40vh] overflow-y-auto">
          {isLoadingStats ? (
            <p className="text-base text-base-content">{t("common.loading")}</p>
          ) : (
            <div className="space-y-1">
              {/* Untagged filter option - always shown at the top */}
              <NotesFilterOption
                label={t("notesSidebar.untagged")}
                countLabel={`(${t("notesSidebar.pinned")})`}
                iconName="document-text"
                selected={showUntaggedOnly}
                onClick={onUntaggedToggle}
              />

              {/* Regular tags */}
              {availableNoteTags.length === 0 ? (
                <p className="text-base text-base-content">
                  {t("notesSidebar.noTags")}
                </p>
              ) : (
                availableNoteTags.map((tag) => {
                  const usageCount = tagUsageStats[tag.id] || 0;
                  const isSelected = selectedFilterTags.some(
                    (t) => t.id === tag.id,
                  );
                  return (
                    <NotesFilterOption
                      key={tag.id}
                      label={`#${tag.name}`}
                      countLabel={`(${usageCount})`}
                      iconName="tag"
                      selected={isSelected}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onTagToggle(tag);
                        // keep section expanded
                        setExpandedSections((prev) => ({
                          ...prev,
                          tags: true,
                        }));
                      }}
                    />
                  );
                })
              )}
            </div>
          )}
        </div>
      </ExpandableCard>
    </div>
  );
}
