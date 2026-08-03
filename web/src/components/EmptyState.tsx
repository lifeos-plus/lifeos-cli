import React, { type ReactNode } from "react";
import ActionButton from "./ActionButton";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description?: string;
  actionText?: string;
  onAction?: () => void;
  className?: string;
}

/**
 * EmptyState - Reusable component for displaying empty states
 */
const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionText,
  onAction,
  className = "",
}) => {
  return (
    <div className={`text-center py-12 ${className}`}>
      <div className="text-4xl mb-4">{icon}</div>
      <h3 className="text-lg font-semibold text-base-content mb-2">
        {title}
      </h3>
      {description ? <p className="text-base mb-4">{description}</p> : null}
      {actionText && onAction && (
        <ActionButton
          label={actionText}
          onClick={onAction}
          color="success"
          variant="solid"
          size="md"
        />
      )}
    </div>
  );
};

export default EmptyState;
