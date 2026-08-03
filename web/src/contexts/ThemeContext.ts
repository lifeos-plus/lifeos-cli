import { createContext, useContext } from "react";
import type { PreferenceWithBootstrapReturn } from "@/hooks/queries/usePreferenceWithBootstrap";
import type { AppTheme } from "@/theme";

interface ThemeContextValue extends PreferenceWithBootstrapReturn<AppTheme> {
  theme: AppTheme;
  effectiveTheme: Exclude<AppTheme, "system">;
  setTheme: (nextTheme: AppTheme) => Promise<void>;
  isSystem: boolean;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }

  return context;
}
