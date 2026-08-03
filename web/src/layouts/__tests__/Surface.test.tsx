import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Surface from "@/layouts/Surface";

describe("Surface", () => {
  it("renders semantic surface variants", () => {
    render(
      <Surface
        as="section"
        padding="md"
        radius="xl"
        border="subtle"
        elevation="subtle"
        interactive
      >
        Content
      </Surface>,
    );

    const surface = screen.getByText("Content");
    expect(surface.tagName).toBe("SECTION");
    expect(surface).toHaveClass(
      "bg-base-100",
      "p-4",
      "rounded-2xl",
      "border-base-200",
      "shadow-sm",
      "hover:shadow-md",
    );
  });
});
