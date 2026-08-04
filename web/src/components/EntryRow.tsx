import React from "react";
import { useTranslation } from "react-i18next";
import type { ProcessedEntry, PlaceholderEntry } from "@/utils/datetime";
import {
  formatDate,
  formatDateInTimezone,
  formatDurationFromTimes,
} from "@/utils/datetime";
import TimeRangeText from "./TimeRangeText";
import AreaBadge from "./AreaBadge";
import PersonsList from "./PersonsList";
import ActionButton, { EditButton, DeleteButton } from "./ActionButton";
import { ActionButtonGroup } from "./ActionButton";
import Checkbox from "./forms/Checkbox";
import type { UUID } from "@/types/primitive";
import type { QueryMode } from "@/hooks/useQueryMode";

interface EntryRowProps {
  entry: ProcessedEntry;
  index: number;
  isSelectMode: boolean;
  selected: boolean;
  onSelectChange: (id: UUID, checked: boolean) => void;
  onEdit: (entry: ProcessedEntry) => void;
  onDelete: (id: UUID) => void;
  onPlaceholderClick: (placeholder: PlaceholderEntry) => void;
  onCreateNote?: (entry: ProcessedEntry) => void;
  onViewNotes?: (entry: ProcessedEntry) => void;
  areaMap: Map<UUID, { name: string; color: string }>;
  selectedDate: Date;
  timezone?: string;
  queryMode: QueryMode;
  onHoverTooltip?: (
    entry: ProcessedEntry,
    position: { x: number; y: number },
  ) => void;
  onHoverMove?: (
    entry: ProcessedEntry,
    position: { x: number; y: number },
  ) => void;
  onHoverLeave?: () => void;
  onFocusTooltip?: (entry: ProcessedEntry, element: HTMLElement) => void;
  onBlurTooltip?: () => void;
}

