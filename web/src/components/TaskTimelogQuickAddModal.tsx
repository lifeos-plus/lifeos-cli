import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import ModalBase from "@/layouts/ModalBase";
import InlineQuickTimeEntry from "./InlineQuickTimeEntry";
import type {
  TaskWithSubtasks,
  TimelogWithEnergyResponse,
} from "@/services/api";
import { tasksApi } from "@/services/api/tasks";
import { tasksKeys } from "@/services/api/queryKeys";
import { useSystemTimezone } from "@/hooks/useSystemTimezone";
import { formatTime } from "@/utils/datetime";
import { createModalSessionId } from "@/utils/session";

interface TaskTimelogQuickAddModalProps {
  isOpen: boolean;
  onClose: () => void;
  task: TaskWithSubtasks | null;
  onTimelogCreated: (result: TimelogWithEnergyResponse) => void;
}

export default function TaskTimelogQuickAddModal({
  isOpen,
  onClose,
  task,
  onTimelogCreated,
}: TaskTimelogQuickAddModalProps) {
  const { t } = useTranslation();
  const timezonePreference = useSystemTimezone();
  const activeTimezone = timezonePreference.timezone;
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setLocalError(null);
    }
  }, [isOpen]);

  const latestTimelogQuery = useQuery({
    queryKey: task?.id
      ? [...tasksKeys.timelogs(task.id), "latest"]
      : [...tasksKeys.all, "timelogs", "latest", "idle"],
    queryFn: async () => {
      if (!task?.id) return null;
      const response = await tasksApi.getTimelogs(task.id, 1, 1);
      return response.items[0] ?? null;
    },
    enabled: isOpen && Boolean(task?.id),
    staleTime: 30 * 1000,
  });

  const sessionId = useMemo(() => createModalSessionId(), []);

  const latestEndTime = latestTimelogQuery.data?.end_time ?? null;
  const selectedDate = useMemo(
    () => (latestEndTime ? new Date(latestEndTime) : new Date()),
    [latestEndTime],
  );
  const defaultTime = latestEndTime
    ? formatTime(latestEndTime, activeTimezone)
    : "";

  if (!task) {
    return null;
  }

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={onClose}
      header={t("timeLog.modal.addTimeLog")}
      size="2xl"
      loading={latestTimelogQuery.isLoading}
      error={latestTimelogQuery.error?.message ?? localError ?? undefined}
      onErrorDismiss={() => {
        if (latestTimelogQuery.error) {
          void latestTimelogQuery.refetch();
          return;
        }
        setLocalError(null);
      }}
      showLoadingSpinner
      loadingSpinnerSize="md"
      showCloseButton
      errorDisplayMode="inline"
    >
      {!latestTimelogQuery.isLoading && !latestTimelogQuery.error && (
        <InlineQuickTimeEntry
          selectedDate={selectedDate}
          startTime={defaultTime}
          endTime=""
          blankInitialEndTime
          preselectedTaskId={task.id}
          allowedTaskIds={[task.id]}
          preloadedTasks={[task]}
          idPrefix={`task-${task.id}-timelog`}
          sessionId={sessionId}
          timezone={activeTimezone}
          onEntryCreated={(result) => {
            setLocalError(null);
            onTimelogCreated(result);
          }}
          onError={setLocalError}
          onCancel={() => onClose()}
        />
      )}
    </ModalBase>
  );
}
