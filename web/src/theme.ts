import themeCatalog from "@/config/themeCatalog.json";

const THEME_STORAGE_KEY = "app-theme";

type DaisyTheme = keyof typeof themeCatalog.themes;

export type AppTheme = "system" | DaisyTheme;

export const AVAILABLE_THEMES: AppTheme[] = [
  "system",
  ...(Object.keys(themeCatalog.themes) as DaisyTheme[]),
];

function applyTheme(theme: Exclude<AppTheme, "system">) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
}

export function applyThemeWithTransition(theme: Exclude<AppTheme, "system">) {
  if (typeof document === "undefined") return;

  // Remove initializing class to enable transitions
  document.documentElement.classList.remove("theme-initializing");

  // Apply theme
  document.documentElement.setAttribute("data-theme", theme);
}

export function getSavedTheme(): AppTheme | null {
  if (typeof window === "undefined") return null;
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (!saved) return null;
    if (AVAILABLE_THEMES.includes(saved as AppTheme)) return saved as AppTheme;
    return null;
  } catch {
    return null;
  }
}

function saveTheme(theme: AppTheme) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // ignore storage errors
  }
}

export function resolveSystemTheme(): "pastel" | "night" {
  if (typeof window === "undefined" || !window.matchMedia) return "pastel";
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "night" : "pastel";
}

export function initTheme() {
  // Add initializing class to prevent flash during initial load
  if (typeof document !== "undefined") {
    document.documentElement.classList.add("theme-initializing");
  }

  const saved = getSavedTheme();
  const effective: Exclude<AppTheme, "system"> =
    saved === "system" || !saved ? resolveSystemTheme() : saved;

  // Use regular applyTheme for initial load (no transition)
  applyTheme(effective);

  // Remove initializing class after a short delay to enable transitions
  if (typeof document !== "undefined") {
    setTimeout(() => {
      document.documentElement.classList.remove("theme-initializing");
    }, 100);
  }
}

export function setTheme(next: AppTheme) {
  saveTheme(next);
  const effective: Exclude<AppTheme, "system"> =
    next === "system" ? resolveSystemTheme() : next;
  applyThemeWithTransition(effective);
}

export function watchSystemThemeChange(
  callback: (theme: "pastel" | "night") => void,
) {
  if (typeof window === "undefined") return () => {};

  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const handleChange = () => {
    callback(resolveSystemTheme());
  };

  mediaQuery.addEventListener("change", handleChange);
  return () => mediaQuery.removeEventListener("change", handleChange);
}