const EntryRowComponent: React.FC<EntryRowProps> = ({
  entry,
  index,
  isSelectMode,
  selected,
  onSelectChange,
  onEdit,
  onDelete,
  onPlaceholderClick,
  onCreateNote,
  onViewNotes,
  areaMap,
  selectedDate,
  timezone,
  queryMode,
  onHoverTooltip,
  onHoverMove,
  onHoverLeave,
  onFocusTooltip,
  onBlurTooltip,
}) => {
  const { t } = useTranslation();
  const hasLinkedNotes = (entry.linked_notes?.length ?? 0) > 0;
  const subduedViewNotesClass =
    "opacity-40 hover:opacity-60 transition-opacity";
  const isPlaceholder = Boolean(entry.isPlaceholder);
  let rowClassName = "transition-colors ";
  if (isPlaceholder) {
    rowClassName += "bg-warning/20 hover:bg-warning/30";
  } else if (entry.validationResult && !entry.validationResult.isValid) {
    rowClassName += "bg-error/20 hover:bg-error/30";
  } else {
    rowClassName +=
      index % 2 === 0
        ? "bg-base-100 hover:bg-base-200"
        : "bg-base-200/30 hover:bg-base-200";
  }

  // Calculate display date
  const getDisplayDate = () => {
    if (queryMode === "single") {
      // Single day mode: show selected date
      return formatDateInTimezone(selectedDate, timezone);
    } else {
      // Advanced query mode: show actual record date
      if (entry.start_time) {
        return formatDate(entry.start_time, timezone);
      }
      return "-";
    }
  };

  return (
    <tr className={rowClassName}>
      {isSelectMode && (
        <td className="px-4 py-3 text-center">
          {!entry.isPlaceholder ? (
            <Checkbox
              id={`entry-${entry.id}-select`}
              name={`entry-${entry.id}-select`}
              checked={selected}
              onCheckedChange={(checked) => onSelectChange(entry.id, checked)}
              variant="primary"
              size="sm"
              aria-label={t("entryRow.selectRecord", { id: entry.id })}
            />
          ) : (
            <span className="text-base text-base-content/50">-</span>
          )}
        </td>
      )}

      <td className="px-4 py-3 whitespace-nowrap">
        <div className="text-base font-medium text-base-content">
          {getDisplayDate()}
        </div>
      </td>

      <td className="px-4 py-3 whitespace-nowrap">
        <TimeRangeText
          start={entry.start_time}
          end={entry.end_time}
          timezone={timezone}
        />
      </td>

      <td className="px-4 py-3 whitespace-nowrap">
        <span className="text-base font-mono text-base-content">
          {formatDurationFromTimes(entry.start_time, entry.end_time)}
        </span>
      </td>

      <td className="px-4 py-3 whitespace-nowrap">
        <AreaBadge
          areaId={entry.area_id || undefined}
          areaMap={areaMap}
        />
      </td>

      <td
        className="px-4 py-3"
        tabIndex={isPlaceholder ? -1 : 0}
        onMouseEnter={(event) => {
          if (isPlaceholder) {
            return;
          }
          onHoverTooltip?.(entry, {
            x: event.clientX,
            y: event.clientY,
          });
        }}
        onMouseMove={(event) => {
          if (isPlaceholder) {
            return;
          }
          onHoverMove?.(entry, {
            x: event.clientX,
            y: event.clientY,
          });
        }}
        onMouseLeave={() => {
          if (isPlaceholder) {
            return;
          }
          onHoverLeave?.();
        }}
        onFocus={(event) => {
          if (isPlaceholder) {
            return;
          }
          onFocusTooltip?.(entry, event.currentTarget);
        }}
        onBlur={() => {
          if (isPlaceholder) {
            return;
          }
          onBlurTooltip?.();
        }}
      >
        <div className="text-base font-medium text-base-content">
          {entry.title}
        </div>
      </td>

      <td className="px-4 py-3 whitespace-nowrap">
        {!entry.isPlaceholder && entry.task ? (
          <div className="text-base">
            <div className="flex items-center">
              <span className="text-base text-base-content/80">
                {entry.task.content.length > 15
                  ? `${entry.task.content.substring(0, 15)}...`
                  : entry.task.content}
              </span>
            </div>
          </div>
        ) : (
          <span className="text-base text-base-content/50">-</span>
        )}
      </td>

      <td className="px-4 py-3 whitespace-nowrap">
        {!entry.isPlaceholder ? (
          <PersonsList people={entry.people} />
        ) : (
          <span className="text-base text-base-content/50">-</span>
        )}
      </td>

      <td className="px-4 py-3 whitespace-nowrap text-center">
        <div className="flex justify-center gap-1" data-tooltip-exempt>
          {entry.isPlaceholder ? (
            <ActionButton
              label={t("quickTimeEntry.title")}
              iconName="bolt"
              color="primary"
              ariaLabel={t("entryRow.quickAddAriaLabel")}
              onClick={(e) => {
                e.stopPropagation();
                // Narrow type via runtime guard instead of double assertion
                if (entry.isPlaceholder) {
                  onPlaceholderClick(entry as PlaceholderEntry);
                }
              }}
            />
          ) : (
            <ActionButtonGroup gap="sm" align="center">
              <EditButton onClick={() => onEdit(entry)} />
              {onCreateNote && (
                <ActionButton
                  label={t("common.add")}
                  iconName="document-plus"
                  color="primary"
                  onClick={() => onCreateNote(entry)}
                  iconOnly
                  ariaLabel={t("notes.actions.addNote")}
                />
              )}
              {onViewNotes && (
                <ActionButton
                  label={t("notes.actions.viewNotes")}
                  iconName="book-open"
                  color={hasLinkedNotes ? "primary" : "neutral"}
                  className={hasLinkedNotes ? undefined : subduedViewNotesClass}
                  onClick={() => onViewNotes(entry)}
                  iconOnly
                  ariaLabel={t("notes.actions.viewNotes")}
                />
              )}
              <DeleteButton onClick={() => onDelete(entry.id)} />
            </ActionButtonGroup>
          )}
        </div>
      </td>
    </tr>
  );
};

const EntryRow = React.memo(
  EntryRowComponent,
  (prev, next) =>
    prev.entry === next.entry &&
    prev.index === next.index &&
    prev.isSelectMode === next.isSelectMode &&
    prev.selected === next.selected &&
    prev.areaMap === next.areaMap &&
    prev.selectedDate === next.selectedDate &&
    prev.queryMode === next.queryMode &&
    prev.onSelectChange === next.onSelectChange &&
    prev.onEdit === next.onEdit &&
    prev.onDelete === next.onDelete &&
    prev.onPlaceholderClick === next.onPlaceholderClick &&
    prev.onCreateNote === next.onCreateNote &&
    prev.onViewNotes === next.onViewNotes &&
    prev.onHoverTooltip === next.onHoverTooltip &&
    prev.onHoverMove === next.onHoverMove &&
    prev.onHoverLeave === next.onHoverLeave &&
    prev.onFocusTooltip === next.onFocusTooltip &&
    prev.onBlurTooltip === next.onBlurTooltip,
);

export default EntryRow;
