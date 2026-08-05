import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import luxon3Plugin from "@fullcalendar/luxon3";
import type { Task as ApiTask } from "@/services/api";
import PlannedEventModal from "@/components/PlannedEventModal";
import ErrorDisplay from "@/components/ErrorDisplay";
import LoadingSpinner from "@/components/LoadingSpinner";
import { usePageHeader } from "@/contexts/PageHeaderContext";
import ActionButton from "@/components/ActionButton";
import { SegmentedControl } from "@/components/forms";
import PeriodNavigation from "@/components/PeriodNavigation";
import PageLayout from "@/layouts/PageLayout";
import AreaSelect from "@/components/selects/AreaSelect";
import ToolbarContainer from "@/components/ToolbarContainer";
import { useSystemTimezone } from "@/hooks/useSystemTimezone";
import { usePersistentState } from "@/hooks/usePersistentState";
import { useCalendarAdapter } from "@/hooks/useCalendarAdapter";
import {
  getFullCalendarFirstDay,
  getFullCalendarVisibleRange,
} from "@/utils/calendar";
import { Icon } from "@/components/icons";
import { useVisions } from "@/hooks/queries/useVisions";
import { useAllTasks } from "@/hooks/queries/useTasks";
import "@/styles/calendar.css";
import Container from "@/layouts/Container";
import type { UUID } from "@/types/primitive";
import {
  formatDateKey,
  parseDateKey,
} from "@/utils/datetime";
import { useCalendarScheduleController } from "@/features/calendar/controller/useCalendarScheduleController";

