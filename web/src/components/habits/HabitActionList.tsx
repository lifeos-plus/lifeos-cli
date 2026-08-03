import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { type HabitAction } from "@/services/api/habits";
import {
  HABIT_EDITABLE_DAYS,
  HABIT_ACTION_STATUS_OPTIONS,
  HABIT_ACTION_STATUS_CONFIG,
} from "@/utils/constants";
import ActionButton from "@/components/ActionButton";
import Surface from "@/layouts/Surface";
import EnumSelect from "@/components/selects/EnumSelect";
import type { UUID } from "@/types/primitive";
import CreateNoteModal from "@/components/CreateNoteModal";
import TaskNotesModal from "@/components/TaskNotesModal";
import type { NoteHabitActionSummary } from "@/services/api/notes";
import type {
  CalendarAdapter,
  ExtendedPlanningViewType,
} from "@/utils/calendar";
import {
  addDays,
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  formatDate,
  formatDateKey,
  formatMonthKey,
  isSameDay,
  parseDateStringToLocalDate,
  startOfMonth,
  startOfLocalDay,
  startOfWeek,
  subMonths,
} from "@/utils/datetime";

interface HabitActionListProps {
  actions: HabitAction[];
  habitId: UUID;
  habitTitle: string;
  durationDays: number;
  startDate: string;
  cadenceFrequency?: string | null;
  calendarAdapter: CalendarAdapter;
  centerDate: Date;
  onCenterDateChange: (date: Date) => void;
  onStatusUpdate: (
    habitId: UUID,
    action: HabitAction,
    newStatus: string,
  ) => void;
  onNotesChanged?: () => void;
}

const subduedNoteButtonClass = "opacity-40 hover:opacity-60 transition-opacity";

function cadenceToPeriodViewType(
  cadenceFrequency?: string | null,
): ExtendedPlanningViewType {
  switch (cadenceFrequency) {
    case "weekly":
      return "week";
    case "monthly":
      return "month";
    case "yearly":
      return "year";
    case "daily":
    default:
      return "day";
  }
}

