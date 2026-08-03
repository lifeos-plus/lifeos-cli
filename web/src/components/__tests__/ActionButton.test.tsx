import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { setupTranslationMock } from "@test/utils";

setupTranslationMock();

let ActionButton: typeof import("@/components/ActionButton").default;
let FormActions: typeof import("@/components/ActionButton").FormActions;
let ExpandButton: typeof import("@/components/ActionButton").ExpandButton;

beforeAll(async () => {
  ({ default: ActionButton, FormActions, ExpandButton } = await import(
    "@/components/ActionButton"
  ));
});

describe("FormActions", () => {
  it("replaces the cancel action with a labeled delete action in edit mode", async () => {
    const onCancel = vi.fn();
    const onDelete = vi.fn();
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    render(
      <FormActions
        onCancel={onCancel}
        onDelete={onDelete}
        onSubmit={onSubmit}
      />,
    );

    expect(
      screen.queryByRole("button", { name: "common.cancel" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "common.delete" }));
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "common.submit" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});

const getActionButton = () => {
  if (!ActionButton) {
    throw new Error("ActionButton was not loaded");
  }
  return ActionButton;
};

describe("ActionButton", () => {
  it("renders label and optional icon", () => {
    const Component = getActionButton();

    render(
      <Component
        label="Create"
        color="primary"
        variant="solid"
        icon={<span data-testid="icon">*</span>}
      />,
    );

    const button = screen.getByRole("button", { name: "Create" });
    expect(button).toBeInTheDocument();
    expect(button).toHaveClass("btn", "btn-primary");
    expect(screen.getByTestId("icon")).toBeInTheDocument();
  });

  it("invokes onClick when enabled", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    const Component = getActionButton();

    render(<Component label="Save" onClick={onClick} />);

    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("preserves keyboard focus after activation", async () => {
    const user = userEvent.setup();
    const Component = getActionButton();

    render(<Component label="Save" />);

    const button = screen.getByRole("button", { name: "Save" });
    await user.tab();
    await user.keyboard("{Enter}");
    expect(button).toHaveFocus();
  });

  it("supports xs size and iconOnly presentation", () => {
    const Component = getActionButton();

    render(
      <Component
        label="Edit"
        icon={<span data-testid="icon">*</span>}
        size="xs"
        iconOnly
        ariaLabel="Edit action"
      />,
    );

    const button = screen.getByRole("button", { name: "Edit action" });
    expect(button).toHaveClass("btn-xs");
    expect(button).toHaveClass("btn-square");
    const srOnlyLabel = button.querySelector(".sr-only");
    expect(srOnlyLabel).not.toBeNull();
    expect(srOnlyLabel).toHaveTextContent("Edit");
  });

  it("allows overriding shape to circle", () => {
    const Component = getActionButton();

    render(
      <Component
        label=""
        icon={<span data-testid="icon">*</span>}
        size="sm"
        iconOnly
        shape="circle"
        ariaLabel="Close menu"
      />,
    );

    const button = screen.getByRole("button", { name: "Close menu" });
    expect(button).toHaveClass("btn-circle");
  });

  it("does not invoke onClick when disabled", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    const Component = getActionButton();

    render(<Component label="Disabled" onClick={onClick} disabled />);

    await user.click(screen.getByRole("button", { name: "Disabled" }));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("ExpandButton", () => {
  it("uses DaisyUI sizing and announces the available action", () => {
    render(<ExpandButton isExpanded onClick={vi.fn()} size="xs" />);

    const button = screen.getByRole("button", { name: "common.collapse" });
    expect(button).toHaveClass("btn", "btn-xs", "btn-square");
    expect(button.querySelector("svg")).toHaveClass("rotate-90");
  });
});
