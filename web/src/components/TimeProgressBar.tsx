import React, { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { Area } from "@/services/api/areas";
import type { ProcessedEntry } from "@/utils/datetime";
import { statsApi } from "@/services/api/stats";
import { formatDuration } from "@/utils/datetime";
import { useAreaOrderReadOnly } from "@/hooks/queries/useAreaOrderReadOnly";
import Card from "@/layouts/Card";
import type { UUID } from "@/types/primitive";
import { UNKNOWN_AREA_COLOR } from "@/utils/areaColors";

interface TimeProgressBarProps {
  entries: ProcessedEntry[];
  areas: Area[];
  // Optional: when provided, fetch server-side day breakdown for this local date
  localDateISO?: string; // YYYY-MM-DD (client local)
  timezone?: string;
  isLoading?: boolean;
  className?: string;
}

interface AreaTimeData {
  areaId: UUID;
  areaName: string;
  areaColor: string;
  totalMinutes: number;
  percentage: number;
}

/**
 * TimeProgressBar - Displays 24-hour time allocation by area
 *
 * This component creates a horizontal progress bar showing how time is distributed
 * across different areas throughout the day, sorted by duration.
 */
const TimeProgressBar: React.FC<TimeProgressBarProps> = ({
  entries,
  areas,
  localDateISO,
  timezone,
  isLoading = false,
  className,
}) => {
  const { t } = useTranslation();
  // Optional server minutes per area for local day
  const [serverMinutes, setServerMinutes] = useState<Record<UUID, number> | null>(
    null,
  );

  // Read-only area order via TanStack Query cache
  const { order: areaOrder } = useAreaOrderReadOnly();

  useEffect(() => {
    const shouldFetch = Boolean(localDateISO);
    if (!shouldFetch) {
      setServerMinutes(null);
      return;
    }
    statsApi
      .getLocalDayBreakdown(localDateISO!)
      .then((response) => {
        const rows = response.items ?? [];
        const map: Record<UUID, number> = {};
        rows.forEach((r) => (map[r.area_id] = r.minutes));
        setServerMinutes(map);
      })
      .catch(() => setServerMinutes(null));
  }, [localDateISO, timezone]);
  // Calculate time allocation by area
  const calculateTimeAllocation = useMemo((): AreaTimeData[] => {
    const areaTimeMap = new Map<UUID, number>();

    // Initialize all areas with 0 minutes
    areas.forEach((area) => {
      areaTimeMap.set(area.id, 0);
    });

    // Add unknown area for placeholders and gaps
    areaTimeMap.set("-1", 0);

    if (serverMinutes) {
      // Use backend totals (per local day)
      Object.entries(serverMinutes).forEach(([areaIdStr, minutes]) => {
        const areaId = areaIdStr as UUID;
        areaTimeMap.set(areaId, minutes as number);
      });
    } else {
      // Fallback to client-side calculation from entries
      entries.forEach((entry) => {
        if (entry.start_time && entry.end_time) {
          const startTime = new Date(entry.start_time);
          const endTime = new Date(entry.end_time);
          const durationMs = endTime.getTime() - startTime.getTime();
          const durationMinutes = Math.round(durationMs / (1000 * 60));

          if (entry.isPlaceholder) {
            const currentMinutes = areaTimeMap.get("-1") || 0;
            areaTimeMap.set("-1", currentMinutes + durationMinutes);
          } else {
            const areaId = entry.area_id || "-1";
            const currentMinutes =
              areaTimeMap.get(areaId as UUID) || 0;
            areaTimeMap.set(
              areaId as UUID,
              currentMinutes + durationMinutes,
            );
          }
        }
      });
    }

    // Calculate total time (should be 24 hours = 1440 minutes)
    const totalMinutes = 1440; // Fixed 24 hours

    // Convert to array and calculate percentages
    const areaTimeData: AreaTimeData[] = Array.from(
      areaTimeMap.entries(),
    )
      .map(([areaId, minutesForArea]) => {
        if (areaId === "-1") {
          // Unknown area (placeholders and gaps)
          return {
            areaId: areaId as UUID,
            areaName: t("timeLog.progressBar.unknownUnfilled"),
            areaColor: UNKNOWN_AREA_COLOR,
            totalMinutes: minutesForArea,
            percentage: 0,
          };
        } else {
          const area = areas.find((item) => item.id === areaId);
          return {
            areaId: areaId as UUID,
            areaName:
              area?.name || t("timeLog.progressBar.unknownArea"),
            areaColor: area?.color || UNKNOWN_AREA_COLOR,
            totalMinutes: minutesForArea,
            percentage: 0,
          };
        }
      })
      .filter((item) => item.totalMinutes > 0) // Only show areas with time
      .sort((a, b) => {
        // Sort by backend order first, then by duration descending
        const aOrder = areaOrder.indexOf(a.areaId);
        const bOrder = areaOrder.indexOf(b.areaId);

        // If both areas are in the order, sort by order
        if (aOrder !== -1 && bOrder !== -1) {
          return aOrder - bOrder;
        }

        // If only one is in the order, prioritize the one in order
        if (aOrder !== -1) return -1;
        if (bOrder !== -1) return 1;

        // If neither is in the order, sort by duration descending
        return b.totalMinutes - a.totalMinutes;
      });

    // Recalculate percentages based on 24 hours (1440 minutes)
    areaTimeData.forEach((item) => {
      item.percentage = (item.totalMinutes / totalMinutes) * 100;
    });

    return areaTimeData;
  }, [entries, areas, serverMinutes, areaOrder, t]);

  const timeAllocation = calculateTimeAllocation;

  const cardClassName = [isLoading ? "min-h-[160px]" : "", "h-auto", className]
    .filter(Boolean)
    .join(" ");

  if (isLoading) {
    return (
      <Card className={cardClassName}>
        <div className="flex flex-col gap-4 animate-pulse">
          <div className="flex flex-wrap gap-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-base-300" />
                <div className="h-4 w-20 bg-base-300 rounded" />
                <div className="h-4 w-14 bg-base-300 rounded" />
                <div className="h-4 w-16 bg-base-300 rounded" />
              </div>
            ))}
          </div>
          <div className="flex h-6 bg-base-200 rounded-lg overflow-hidden mt-3">
            <div className="flex-1 h-full bg-base-300" />
          </div>
        </div>
      </Card>
    );
  }

  // Always show the progress bar, even if no time is recorded
  // If no time is recorded, show 100% unknown
  if (timeAllocation.length === 0) {
    timeAllocation.push({
      areaId: "-1",
      areaName: t("timeLog.progressBar.unknownUnfilled"),
      areaColor: UNKNOWN_AREA_COLOR,
      totalMinutes: 1440, // 24 hours
      percentage: 100,
    });
  }

  return (
    <Card className={cardClassName}>
      {/* Legend */}
      <div className="flex flex-wrap gap-3 mb-3">
        {timeAllocation.map((item: AreaTimeData) => (
          <div key={item.areaId} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: item.areaColor }}
            ></div>
            <span className="text-sm font-medium">{item.areaName}</span>
            <span className="text-sm">{formatDuration(item.totalMinutes)}</span>
            <span className="text-sm">({item.percentage.toFixed(1)}%)</span>
          </div>
        ))}
      </div>
      {/* Progress Bar */}
      <div className="flex h-6 bg-base-200 rounded-lg overflow-hidden mt-3">
        {timeAllocation.map((item: AreaTimeData) => (
          <div
            key={item.areaId}
            className="flex items-center justify-center text-sm text-base-content font-medium"
            style={{
              width: `${item.percentage}%`,
              backgroundColor: item.areaColor,
              minWidth: item.percentage > 5 ? "auto" : "20px",
            }}
            title={`${item.areaName}: ${formatDuration(item.totalMinutes)} (${item.percentage.toFixed(1)}%)`}
          >
            {item.percentage > 8 && (
              <span className="truncate px-1">
                {formatDuration(item.totalMinutes)}
              </span>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
};

export default TimeProgressBar;
