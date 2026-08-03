import React, { useRef, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ActionButton from "./ActionButton";
import type { CalendarAdapter } from "@/utils/calendar";
import { useCalendarAdapter } from "@/hooks/useCalendarAdapter";
import {
  dateStringToISO,
  formatDate,
  formatDateInTimezone,
} from "@/utils/datetime";
import { TextInput } from "./forms";

type PeriodType = "day" | "week" | "month" | "year" | "7years" | "sevenYear";

interface PeriodNavigationProps {
  // 周期类型
  periodType: PeriodType;

  // 当前选中日期
  selectedDate: Date;

  // 事件处理
  onPrevious: () => void;
  onNext: () => void;
  onCurrent: () => void;
  onSelectDate?: (date: Date) => void;

  // 可选配置
  disabled?: boolean;
  className?: string;
  timezone?: string;

  // 中间按钮显示内容（可选，默认自动生成）
  currentPeriodLabel?: string;

  // 是否显示中间按钮的图标
  showCurrentIcon?: boolean;

  // 中间按钮宽度控制
  centerButtonWidth?: "auto" | "sm" | "md" | "lg" | "xl";

  // 可选的日期范围（用于 sevenYear 等视图的准确标签显示）
  startDate?: string; // YYYY-MM-DD 格式
  endDate?: string; // YYYY-MM-DD 格式
}

/**
 * 统一的周期导航组件
 * 提供前一周期、当前周期、后一周期的导航功能
 */
const parseLocalIso = (iso: string): Date => {
  const [yearStr, monthStr, dayStr] = iso.split("-");
  const year = Number(yearStr);
  const month = Number(monthStr) - 1;
  const day = Number(dayStr);
  return new Date(year, month, day, 0, 0, 0, 0);
};

const formatDateInput = (date: Date, timezone?: string): string => {
  if (timezone) {
    return formatDateInTimezone(date, timezone);
  }

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const parseDateInput = (value: string, timezone?: string): Date | null => {
  if (!value) return null;
  const [yearStr, monthStr, dayStr] = value.split("-");
  if (!yearStr || !monthStr || !dayStr) return null;

  const year = Number(yearStr);
  const month = Number(monthStr);
  const day = Number(dayStr);

  if (Number.isNaN(year) || Number.isNaN(month) || Number.isNaN(day)) {
    return null;
  }

  if (timezone) {
    const iso = dateStringToISO(value, timezone, false);
    return iso ? new Date(iso) : null;
  }

  return new Date(year, month - 1, day, 0, 0, 0, 0);
};

const getPeriodStartForDate = (
  adapter: CalendarAdapter,
  periodType: PeriodType,
  date: Date,
): Date => {
  if (periodType === "day") {
    return date;
  }

  const range = adapter.getPeriodRange(periodType, date);
  return parseLocalIso(range.start);
};

const isSamePeriod = (
  adapter: CalendarAdapter,
  viewType: "year" | "sevenYear",
  a: Date,
  b: Date,
): boolean => {
  const rangeA = adapter.getPeriodRange(viewType, a);
  const rangeB = adapter.getPeriodRange(viewType, b);
  const startA = parseLocalIso(rangeA.start).getTime();
  const endA = parseLocalIso(rangeA.end).getTime();
  const startB = parseLocalIso(rangeB.start).getTime();
  const endB = parseLocalIso(rangeB.end).getTime();
  return startA === startB && endA === endB;
};

const PeriodNavigation: React.FC<PeriodNavigationProps> = ({
  periodType,
  selectedDate,
  onPrevious,
  onNext,
  onCurrent,
  onSelectDate,
  disabled = false,
  className = "",
  currentPeriodLabel,
  showCurrentIcon = false,
  centerButtonWidth = "xl",
  startDate,
  endDate,
  timezone,
}) => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [pendingDateInput, setPendingDateInput] = useState<string>(() =>
    formatDateInput(selectedDate, timezone),
  );
  const pickerContainerRef = useRef<HTMLDivElement>(null);
  const pickerButtonRef = useRef<HTMLButtonElement>(null);
  const pickerInputRef = useRef<HTMLInputElement>(null);

  const { adapter: calendarAdapter } = useCalendarAdapter();

  // 容器宽度监听
  useEffect(() => {
    const updateWidth = () => {
      const container = containerRef.current;
      if (container) {
        setContainerWidth(container.offsetWidth);
      }
    };

    updateWidth();
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  useEffect(() => {
    if (!isPickerOpen) {
      setPendingDateInput(formatDateInput(selectedDate, timezone));
    }
  }, [selectedDate, isPickerOpen, timezone]);

  useEffect(() => {
    if (!onSelectDate) {
      setIsPickerOpen(false);
    }
  }, [onSelectDate]);

  useEffect(() => {
    if (!isPickerOpen) return;

    const handlePointerDown = (event: MouseEvent | PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (
        pickerContainerRef.current?.contains(target) ||
        pickerButtonRef.current?.contains(target)
      ) {
        return;
      }
      setIsPickerOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsPickerOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isPickerOpen]);

  useEffect(() => {
    if (isPickerOpen) {
      pickerInputRef.current?.focus();
    }
  }, [isPickerOpen]);

  const isCurrentPeriod = React.useMemo(() => {
    const now = new Date();
    switch (periodType) {
      case "day":
        if (timezone) {
          return (
            formatDateInTimezone(selectedDate, timezone) ===
            formatDateInTimezone(now, timezone)
          );
        }
        return selectedDate.toDateString() === now.toDateString();

      case "week": {
        const weekStart = calendarAdapter.getWeekStart(selectedDate);
        const nowWeekStart = calendarAdapter.getWeekStart(now);
        return weekStart.getTime() === nowWeekStart.getTime();
      }

      case "month": {
        const selectedMonthInfo = calendarAdapter.getMonthInfo(selectedDate);
        const nowMonthInfo = calendarAdapter.getMonthInfo(now);

        if (!selectedMonthInfo.isValidMonth || !nowMonthInfo.isValidMonth) {
          return false;
        }

        return (
          selectedMonthInfo.monthStart?.getTime() ===
          nowMonthInfo.monthStart?.getTime()
        );
      }

      case "year":
        return isSamePeriod(calendarAdapter, "year", selectedDate, now);
      case "7years":
      case "sevenYear": {
        return isSamePeriod(calendarAdapter, "sevenYear", selectedDate, now);
      }

      default:
        return false;
    }
  }, [selectedDate, periodType, calendarAdapter, timezone]);

  const autoGeneratedLabel = React.useMemo(() => {
    const addCurrentIndicator = (label: string) =>
      isCurrentPeriod
        ? `${t("planning.periodNavigation.current")} · ${label}`
        : label;

    switch (periodType) {
      case "day": {
        const dateStr = timezone
          ? formatDateInTimezone(selectedDate, timezone)
          : formatDate(selectedDate.toISOString());
        return addCurrentIndicator(dateStr);
      }

      case "week": {
        const range = calendarAdapter.getPeriodRange("week", selectedDate);
        const weekStart = parseLocalIso(range.start);
        const weekEnd = parseLocalIso(range.end);

        const startDateStr = formatDate(range.start, timezone);
        const endDateStr = formatDate(range.end, timezone);

        if (range.start === range.end) {
          return addCurrentIndicator(startDateStr);
        }

        // Show complete dates when the week crosses a year boundary.
        if (weekStart.getFullYear() !== weekEnd.getFullYear()) {
          const weekRange = `${startDateStr} - ${endDateStr}`;
          return addCurrentIndicator(weekRange);
        }

        // Include the month when the week crosses a month boundary.
        if (weekStart.getMonth() !== weekEnd.getMonth()) {
          const startMonthStr = formatDate(
            range.start,
            timezone,
          ).substring(0, 7);
          const endDay = String(weekEnd.getDate()).padStart(2, "0");
          const weekRange = `${startMonthStr}-${String(weekStart.getDate()).padStart(2, "0")}~${endDay}`;
          return addCurrentIndicator(weekRange);
        }

        // Use the compact form when the week stays within one month.
        const startDay = String(weekStart.getDate()).padStart(2, "0");
        const endDay = String(weekEnd.getDate()).padStart(2, "0");
        const weekRange = `${formatDate(range.start, timezone).substring(0, 7)}-${startDay}~${endDay}`;
        return addCurrentIndicator(weekRange);
      }

      case "month": {
        const range = calendarAdapter.getPeriodRange("month", selectedDate);
        const label = `${range.start}-${range.end}`;
        return addCurrentIndicator(label);
      }

      case "year": {
        const range = calendarAdapter.getPeriodRange("year", selectedDate);
        const label = `${range.start}-${range.end}`;
        return addCurrentIndicator(label);
      }

      case "7years":
      case "sevenYear": {
        if (startDate && endDate) {
          const label = `${startDate}-${endDate}`;
          return addCurrentIndicator(label);
        }
        const range = calendarAdapter.getPeriodRange(periodType, selectedDate);
        const label = `${range.start}-${range.end}`;
        return addCurrentIndicator(label);
      }

      default:
        return t("common.loading");
    }
  }, [
    selectedDate,
    periodType,
    isCurrentPeriod,
    calendarAdapter,
    t,
    startDate,
    endDate,
    timezone,
  ]);

  // 生成当前周期按钮的图标
  const currentIconName = React.useMemo(() => {
    if (!showCurrentIcon) return null;
    return isCurrentPeriod ? "pin" : "refresh";
  }, [showCurrentIcon, isCurrentPeriod]);

  // 响应式文本处理
  const getResponsiveLabel = React.useCallback(
    (label: string) => {
      // 更宽松的截断策略 - 主要在极端情况下才截断
      // 移动设备 (< 480px): 当宽度不足时才截断
      if (containerWidth > 0 && containerWidth < 480 && label.length > 20) {
        return `${label.substring(0, 17)}...`;
      }
      // 中等屏幕 (< 640px): 更充足的文本空间
      if (containerWidth < 640 && label.length > 30) {
        return `${label.substring(0, 27)}...`;
      }
      // 大屏幕基本不截断，除非文本过长
      if (label.length > 40) {
        return `${label.substring(0, 37)}...`;
      }
      return label;
    },
    [containerWidth],
  );

  const displayLabel = currentPeriodLabel || autoGeneratedLabel;
  const responsiveDisplayLabel = getResponsiveLabel(displayLabel);

  // 响应式宽度类名映射
  const responsiveWidthClassMap = {
    sm: "w-full min-w-0 max-w-32 sm:max-w-40",
    md: "w-full min-w-0 max-w-40 sm:max-w-48 md:max-w-56",
    lg: "w-full min-w-0 max-w-56 sm:max-w-64 md:max-w-72",
    xl: "w-full min-w-0 max-w-64 sm:max-w-72 md:max-w-80 lg:max-w-96",
    auto: "w-auto min-w-0",
  } as const;

  const getCenterButtonWidthClass = () =>
    responsiveWidthClassMap[centerButtonWidth] || responsiveWidthClassMap.auto;

  const datePickerEnabled = Boolean(onSelectDate);
  const dateInputId = React.useId();
  const datePickerButtonLabel = t("planning.periodNavigation.pickDateButton");
  const datePickerLabel = t("planning.periodNavigation.pickDateLabel");
  const datePickerPlaceholder = t(
    "planning.periodNavigation.pickDatePlaceholder",
  );
  const datePickerHint = datePickerEnabled
    ? t(`planning.periodNavigation.pickDateHint.${periodType}`, {
        defaultValue: "",
      })
    : "";
  const labelId = `${dateInputId}-label`;
  const hintId = datePickerHint ? `${dateInputId}-hint` : undefined;

  const handleTogglePicker = React.useCallback(() => {
    if (disabled || !onSelectDate) return;
    setPendingDateInput(formatDateInput(selectedDate, timezone));
    setIsPickerOpen((prev) => !prev);
  }, [disabled, onSelectDate, selectedDate, timezone]);

  const handleApplyDate = React.useCallback(() => {
    if (!onSelectDate || !pendingDateInput) return;
    const parsed = parseDateInput(pendingDateInput, timezone);
    if (!parsed) return;

    const normalized = getPeriodStartForDate(
      calendarAdapter,
      periodType,
      parsed,
    );
    onSelectDate(normalized);
    setIsPickerOpen(false);
    setTimeout(() => pickerButtonRef.current?.focus(), 0);
  }, [onSelectDate, pendingDateInput, calendarAdapter, periodType, timezone]);

  const handleCancelPicker = React.useCallback(() => {
    setIsPickerOpen(false);
    setPendingDateInput(formatDateInput(selectedDate, timezone));
    setTimeout(() => pickerButtonRef.current?.focus(), 0);
  }, [selectedDate, timezone]);

  const handleDateInputChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    setPendingDateInput(event.target.value);
  };

  const handleDateFormSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    handleApplyDate();
  };

  return (
    <div
      ref={containerRef}
      className={`flex min-w-0 max-w-full items-center gap-1 sm:gap-2 ${className}`}
    >
      {/* 前一周期按钮 */}
      <ActionButton
        label=""
        iconName="chevron-left"
        onClick={onPrevious}
        color="neutral"
        variant="ghost"
        size="sm"
        ariaLabel={`${t("planning.periodNavigation.previous")}${t(`planning.periodNavigation.periodTypes.${periodType}`)}`}
        disabled={disabled}
        className="font-normal text-sm sm:text-base"
      />

      {/* 当前周期按钮 + 日期选择器 */}
      <div className="flex min-w-0 flex-1 items-center gap-1 sm:gap-1.5">
        <div className={`${getCenterButtonWidthClass()} flex justify-center`}>
          <ActionButton
            label={responsiveDisplayLabel}
            iconName={currentIconName ?? undefined}
            onClick={onCurrent}
            color="primary"
            variant="solid"
            size="sm"
            ariaLabel={
              isCurrentPeriod
                ? t("planning.periodNavigation.current")
                : t("planning.periodNavigation.goToCurrent")
            }
            disabled={disabled}
            className={`w-full min-w-0 max-w-full font-normal text-sm sm:text-lg font-medium [&_span.truncate]:whitespace-normal [&_span.truncate]:text-ellipsis [&_span.truncate]:overflow-hidden ${
              centerButtonWidth !== "auto" ? "" : ""
            }`}
          />
        </div>

        {datePickerEnabled ? (
          <div ref={pickerContainerRef} className="relative ml-0 sm:ml-1">
            <ActionButton
              ref={pickerButtonRef}
              label=""
              iconName="calendar"
              onClick={handleTogglePicker}
              color="neutral"
              variant="ghost"
              size="sm"
              ariaLabel={datePickerButtonLabel}
              ariaHasPopup="dialog"
              ariaExpanded={isPickerOpen}
              disabled={disabled}
              className="font-normal text-xs sm:text-sm"
            />

            {isPickerOpen && (
              <div
                role="dialog"
                aria-modal="false"
                aria-labelledby={labelId}
                aria-describedby={hintId}
                className="absolute right-0 mt-2 w-64 sm:w-72 rounded-2xl border border-base-300 bg-base-100 p-4 shadow-xl z-dropdown"
              >
                <form className="space-y-3" onSubmit={handleDateFormSubmit}>
                  <div className="form-control">
                    <label
                      htmlFor={dateInputId}
                      id={labelId}
                      className="label py-0"
                    >
                      <span className="label-text text-sm text-base-content">
                        {datePickerLabel}
                      </span>
                    </label>
                    <TextInput
                      ref={pickerInputRef}
                      id={dateInputId}
                      type="date"
                      value={pendingDateInput}
                      onChange={handleDateInputChange}
                      size="sm"
                      placeholder={datePickerPlaceholder}
                      aria-describedby={hintId}
                    />
                    {datePickerHint ? (
                      <span
                        id={hintId}
                        className="mt-1 block text-xs text-base-content/70"
                      >
                        {datePickerHint}
                      </span>
                    ) : null}
                  </div>

                  <div className="flex justify-end gap-2">
                    <ActionButton
                      label={t("common.cancel")}
                      size="sm"
                      variant="ghost"
                      onClick={handleCancelPicker}
                      type="button"
                    />
                    <ActionButton
                      label={t("common.confirm")}
                      size="sm"
                      color="primary"
                      variant="solid"
                      type="submit"
                      disabled={!pendingDateInput}
                    />
                  </div>
                </form>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* 后一周期按钮 */}
      <ActionButton
        label=""
        iconName="chevron-right"
        onClick={onNext}
        color="neutral"
        variant="ghost"
        size="sm"
        ariaLabel={`${t("planning.periodNavigation.next")}${t(`planning.periodNavigation.periodTypes.${periodType}`)}`}
        disabled={disabled}
        className="font-normal text-sm sm:text-base"
      />
    </div>
  );
};

export default PeriodNavigation;
