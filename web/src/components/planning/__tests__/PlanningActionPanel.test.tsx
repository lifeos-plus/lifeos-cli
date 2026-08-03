import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import PlanningActionPanel from "@/components/planning/PlanningActionPanel";

describe("PlanningActionPanel", () => {
  it("applies a semantic tone and exposes the shared close action", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();

    render(
      <PlanningActionPanel
        title="Carry forward"
        closeLabel="Close"
        onClose={onClose}
        tone="warning"
      >
        Content
      </PlanningActionPanel>,
    );

    expect(screen.getByRole("heading", { name: "Carry forward" })).toHaveClass(
      "text-warning",
    );
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
