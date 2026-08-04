import React from "react";
import { useTranslation } from "react-i18next";
import ActionButton from "./ActionButton";
import PeriodNavigation from "./PeriodNavigation";
import ToolbarContainer from "./ToolbarContainer";
import type { QueryMode } from "@/hooks/useQueryMode";
import { dateStringToISO, formatDateInTimezone } from "@/utils/datetime";

interface TimeLogToolbarProps {
  queryMode: QueryMode;
  selectedDate: Date;
  timezone?: string;
  onDateChange: (date: Date) => void;
  onQueryModeChange: (mode: QueryMode) => void;
}

const shiftDateInTimezone = (
  date: Date,
  timezone: string | undefined,
  deltaDays: number,
): Date => {
  if (!timezone) {
    const nextDate = new Date(date);
    nextDate.setDate(nextDate.getDate() + deltaDays);
    return nextDate;
  }

  const dateOnly = formatDateInTimezone(date, timezone);
  const [year, month, day] = dateOnly.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, month - 1, day + deltaDays));
  const shiftedDateOnly = [
    shifted.getUTCFullYear(),
    String(shifted.getUTCMonth() + 1).padStart(2, "0"),
    String(shifted.getUTCDate()).padStart(2, "0"),
  ].join("-");
  const shiftedIso = dateStringToISO(shiftedDateOnly, timezone, false);
  return shiftedIso ? new Date(shiftedIso) : date;
};

const TimeLogToolbar: React.FC<TimeLogToolbarProps> = ({
  queryMode,
  selectedDate,
  timezone,
  onDateChange,
  onQueryModeChange,
}) => {
  const { t } = useTranslation();
  const goToPreviousDay = () => {
    onDateChange(shiftDateInTimezone(selectedDate, timezone, -1));
  };

  const goToNextDay = () => {
    onDateChange(shiftDateInTimezone(selectedDate, timezone, 1));
  };

  const goToToday = () => {
    onDateChange(new Date());
  };

  const isImportMode = queryMode === "import";

  return (
    <ToolbarContainer
      className="mb-4"
      padding="md"
      layout="three-column"
    >
      {/* 左列：导入与返回按钮 */}
      <div className="flex justify-start gap-2 flex-wrap">
        {!isImportMode && (
          <ActionButton
            label={t("timeLog.toolbar.bulkImport")}
            iconName="arrow-down"
            color="primary"
            variant="outline"
            ariaLabel={t("timeLog.toolbar.bulkImport")}
            onClick={() => onQueryModeChange("import")}
            className="font-normal text-base"
          />
        )}
        {isImportMode && (
          <ActionButton
            label={t("timeLog.toolbar.returnToSingle")}
            iconName="arrow-left"
            color="neutral"
            variant="outline"
            ariaLabel={t("timeLog.toolbar.returnToSingle")}
            onClick={() => onQueryModeChange("single")}
            className="font-normal text-base"
          />
        )}
      </div>

      {/* 中列：日期切换与今天 */}
      <div className="flex items-center gap-2 justify-start sm:justify-center">
        <PeriodNavigation
          periodType="day"
          selectedDate={selectedDate}
          onPrevious={goToPreviousDay}
          onNext={goToNextDay}
          onCurrent={goToToday}
          onSelectDate={onDateChange}
          timezone={timezone}
          disabled={queryMode === "advanced"}
        />
      </div>

      {/* 右列：模式切换 */}
      <div className="flex justify-end">
        <ActionButton
          label={
            queryMode === "advanced"
              ? t("timeLog.toolbar.returnToSingle")
              : t("timeLog.toolbar.advancedFeatures")
          }
          iconName={queryMode === "advanced" ? "calendar" : "search"}
          color={queryMode === "advanced" ? "neutral" : "primary"}
          variant="solid"
          ariaLabel={
            queryMode === "advanced"
              ? "Switch to single day mode"
              : "Switch to advanced search mode"
          }
          onClick={() =>
            onQueryModeChange(queryMode === "advanced" ? "single" : "advanced")
          }
          className="font-normal text-base"
        />
      </div>
    </ToolbarContainer>
  );
};

export default TimeLogToolbar;
