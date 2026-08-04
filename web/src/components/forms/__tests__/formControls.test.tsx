import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TextArea from "@/components/forms/TextArea";
import TextInput from "@/components/forms/TextInput";

describe("form controls", () => {
  it("uses DaisyUI input size variants", () => {
    render(<TextInput aria-label="Name" size="lg" />);

    expect(screen.getByRole("textbox", { name: "Name" })).toHaveClass(
      "input",
      "input-lg",
    );
  });

  it("keeps textarea rows while applying DaisyUI size variants", () => {
    render(<TextArea aria-label="Notes" rows={5} size="sm" />);

    const textarea = screen.getByRole("textbox", { name: "Notes" });
    expect(textarea).toHaveClass("textarea", "textarea-sm", "min-h-16");
    expect(textarea).toHaveAttribute("rows", "5");
  });
});
