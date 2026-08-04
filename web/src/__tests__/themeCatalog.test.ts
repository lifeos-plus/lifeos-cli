import { describe, expect, it } from "vitest";

import themeCatalog from "@/config/themeCatalog.json";
import en from "@/locales/en/common.json";
import zh from "@/locales/zh/common.json";
import { AVAILABLE_THEMES } from "@/theme";

describe("theme catalog", () => {
  it("drives the application theme list", () => {
    expect(AVAILABLE_THEMES).toEqual([
      "system",
      ...Object.keys(themeCatalog.themes),
    ]);
    expect(new Set(AVAILABLE_THEMES).size).toBe(AVAILABLE_THEMES.length);
  });

  it("has labels for every available theme in each locale", () => {
    expect(Object.keys(en.theme)).toEqual(AVAILABLE_THEMES);
    expect(Object.keys(zh.theme)).toEqual(AVAILABLE_THEMES);
  });
});
