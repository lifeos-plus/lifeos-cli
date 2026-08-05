import React, { useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  dateStringToISO,
  formatDate,
  formatDateTime,
  localDateTimeLocalToUtcIso,
  normalizeTimezone,
  utcToLocalDateTimeLocal,
} from "@/utils/datetime";
import TextInput from "./TextInput";
import { FORM_LABEL_COMPACT_CLASS } from "./styles";

interface DateTimeSelectorProps {
  /** Current ISO datetime string */
  value: string;
  /** Whether this is for an all-day planned event (date only) */
  isAllDay?: boolean;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Callback when datetime changes */
  onChange: (isoString: string) => void;
  /** Placeholder text */
  placeholder?: string;
  /** HTML id for the date input */
  dateId?: string;
  /** HTML id for the time input */
  timeId?: string;
  /** Custom quick time options */
  quickTimeOptions?: string[];
  /** Additional CSS classes */
  className?: string;
  /** Preferred timezone (falls back to the cached system preference or UTC) */
  timezone?: string;
}

const DEFAULT_QUICK_TIMES = [
  "00:00",
  "06:00",
  "08:00",
  "09:00",
  "12:00",
  "14:00",
  "17:00",
  "18:00",
  "20:00",
  "22:00",
];

export default function DateTimeSelector({
  value,
  isAllDay = false,
  disabled = false,
  onChange,
  placeholder = "",
  dateId,
  timeId,
  quickTimeOptions = DEFAULT_QUICK_TIMES,
  className = "",
  timezone,
}: DateTimeSelectorProps) {
  const { t } = useTranslation();

  // Get user's timezone
  const userTimezone = useMemo(() => normalizeTimezone(timezone), [timezone]);

  // Parse current value to date and time parts (timezone-aware)
  const { datePart, timePart } = useMemo(() => {
    if (!value) {
      return { datePart: "", timePart: "" };
    }

    if (isAllDay) {
      return {
        datePart: formatDate(value, userTimezone),
        timePart: "",
      };
    }

    const localDateTime = utcToLocalDateTimeLocal(value, userTimezone);
    const [localDate, localTime] = localDateTime.split("T");

    return {
      datePart: localDate ?? "",
      timePart: localTime ?? "",
    };
  }, [value, isAllDay, userTimezone]);

  const handleDateChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newDate = e.target.value;
      if (!newDate) {
        onChange("");
        return;
      }

      if (isAllDay) {
        onChange(dateStringToISO(newDate, userTimezone));
      } else if (timePart) {
        onChange(
          localDateTimeLocalToUtcIso(
            `${newDate}T${timePart}`,
            userTimezone,
          ),
        );
      } else {
        onChange(dateStringToISO(newDate, userTimezone));
      }
    },
    [isAllDay, timePart, onChange, userTimezone],
  );

  const handleTimeChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newTime = e.target.value;
      if (!newTime || !datePart) {
        return;
      }

      onChange(
        localDateTimeLocalToUtcIso(
          `${datePart}T${newTime}`,
          userTimezone,
        ),
      );
    },
    [datePart, onChange, userTimezone],
  );

  const handleQuickTimeSelect = useCallback(
    (time: string) => {
      if (!datePart) {
        return;
      }

      onChange(
        localDateTimeLocalToUtcIso(
          `${datePart}T${time}`,
          userTimezone,
        ),
      );
    },
    [datePart, onChange, userTimezone],
  );

  return (
    <div className={`space-y-2 ${className}`}>
      {/* Date input */}
      <div>
        <label
          htmlFor={dateId}
          className={FORM_LABEL_COMPACT_CLASS}
        >
          {t("common.date")}
        </label>
        <TextInput
          id={dateId}
          type="date"
          value={datePart}
          onChange={handleDateChange}
          disabled={disabled}
          placeholder={placeholder}
        />
      </div>

      {/* Time input (only for non-all-day planned events) */}
      {!isAllDay && (
        <div>
          <label
            htmlFor={timeId}
            className={FORM_LABEL_COMPACT_CLASS}
          >
            {t("common.time")}
          </label>
          <div className="space-y-2">
            {/* Standard time input */}
            <TextInput
              id={timeId}
              type="time"
              value={timePart}
              onChange={handleTimeChange}
              disabled={disabled}
              step="300" // 5-minute intervals
            />

            {/* Quick time buttons */}
            <div className="flex flex-wrap gap-1">
              {quickTimeOptions.map((time) => (
                <button
                  key={time}
                  type="button"
                  onClick={() => handleQuickTimeSelect(time)}
                  disabled={disabled}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    timePart === time
                      ? "bg-primary text-primary-content"
                      : "bg-base-200 hover:bg-base-300 text-base-content"
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {time}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Display current selection in human-readable format */}
      {value && (
        <div className="text-xs text-base-content/60 mt-2">
          {t("common.selected")}: {formatDateTime(value)}
        </div>
      )}
    </div>
  );
}
