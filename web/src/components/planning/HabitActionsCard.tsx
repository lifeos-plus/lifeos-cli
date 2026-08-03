import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import Card from "@/layouts/Card";
import EnumSelect from "@/components/selects/EnumSelect";
import ActionButton from "@/components/ActionButton";
import {
  HABIT_ACTION_STATUS_OPTIONS,
  HABIT_ACTION_STATUS_CONFIG,
} from "@/utils/constants";
import type { HabitActionWithHabit } from "@/services/api/habits";
import type { UUID } from "@/types/primitive";
import { Icon } from "@/components/icons";
import type { IconName } from "@/components/icons";
import { parseDateStringToLocalDate, startOfLocalDay } from "@/utils/datetime";
import CreateNoteModal from "@/components/CreateNoteModal";
import TaskNotesModal from "@/components/TaskNotesModal";
import type { NoteHabitActionSummary } from "@/services/api/notes";

interface HabitActionsCardProps {
  habitActions: HabitActionWithHabit[];
  onStatusChange: (actionId: UUID, habitId: UUID, status: string) => void;
  onNotesChanged?: () => void;
}

const subduedNoteButtonClass = "opacity-40 hover:opacity-60 transition-opacity";

const getHabitActionStatusStyling = (status: string) => {
  // Map status to icon names
  const statusIconMap: Record<string, IconName> = {
    pending: "timer",
    done: "check",
    skip: "forward",
    miss: "x-mark",
  };

  const config =
    HABIT_ACTION_STATUS_CONFIG[
      status as keyof typeof HABIT_ACTION_STATUS_CONFIG
    ] || HABIT_ACTION_STATUS_CONFIG.pending;

  return {
    iconName: statusIconMap[status] || "timer",
    color: `text-${config.color}`,
    bgColor: config.bgColor,
    hoverColor: config.bgColor.replace("/15", "/25"),
  };
};

export const HabitActionsCard: React.FC<HabitActionsCardProps> = ({
  habitActions,
  onStatusChange,
  onNotesChanged,
}) => {
  const { t } = useTranslation();
  const [creatingNoteForAction, setCreatingNoteForAction] =
    useState<HabitActionWithHabit | null>(null);
  const [viewingNotesForAction, setViewingNotesForAction] =
    useState<HabitActionWithHabit | null>(null);

  const buildHabitActionSummary = (
    action: HabitActionWithHabit,
  ): NoteHabitActionSummary => ({
    id: action.id,
    habit_id: action.habit_id,
    habit_title: action.habit.title,
    action_date: action.action_date,
    status: action.status,
  });

  // 计算天数信息
  const calculateDayInfo = (action: HabitActionWithHabit) => {
    const habitStartDate = startOfLocalDay(
      parseDateStringToLocalDate(action.habit.start_date),
    );
    const actionDate = startOfLocalDay(
      parseDateStringToLocalDate(action.action_date),
    );

    const timeDiff = actionDate.getTime() - habitStartDate.getTime();
    const dayDiff = Math.floor(timeDiff / (1000 * 60 * 60 * 24));
    const dayNumber = Math.max(1, dayDiff + 1);
    const totalDays = action.habit.duration_days;

    if (Number.isNaN(dayNumber)) {
      return `--/${totalDays}`;
    }

    return `${dayNumber}/${totalDays}`;
  };

  return (
    <Card
      title={t("planning.habitActions.title")}
      size="md"
      elevation="moderate"
      className="mb-4"
    >
      <div className="space-y-0">
        {habitActions.map((action) => {
          const statusStyling = getHabitActionStatusStyling(action.status);
          const dayInfo = calculateDayInfo(action);
          const linkedNotesCount =
            action.linked_notes_count ?? (action.notes?.trim() ? 1 : 0);
          const hasLinkedNotes = linkedNotesCount > 0;

          return (
            <div
              key={action.id}
              data-testid="planning-habit-action-row"
              className="group w-full border-b border-base-200/50 last:border-b-0"
            >
              <div className="w-full min-w-0">
                <div
                  className={`w-full px-2 py-3 transition-all duration-200 ease-in-out hover:bg-base-200 hover:shadow-md group-hover:bg-base-200/80 sm:px-4 ${statusStyling.bgColor}`}
                >
                  <div
                    data-testid="planning-habit-action-layout"
                    className="flex w-full min-w-0 flex-col items-stretch gap-3 md:flex-row md:items-center md:justify-between"
                  >
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      <span className={`text-lg ${statusStyling.color}`}>
                        <Icon
                          name={statusStyling.iconName}
                          size={18}
                          aria-hidden
                        />
                      </span>

                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <div className="text-base-content/70 min-w-[40px]">
                          {dayInfo}
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex min-w-0 flex-col items-start gap-1 sm:flex-row sm:items-center sm:gap-2">
                            <h5 className="font-medium text-base-content text-base min-w-0 truncate">
                              {action.habit.title}
                            </h5>
                            {action.habit.description && (
                              <span className="text-base text-base-content/70 min-w-0 truncate">
                                {action.habit.description}
                              </span>
                            )}
                          </div>

                        </div>
                      </div>
                    </div>

                    <div className="flex w-full flex-wrap items-center justify-end gap-2 md:ml-3 md:w-auto md:flex-nowrap">
                      <ActionButton
                        label={t("notes.actions.addNote")}
                        iconName="document-plus"
                        color="primary"
                        onClick={() => setCreatingNoteForAction(action)}
                        iconOnly
                        ariaLabel={t("notes.actions.addNote")}
                      />

                      <ActionButton
                        label={t("notes.actions.viewNotes")}
                        iconName="book-open"
                        color={hasLinkedNotes ? "primary" : "neutral"}
                        className={
                          hasLinkedNotes ? undefined : subduedNoteButtonClass
                        }
                        onClick={() => setViewingNotesForAction(action)}
                        iconOnly
                        ariaLabel={t("notes.actions.viewNotes")}
                      />

                      <div className="w-32 min-w-0 md:w-28">
                        <EnumSelect
                          value={action.status}
                          onChange={(value) =>
                            onStatusChange(
                              action.id,
                              action.habit_id,
                              value as string,
                            )
                          }
                          options={HABIT_ACTION_STATUS_OPTIONS}
                          idPrefix={`habit-action-status-${action.id}`}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {creatingNoteForAction && (
        <CreateNoteModal
          isOpen={!!creatingNoteForAction}
          onClose={() => setCreatingNoteForAction(null)}
          preSelectedHabitActionId={creatingNoteForAction.id}
          preSelectedHabitAction={buildHabitActionSummary(creatingNoteForAction)}
          onNoteCreated={() => {
            setCreatingNoteForAction(null);
            onNotesChanged?.();
          }}
        />
      )}

      {viewingNotesForAction && (
        <TaskNotesModal
          isOpen={!!viewingNotesForAction}
          onClose={() => setViewingNotesForAction(null)}
          entityType="habit_action"
          habitAction={buildHabitActionSummary(viewingNotesForAction)}
          onNotesChanged={onNotesChanged}
        />
      )}
    </Card>
  );
};
