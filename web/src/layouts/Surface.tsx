import type { ReactNode } from "react";

type SurfacePadding = "none" | "sm" | "md" | "lg" | "responsive";
type SurfaceRadius = "md" | "lg" | "xl";
type SurfaceBorder = "none" | "subtle" | "dashed";
type SurfaceElevation = "none" | "subtle" | "moderate" | "elevated";

interface SurfaceProps {
  as?: "div" | "section";
  children: ReactNode;
  className?: string;
  padding?: SurfacePadding;
  radius?: SurfaceRadius;
  border?: SurfaceBorder;
  elevation?: SurfaceElevation;
  interactive?: boolean;
}

const paddingClasses: Record<SurfacePadding, string> = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
  responsive: "p-3 sm:p-4 lg:p-6",
};

const radiusClasses: Record<SurfaceRadius, string> = {
  md: "rounded-md",
  lg: "rounded-lg",
  xl: "rounded-2xl",
};

const borderClasses: Record<SurfaceBorder, string> = {
  none: "border-0",
  subtle: "border border-base-200",
  dashed: "border border-dashed border-base-300",
};

const elevationClasses: Record<SurfaceElevation, string> = {
  none: "shadow-none",
  subtle: "shadow-sm",
  moderate: "shadow-md",
  elevated: "shadow-lg",
};

export default function Surface({
  as = "div",
  children,
  className = "",
  padding = "none",
  radius = "lg",
  border = "none",
  elevation = "none",
  interactive = false,
}: SurfaceProps) {
  const Component = as;
  const classes = [
    "bg-base-100",
    paddingClasses[padding],
    radiusClasses[radius],
    borderClasses[border],
    elevationClasses[elevation],
    interactive ? "transition-shadow hover:shadow-md" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <Component className={classes}>{children}</Component>;
}
