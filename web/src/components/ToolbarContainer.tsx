import React from "react";
import Container from "@/layouts/Container";

interface ToolbarContainerProps {
  children: React.ReactNode;
  className?: string;
  responsive?: boolean;
  padding?: "sm" | "md" | "lg";
  layout?: "flex" | "three-column";
}

/**
 * Shared visual container and responsive layout for page toolbars.
 *
 * Padding controls density; layout controls content arrangement.
 */
const ToolbarContainer: React.FC<ToolbarContainerProps> = ({
  children,
  className = "",
  responsive = true,
  padding = "md",
  layout = "flex",
}) => {
  const paddingClasses = {
    sm: "p-3",
    md: "p-4",
    lg: "p-6",
  };

  const getLayoutClasses = () => {
    if (layout === "three-column") {
      return responsive
        ? "flex min-w-0 flex-col gap-3 lg:grid lg:grid-cols-[repeat(3,minmax(0,1fr))] lg:items-center"
        : "grid min-w-0 grid-cols-[repeat(3,minmax(0,1fr))] items-center gap-3";
    }

    return responsive
      ? "flex min-w-0 flex-col gap-3 md:flex-row md:items-center md:justify-between"
      : "flex min-w-0 items-center justify-between gap-3";
  };

  const contentClasses = getLayoutClasses();

  return (
    <Container
      className={`w-full ${className}`.trim()}
      overflow="visible"
      maxHeight="fit"
      padding="none"
    >
      <div className={`${paddingClasses[padding]} ${contentClasses} text-base`}>
        {children}
      </div>
    </Container>
  );
};

export default ToolbarContainer;
