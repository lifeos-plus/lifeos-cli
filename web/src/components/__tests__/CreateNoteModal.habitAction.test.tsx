import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import CreateNoteModal from "@/components/CreateNoteModal";
import { ModalProvider } from "@/contexts/ModalProvider";
import { renderWithProviders } from "@test/utils";
import type { UUID } from "@/types/primitive";

const notesApiMock = vi.hoisted(() => ({
  create: vi.fn(),
  update: vi.fn(),
}));

vi.mock("@/services/api/notes", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/api/notes")>();
  return {
    ...actual,
    notesApi: notesApiMock,
  };
});

vi.mock("@/hooks/selectors/useTagSelectorSource", () => ({
  useTagSelectorSource: () => ({
    tags: [],
    createTag: vi.fn(),
  }),
}));

vi.mock("@/components/selects/PersonSelector", () => ({
  __esModule: true,
  default: () => <div data-testid="person-selector" />,
}));

vi.mock("@/components/selects/TagSelector", () => ({
  __esModule: true,
  default: () => <div data-testid="tag-selector" />,
}));

vi.mock("@/components/selects/TaskSelector", () => ({
  __esModule: true,
  default: () => <div data-testid="task-selector" />,
}));

const ModalWrapper = ({ children }: { children: ReactNode }) => (
  <ModalProvider>{children}</ModalProvider>
);

describe("CreateNoteModal habit action links", () => {
  it("routes edit-mode deletion through the caller confirmation flow", () => {
    const onClose = vi.fn();
    const onRequestDelete = vi.fn();
    const existingNote = {
      id: "note-1" as UUID,
      content: "Existing note",
      created_at: "2026-07-05T12:00:00.000Z",
      updated_at: "2026-07-05T12:00:00.000Z",
    };

    renderWithProviders(
      <CreateNoteModal
        isOpen
        onClose={onClose}
        mode="edit"
        existingNote={existingNote}
        onRequestDelete={onRequestDelete}
      />,
      { wrapper: ModalWrapper },
    );

    fireEvent.click(screen.getByRole("button", { name: "common.delete" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onRequestDelete).toHaveBeenCalledWith(existingNote);
    expect(
      screen.queryByRole("button", { name: "common.cancel" }),
    ).not.toBeInTheDocument();
  });

  it("submits locked habit action identifiers when creating a note", async () => {
    notesApiMock.create.mockResolvedValue({
      id: "note-1",
      content: "Completed after lunch",
      created_at: "2026-07-05T12:00:00.000Z",
      updated_at: "2026-07-05T12:00:00.000Z",
      habit_actions: [
        {
          id: "action-1",
          habit_id: "habit-1",
          habit_title: "Morning Walk",
          action_date: "2026-07-05",
          status: "done",
        },
      ],
    });

    renderWithProviders(
      <CreateNoteModal
        isOpen
        onClose={vi.fn()}
        preSelectedHabitActionId={"action-1" as UUID}
        preSelectedHabitAction={{
          id: "action-1" as UUID,
          habit_id: "habit-1" as UUID,
          habit_title: "Morning Walk",
          action_date: "2026-07-05",
          status: "done",
        }}
      />,
      { wrapper: ModalWrapper },
    );

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Completed after lunch" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "createNoteModal.submitText" }),
    );

    await waitFor(() => {
      expect(notesApiMock.create).toHaveBeenCalledWith(
        expect.objectContaining({
          content: "Completed after lunch",
          habit_action_ids: ["action-1"],
        }),
      );
    });
  });
});
