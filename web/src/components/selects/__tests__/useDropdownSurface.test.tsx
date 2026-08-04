import { createRef } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useDropdownSurface } from "@/components/selects/useDropdownSurface";

describe("useDropdownSurface", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("honors the viewport when a configured minimum width is wider", async () => {
    vi.spyOn(window, "innerWidth", "get").mockReturnValue(320);
    vi.spyOn(window, "innerHeight", "get").mockReturnValue(800);
    const anchor = document.createElement("div");
    vi.spyOn(anchor, "getBoundingClientRect").mockReturnValue({
      bottom: 140,
      height: 40,
      left: 16,
      right: 196,
      top: 100,
      width: 180,
      x: 16,
      y: 100,
      toJSON: () => ({}),
    } as DOMRect);
    const anchorRef = createRef<HTMLElement>();
    anchorRef.current = anchor;

    const { result } = renderHook(() =>
      useDropdownSurface({
        anchorRef,
        isOpen: true,
        minWidth: 480,
        maxWidth: 800,
        getPreferredWidth: () => 640,
      }),
    );

    await waitFor(() => {
      expect(result.current.getSurfaceStyle().width).toBe(304);
      expect(result.current.getSurfaceStyle().left).toBe(8);
    });
  });
});
