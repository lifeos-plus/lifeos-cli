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
        ? "flex flex-col lg:grid lg:grid-cols-3 gap-3 lg:items-center"
        : "grid grid-cols-3 gap-3 items-center";
    }

    return responsive
      ? "flex flex-col md:flex-row md:items-center md:justify-between gap-3"
      : "flex items-center justify-between gap-3";
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
