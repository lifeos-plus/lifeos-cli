import { useSystemTimezone } from "@/hooks/useSystemTimezone";
import { useCalendarAdapter } from "@/hooks/useCalendarAdapter";
import type { CalendarAdapter } from "@/utils/calendar";
import { useAreas } from "@/hooks/queries/useAreas";
import { useAreaOrderReadOnly } from "@/hooks/queries/useAreaOrderReadOnly";

interface InsightsPageData {
  firstDayOfWeek: number;
  calendarSystem: "gregorian" | "mayan_13_moon";
  activeTimezone: string;
  calendarAdapter: CalendarAdapter;
  areas: ReturnType<typeof useAreas>["areas"];
  areaMap: ReturnType<typeof useAreas>["areaMap"];
  areaOrder: ReturnType<typeof useAreaOrderReadOnly>["order"];
  calendarLoading: boolean;
}

export function useInsightsPageData(): InsightsPageData {
  const {
    adapter: calendarAdapter,
    calendarSystem,
    firstDayOfWeek,
    loading: calendarPreferencesLoading,
  } = useCalendarAdapter();

  const timezonePreferenceState = useSystemTimezone();
  const activeTimezone = timezonePreferenceState.timezone;
  const calendarLoading =
    calendarPreferencesLoading || timezonePreferenceState.loading;

  const { areas, areaMap } = useAreas();
  const { order: areaOrder } = useAreaOrderReadOnly();

  return {
    firstDayOfWeek,
    calendarSystem,
    activeTimezone,
    calendarAdapter,
    areas,
    areaMap,
    areaOrder,
    calendarLoading,
  };
}
