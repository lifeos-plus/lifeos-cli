import React from "react";
import ActionButton from "./ActionButton";
import { Icon } from "./icons";
import { t } from "@/i18n";

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

const ErrorDisplay: React.FC = () => {
  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-base-100 shadow rounded p-6 text-center">
        <Icon
          name="warning"
          size={32}
          aria-hidden
          className="text-error mb-2"
        />
        <h1 className="text-lg font-semibold mb-2">
          {t("errorBoundary.title")}
        </h1>
        <p className="text-base text-base-content mb-4">
          {t("errorBoundary.message")}
        </p>
        <ActionButton
          label={t("errorBoundary.refresh")}
          onClick={() => window.location.reload()}
          color="primary"
          variant="solid"
          iconName="refresh"
        />
      </div>
    </div>
  );
};

class ErrorBoundaryImpl extends React.Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(): void {}

  render() {
    if (this.state.hasError) {
      return <ErrorDisplay />;
    }

    return this.props.children;
  }
}

export const ErrorBoundary: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  return <ErrorBoundaryImpl>{children}</ErrorBoundaryImpl>;
};
