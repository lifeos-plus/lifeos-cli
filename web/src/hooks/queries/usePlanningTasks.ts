import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  tasksApi,
  type Task,
  type TaskWithSubtasks,
  toISODate,
} from "@/services/api/tasks";
import { tasksKeys } from "@/services/api/queryKeys";
import type { UUID } from "@/types/primitive";

type PlanningCycleType = "7years" | "year" | "month" | "week" | "day";
function buildTaskHierarchy(flatTasks: Task[]): TaskWithSubtasks[] {
  const taskMap = new Map<UUID, TaskWithSubtasks>();
  const rootTasks: TaskWithSubtasks[] = [];

  flatTasks.forEach((task) => {
    taskMap.set(task.id, {
      ...task,
      subtasks: [],
      completion_percentage: 0,
      depth: 0,
    } as TaskWithSubtasks);
  });

  flatTasks.forEach((task) => {
    const node = taskMap.get(task.id)!;
    if (task.parent_task_id) {
      const parent = taskMap.get(task.parent_task_id);
      if (parent) {
        parent.subtasks.push(node);
        node.depth = parent.depth + 1;
      } else {
        rootTasks.push(node);
      }
    } else {
      rootTasks.push(node);
    }
  });

  return rootTasks;
}

export function usePlanningTasks(
  viewType: PlanningCycleType,
  selectedDate?: Date,
  opts?: {
    limit?: number;
    staleTimeMs?: number;
    gcTimeMs?: number;
    enabled?: boolean;
  },
) {
  const queryClient = useQueryClient();
  const size = opts?.limit ?? 100;
  const staleTime = opts?.staleTimeMs ?? 60 * 1000;
  const gcTime = opts?.gcTimeMs ?? 5 * 60 * 1000;
  const enabled = opts?.enabled ?? true;

  const query = useQuery({
    queryKey: tasksKeys.list({
      planning_cycle_type: viewType,
      planning_cycle_start_date: toISODate(selectedDate),
      fields: "full",
      size,
    }),
    queryFn: async () => {
      const response = await tasksApi.getAll(undefined, undefined, {
        planning_cycle_type: viewType,
        planning_cycle_start_date: toISODate(selectedDate),
        fields: "full",
        size,
      });
      const tasks = response.items ?? [];
      // filter out deleted if any
      const filtered = tasks.filter(
        (t) =>
          (t as unknown as { deleted_at?: string | null }).deleted_at == null,
      );
      return buildTaskHierarchy(filtered);
    },
    staleTime,
    gcTime,
    enabled,
  });

  const prefetch = useCallback(
    (type: PlanningCycleType, prefetchDate?: Date) => {
      return queryClient.prefetchQuery({
        queryKey: tasksKeys.list({
          planning_cycle_type: type,
          planning_cycle_start_date: toISODate(prefetchDate),
          fields: "full",
          size,
        }),
        queryFn: async () => {
          const response = await tasksApi.getAll(undefined, undefined, {
            planning_cycle_type: type,
            planning_cycle_start_date: toISODate(prefetchDate),
            fields: "full",
            size,
          });
          const tasks = response.items ?? [];
          const filtered = tasks.filter(
            (t) =>
              (t as unknown as { deleted_at?: string | null }).deleted_at ==
              null,
          );
          return buildTaskHierarchy(filtered);
        },
        staleTime,
        gcTime,
      });
    },
    [
      gcTime,
      queryClient,
      size,
      staleTime,
    ],
  );

  return {
    tasks: (query.data as TaskWithSubtasks[] | undefined) ?? [],
    query,
    prefetch,
  };
}
