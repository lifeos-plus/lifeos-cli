import { render, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import React from "react";

import type { SelectorValue } from "@/components/selects/selectorTypes";
import type { UUID } from "@/types/primitive";
import { setupTranslationMock } from "@test/utils";

const defaultVisionId = "11111111-1111-1111-1111-111111111111" as UUID;
const mockAsyncSelect = vi.fn();

vi.mock("@/components/selects/AsyncEntitySelect", () => ({
  __esModule: true,
  default: React.forwardRef((props: unknown, _ref) => {
    mockAsyncSelect(props);
    return <div data-testid="vision-select" />;
  }),
}));

vi.mock("@/hooks/queries/useDefaultInboxVision", () => ({
  useDefaultInboxVision: () => ({
    defaultInboxVision: defaultVisionId,
    loading: false,
    error: null,
  }),
}));

vi.mock("@/hooks/queries/useVisions", () => ({
  useVisions: () => ({
    visions: [
      { id: defaultVisionId, name: "Default Vision", status: "active" },
      {
        id: "22222222-2222-2222-2222-222222222222",
        name: "Other Vision",
        status: "active",
      },
    ],
    loading: false,
    error: null,
  }),
}));

setupTranslationMock();

let VisionSelector: typeof import("@/components/selects/VisionSelector").default;

beforeAll(async () => {
  ({ default: VisionSelector } = await import(
    "@/components/selects/VisionSelector"
  ));
});

describe("VisionSelector", () => {
  beforeEach(() => {
    mockAsyncSelect.mockClear();
  });

  it("uses the real default vision id for the displayed default option", () => {
    const handleChange = vi.fn();

    render(
      <VisionSelector
        value={defaultVisionId}
        onChange={handleChange}
        showDefaultOption
      />,
    );

    const props = mockAsyncSelect.mock.calls.at(-1)?.[0] as Record<
      string,
      unknown
    >;
    expect(props.value).toBe(defaultVisionId);
    expect(props.options).toEqual([
      {
        id: defaultVisionId,
        label: "Default Vision (common.default)",
      },
      {
        id: "22222222-2222-2222-2222-222222222222",
        label: "Other Vision",
      },
    ]);

    (props.onChange as (value: SelectorValue) => void)(defaultVisionId);
    expect(handleChange).toHaveBeenCalledWith(defaultVisionId);
  });

  it("auto-selects the default vision by its real id", async () => {
    const handleChange = vi.fn();

    render(
      <VisionSelector
        value={null}
        onChange={handleChange}
        showDefaultOption
        defaultToInboxVision
      />,
    );

    await waitFor(() => {
      expect(handleChange).toHaveBeenCalledWith(defaultVisionId);
    });
  });
});
