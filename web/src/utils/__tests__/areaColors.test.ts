import { describe, expect, it } from "vitest";

import { getReadableTextColor } from "@/utils/areaColors";

describe("getReadableTextColor", () => {
  it("uses dark text on light area colors", () => {
    expect(getReadableTextColor("#F59E0B")).toBe("#111827");
  });

  it("uses light text on dark area colors", () => {
    expect(getReadableTextColor("#1E3A8A")).toBe("#FFFFFF");
  });

  it("falls back to dark text for invalid colors", () => {
    expect(getReadableTextColor("not-a-color")).toBe("#111827");
  });
});
