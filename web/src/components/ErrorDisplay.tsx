import React from "react";
import { Icon } from "./icons";

interface ErrorDisplayProps {
  error: string | null;
  className?: string;
  action?: React.ReactNode;
}

/**
 * ErrorDisplay - Reusable component for displaying error messages
 */
const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  error,
  className = "",
  action,
}) => {
  if (!error) return null;

  return (
    <div className={`alert alert-error ${className}`}>
      <div className="flex w-full min-w-0 flex-wrap items-center justify-between gap-3">
        <span className="inline-flex min-w-0 flex-1 items-start gap-2 break-words">
          <Icon name="warning" size={18} className="flex-shrink-0" aria-hidden />
          <span className="min-w-0 break-words">{error}</span>
        </span>
        {action ? (
          <div className="flex flex-shrink-0 items-center">{action}</div>
        ) : null}
      </div>
    </div>
  );
};

export default ErrorDisplay;
