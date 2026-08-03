import type { ReactNode } from "react";

import ActionButton from "@/components/ActionButton";

type PlanningActionTone = "neutral" | "primary" | "warning";

interface PlanningActionPanelProps {
  title: ReactNode;
  closeLabel: string;
  onClose: () => void;
  tone?: PlanningActionTone;
  children: ReactNode;
}

const toneClasses: Record<
  PlanningActionTone,
  { panel: string; title: string; button: PlanningActionTone }
> = {
  neutral: {
    panel: "border-base-300 bg-base-200/50",
    title: "text-base-content",
    button: "neutral",
  },
  primary: {
    panel: "border-primary/20 bg-primary/10",
    title: "text-primary",
    button: "primary",
  },
  warning: {
    panel: "border-warning/20 bg-warning/10",
    title: "text-warning",
    button: "warning",
  },
};

export default function PlanningActionPanel({
  title,
  closeLabel,
  onClose,
  tone = "neutral",
  children,
}: PlanningActionPanelProps) {
  const styles = toneClasses[tone];

  return (
    <section
      className={`mb-4 rounded-lg border p-4 shadow-sm ${styles.panel}`}
    >
      <div className="mb-3 flex items-center justify-between">
        <h4 className={`text-base font-medium ${styles.title}`}>{title}</h4>
        <ActionButton
          label={closeLabel}
          ariaLabel={closeLabel}
          iconName="x-mark"
          color={styles.button}
          size="xs"
          variant="ghost"
          iconOnly
          onClick={onClose}
        />
      </div>
      {children}
    </section>
  );
}
