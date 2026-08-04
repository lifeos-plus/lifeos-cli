import { useState, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { areasApi, type Area } from "@/services/api/areas";
import { logger } from "@/utils/core";
import type { UUID } from "@/types/primitive";
import ActionButton from "./ActionButton";
import { UNKNOWN_AREA_COLOR } from "@/utils/areaColors";

interface AreaSorterProps {
  areaOrder: UUID[];
  onOrderChange: (order: UUID[]) => void;
  loading?: boolean;
  disabled?: boolean;
  refreshTrigger?: number; // Add refresh trigger prop
  id?: string; // Add id prop for accessibility
  /** Whether to show a Clear All option */
  showClearAll?: boolean;
}

export default function AreaSorter({
  areaOrder,
  onOrderChange,
  loading = false,
  disabled = false,
  refreshTrigger,
  id,
  showClearAll = true,
}: AreaSorterProps) {
  const { t } = useTranslation();
  const [areas, setAreas] = useState<Area[]>([]);
  const [areasLoading, setAreasLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load areas
  useEffect(() => {
    const loadAreas = async () => {
      try {
        setAreasLoading(true);
        setError(null);
        const response = await areasApi.getAreas();
        setAreas(response.items ?? []);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to load areas";
        setError(errorMessage);
        logger.error("Failed to load areas", err);
      } finally {
        setAreasLoading(false);
      }
    };

    loadAreas();
  }, [refreshTrigger]); // Add refreshTrigger as dependency

  const { allAreaIds, completeOrder } = useMemo(() => {
    const ids = areas.map((d) => d.id);
    const filteredOrder = areaOrder.filter((id) => ids.includes(id));
    const missing = ids.filter((id) => !filteredOrder.includes(id));

    return {
      allAreaIds: ids,
      completeOrder: [...filteredOrder, ...missing],
    };
  }, [areas, areaOrder]);

  // Handle move up/down buttons based on the complete order we display
  const moveArea = (areaId: UUID, direction: "up" | "down") => {
    const workingOrder = [...completeOrder];
    const currentIndex = workingOrder.indexOf(areaId);

    if (currentIndex === -1) return;

    const newIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;

    if (newIndex < 0 || newIndex >= workingOrder.length) return;

    [workingOrder[currentIndex], workingOrder[newIndex]] = [
      workingOrder[newIndex],
      workingOrder[currentIndex],
    ];

    onOrderChange(workingOrder);
  };

  const allOrderedAreas = completeOrder
    .map((id) => areas.find((d) => d.id === id))
    .filter((d): d is Area => d !== undefined);

  if (areasLoading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="text-sm text-base-content/60">
          {t("settings.areaSorter.loading")}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-error bg-error/20 rounded">
        {t("settings.areaSorter.error", { message: error })}
      </div>
    );
  }

  if (allOrderedAreas.length === 0) {
    return (
      <div className="p-4 text-sm bg-base-200 rounded">
        {t("settings.areaSorter.empty")}
      </div>
    );
  }

  return (
    <div
      id={id}
      role="group"
      aria-label={t("settings.areaSorter.groupLabel")}
      className="space-y-2"
    >
      <div className="flex items-center justify-between text-sm mb-2">
        <span>{t("settings.areaSorter.instructions")}</span>
        {showClearAll && (
          <ActionButton
            label={t("settings.areaSorter.clearAll")}
            size="xs"
            variant="ghost"
            onClick={() => onOrderChange([...allAreaIds])}
            disabled={disabled || loading || completeOrder.length === 0}
            ariaLabel={t("settings.areaSorter.clearAllAria")}
            className="h-7"
          />
        )}
      </div>
      <div
        role="list"
        aria-label={t("settings.areaSorter.listLabel")}
        className="space-y-1"
      >
        {allOrderedAreas.map((area, index) => {
          return (
            <div
              key={area.id}
              role="listitem"
              aria-label={t("settings.areaSorter.itemLabel", {
                name: area.name,
                position: index + 1,
              })}
              className={`flex min-w-0 items-center gap-2 overflow-hidden rounded border p-2 transition-colors ${
                disabled || loading
                  ? "bg-base-200 cursor-not-allowed opacity-60"
                  : "bg-base-100 transition-all hover:bg-base-300 hover:shadow-md"
              }`}
            >
              {/* Order number */}
              <div className="w-6 h-6 bg-base-300 rounded-full flex items-center justify-center text-sm font-medium">
                {index + 1}
              </div>

              {/* Area color indicator */}
              <div
                className="w-4 h-4 rounded-full border"
                style={{ backgroundColor: area.color || UNKNOWN_AREA_COLOR }}
              />

              {/* Area name */}
              <div className="min-w-0 flex-1 break-words text-sm font-medium">
                {area.name}
              </div>

              {/* Move buttons */}
              <div className="flex flex-shrink-0 flex-row gap-1">
                <ActionButton
                  label={t("settings.areaSorter.moveUp", {
                    name: area.name,
                  })}
                  iconName="arrow-up"
                  size="xs"
                  variant="ghost"
                  shape="square"
                  className="h-6 w-6"
                  onClick={() => moveArea(area.id, "up")}
                  disabled={disabled || loading || index === 0}
                  ariaLabel={t("settings.areaSorter.moveUp", {
                    name: area.name,
                  })}
                  iconOnly
                />
                <ActionButton
                  label={t("settings.areaSorter.moveDown", {
                    name: area.name,
                  })}
                  iconName="arrow-down"
                  size="xs"
                  variant="ghost"
                  shape="square"
                  className="h-6 w-6"
                  onClick={() => moveArea(area.id, "down")}
                  disabled={
                    disabled ||
                    loading ||
                    index === allOrderedAreas.length - 1
                  }
                  ariaLabel={t("settings.areaSorter.moveDown", {
                    name: area.name,
                  })}
                  iconOnly
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
