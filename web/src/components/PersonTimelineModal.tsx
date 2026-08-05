import React, { useRef, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import ModalBase from "@/layouts/ModalBase";
import LoadingSpinner from "./LoadingSpinner";
import EmptyState from "./EmptyState";
import ActionButton from "./ActionButton";
import { Icon } from "./icons";
import {
  formatDate,
  formatDateTime,
  formatDuration,
  formatDurationFromTimes,
  formatTime,
} from "@/utils/datetime";
import type { PersonSummary } from "@/services/api";
import type {
  PersonActivityItem,
  PersonActivityType,
} from "@/services/api/persons";
import { useAreas } from "@/hooks/queries/useAreas";
import { useSystemTimezone } from "@/hooks/useSystemTimezone";
import AreaBadge from "./AreaBadge";

interface PersonTimelineModalProps {
  person: PersonSummary | null;
  isOpen: boolean;
  onClose: () => void;
  activities: PersonActivityItem[];
  total: number;
  totalPages: number;
  isLoadingActivities: boolean;
  isFetchingActivities: boolean;
  page: number;
  onPageChange: (page: number) => void;
  activityType: "all" | PersonActivityType;
  onActivityTypeChange: (value: "all" | PersonActivityType) => void;
  timelogStats?: {
    count: number;
    totalMinutes: number;
  } | null;
}

/**
 * PersonTimelineModal - Modal component for displaying person activity timeline
 *
 * This component provides a modal interface for:
 * - Displaying person activity timeline
 * - Showing activity details with status and type
 * - Handling loading and empty states
 */
const PersonTimelineModal: React.FC<PersonTimelineModalProps> = ({
  person,
  isOpen,
  onClose,
  activities,
  total,
  totalPages,
  isLoadingActivities,
  isFetchingActivities,
  page,
  onPageChange,
  activityType,
  onActivityTypeChange,
  timelogStats,
}) => {
  const { t } = useTranslation();
  const parentRef = useRef<HTMLDivElement>(null);
  const timezonePreference = useSystemTimezone();
  const activeTimezone = timezonePreference.timezone;
  const { areaMap } = useAreas();

  useEffect(() => {
    if (parentRef.current) {
      parentRef.current.scrollTop = 0;
    }
  }, [page, activityType]);

  const activityTypeMeta = useMemo(
    () => ({
      vision: {
        label: t("persons.activityTypes.vision"),
        badgeClass: "text-secondary bg-secondary/10",
        icon: "star" as const,
      },
      task: {
        label: t("persons.activityTypes.task"),
        badgeClass: "text-primary bg-primary/10",
        icon: "clipboard" as const,
      },
      planned_event: {
        label: t("persons.activityTypes.planned_event"),
        badgeClass: "text-info bg-info/10",
        icon: "calendar" as const,
      },
      timelog: {
        label: t("persons.activityTypes.timelog"),
        badgeClass: "text-warning bg-warning/20",
        icon: "timer" as const,
      },
      note: {
        label: t("persons.activityTypes.note"),
        badgeClass: "text-base-content bg-base-200/80",
        icon: "document-text" as const,
      },
    }),
    [t],
  );

  const filterOptions = useMemo(
    () => [
      { value: "all" as const, label: t("common.all") },
      {
        value: "timelog" as const,
        label: activityTypeMeta.timelog.label,
      },
      { value: "note" as const, label: activityTypeMeta.note.label },
      { value: "task" as const, label: activityTypeMeta.task.label },
      {
        value: "planned_event" as const,
        label: activityTypeMeta.planned_event.label,
      },
      { value: "vision" as const, label: activityTypeMeta.vision.label },
    ],
    [activityTypeMeta, t],
  );

  const getActivityTypeMeta = (type: string) =>
    activityTypeMeta[type as keyof typeof activityTypeMeta] ??
    activityTypeMeta.note;

  const safeTotalPages = Math.max(1, totalPages);
  const canGoPrev = page > 1;
  const canGoNext = page < safeTotalPages;

  useEffect(() => {
    if (page > safeTotalPages) {
      onPageChange(safeTotalPages);
    }
  }, [page, safeTotalPages, onPageChange]);

  // Get activity status display
  const getStatusDisplay = (status: string | null) => {
    if (!status) return null;

    const statusMap = {
      todo: t("status.todo"),
      in_progress: t("status.in_progress"),
      done: t("status.done"),
      cancelled: t("status.cancelled"),
      active: t("status.active"),
      archived: t("status.archived"),
      fruit: t("status.fruit"),
      planned: t("persons.activityStatus.planned"),
      completed: t("status.completed"),
    };

    return statusMap[status as keyof typeof statusMap] || status;
  };

  // Get status color
  const getStatusColor = (status: string | null) => {
    if (!status) return "bg-base-200 text-base-content/70";

    const colorMap = {
      todo: "bg-base-200 text-base-content/70",
      in_progress: "bg-error/20 text-error",
      done: "bg-success/20 text-success",
      cancelled: "bg-base-200 text-base-content/70",
      paused: "bg-warning/20 text-warning",
      active: "bg-success/20 text-success",
      archived: "bg-base-200 text-base-content/70",
      fruit: "bg-secondary/20 text-secondary",
      planned: "bg-info/20 text-info",
      completed: "bg-success/20 text-success",
    };

    return (
      colorMap[status as keyof typeof colorMap] ||
      "bg-base-200 text-base-content/70"
    );
  };

  const renderTimelogDetails = (activity: PersonActivityItem) => {
    const startTime = activity.start_time ?? activity.date;
    const endTime = activity.end_time ?? null;
    const timeRange = `${formatTime(startTime, activeTimezone)}${
      endTime ? `-${formatTime(endTime, activeTimezone)}` : ""
    }`;
    const duration = formatDurationFromTimes(startTime, endTime);
    const areaName =
      (activity.area_id ? areaMap.get(activity.area_id)?.name : null) ??
      t("taskTimelogs.unknownArea");
    return (
      <div className="grid grid-cols-1 gap-2 text-sm leading-relaxed sm:grid-cols-[minmax(100px,0.8fr)_minmax(70px,0.6fr)_minmax(120px,0.8fr)_minmax(180px,2fr)] sm:gap-3">
        <div className="text-base-content/80">{timeRange}</div>
        <div className="text-base-content/80">{duration}</div>
        <div className="min-w-0">
          <AreaBadge
            areaId={activity.area_id ?? undefined}
            areaMap={areaMap}
            name={areaName}
            showLabel
            size="sm"
            labelClassName="text-sm"
            ariaLabel={areaName}
          />
        </div>
        <div className="min-w-0 truncate text-base-content/90" title={activity.title}>
          {activity.title}
        </div>
      </div>
    );
  };

  if (!isOpen || !person) return null;

  const titleContent = (
    <>
      {t("persons.timeline.title", {
        name: person.display_name,
      })}
      {t("persons.timeline.activityCount", {
        count: total,
      })}
    </>
  );
  const shouldShowTimelogStats = activityType === "timelog" && timelogStats;
  const timelineBodyClassName =
    "h-[calc(100dvh-14rem)] min-h-[18rem] max-h-[42rem] overflow-auto";

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={onClose}
      ariaLabelledBy="person-timeline-title"
      size="2xl"
      loading={isLoadingActivities}
      showLoadingOverlay={false}
      showLoadingSpinner={true}
      loadingSpinnerSize="md"
      showCloseButton={true}
      title={titleContent}
    >
      {isLoadingActivities ? (
        <LoadingSpinner message={t("persons.timeline.loadingActivities")} />
      ) : (
        <>
          <div className="flex flex-wrap gap-2 px-4 pb-3">
            {filterOptions.map((option) => {
              const isActive = activityType === option.value;
              return (
                <ActionButton
                  key={option.value}
                  label={option.label}
                  size="sm"
                  color={isActive ? "primary" : "neutral"}
                  variant={isActive ? "solid" : "ghost"}
                  onClick={() => {
                    onActivityTypeChange(option.value);
                    if (page !== 1) {
                      onPageChange(1);
                    }
                  }}
                />
              );
            })}
          </div>
          <div className="min-h-5 px-4 pb-3 text-sm text-base-content/70">
            {shouldShowTimelogStats
              ? t("persons.timeline.timelogStats", {
                  count: timelogStats.count,
                  duration: formatDuration(timelogStats.totalMinutes),
                })
              : null}
          </div>
          <>
            <div ref={parentRef} className={timelineBodyClassName}>
              {activities.length > 0 ? (
                activities.map((activity) => {
                  const typeMeta = getActivityTypeMeta(activity.type);
                  const isTimelog = activity.type === "timelog";
                  const shouldRenderDescription =
                    Boolean(activity.description) &&
                    !isTimelog &&
                    !(
                      activity.type === "note" &&
                      activity.description?.trim() === activity.title.trim()
                    );
                  return (
                    <div
                      key={`${activity.type}-${activity.id}`}
                      className="border-b border-base-200 px-4 py-3"
                    >
                      <div className="grid grid-cols-1 gap-2 md:grid-cols-[110px_minmax(140px,auto)_minmax(0,1fr)] md:gap-4">
                        <div className="flex-shrink-0 font-mono text-sm text-base-content/80">
                          {isTimelog
                            ? formatDate(
                                activity.start_time ?? activity.date,
                                activeTimezone,
                              )
                            : formatDateTime(activity.date, activeTimezone)}
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`inline-flex items-center gap-1 rounded px-2 py-1 text-sm ${typeMeta.badgeClass}`}
                          >
                            <Icon
                              name={typeMeta.icon}
                              size={14}
                              className="text-current"
                              aria-hidden
                            />
                            {typeMeta.label}
                          </span>
                          {activity.status && !isTimelog && (
                            <span
                              className={`inline-flex items-center rounded px-2 py-1 text-sm ${getStatusColor(activity.status)}`}
                            >
                              {getStatusDisplay(activity.status)}
                            </span>
                          )}
                        </div>

                        <div className="min-w-0">
                          {isTimelog ? (
                            renderTimelogDetails(activity)
                          ) : (
                            <h4 className="break-words text-sm font-medium leading-relaxed">
                              {activity.title}
                            </h4>
                          )}
                          {shouldRenderDescription && (
                            <p className="mt-2 break-words text-sm leading-relaxed text-base-content/90">
                              {activity.description}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="flex h-full items-center justify-center px-4 pb-4">
                  <EmptyState
                    icon={<Icon name="document-text" size={48} aria-hidden />}
                    title={t("persons.timeline.noActivities")}
                    description={t("persons.timeline.noActivitiesDescription")}
                  />
                </div>
              )}
            </div>
            <div className="flex min-h-9 items-center justify-between px-4 pt-3">
              {activities.length > 0 ? (
                <>
                  <ActionButton
                    label={t("persons.timeline.previousPage")}
                    size="sm"
                    variant="outline"
                    color="neutral"
                    disabled={!canGoPrev}
                    onClick={() => onPageChange(page - 1)}
                  />
                  <div className="flex items-center gap-3 text-sm text-base-content/70">
                    <span>
                      {t("persons.timeline.pageIndicator", {
                        page,
                        total: safeTotalPages,
                      })}
                    </span>
                    {isFetchingActivities && (
                      <span className="text-xs text-base-content/60">
                        {t("common.loading")}
                      </span>
                    )}
                  </div>
                  <ActionButton
                    label={t("persons.timeline.nextPage")}
                    size="sm"
                    variant="outline"
                    color="neutral"
                    disabled={!canGoNext}
                    onClick={() => onPageChange(page + 1)}
                  />
                </>
              ) : null}
            </div>
          </>
        </>
      )}
    </ModalBase>
  );
};

export default PersonTimelineModal;
