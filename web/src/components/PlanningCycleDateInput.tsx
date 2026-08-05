import React from "react";
import { useTranslation } from "react-i18next";
import { usePlanningCycle } from "@/hooks/useCalendarAdapter";
import { parseLocalDateString } from "@/utils/calendar";
import { formatDateKey } from "@/utils/datetime";
import EnumSelect from "./selects/EnumSelect";
import { TextInput } from "./forms";

interface PlanningCycleDateInputProps {
  cycleType: string;
  startDate: string | undefined;
  onStartDateChange: (startDate: string | undefined) => void;
  disabled?: boolean;
  className?: string;
  id?: string;
  name?: string;
  /** Optional year range for year selection */
  minYear?: number;
  maxYear?: number;
}

/**
 * Planning cycle date input component
 * Handles different input types based on cycle type and calendar system
 */
export const PlanningCycleDateInput: React.FC<PlanningCycleDateInputProps> = ({
  cycleType,
  startDate,
  onStartDateChange,
  disabled = false,
  className = "",
  id,
  name,
  minYear = 2020,
  maxYear = 2030,
}) => {
  const { t } = useTranslation();
  const { adapter } = usePlanningCycle();

  // Handle month selection for any calendar system
  if (cycleType === "month") {
    const monthInfo = startDate
      ? adapter.getMonthInfo(parseLocalDateString(startDate))
      : null;
    const isValidMonth = monthInfo?.isValidMonth;

    if (isValidMonth) {
      // Pass current date to get month options with start date information
      const currentDate = startDate
        ? parseLocalDateString(startDate)
        : new Date();

      // Get localized month names for Gregorian calendar
      const monthNames = Array.from({ length: 12 }, (_, i) =>
        t(`months.${i + 1}`),
      );

      const monthOptions = adapter.getMonthOptions(currentDate, monthNames);
      return (
        <EnumSelect
          id={id || "month-select"}
          value={monthInfo?.monthIndex ? String(monthInfo.monthIndex) : ""}
          onChange={(value) => {
            if (value) {
              const monthIndex = parseInt(value);
              const yearStart = adapter.getYearStart(currentDate);
              const monthStart = adapter.getMonthStart(yearStart, monthIndex);
              onStartDateChange(formatDateKey(monthStart));
            }
          }}
          disabled={disabled}
          autoWidth={true}
          options={[
            { value: "", label: t("common.please_select"), disabled: true },
            ...monthOptions.map((option) => ({
              value: String(option.index),
              label: option.name,
            })),
          ]}
        />
      );
    }
  }

  // Handle year-based cycle selection via EnumSelect with configurable range
  if (cycleType === "year" || cycleType === "7years") {
    // Use adapter's display year logic for consistent behavior across calendar systems
    let currentYear = "";
    if (startDate && adapter && adapter.getDisplayYear) {
      currentYear = String(adapter.getDisplayYear(startDate));
    }

    const clampedMin = Math.min(minYear, maxYear);
    const clampedMax = Math.max(minYear, maxYear);
    const yearOptions = Array.from({ length: clampedMax - clampedMin + 1 }).map(
      (_, i) => {
        const y = clampedMin + i;
        return { value: String(y), label: String(y) };
      },
    );

    return (
      <EnumSelect
        id={id || "year-select"}
        value={currentYear}
        onChange={(value) => {
          if (value === undefined || value === "") {
            onStartDateChange(undefined);
            return;
          }
          const year =
            typeof value === "number" ? value : parseInt(String(value));
          if (
            !Number.isNaN(year) &&
            adapter &&
            adapter.getDateForYearSelection
          ) {
            const newStart = adapter.getDateForYearSelection(year);
            onStartDateChange(formatDateKey(newStart));
          }
        }}
        disabled={disabled}
        options={[
          { value: "", label: t("common.please_select"), disabled: true },
          ...yearOptions,
        ]}
      />
    );
  }

  // Handle regular date inputs
  const getInputType = () => {
    switch (cycleType) {
      case "year":
      case "7years":
        return "number";
      case "month":
        return "month";
      case "week":
      case "day":
        return "date";
      default:
        return "date";
    }
  };

  const getInputValue = () => {
    if (!startDate) return "";

    switch (cycleType) {
      case "year":
      case "7years":
        // Use adapter's display year logic for consistent behavior
        if (adapter && adapter.getDisplayYear) {
          return adapter.getDisplayYear(startDate);
        }
        // Fallback to simple parsing
        return parseInt(startDate.split("-")[0]);
      case "month": {
        const [year, month] = startDate.split("-");
        return `${year}-${month}`;
      }
      default:
        return startDate;
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let newStartDate: string | undefined;

    switch (cycleType) {
      case "month": {
        const [year, month] = e.target.value.split("-");
        if (year && month) {
          newStartDate = `${year}-${month.padStart(2, "0")}-01`;
        }
        break;
      }
      case "week": {
        const selectedDate = parseLocalDateString(e.target.value);
        const weekStart = adapter.getWeekStart(selectedDate);
        newStartDate = formatDateKey(weekStart);
        break;
      }
      case "day": {
        newStartDate = e.target.value || undefined;
        break;
      }
      default:
        newStartDate = e.target.value || undefined;
    }

    onStartDateChange(newStartDate);
  };

  return (
    <TextInput
      id={id}
      name={name}
      type={getInputType()}
      value={getInputValue()}
      onChange={handleChange}
      className={`w-full ${className}`.trim()}
      disabled={disabled}
      placeholder={t("common.please_select")}
    />
  );
};
