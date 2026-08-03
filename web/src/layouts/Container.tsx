import React from "react";

interface ContainerProps {
  children: React.ReactNode;
  className?: string;
  /** Content overflow behavior. */
  overflow?: "hidden" | "auto" | "visible" | "scroll";
  /** Maximum height constraint. */
  maxHeight?: "none" | "full" | "screen" | "fit";
  /** Container padding. */
  padding?: "none" | "sm" | "md" | "lg" | "responsive";
  /** Whether to apply the minimum-width constraint. */
  minWidth?: boolean;
  /** Whether to apply the maximum-width constraint. */
  maxWidth?: boolean;
  /** Flex sizing behavior. */
  flex?: "1" | "none" | "auto" | "initial";
  /** Minimum height constraint. */
  minHeight?: "0" | "auto" | "full" | "screen" | "fit";
  /** Border style. */
  borderVariant?: "default" | "subtle" | "none";
  /** Shadow strength. */
  shadow?: "none" | "sm" | "md" | "lg";
}

/**
 * Enhanced Container - unified border, shadow and radius with flexible configuration.
 *
 * Features:
 * - Flexible overflow handling
 * - Responsive padding options
 * - Configurable height constraints
 * - Better mobile support
 */
function Container({
  children,
  className = "",
  overflow = "visible",
  maxHeight = "full",
  padding = "responsive",
  minWidth = true,
  maxWidth = true,
  flex = "none",
  minHeight = "auto",
  borderVariant = "none",
  shadow = "md",
}: ContainerProps) {
  const baseClasses = [
    "bg-base-100 rounded-lg w-full",
    minWidth ? "min-w-0" : "",
    maxWidth ? "max-w-full" : "",
    maxHeight === "full"
      ? "max-h-full"
      : maxHeight === "screen"
        ? "max-h-screen"
        : maxHeight === "fit"
          ? "max-h-fit"
          : "",
    minHeight === "0"
      ? "min-h-0"
      : minHeight === "auto"
        ? "min-h-auto"
        : minHeight === "full"
          ? "min-h-full"
          : minHeight === "screen"
            ? "min-h-screen"
            : minHeight === "fit"
              ? "min-h-fit"
              : "",
    overflow === "hidden"
      ? "overflow-hidden"
      : overflow === "auto"
        ? "overflow-auto"
        : overflow === "scroll"
          ? "overflow-scroll"
          : "overflow-visible",
    flex === "1"
      ? "flex-1"
      : flex === "none"
        ? "flex-none"
        : flex === "auto"
          ? "flex-auto"
          : flex === "initial"
            ? "flex-initial"
            : "",
    padding === "none"
      ? ""
      : padding === "sm"
        ? "p-2"
        : padding === "md"
          ? "p-4"
          : padding === "lg"
            ? "p-6"
            : "p-2 md:p-4 lg:p-6", // responsive
    borderVariant === "none"
      ? ""
      : borderVariant === "subtle"
        ? "border border-base-200"
        : "border border-base-300",
    shadow === "none"
      ? "shadow-none"
      : shadow === "sm"
        ? "shadow-sm"
        : shadow === "lg"
          ? "shadow-lg"
          : "shadow-md",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <div className={baseClasses}>{children}</div>;
}

export default Container;
