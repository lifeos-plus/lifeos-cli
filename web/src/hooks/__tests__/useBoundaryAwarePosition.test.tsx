import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useBoundaryAwarePosition } from "@/hooks/useBoundaryAwarePosition";

const mockRect = (left: number, width: number): DOMRect =>
  ({
    bottom: 140,
    height: 40,
    left,
    right: left + width,
    top: 100,
    width,
    x: left,
    y: 100,
    toJSON: () => ({}),
  }) as DOMRect;

describe("useBoundaryAwarePosition", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("clamps wide portal surfaces to the viewport", () => {
    vi.spyOn(window, "innerWidth", "get").mockReturnValue(320);
    vi.spyOn(window, "innerHeight", "get").mockReturnValue(800);
    const anchor = document.createElement("div");
    vi.spyOn(anchor, "getBoundingClientRect").mockReturnValue(
      mockRect(16, 180),
    );

    const { result } = renderHook(() =>
      useBoundaryAwarePosition({ menuItemHeight: 40 }),
    );

    act(() => result.current.computePosition(anchor, 240, 640));

    expect(result.current.menuPos.width).toBe(304);
    expect(result.current.menuPos.left).toBe(8);
  });

  it("moves a surface left when it would cross the right viewport edge", () => {
    vi.spyOn(window, "innerWidth", "get").mockReturnValue(1024);
    vi.spyOn(window, "innerHeight", "get").mockReturnValue(800);
    const anchor = document.createElement("div");
    vi.spyOn(anchor, "getBoundingClientRect").mockReturnValue(
      mockRect(900, 100),
    );

    const { result } = renderHook(() =>
      useBoundaryAwarePosition({ menuItemHeight: 40 }),
    );

    act(() => result.current.computePosition(anchor, 240, 300));

    expect(result.current.menuPos.width).toBe(300);
    expect(result.current.menuPos.left).toBe(716);
  });
});
