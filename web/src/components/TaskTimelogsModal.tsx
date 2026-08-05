import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Timelog, TaskWithSubtasks } from "@/services/api";
import type { UUID } from "@/types/primitive";
import { formatDate } from "@/utils/datetime";
import TimeRangeText from "./TimeRangeText";
import ModalBase from "@/layouts/ModalBase";
import { useTaskTimelogs } from "@/hooks/queries/useTaskTimelogs";
import ListContainer from "@/layouts/ListContainer";
import AreaBadge from "./AreaBadge";
import { Icon } from "./icons";
import { useSystemTimezone } from "@/hooks/useSystemTimezone";
import { useAreas } from "@/hooks/queries/useAreas";
import ActionButton from "./ActionButton";

interface TaskTimelogsModalProps {
  isOpen: boolean;
  onClose: () => void;
  task: TaskWithSubtasks | null;
}

/**
 * TaskTimelogsModal - Independent modal for displaying time records associated with a task
 *
 * This modal shows all timelogs (timelog records) that are associated
 * with a specific task, ordered by time (newest first).
 */
const TaskTimelogsModal: React.FC<TaskTimelogsModalProps> = ({
  isOpen,
  onClose,
  task,
}) => {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const pageSize = 15;
  const timezonePreference = useSystemTimezone();
  const activeTimezone = timezonePreference.timezone;
  const { areaMap } = useAreas();

  useEffect(() => {
    if (isOpen) {
      setPage(1);
    }
  }, [isOpen, task?.id]);

  const {
    data: timelogsData,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useTaskTimelogs(task?.id || ("" as UUID), {
    enabled: !!task?.id && isOpen,
    page,
    size: pageSize,
  });
  const timelogs = useMemo(
    () => timelogsData?.items ?? [],
    [timelogsData],
  );
  const totalRecords = timelogsData?.pagination.total ?? 0;
  const safeTotalPages = Math.max(1, timelogsData?.pagination.pages ?? 0);
  const canGoPrev = page > 1;
  const canGoNext = page < safeTotalPages;

  useEffect(() => {
    if (page > safeTotalPages) {
      setPage(safeTotalPages);
    }
  }, [page, safeTotalPages]);

  // Calculate duration for an event
  const calculateDuration = (event: Timelog): string => {
    if (!event.start_time || !event.end_time) {
      return t("taskTimelogs.duration");
    }

    const startTime = new Date(event.start_time);
    const endTime = new Date(event.end_time);
    const durationMs = endTime.getTime() - startTime.getTime();
    const durationMinutes = Math.round(durationMs / (1000 * 60));

    if (durationMinutes < 60) {
      return `${durationMinutes}${t("taskTimelogs.minutes")}`;
    } else {
      const hours = Math.floor(durationMinutes / 60);
      const minutes = durationMinutes % 60;
      return minutes > 0
        ? `${hours}${t("taskTimelogs.hours")}${minutes}${t("taskTimelogs.minutes")}`
        : `${hours}${t("taskTimelogs.hours")}`;
    }
  };

  const formatMinutes = (totalMinutes: number): string => {
    if (totalMinutes < 60) {
      return `${totalMinutes}${t("taskTimelogs.minutes")}`;
    }
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return minutes > 0
      ? `${hours}${t("taskTimelogs.hours")}${minutes}${t("taskTimelogs.minutes")}`
      : `${hours}${t("taskTimelogs.hours")}`;
  };

  const calculateTotalTime = (): string =>
    formatMinutes(Math.max(0, task?.actual_effort_self ?? 0));

  const paginationFooter =
    !isLoading && !error && safeTotalPages > 1 ? (
      <div
        className="flex items-center justify-between gap-3 border-t border-base-300 pt-3"
        data-testid="task-timelogs-pagination"
      >
        <ActionButton
          label={t("taskTimelogs.previousPage")}
          size="sm"
          variant="outline"
          color="neutral"
          disabled={!canGoPrev}
          onClick={() => setPage((current) => Math.max(1, current - 1))}
        />
        <div className="flex items-center gap-3 text-sm text-base-content/70">
          <span>
            {t("taskTimelogs.pageIndicator", {
              page,
              total: safeTotalPages,
            })}
          </span>
          {isFetching && (
            <span className="text-xs text-base-content/60">
              {t("common.loading")}
            </span>
          )}
        </div>
        <ActionButton
          label={t("taskTimelogs.nextPage")}
          size="sm"
          variant="outline"
          color="neutral"
          disabled={!canGoNext}
          onClick={() =>
            setPage((current) => Math.min(safeTotalPages, current + 1))
          }
        />
      </div>
    ) : null;

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={onClose}
      header={t("taskTimelogs.title")}
      size="2xl"
      loading={isLoading}
      error={error?.message}
      onErrorDismiss={() => refetch()}
      showLoadingSpinner={true}
      loadingSpinnerSize="md"
      showCloseButton={true}
      errorDisplayMode="inline"
      footer={paginationFooter}
    >
      <div className="space-y-3">
        {!isLoading && !error && (
          <div className="flex flex-wrap items-center justify-between gap-2 px-2 pt-4 pb-2">
            <div className="min-w-0 text-base">
              {task && (
                <span className="line-clamp-2">
                  {t("taskTimelogs.taskLabel")} {task.content}
                </span>
              )}
            </div>
            <div className="flex flex-shrink-0 items-center gap-3">
              <div className="text-sm text-base-content/40">
                {t("taskTimelogs.totalTime")} {calculateTotalTime()}
              </div>
              <div className="text-sm text-base-content/40">
                {t("taskTimelogs.recordsCount", {
                  count: totalRecords,
                })}
              </div>
            </div>
          </div>
        )}

        <ListContainer
          title={t("taskTimelogs.title")}
          hideHeader
          size="lg"
          borderVariant="subtle"
          contentClassName="overflow-visible"
          columns={[
            {
              key: "date",
              label: t("taskTimelogs.columns.date"),
              width: "0.5fr",
              align: "left",
            },
            {
              key: "timeRange",
              label: t("taskTimelogs.columns.timeRange"),
              width: "0.7fr",
              align: "left",
            },
            {
              key: "duration",
              label: t("taskTimelogs.columns.duration"),
              width: "0.5fr",
              align: "left",
            },
            {
              key: "area",
              label: t("taskTimelogs.columns.area"),
              width: "0.5fr",
              align: "left",
            },
            {
              key: "description",
              label: t("taskTimelogs.columns.description"),
              width: "2.5fr",
              align: "left",
            },
          ]}
          emptyState={
            !isLoading && !error && timelogs.length === 0 ? (
              <div className="flex items-center justify-center py-16">
                <div className="text-center max-w-md">
                  <Icon
                    name="timer"
                    size={48}
                    className="mb-6 opacity-60 text-info"
                    aria-hidden
                  />
                  <h3 className="text-lg font-semibold text-base-content mb-3">
                    {t("taskTimelogs.emptyState.title")}
                  </h3>
                  <p className="text-base-content/80 mb-4 leading-relaxed">
                    {t("taskTimelogs.emptyState.description")}
                  </p>
                </div>
              </div>
            ) : null
          }
        >
          {!isLoading && !error && timelogs.length > 0 && (
            <div
              className="overflow-x-auto px-2 py-3"
              data-testid="task-timelogs-scroll-area"
            >
              <div
                className="min-w-[760px] grid gap-4"
                style={{
                  gridTemplateColumns: [
                    "0.5fr",
                    "0.7fr",
                    "0.5fr",
                    "0.5fr",
                    "2.5fr",
                  ].join(" "),
                }}
              >
                {timelogs.map((event) => {
                  const trimmedTitle = event.title.trim();
                  const description =
                    trimmedTitle.length > 0
                      ? trimmedTitle
                      : t("taskTimelogs.untitled");
                  const areaName =
                    event.area_summary?.name ??
                    (event.area_id ? areaMap.get(event.area_id)?.name : null) ??
                    t("taskTimelogs.unknownArea");
                  const areaColor =
                    event.area_summary?.color ??
                    (event.area_id
                      ? areaMap.get(event.area_id)?.color
                      : null) ??
                    undefined;

                  return (
                    <React.Fragment key={event.id}>
                      <div className="text-base-content/80 flex items-center">
                        {formatDate(event.start_time, activeTimezone)}
                      </div>
                      <div className="text-base-content/90 flex items-center">
                        <TimeRangeText
                          start={event.start_time}
                          end={event.end_time || null}
                          timezone={activeTimezone}
                        />
                      </div>
                      <div className="text-left text-base-content/90 flex items-center gap-2">
                        {calculateDuration(event)}
                      </div>
                      <div className="flex items-center">
                        <AreaBadge
                          areaId={event.area_id ?? undefined}
                          areaMap={areaMap}
                          name={areaName}
                          color={areaColor}
                          showLabel
                          labelClassName="text-base"
                          ariaLabel={areaName}
                        />
                      </div>
                      <div
                        className="text-base-content/90 flex items-center truncate"
                        title={description}
                      >
                        {description}
                      </div>
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
          )}
        </ListContainer>
      </div>
    </ModalBase>
  );
};

export default TaskTimelogsModal;