export function HabitActionList({
  actions,
  habitId,
  habitTitle,
  durationDays,
  startDate,
  cadenceFrequency,
  calendarAdapter,
  centerDate,
  onCenterDateChange,
  onStatusUpdate,
  onNotesChanged,
}: HabitActionListProps) {
  const { t } = useTranslation();
  const [creatingNoteForAction, setCreatingNoteForAction] =
    useState<HabitAction | null>(null);
  const [viewingNotesForAction, setViewingNotesForAction] =
    useState<HabitAction | null>(null);
  const [selectedMonth, setSelectedMonth] = useState(
    () => new Date(centerDate),
  );
  const [selectedDate, setSelectedDate] = useState(() => new Date(centerDate));

  useEffect(() => {
    setSelectedMonth(new Date(centerDate));
    setSelectedDate(new Date(centerDate));
  }, [centerDate]);

  const updateCenterDate = (date: Date) => {
    onCenterDateChange(new Date(date));
  };

  // Get today's date
  const today = new Date();

  const habitStartDate = parseDateStringToLocalDate(startDate);
  const habitEndDate = addDays(habitStartDate, durationDays - 1);
  const periodViewType = cadenceToPeriodViewType(cadenceFrequency);
  const isDailyCadence = periodViewType === "day";

  const sortedActions = useMemo(
    () =>
      [...actions].sort((a, b) =>
        a.action_date.localeCompare(b.action_date),
      ),
    [actions],
  );

  const actionDates = useMemo(
    () =>
      sortedActions
        .map((action) => parseDateStringToLocalDate(action.action_date))
        .filter((date) => date >= habitStartDate && date <= habitEndDate),
    [habitEndDate, habitStartDate, sortedActions],
  );

  const isWithinHabitRange = (date: Date) => {
    const day = startOfLocalDay(date);
    return day >= habitStartDate && day <= habitEndDate;
  };

  const getPeriodRangeForDate = (date: Date) =>
    calendarAdapter.getPeriodRange(periodViewType, date);

  const parsePeriodStart = (range: { start: string; end: string }) =>
    parseDateStringToLocalDate(range.start);

  const formatPeriodLabel = (date: Date) => {
    const range = getPeriodRangeForDate(date);
    const startLabel = formatDate(range.start);
    if (range.start === range.end) {
      return startLabel;
    }
    return `${startLabel} - ${formatDate(range.end)}`;
  };

  const isDateInPeriod = (targetDate: Date, periodDate: Date) => {
    const targetKey = formatDateKey(targetDate);
    const range = getPeriodRangeForDate(periodDate);
    return targetKey >= range.start && targetKey <= range.end;
  };

  const canModifyPeriod = (periodDate: Date) => {
    const todayKey = formatDateKey(new Date());
    const todayStart = startOfLocalDay(new Date());
    const periodRange = getPeriodRangeForDate(periodDate);
    if (periodRange.start > todayKey) {
      return false;
    }
    if (periodRange.end >= todayKey) {
      return true;
    }

    const periodEnd = startOfLocalDay(
      parseDateStringToLocalDate(periodRange.end),
    );
    const daysSincePeriodEnd = Math.floor(
      (todayStart.getTime() - periodEnd.getTime()) / (1000 * 60 * 60 * 24),
    );
    return daysSincePeriodEnd <= HABIT_EDITABLE_DAYS;
  };

  const handleStatusChange = (
    action: HabitAction,
    newStatus: string,
    periodDate: Date,
  ) => {
    if (!canModifyPeriod(periodDate)) {
      return;
    }
    onStatusUpdate(habitId, action, newStatus);
  };

  const buildHabitActionSummary = (
    action: HabitAction,
  ): NoteHabitActionSummary => ({
    id: action.id,
    habit_id: action.habit_id,
    habit_title: habitTitle,
    action_date: action.action_date,
    status: action.status,
  });

  const findAnchorActionIndex = (date: Date) => {
    const target = startOfLocalDay(date);
    const index = actionDates.findIndex((actionDate) => actionDate >= target);
    return index === -1 ? actionDates.length - 1 : index;
  };

  const getFallbackDisplayPeriods = (date: Date) => {
    const centerRange = getPeriodRangeForDate(date);
    const displayPeriods = [parsePeriodStart(centerRange)].filter(
      isWithinHabitRange,
    );
    let firstRange = centerRange;
    let lastRange = centerRange;

    while (displayPeriods.length < 5) {
      const previousRange = calendarAdapter.shiftPeriodRange(
        periodViewType,
        firstRange.start,
        firstRange.end,
        -1,
      );
      const previousDate = parsePeriodStart(previousRange);
      if (isWithinHabitRange(previousDate)) {
        displayPeriods.unshift(previousDate);
        firstRange = previousRange;
        continue;
      }

      const nextRange = calendarAdapter.shiftPeriodRange(
        periodViewType,
        lastRange.start,
        lastRange.end,
        1,
      );
      const nextDate = parsePeriodStart(nextRange);
      if (isWithinHabitRange(nextDate)) {
        displayPeriods.push(nextDate);
        lastRange = nextRange;
        continue;
      }

      break;
    }

    return displayPeriods;
  };

  const getDisplayDays = (date: Date) => {
    if (actionDates.length > 0) {
      const centerIndex = findAnchorActionIndex(date);
      let startIndex = Math.max(0, centerIndex - 2);
      const endIndex = Math.min(actionDates.length, startIndex + 5);
      startIndex = Math.max(0, endIndex - 5);
      return actionDates.slice(startIndex, endIndex);
    }

    return getFallbackDisplayPeriods(date);
  };

  const displayDays = getDisplayDays(selectedDate);

  // Get actions for recent days
  const getActionForDate = (date: Date) => {
    const dateStr = formatDateKey(date);
    if (isDailyCadence) {
      return sortedActions.find((action) => action.action_date === dateStr);
    }

    const periodRange = getPeriodRangeForDate(date);
    return sortedActions.find(
      (action) =>
        action.action_date >= periodRange.start &&
        action.action_date <= periodRange.end,
    );
  };

  // Generate calendar days for selected month
  const monthStart = startOfMonth(selectedMonth);
  const monthEnd = endOfMonth(selectedMonth);
  const calendarStart = startOfWeek(monthStart);
  const calendarEnd = endOfWeek(monthEnd);

  const calendarDays = eachDayOfInterval({
    start: calendarStart,
    end: calendarEnd,
  });

  const getActionForCalendarDate = (date: Date) => {
    const dateStr = formatDateKey(date);
    return sortedActions.find((action) => action.action_date === dateStr);
  };

  const changeMonth = (direction: "prev" | "next") => {
    const newMonth =
      direction === "prev"
        ? subMonths(selectedMonth, 1)
        : addMonths(selectedMonth, 1);
    setSelectedMonth(newMonth);
    setSelectedDate(newMonth);
    updateCenterDate(newMonth);
  };

  // Handle date selection from calendar
  const handleDateSelect = (date: Date) => {
    setSelectedDate(date);
    setSelectedMonth(date);
    updateCenterDate(date);
  };

  // Navigate to previous/next five occurrence periods.
  const navigatePeriod = (direction: "prev" | "next") => {
    const step = direction === "prev" ? -5 : 5;
    let newDate: Date | null = null;

    if (actionDates.length > 0) {
      const currentIndex = findAnchorActionIndex(selectedDate);
      const nextIndex = Math.min(
        Math.max(currentIndex + step, 0),
        actionDates.length - 1,
      );
      newDate = actionDates[nextIndex];
    } else {
      const currentRange = getPeriodRangeForDate(selectedDate);
      const shiftedRange = calendarAdapter.shiftPeriodRange(
        periodViewType,
        currentRange.start,
        currentRange.end,
        step,
      );
      newDate = parsePeriodStart(shiftedRange);
    }

    if (newDate && isWithinHabitRange(newDate)) {
      setSelectedDate(newDate);
      setSelectedMonth(newDate);
      updateCenterDate(newDate);
    }
  };

  return (
    <div className="space-y-6">
      {/* Lower Section - Calendar and Recent List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Side - Monthly Calendar View */}
        <Surface padding="lg" elevation="moderate">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-base-content">
              {t("habits.actionList.monthView")}
            </h3>
            <div className="flex gap-2">
              <ActionButton
                label={t("habits.actionList.previousMonth")}
                iconName="chevron-left"
                variant="ghost"
                color="neutral"
                onClick={() => changeMonth("prev")}
                ariaLabel={t("habits.actionList.previousMonth")}
                iconOnly
              />
              <span className="px-3 py-2 font-medium">
                {formatMonthKey(selectedMonth)}
              </span>
              <ActionButton
                label={t("habits.actionList.nextMonth")}
                iconName="chevron-right"
                variant="ghost"
                color="neutral"
                onClick={() => changeMonth("next")}
                ariaLabel={t("habits.actionList.nextMonth")}
                iconOnly
              />
            </div>
          </div>

          <div className="grid grid-cols-7 gap-1 text-sm">
            {[
              t("habits.actionList.weekdays.sunday"),
              t("habits.actionList.weekdays.monday"),
              t("habits.actionList.weekdays.tuesday"),
              t("habits.actionList.weekdays.wednesday"),
              t("habits.actionList.weekdays.thursday"),
              t("habits.actionList.weekdays.friday"),
              t("habits.actionList.weekdays.saturday"),
            ].map((day) => (
              <div
                key={day}
                className="p-2 text-center font-medium text-base-content/70"
              >
                {day}
              </div>
            ))}

            {calendarDays.map((day, index) => {
              const action = getActionForCalendarDate(day);
              const isCurrentMonth =
                day.getMonth() === selectedMonth.getMonth();

              // Determine calendar cell status
              let cellStatus = "";
              let cellBgColor = "";
              let cellBorderColor = "";
              let statusText = "";

              if (action) {
                // Has action record - use unified status configuration
                const statusConfig =
                  HABIT_ACTION_STATUS_CONFIG[
                    action.status as keyof typeof HABIT_ACTION_STATUS_CONFIG
                  ] || HABIT_ACTION_STATUS_CONFIG.pending;
                cellStatus = statusConfig.cellStatus;
                cellBgColor = statusConfig.bgColor;
                cellBorderColor = statusConfig.borderColor;
                statusText = statusConfig.label;
              } else {
                // No action record - normal calendar display
                cellStatus = "no-action";
                cellBgColor = "bg-transparent";
                cellBorderColor = "border-base-300";
                statusText = "";
              }

              const isSelectedDate = isSameDay(day, selectedDate);
              const isClickable =
                isCurrentMonth &&
                day >= habitStartDate &&
                day <= habitEndDate;

              return (
                <div
                  key={index}
                  className={`p-2 text-center border rounded transition-colors ${
                    !isCurrentMonth
                      ? "text-base-content/30"
                      : "text-base-content"
                  } ${cellBgColor} ${cellBorderColor} ${
                    isClickable
                      ? "cursor-pointer transition-all hover:bg-base-300 hover:shadow-md"
                      : "cursor-not-allowed"
                  } ${
                    isSelectedDate ? "ring-2 ring-primary ring-offset-1" : ""
                  }`}
                  title={`${formatDateKey(day)} - ${cellStatus}`}
                  onClick={() => isClickable && handleDateSelect(day)}
                >
                  <div className="text-base font-medium">{day.getDate()}</div>
                  {statusText && (
                    <div className="text-sm mt-1 opacity-80">{statusText}</div>
                  )}
                </div>
              );
            })}
          </div>
        </Surface>

        {/* Right Side - 5 Days View */}
        <Surface padding="lg" elevation="moderate">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-base-content">
              {t("habits.actionList.fiveDayView")}
            </h3>
            <div className="flex gap-2">
              <ActionButton
                label={t("habits.actionList.previousFiveDays")}
                iconName="chevron-left"
                variant="ghost"
                color="neutral"
                onClick={() => navigatePeriod("prev")}
                ariaLabel={t("habits.actionList.previousFiveDays")}
                iconOnly
              />
              <span className="px-3 py-2 font-medium">
                {formatDateKey(selectedDate)}
              </span>
              <ActionButton
                label={t("habits.actionList.nextFiveDays")}
                iconName="chevron-right"
                variant="ghost"
                color="neutral"
                onClick={() => navigatePeriod("next")}
                ariaLabel={t("habits.actionList.nextFiveDays")}
                iconOnly
              />
            </div>
          </div>
          <div className="space-y-2">
            {displayDays.map((date) => {
              const action = getActionForDate(date);
              const isTodayDate = isDateInPeriod(today, date);
              const isSelectedDate = isDateInPeriod(selectedDate, date);
              const periodRange = getPeriodRangeForDate(date);
              const isPastDate = periodRange.end < formatDateKey(today);
              const canModifyAction = canModifyPeriod(date);
              const linkedNotesCount = action
                ? (action.linked_notes_count ?? (action.notes?.trim() ? 1 : 0))
                : 0;
              const hasLinkedNotes = linkedNotesCount > 0;

              return (
                <div
                  key={formatDateKey(date)}
                  className={`flex min-w-0 flex-col items-stretch gap-2 rounded-lg border p-3 transition-colors hover:bg-primary/10 focus-within:bg-primary/10 sm:flex-row sm:items-center sm:justify-between ${
                    isSelectedDate
                      ? "border-primary bg-primary/10 ring-2 ring-primary/20"
                      : isTodayDate
                        ? "border-primary/40 bg-primary/10"
                        : isPastDate
                          ? "border-base-300"
                          : "border-base-300 bg-base-200"
                  }`}
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <div className="min-w-0 text-base">
                      {isDailyCadence && (
                        <span className="font-medium text-base-content">
                          {(() => {
                            const current = startOfLocalDay(date);
                            const start = startOfLocalDay(habitStartDate);
                            const dayDiff = Math.floor(
                              (current.getTime() - start.getTime()) /
                                (1000 * 60 * 60 * 24),
                            );
                            return Math.max(1, dayDiff + 1);
                          })()}
                          /{durationDays}
                        </span>
                      )}
                      <span
                        className={`break-words text-sm text-base-content/70 ${
                          isDailyCadence ? "ml-2" : "font-medium"
                        }`}
                      >
                        {formatPeriodLabel(date)}
                        {isTodayDate && ` (${t("planning.presets.today")})`}
                      </span>
                    </div>

                    {!action && (
                      <span className="min-w-0 break-words text-base text-base-content/50">
                        {t("habits.actionList.notRecorded")}
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center justify-end gap-2 sm:flex-nowrap">
                    {action && (
                      <>
                        {canModifyAction && (
                          <ActionButton
                            label={t("notes.actions.addNote")}
                            iconName="document-plus"
                            color="primary"
                            onClick={() => setCreatingNoteForAction(action)}
                            iconOnly
                            ariaLabel={t("notes.actions.addNote")}
                          />
                        )}
                        <ActionButton
                          label={t("notes.actions.viewNotes")}
                          iconName="book-open"
                          color={hasLinkedNotes ? "primary" : "neutral"}
                          className={
                            hasLinkedNotes ? undefined : subduedNoteButtonClass
                          }
                          onClick={() => setViewingNotesForAction(action)}
                          iconOnly
                          ariaLabel={t("notes.actions.viewNotes")}
                        />
                        {canModifyAction && (
                          <EnumSelect
                            id={`status-select-${action.id}`}
                            value={action.status}
                            onChange={(value) => {
                              if (value) {
                                handleStatusChange(
                                  action,
                                  value as string,
                                  date,
                                );
                              }
                            }}
                            options={HABIT_ACTION_STATUS_OPTIONS}
                          />
                        )}
                      </>
                    )}

                    {!canModifyAction && !action && (
                      <div className="text-sm text-base-content/60">
                        {date > today ? t("habits.actionList.notStarted") : ""}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Surface>
      </div>

      {creatingNoteForAction && (
        <CreateNoteModal
          isOpen={!!creatingNoteForAction}
          onClose={() => setCreatingNoteForAction(null)}
          preSelectedHabitActionId={creatingNoteForAction.id}
          preSelectedHabitAction={buildHabitActionSummary(creatingNoteForAction)}
          onNoteCreated={() => {
            setCreatingNoteForAction(null);
            onNotesChanged?.();
          }}
        />
      )}

      {viewingNotesForAction && (
        <TaskNotesModal
          isOpen={!!viewingNotesForAction}
          onClose={() => setViewingNotesForAction(null)}
          entityType="habit_action"
          habitAction={buildHabitActionSummary(viewingNotesForAction)}
          onNotesChanged={onNotesChanged}
        />
      )}
    </div>
  );
}
