const FALLBACK_TIMEZONES = [
  "UTC",
  "America/Los_Angeles",
  "America/New_York",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Asia/Singapore",
  "Australia/Sydney",
];

const PREFERRED_TIMEZONE_STORAGE_KEY = "cc_preferred_timezone";
let preferredTimezoneCache: string | null = null;

function getPreferredTimezone(): string | null {
  if (preferredTimezoneCache) {
    return preferredTimezoneCache;
  }
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(PREFERRED_TIMEZONE_STORAGE_KEY);
    if (stored && isValidTimezone(stored)) {
      preferredTimezoneCache = stored;
      return stored;
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function setPreferredTimezone(value?: string | null): void {
  if (!value || !isValidTimezone(value)) return;
  preferredTimezoneCache = value;
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PREFERRED_TIMEZONE_STORAGE_KEY, value);
  } catch {
    /* ignore */
  }
}

export function resolvePreferredTimezone(preferred?: string | null): string {
  if (preferred && isValidTimezone(preferred)) {
    return preferred;
  }
  const cached = getPreferredTimezone();
  return cached ?? "UTC";
}

function isValidTimezone(value?: string | null): boolean {
  if (!value || !value.trim()) {
    return false;
  }
  try {
    Intl.DateTimeFormat(undefined, { timeZone: value }).format(new Date());
    return true;
  } catch {
    return false;
  }
}

export function normalizeTimezone(preferred?: string | null): string {
  if (preferred && isValidTimezone(preferred)) {
    return preferred;
  }
  if (preferred) {
    const compact = preferred.replace(/\s+/g, "_");
    if (isValidTimezone(compact)) {
      return compact;
    }
  }
  return resolvePreferredTimezone();
}

export function getAvailableTimezones(): string[] {
  try {
    type SupportedValuesOfFn = (key: string) => string[];
    const supportedValuesOf = (
      Intl as { supportedValuesOf?: SupportedValuesOfFn }
    ).supportedValuesOf;
    if (typeof supportedValuesOf === "function") {
      const values = supportedValuesOf("timeZone");
      if (Array.isArray(values) && values.length > 0) {
        return values;
      }
    }
  } catch {
    /* ignore */
  }
  return FALLBACK_TIMEZONES;
}