function CalendarPage() {
  const { t } = useTranslation();
  const { setHeader } = usePageHeader();
  const calendarRef = useRef<FullCalendar>(null);

  const { state: viewType, setState: setViewType } = usePersistentState<
    "week" | "day"
  >({
    key: "calendar_view_type",
    defaultValue: "day",
    expireInHours: 0,
  });
  const [calendarTitle, setCalendarTitle] = useState<string>("");
  const [currentDate, setCurrentDate] = useState<Date>(new Date());

  const {
    adapter: calendarAdapter,
    calendarSystem,
    firstDayOfWeek,
    loading: calendarPreferencesLoading,
  } = useCalendarAdapter();
  const fullCalendarFirstDay = useMemo(
    () =>
      getFullCalendarFirstDay(
        calendarSystem,
        calendarAdapter,
        currentDate,
        firstDayOfWeek,
      ),
    [calendarSystem, calendarAdapter, currentDate, firstDayOfWeek],
  );

  const timezonePreference = useSystemTimezone();
  const activeTimezone = timezonePreference.timezone;
  const calendarConfigurationLoading =
    calendarPreferencesLoading || timezonePreference.loading;

  const [showPlannedEvents, setShowPlannedEvents] = useState(true);
  const [showTimelogs, setShowTimelogs] = useState(false);
  const [selectedAreaId, setSelectedAreaId] = useState<
    UUID | null | undefined
  >(undefined);

  const visionsRaw = useVisions();
  const { visions } = useMemo(() => visionsRaw, [visionsRaw]);
  const stableVisions = useMemo(() => visions, [visions]);

  const { data: allFlatTasksData } = useAllTasks({
    excludeStatus: ["done", "cancelled"],
    enabled: stableVisions.length > 0,
  });

  const allowedVisionIds = useMemo<Set<UUID> | null>(() => {
    if (!stableVisions || stableVisions.length === 0) {
      return null;
    }
    return new Set(stableVisions.map((vision) => vision.id));
  }, [stableVisions]);

  const allFlatTasks = useMemo<ApiTask[]>(() => {
    if (!allowedVisionIds) {
      return [];
    }
    return (allFlatTasksData ?? []).filter((task): task is ApiTask =>
      Boolean(task.vision_id && allowedVisionIds.has(task.vision_id)),
    );
  }, [allFlatTasksData, allowedVisionIds]);
  const stableAllFlatTasks = useMemo(() => allFlatTasks, [allFlatTasks]);

  useEffect(() => {
    if (!showTimelogs) {
      setSelectedAreaId(undefined);
    }
  }, [showTimelogs]);

  const [startISO, setStartISO] = useState<string | null>(null);
  const [endISO, setEndISO] = useState<string | null>(null);

  const handleDatesSet = useCallback(
    (info: { start: Date; end: Date; startStr: string }) => {
      setStartISO(info.start.toISOString());
      setEndISO(info.end.toISOString());
      const api = calendarRef.current?.getApi();
      if (api) {
        setCalendarTitle(api.view?.title ?? "");
        const type = api.view?.type;
        if (type === "timeGridWeek") setViewType("week");
        if (type === "timeGridDay") setViewType("day");
      }
      setCurrentDate(parseDateKey(info.startStr.slice(0, 10)));
    },
    [setViewType],
  );

  const {
    scheduleEntries,
    loading,
    error,
    showPlannedEventModal,
    plannedEventModalProps,
    handleDateSelect,
    handlePlannedEventClick,
  } = useCalendarScheduleController({
    startISO,
    endISO,
    showPlannedEvents,
    showTimelogs,
    selectedAreaId,
    taskIndicatorLabel: t("modules.calendar.taskIndicator"),
    preloadedTasks: stableAllFlatTasks,
    visions: stableVisions,
    timezone: activeTimezone,
  });

  useEffect(() => {
    return () => setHeader({ actions: undefined });
  }, [setHeader]);

  const handleViewTypeSelect = useCallback(
    (nextViewType: "week" | "day") => {
      const api = calendarRef.current?.getApi();
      if (!api) {
        return;
      }
      api.changeView(nextViewType === "week" ? "timeGridWeek" : "timeGridDay");
      setViewType(nextViewType);
      setCalendarTitle(api.view?.title ?? "");
    },
    [setViewType],
  );

  return (
    <PageLayout>
      <ToolbarContainer className="mb-4" layout="three-column">
        <div className="flex items-center gap-2">
          <span className="text-base font-bold">
            {t("modules.calendar.view.label")}
          </span>
          <SegmentedControl
            value={viewType}
            size="md"
            options={[
              {
                value: "week",
                label: t("modules.calendar.view.week"),
                ariaLabel: t("modules.calendar.view.weekTitle"),
              },
              {
                value: "day",
                label: t("modules.calendar.view.day"),
                ariaLabel: t("modules.calendar.view.dayTitle"),
              },
            ]}
            onChange={(nextValue) =>
              handleViewTypeSelect(nextValue as "week" | "day")
            }
          />
        </div>

        <div className="flex items-center justify-center">
          <PeriodNavigation
            periodType={viewType === "week" ? "week" : "day"}
            selectedDate={currentDate}
            onPrevious={() => {
              const api = calendarRef.current?.getApi();
              if (!api) return;
              const target = calendarAdapter.getPreviousPeriod(
                currentDate,
                viewType === "week" ? "week" : "day",
              );
              api.gotoDate(formatDateKey(target));
              setCalendarTitle(api.view?.title ?? "");
            }}
            onNext={() => {
              const api = calendarRef.current?.getApi();
              if (!api) return;
              const target = calendarAdapter.getNextPeriod(
                currentDate,
                viewType === "week" ? "week" : "day",
              );
              api.gotoDate(formatDateKey(target));
              setCalendarTitle(api.view?.title ?? "");
            }}
            onCurrent={() => {
              const api = calendarRef.current?.getApi();
              if (!api) return;
              api.today();
              setCalendarTitle(api.view?.title ?? "");
            }}
            onSelectDate={(date) => {
              const api = calendarRef.current?.getApi();
              if (!api) return;
              api.gotoDate(formatDateKey(date));
              setCalendarTitle(api.view?.title ?? "");
              setCurrentDate(date);
            }}
            currentPeriodLabel={calendarTitle}
          />
        </div>

        <div className="flex items-center justify-end gap-4">
          <div className="flex gap-2">
            <ActionButton
              label={t("modules.calendar.toggle.planned_label")}
              iconName="clipboard"
              color={showPlannedEvents ? "primary" : "neutral"}
              variant={showPlannedEvents ? "solid" : "ghost"}
              ariaLabel={
                showPlannedEvents
                  ? t("modules.calendar.toggle.planned.title.hide")
                  : t("modules.calendar.toggle.planned.title.show")
              }
              ariaPressed={showPlannedEvents}
              onClick={() => setShowPlannedEvents((v) => !v)}
            />
            <ActionButton
              label={t("modules.calendar.toggle.actual_label")}
              iconName="timer"
              color={showTimelogs ? "primary" : "neutral"}
              variant={showTimelogs ? "solid" : "ghost"}
              ariaLabel={
                showTimelogs
                  ? t("modules.calendar.toggle.actual.title.hide")
                  : t("modules.calendar.toggle.actual.title.show")
              }
              ariaPressed={showTimelogs}
              onClick={() => setShowTimelogs((v) => !v)}
            />
          </div>
          {showTimelogs && (
            <div className="flex items-center gap-2 pl-4 border-l border-base-300">
              <AreaSelect
                value={
                  selectedAreaId === undefined
                    ? undefined
                    : selectedAreaId
                }
                onChange={(id) => setSelectedAreaId(id)}
                placeholder={t("common.all")}
                showAllOption
                showNoneOption
                noneLabel={t("common.noArea")}
                id="calendar-area-filter"
              />
            </div>
          )}
        </div>
      </ToolbarContainer>

      {(loading || calendarConfigurationLoading) && (
        <LoadingSpinner message={t("modules.calendar.loading")} />
      )}
      <ErrorDisplay error={error} className="mb-6" />

      <Container>
        {showTimelogs && selectedAreaId === undefined && (
          <div className="mb-4 p-3  bg-primary/10 border border-primary/20 rounded-md ">
            <div className="flex items-center gap-2 text-primary">
              <span className="text-base inline-flex items-center gap-1">
                <Icon name="sparkles" size={16} aria-hidden />
                {t("modules.calendar.hint.title")}
              </span>
              <span className="text-base">
                {t("modules.calendar.hint.actualEnabled")}
              </span>
            </div>
          </div>
        )}
        {!calendarConfigurationLoading && <FullCalendar
          ref={calendarRef}
          plugins={[luxon3Plugin, timeGridPlugin, interactionPlugin]}
          initialView={viewType === "week" ? "timeGridWeek" : "timeGridDay"}
          headerToolbar={false}
          height="85vh"
          slotMinTime="00:00:00"
          slotMaxTime="24:00:00"
          slotDuration="00:30:00"
          slotLabelInterval="01:00:00"
          nowIndicator
          scrollTime="08:00:00"
          expandRows
          events={scheduleEntries}
          selectable
          selectMirror
          dayMaxEvents
          weekends
          timeZone={activeTimezone}
          firstDay={fullCalendarFirstDay}
          visibleRange={(date) =>
            getFullCalendarVisibleRange(
              calendarAdapter,
              viewType,
              date,
              activeTimezone,
            )
          }
          datesSet={handleDatesSet}
          select={handleDateSelect}
          eventClick={handlePlannedEventClick}
          locale="zh-cn"
          buttonText={{
            today: t("modules.calendar.fc.today"),
            week: t("modules.calendar.fc.week"),
            day: t("modules.calendar.fc.day"),
          }}
          allDayText={t("modules.calendar.fc.allDay")}
          noEventsText={t("modules.calendar.fc.noEvents")}
          moreLinkText={t("modules.calendar.fc.more")}
          eventDisplay="auto"
          displayEventTime
          eventTimeFormat={{
            hour: "numeric",
            minute: "2-digit",
            hour12: false,
          }}
          slotLabelFormat={{
            hour: "numeric",
            minute: "2-digit",
            hour12: false,
          }}
          nextDayThreshold="00:00:00"
          eventClassNames={(arg) => {
            const entryType = arg.event.extendedProps?.entryType;
            return entryType === "planned"
              ? "planned-event-custom"
              : "timelog-event-custom";
          }}
        />}
      </Container>

      {showPlannedEventModal && <PlannedEventModal {...plannedEventModalProps} />}
    </PageLayout>
  );
}

export default CalendarPage;
