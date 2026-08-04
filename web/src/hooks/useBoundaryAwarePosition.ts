import { useState, useCallback, useRef } from "react";

export interface BoundaryConfig {
  menuItemHeight: number;
  maxVisibleItems?: number;
  maxHeight?: number;
}

export interface MenuPositionState {
  top: number;
  left: number;
  width: number;
  maxHeight?: number;
  openDirection?: "down" | "up";
}

const FLOAT_TOLERANCE = 0.5;
const VIEWPORT_INLINE_PADDING = 8;

const areMenuPositionsEqual = (
  prev: MenuPositionState,
  next: MenuPositionState,
) => {
  const isEqualNumber = (
    a: number | undefined,
    b: number | undefined,
  ): boolean => {
    if (a === undefined || b === undefined) {
      return a === b;
    }
    // Ignore sub-pixel jitter that would otherwise create redundant renders.
    return Math.abs(a - b) < FLOAT_TOLERANCE;
  };

  return (
    isEqualNumber(prev.top, next.top) &&
    isEqualNumber(prev.left, next.left) &&
    isEqualNumber(prev.width, next.width) &&
    isEqualNumber(prev.maxHeight, next.maxHeight) &&
    prev.openDirection === next.openDirection
  );
};

/**
 * Hook for intelligent dropdown menu positioning with boundary detection
 *
 * Automatically determines whether to open dropdown above or below trigger element
 * based on available viewport space.
 */
export const useBoundaryAwarePosition = (config: BoundaryConfig) => {
  const [menuPos, setMenuPos] = useState<MenuPositionState>({
    top: 0,
    left: 0,
    width: 0,
  });

  // Use ref to avoid dependency on config in callback
  const configRef = useRef(config);
  configRef.current = config;

  const computePosition = useCallback(
    (
      inputElement: HTMLElement,
      actualMenuHeight?: number,
      customWidth?: number,
    ) => {
      const rect = inputElement.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const viewportWidth = window.innerWidth;
      const bottomPadding = 20;
      const gapSize = 4;

      // Use ref to get latest config without dependency
      const currentConfig = configRef.current;

      // Calculate estimated menu height
      const maxItems = currentConfig.maxVisibleItems || 8;
      const estimatedHeight =
        actualMenuHeight ||
        Math.min(
          maxItems * currentConfig.menuItemHeight + 16,
          currentConfig.maxHeight || 300,
        );

      // Calculate available space
      const spaceBelow = viewportHeight - rect.bottom - bottomPadding;
      const spaceAbove = rect.top - bottomPadding;

      // Determine opening direction and position
      let top: number;
      let maxHeight: number;
      let openDirection: "down" | "up";

      if (spaceBelow >= estimatedHeight || spaceBelow >= spaceAbove) {
        // Open downward
        top = rect.bottom + gapSize;
        maxHeight = Math.min(estimatedHeight, spaceBelow - gapSize);
        openDirection = "down";
      } else {
        // Open upward
        top = rect.top - estimatedHeight - gapSize;
        maxHeight = Math.min(estimatedHeight, spaceAbove - gapSize);
        openDirection = "up";
      }

      // Ensure minimum position constraints
      const minTop = bottomPadding;
      if (top < minTop) {
        top = minTop;
        maxHeight = rect.top - minTop - gapSize;
      }

      const requestedWidth = customWidth || rect.width;
      const availableWidth = Math.max(
        0,
        viewportWidth - VIEWPORT_INLINE_PADDING * 2,
      );
      const width = Math.min(requestedWidth, availableWidth);
      const maxLeft = Math.max(
        VIEWPORT_INLINE_PADDING,
        viewportWidth - VIEWPORT_INLINE_PADDING - width,
      );
      const left = Math.min(
        Math.max(rect.left, VIEWPORT_INLINE_PADDING),
        maxLeft,
      );

      const nextState: MenuPositionState = {
        top,
        left,
        width,
        maxHeight: Math.max(maxHeight, 100),
        openDirection,
      };

      setMenuPos((prevState) => {
        if (areMenuPositionsEqual(prevState, nextState)) {
          return prevState;
        }
        return nextState;
      });
    },
    [],
  ); // Empty dependency array to prevent infinite loops

  return { menuPos, computePosition };
};
