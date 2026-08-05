import { usePreferenceWithBootstrap } from "@/hooks/queries/usePreferenceWithBootstrap";
import {
  normalizeTimezone,
  resolvePreferredTimezone,
} from "@/utils/datetime";

export function useSystemTimezone() {
  const preference = usePreferenceWithBootstrap<string>({
    key: "system.timezone",
    defaultValue: resolvePreferredTimezone(),
    module: "system",
    validator: (value) =>
      typeof value === "string" && normalizeTimezone(value) === value,
  });

  return {
    ...preference,
    timezone: normalizeTimezone(preference.value),
  };
}
