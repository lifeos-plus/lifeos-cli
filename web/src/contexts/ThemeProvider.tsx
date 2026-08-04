import React, { useCallback, useEffect, useMemo, useState } from "react";
import { usePreferenceWithBootstrap } from "@/hooks/queries/usePreferenceWithBootstrap";
import {
  AVAILABLE_THEMES,
  applyThemeWithTransition,
  getSavedTheme,
  resolveSystemTheme,
  setTheme as setThemeUtil,
  watchSystemThemeChange,
  type AppTheme,
} from "@/theme";
import { ThemeContext } from "./ThemeContext";

const THEME_PREFERENCE_KEY = "appearance.theme";

interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const storedTheme = useMemo<AppTheme>(() => {
    return getSavedTheme() ?? "system";
  }, []);

  const preference = usePreferenceWithBootstrap<AppTheme>({
    key: THEME_PREFERENCE_KEY,
    defaultValue: storedTheme,
    module: "appearance",
    validator: (value) => AVAILABLE_THEMES.includes(value),
  });

  const [effectiveTheme, setEffectiveTheme] = useState<
    Exclude<AppTheme, "system">
  >(() => {
    if (storedTheme === "system") return resolveSystemTheme();
    return storedTheme as Exclude<AppTheme, "system">;
  });

  const applyThemeValue = useCallback((nextTheme: AppTheme) => {
    setThemeUtil(nextTheme);
    const resolved = nextTheme === "system" ? resolveSystemTheme() : nextTheme;
    setEffectiveTheme(resolved);
  }, []);

  useEffect(() => {
    if (!preference.bootstrapped) return;
    applyThemeValue(preference.value);
  }, [applyThemeValue, preference.bootstrapped, preference.value]);

  useEffect(() => {
    if (!preference.bootstrapped || preference.value !== "system") return;

    const cleanup = watchSystemThemeChange((newSystemTheme) => {
      setEffectiveTheme(newSystemTheme);
      applyThemeWithTransition(newSystemTheme);
    });

    return cleanup;
  }, [preference.bootstrapped, preference.value]);

  const updateThemeValue = useCallback(
    (nextTheme: AppTheme) => {
      applyThemeValue(nextTheme);
      preference.updateValue(nextTheme);
    },
    [applyThemeValue, preference],
  );

  const saveThemeValue = useCallback(
    async (nextTheme: AppTheme) => {
      return await preference.saveValue(nextTheme);
    },
    [preference],
  );

  const setTheme = useCallback(
    async (nextTheme: AppTheme) => {
      updateThemeValue(nextTheme);
      await preference.saveValue(nextTheme);
    },
    [preference, updateThemeValue],
  );

  const value = useMemo(
    () => ({
      ...preference,
      value: preference.value,
      updateValue: updateThemeValue,
      saveValue: saveThemeValue,
      theme: preference.value,
      effectiveTheme,
      setTheme,
      isSystem: preference.value === "system",
    }),
    [preference, updateThemeValue, saveThemeValue, effectiveTheme, setTheme],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}
