import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

export interface HoverTooltipOverlayPosition {
  x: number;
  y: number;
}

interface HoverTooltipOverlayProps {
  visible: boolean;
  position: HoverTooltipOverlayPosition | null;
  children: React.ReactNode;
  offset?: {
    x?: number;
    y?: number;
  };
  className?: string;
}

const baseClasses =
  "fixed pointer-events-none z-modal bg-base-200 text-base-content/70 text-base px-4 py-3 rounded-lg shadow-xl max-w-64 border border-base-200";

const HoverTooltipOverlay: React.FC<HoverTooltipOverlayProps> = ({
  visible,
  position,
  children,
  offset = {},
  className = "",
}) => {
  const [mounted, setMounted] = useState(false);
  const [style, setStyle] = useState<{ left: number; top: number } | null>(
    null,
  );
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const latestPositionRef = useRef<{
    position: HoverTooltipOverlayPosition | null;
    offsetX: number;
    offsetY: number;
  }>({ position: null, offsetX: 0, offsetY: 0 });

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  const resolvedOffsetX = offset?.x ?? 15;
  const resolvedOffsetY = offset?.y ?? -10;

  useEffect(() => {
    latestPositionRef.current = {
      position,
      offsetX: resolvedOffsetX,
      offsetY: resolvedOffsetY,
    };
  }, [position, resolvedOffsetX, resolvedOffsetY]);

  const updatePosition = useCallback(() => {
    if (!visible) return;
    const {
      position: latestPosition,
      offsetX,
      offsetY,
    } = latestPositionRef.current;
    if (!latestPosition) {
      return;
    }

    const baseLeft = latestPosition.x + offsetX;
    const baseTop = latestPosition.y + offsetY;
    let adjustedLeft = baseLeft;
    let adjustedTop = baseTop;

    const tooltipElement = tooltipRef.current;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const margin = 12;

    if (tooltipElement) {
      const { offsetWidth, offsetHeight } = tooltipElement;
      const maxLeft = Math.max(margin, viewportWidth - offsetWidth - margin);
      const maxTop = Math.max(margin, viewportHeight - offsetHeight - margin);

      adjustedLeft = Math.min(Math.max(adjustedLeft, margin), maxLeft);

      adjustedTop = Math.min(Math.max(adjustedTop, margin), maxTop);
    }

    setStyle((prev) => {
      if (prev && prev.left === adjustedLeft && prev.top === adjustedTop) {
        return prev;
      }
      return { left: adjustedLeft, top: adjustedTop };
    });
  }, [visible]);

  useLayoutEffect(() => {
    if (!visible || !position) return;
    updatePosition();
  }, [visible, position, resolvedOffsetX, resolvedOffsetY, updatePosition]);

  useEffect(() => {
    if (!visible) {
      setStyle(null);
    }
  }, [visible]);

  useEffect(() => {
    if (!visible) return;

    const handleReposition = () => {
      updatePosition();
    };

    window.addEventListener("resize", handleReposition);
    window.addEventListener("scroll", handleReposition, true);

    return () => {
      window.removeEventListener("resize", handleReposition);
      window.removeEventListener("scroll", handleReposition, true);
    };
  }, [visible, updatePosition]);

  if (!mounted || !visible || !position) {
    return null;
  }

  const fallbackLeft = position.x + resolvedOffsetX;
  const fallbackTop = position.y + resolvedOffsetY;
  const computedLeft = style?.left ?? fallbackLeft;
  const computedTop = style?.top ?? fallbackTop;

  return createPortal(
    <div
      role="tooltip"
      className={`${baseClasses} ${className}`.trim()}
      ref={tooltipRef}
      style={{ left: computedLeft, top: computedTop }}
    >
      {children}
    </div>,
    document.body,
  );
};

export default HoverTooltipOverlay;
