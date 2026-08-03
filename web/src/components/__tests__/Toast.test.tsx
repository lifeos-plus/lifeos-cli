import { act, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { ToastContext } from "@/contexts/ToastContext";
import { ToastProvider } from "@/components/Toast";

import { setupTranslationMock } from "@test/utils";

setupTranslationMock();

type ToastContextType = React.ContextType<typeof ToastContext>;

describe("ToastProvider", () => {
  let contextRef: ToastContextType | undefined;

  const Harness: React.FC = () => {
    contextRef = React.useContext(ToastContext);
    return null;
  };

  beforeEach(() => {
    contextRef = undefined;
    vi.useRealTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const renderProvider = () => {
    render(
      <ToastProvider>
        <Harness />
      </ToastProvider>,
    );
    if (!contextRef) {
      throw new Error("Toast context was not initialized");
    }
  };

  it("displays a toast when showSuccess is called", async () => {
    renderProvider();

    act(() => {
      contextRef!.showSuccess("Saved", "All good");
    });

    const toast = await screen.findByRole("alert");
    expect(toast).toHaveTextContent("Saved");
    expect(toast).toHaveClass("alert", "alert-success");

    act(() => {
      screen.getByRole("button", { name: "common.close" }).click();
    });

    await waitFor(() =>
      expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
    );
  });

  it("auto-dismisses toasts after the provided duration", async () => {
    vi.useFakeTimers();
    renderProvider();

    act(() => {
      contextRef!.showToast({
        type: "info",
        title: "Timed",
        message: "Will close",
        duration: 1000,
      });
    });

    expect(screen.getByRole("alert")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    vi.useRealTimers();
  });
});
