import React from "react";
import type { UUID } from "@/types/primitive";
import { DEFAULT_AREA_COLOR, UNKNOWN_AREA_COLOR } from "@/utils/areaColors";

interface AreaBadgeProps {
  /** When provided, used to look up name/color if `name`/`color` not directly given */
  areaId?: UUID;
  /** Area lookup map: id -> { name, color } (stable reference is recommended) */
  areaMap?: Map<UUID, { name: string; color: string }>;
  /** Direct name override; takes precedence over map */
  name?: string;
  /** Direct color override; takes precedence over map */
  color?: string;
  /** Show the name text; set false to render dot only */
  showLabel?: boolean;
  className?: string;
  labelClassName?: string;
  /** Control dot size: sm (2), md (3), lg (4) */
  size?: "sm" | "md" | "lg";
  ariaLabel?: string;
}

const AreaBadgeComponent: React.FC<AreaBadgeProps> = ({
  areaId,
  areaMap,
  name,
  color,
  showLabel = true,
  className,
  labelClassName = "text-base",
  size = "md",
  ariaLabel,
}) => {
  const dotClass =
    size === "lg" ? "w-4 h-4" : size === "sm" ? "w-2 h-2" : "w-3 h-3";

  const isUnknownId = typeof areaId === "string" && areaId === "-1";

  const resolvedColor =
    color ??
    (typeof areaId === "string"
      ? (areaMap?.get(areaId)?.color ??
        (isUnknownId ? UNKNOWN_AREA_COLOR : DEFAULT_AREA_COLOR))
      : DEFAULT_AREA_COLOR);

  const resolvedName =
    name ??
    (typeof areaId === "string"
      ? (areaMap?.get(areaId)?.name ??
        (isUnknownId ? "未知" : "未知领域"))
      : "");

  return (
    <div
      className={["flex items-center flex-shrink-0", className || ""]
        .filter(Boolean)
        .join(" ")}
    >
      <span
        className={`${dotClass} rounded-full mr-2 inline-block flex-shrink-0`}
        style={{ backgroundColor: resolvedColor }}
        aria-label={ariaLabel || resolvedName || "area"}
      />
      {showLabel ? (
        <span
          className={`${labelClassName} text-base-content truncate max-w-[120px]`}
        >
          {resolvedName}
        </span>
      ) : null}
    </div>
  );
};

const AreaBadge = React.memo(
  AreaBadgeComponent,
  (prev, next) =>
    prev.areaId === next.areaId &&
    prev.areaMap === next.areaMap &&
    prev.name === next.name &&
    prev.color === next.color &&
    prev.showLabel === next.showLabel &&
    prev.className === next.className &&
    prev.labelClassName === next.labelClassName &&
    prev.size === next.size &&
    prev.ariaLabel === next.ariaLabel,
);

export default AreaBadge;
