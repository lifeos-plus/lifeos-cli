import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DateTimeSelector from "@/components/forms/DateTimeSelector";
import { renderWithProviders } from "@test/utils";

describe("DateTimeSelector", () => {
  it("round-trips an all-day timestamp through the configured timezone", () => {
    const onChange = vi.fn();
    renderWithProviders(
      <DateTimeSelector
        value="2026-08-04T16:00:00.000Z"
        isAllDay
        timezone="Asia/Shanghai"
        onChange={onChange}
      />,
    );

    const dateInput = screen.getByDisplayValue("2026-08-05");
    fireEvent.change(dateInput, { target: { value: "2026-08-06" } });

    expect(onChange).toHaveBeenCalledWith("2026-08-05T16:00:00.000Z");
  });

  it("converts timed input with the configured timezone", () => {
    const onChange = vi.fn();
    renderWithProviders(
      <DateTimeSelector
        value="2026-08-05T00:30:00.000Z"
        timezone="Asia/Shanghai"
        onChange={onChange}
      />,
    );

    fireEvent.change(screen.getByDisplayValue("08:30"), {
      target: { value: "09:45" },
    });

    expect(onChange).toHaveBeenCalledWith("2026-08-05T01:45:00.000Z");
  });
});
