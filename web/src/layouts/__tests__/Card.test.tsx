import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Card from "@/layouts/Card";

describe("Card", () => {
  it("applies the requested elevation and content divider", () => {
    render(
      <Card elevation="subtle" withTopBorder>
        Content
      </Card>,
    );

    const content = screen.getByText("Content");
    expect(content.parentElement).toHaveClass("border-t", "pt-4");
    expect(content.closest(".bg-base-100")).toHaveClass("shadow-sm");
  });
});
