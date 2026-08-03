import type { CSSProperties, ReactElement, ReactNode } from "react";
import { createPortal } from "react-dom";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import {
  useBoundaryAwarePosition,
  type BoundaryConfig,
  type MenuPositionState,
} from "@/hooks/useBoundaryAwarePosition";

interface UseDropdownSurfaceOptions {
  anchorRef: React.RefObject<HTMLElement | null>;
  isOpen: boolean;
  onRequestClose?: () => void;
  usePortal?: boolean;
  portalTarget?: HTMLElement | null;
  estimatedHeight?: number;
  offset?: number;
  positionConfig?: Partial<BoundaryConfig>;
  minWidth?: number;
  maxWidth?: number;
  getPreferredWidth?: (anchorRect: DOMRect) => number | null | undefined;
  closeOnEscape?: boolean;
}

interface UseDropdownSurfaceResult {
  isOpen: boolean;
  menuRef: React.MutableRefObject<HTMLDivElement | null>;
  menuPos: MenuPositionState;
  dataTheme?: string;
  usePortal: boolean;
  portalTarget: HTMLElement | null;
  getSurfaceStyle: (style?: CSSProperties) => CSSProperties;
  renderSurface: (
    element: ReactElement,
    options?: { preventPortal?: boolean },
  ) => ReactNode;
  recomputePosition: () => void;
}

const defaultPortalTarget = (): HTMLElement | null => {
  if (typeof document === "undefined") {
    return null;
  }
  return document.body;
};

const VIEWPORT_INLINE_PADDING = 8;

const clampWidth = (
  width: number,
  minWidth?: number,
  maxWidth?: number,
): number => {
  let result = width;
  if (typeof minWidth === "number") {
    result = Math.max(result, minWidth);
  }
  if (typeof maxWidth === "number") {
    result = Math.min(result, maxWidth);
  }
  return result;
};

export const useDropdownSurface = (
  options: UseDropdownSurfaceOptions,
): UseDropdownSurfaceResult => {
  const {
    anchorRef,
    isOpen,
    onRequestClose,
    usePortal = true,
    portalTarget = defaultPortalTarget(),
    estimatedHeight,
    offset = 4,
    positionConfig,
    minWidth,
    maxWidth,
    getPreferredWidth,
    closeOnEscape = true,
  } = options;

  const menuRef = useRef<HTMLDivElement | null>(null);
  const [inheritedTheme, setInheritedTheme] = useState<string | undefined>(
    undefined,
  );
  const preferredWidthRef = useRef<number | undefined>(undefined);

  const { menuPos, computePosition } = useBoundaryAwarePosition({
    menuItemHeight: positionConfig?.menuItemHeight ?? 40,
    maxVisibleItems: positionConfig?.maxVisibleItems,
    maxHeight: positionConfig?.maxHeight,
  });
  const menuPosRef = useRef(menuPos);

  useEffect(() => {
    menuPosRef.current = menuPos;
  }, [menuPos]);

  const recomputePosition = useCallback(() => {
    if (!isOpen) return;
    const anchor = anchorRef.current;
    if (!anchor) return;

    const rect = anchor.getBoundingClientRect();
    const previousMenuPos = menuPosRef.current;
    const requestedWidth =
      getPreferredWidth?.(rect) ?? rect.width ?? previousMenuPos.width;
    const configuredWidth = clampWidth(requestedWidth, minWidth, maxWidth);
    const viewportWidth = Math.max(
      0,
      window.innerWidth - VIEWPORT_INLINE_PADDING * 2,
    );
    const clampedWidth = Math.min(configuredWidth, viewportWidth);
    preferredWidthRef.current = clampedWidth;

    const heightEstimate =
      estimatedHeight ?? positionConfig?.maxHeight ?? previousMenuPos.maxHeight;

    computePosition(
      anchor,
      typeof heightEstimate === "number" ? heightEstimate : undefined,
      usePortal ? clampedWidth : undefined,
    );

    if (!usePortal && menuRef.current && clampedWidth) {
      menuRef.current.style.minWidth = `${clampedWidth}px`;
    }
  }, [
    anchorRef,
    computePosition,
    estimatedHeight,
    getPreferredWidth,
    isOpen,
    maxWidth,
    minWidth,
    positionConfig?.maxHeight,
    usePortal,
  ]);

  useLayoutEffect(() => {
    if (!isOpen) return;
    recomputePosition();

    const handleReposition = () => {
      recomputePosition();
    };

    window.addEventListener("resize", handleReposition);
    window.addEventListener("scroll", handleReposition, true);
    return () => {
      window.removeEventListener("resize", handleReposition);
      window.removeEventListener("scroll", handleReposition, true);
    };
  }, [isOpen, recomputePosition]);

  useLayoutEffect(() => {
    if (!isOpen) return;
    const anchor = anchorRef.current;
    if (!anchor) return;
    const themedAncestor = anchor.closest("[data-theme]");
    const themeName =
      themedAncestor instanceof HTMLElement
        ? themedAncestor.getAttribute("data-theme") || undefined
        : undefined;
    setInheritedTheme(themeName);
  }, [anchorRef, isOpen]);

  useEffect(() => {
    if (!isOpen || !onRequestClose) return;

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      const anchorNode = anchorRef.current;
      if (
        (menuRef.current && menuRef.current.contains(target)) ||
        (anchorNode && anchorNode.contains(target))
      ) {
        return;
      }
      onRequestClose();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!closeOnEscape) return;
      if (event.key === "Escape") {
        onRequestClose();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    if (closeOnEscape) {
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      if (closeOnEscape) {
        document.removeEventListener("keydown", handleKeyDown);
      }
    };
  }, [anchorRef, closeOnEscape, isOpen, onRequestClose]);

  const getSurfaceStyle = useCallback(
    (style?: CSSProperties): CSSProperties => {
      const baseStyle: CSSProperties = {};
      if (usePortal) {
        baseStyle.position = "fixed";
        baseStyle.top = menuPos.top;
        baseStyle.left = menuPos.left;
        baseStyle.width =
          preferredWidthRef.current ?? menuPos.width ?? baseStyle.width;
      } else {
        baseStyle.position = "absolute";
        baseStyle.marginTop = offset;
      }
      if (menuPos.maxHeight) {
        baseStyle.maxHeight = `${menuPos.maxHeight}px`;
      }
      return { ...baseStyle, ...style };
    },
    [
      menuPos.left,
      menuPos.maxHeight,
      menuPos.top,
      menuPos.width,
      offset,
      usePortal,
    ],
  );

  const renderSurface = useCallback(
    (
      element: React.ReactElement,
      renderOptions?: { preventPortal?: boolean },
    ): React.ReactNode => {
      if (!isOpen) return null;
      if (!usePortal || renderOptions?.preventPortal || !portalTarget) {
        return element;
      }
      return createPortal(element, portalTarget);
    },
    [isOpen, portalTarget, usePortal],
  );

  return {
    isOpen,
    menuRef,
    menuPos,
    dataTheme: inheritedTheme,
    usePortal,
    portalTarget,
    getSurfaceStyle,
    renderSurface,
    recomputePosition,
  };
};
