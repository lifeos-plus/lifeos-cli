import React from "react";

export type BadgeTone =
  | "neutral"
  | "primary"
  | "secondary"
  | "accent"
  | "info"
  | "success"
  | "warning"
  | "error"
  | "ghost";

export type BadgeVariant = "solid" | "outline";
type BadgeSize = "xs" | "sm" | "md" | "lg";

interface BadgeProps {
  children: React.ReactNode;
  tone?: BadgeTone;
  variant?: BadgeVariant;
  size?: BadgeSize;
  className?: string;
  title?: string;
}

const toneClassMap: Record<BadgeTone, string> = {
  neutral: "badge-neutral",
  primary: "badge-primary",
  secondary: "badge-secondary",
  accent: "badge-accent",
  info: "badge-info",
  success: "badge-success",
  warning: "badge-warning",
  error: "badge-error",
  ghost: "badge-ghost",
};

const sizeClassMap: Record<BadgeSize, string> = {
  xs: "badge-xs",
  sm: "badge-sm",
  md: "",
  lg: "badge-lg",
};

export default function Badge({
  children,
  tone = "neutral",
  variant = "solid",
  size = "md",
  className = "",
  title,
}: BadgeProps) {
  return (
    <span
      className={[
        "badge",
        toneClassMap[tone],
        variant === "outline" ? "badge-outline" : "",
        sizeClassMap[size],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      title={title}
    >
      {children}
    </span>
  );
}
