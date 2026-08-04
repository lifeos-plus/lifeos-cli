import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Container from "@/layouts/Container";

describe("Container", () => {
  it("is borderless by default", () => {
    render(<Container>Content</Container>);

    const container = screen.getByText("Content");
    expect(container).not.toHaveClass("border");
    expect(container).not.toHaveClass("border-base-300");
  });

  it("keeps borders available for explicit structural use", () => {
    render(<Container borderVariant="subtle">Content</Container>);

    expect(screen.getByText("Content")).toHaveClass(
      "border",
      "border-base-200",
    );
  });
});
