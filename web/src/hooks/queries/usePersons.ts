import { useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  personsApi,
  type Person,
  type PersonCreate,
  type PersonUpdate,
  type PersonActivitiesResponse,
  type PersonActivityItem,
  type PersonActivityType,
} from "@/services/api/persons";
import type { PersonSummary } from "@/services/api";
import { personsKeys } from "@/services/api/queryKeys";
import { useToast } from "@/contexts/ToastContext";
import type { UUID } from "@/types/primitive";
import {
  invalidatePersonActivities,
  invalidatePersonsLists,
  removePersonDetailCache,
  setPersonDetailCache,
} from "@/services/api/cacheInvalidation/persons";
interface UsePersonsFilters {
  page?: number;
  size?: number;
  search?: string;
  tagFilter?: string;
  tagId?: UUID;
}

interface UsePersonsReturn {
  // Data
  persons: PersonSummary[];
  total: number;
  activities: PersonActivitiesResponse | null;

  // Loading states
  isLoading: boolean;
  isLoadingActivities: boolean;

  // Error states
  error: Error | null;
  activitiesError: Error | null;

  // Actions
  createPerson: (person: PersonCreate) => void;
  updatePerson: (id: UUID, person: PersonUpdate) => void;
  deletePerson: (id: UUID) => void;
  loadPersonActivities: (personId: UUID) => void;
  refreshData: () => void;

  // Mutations
  createPersonMutation: ReturnType<
    typeof useMutation<Person, Error, PersonCreate>
  >;
  updatePersonMutation: ReturnType<
    typeof useMutation<Person, Error, { id: UUID; person: PersonUpdate }>
  >;
  deletePersonMutation: ReturnType<
    typeof useMutation<void, Error, { id: UUID }>
  >;
}

interface UsePersonActivitiesPageReturn {
  activities: PersonActivityItem[];
  total: number;
  totalPages: number;
  timelogStats: {
    count: number;
    totalMinutes: number;
  } | null;
  isLoading: boolean;
  isFetching: boolean;
  error: Error | null;
  refetch: () => void;
}

export function usePersons(filters: UsePersonsFilters = {}): UsePersonsReturn {
  const queryClient = useQueryClient();
  const toast = useToast();

  // Normalize filters to a stable object so queryKey doesn't change on each render
  const keyFilters = {
    page: filters.page ?? 1,
    size: filters.size ?? 100,
    search: filters.search,
    // queryKeys expects tag_filter; keep stable mapping
    tag_filter: filters.tagFilter,
    tag_id: filters.tagId,
  } as const;

  // 1. 获取人员列表
  const {
    data: personsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: personsKeys.list(keyFilters),
    queryFn: () =>
      personsApi.getAll(
        keyFilters.page,
        keyFilters.size,
        keyFilters.search,
        keyFilters.tag_filter,
        keyFilters.tag_id,
      ),
    staleTime: 5 * 60 * 1000,
  });

  const persons = personsData?.items || [];
  const total = personsData?.pagination?.total || 0;

  // 2. 创建人员
  const createPersonMutation = useMutation({
    mutationFn: (person: PersonCreate) => personsApi.create(person),
    onSuccess: async (created) => {
      toast.showSuccess("联系人创建成功！");
      setPersonDetailCache(queryClient, created);
      await invalidatePersonsLists(queryClient);
    },
    onError: (err: Error) => {
      toast.showError("联系人创建失败", err.message);
    },
  });

  // 3. 更新人员
  const updatePersonMutation = useMutation({
    mutationFn: ({ id, person }: { id: UUID; person: PersonUpdate }) =>
      personsApi.update(id, person),
    onSuccess: async (updated) => {
      toast.showSuccess("联系人更新成功！");
      setPersonDetailCache(queryClient, updated);
      await invalidatePersonsLists(queryClient);
    },
    onError: (err: Error) => {
      toast.showError("联系人更新失败", err.message);
    },
  });

  // 4. 删除人员
  const deletePersonMutation = useMutation({
    mutationFn: ({ id }: { id: UUID }) => personsApi.delete(id),
    onSuccess: async (_, variables) => {
      toast.showSuccess("联系人删除成功！");
      const targetId = variables.id;
      removePersonDetailCache(queryClient, targetId);
      await Promise.all([
        invalidatePersonsLists(queryClient),
        invalidatePersonActivities(queryClient, targetId),
      ]);
    },
    onError: (err: Error) => {
      toast.showError("联系人删除失败", err.message);
    },
  });

  // 6. 创建人员
  const createPerson = (person: PersonCreate) => {
    createPersonMutation.mutate(person);
  };

  // 7. 更新人员
  const updatePerson = (id: UUID, person: PersonUpdate) => {
    updatePersonMutation.mutate({ id, person });
  };

  // 8. 删除人员
  const deletePerson = (id: UUID) => {
    deletePersonMutation.mutate({ id });
  };

  // 9. 加载人员活动记录 - 使用 prefetchQuery 预加载数据
  const loadPersonActivities = (personId: UUID) => {
    const defaultPage = 1;
    const defaultPageSize = 50;
    queryClient.prefetchQuery({
      queryKey: personsKeys.activitiesPage(personId, {
        page: defaultPage,
        size: defaultPageSize,
      }),
      queryFn: () =>
        personsApi.getActivities(personId, defaultPage, defaultPageSize),
      staleTime: 5 * 60 * 1000, // 5分钟缓存
    });
  };

  // 10. 刷新数据
  const refreshData = () => {
    void invalidatePersonsLists(queryClient);
  };

  return {
    persons,
    total,
    activities: null, // 移除 activities 相关状态，使用专门的 hook
    isLoading,
    isLoadingActivities: false, // 移除 activities 加载状态
    error,
    activitiesError: null, // 移除 activities 错误状态
    createPerson,
    updatePerson,
    deletePerson,
    loadPersonActivities,
    refreshData,
    createPersonMutation,
    updatePersonMutation,
    deletePersonMutation,
  };
}

/**
 * Hook for managing person activities with infinite scroll
 * This hook should be used when you need to display large amounts of person activities
 */
export function usePersonActivitiesPage(
  personId: UUID | null,
  page: number,
  pageSize: number = 50,
  activityType?: PersonActivityType | null,
): UsePersonActivitiesPageReturn {
  const previousPersonIdRef = useRef<UUID | null>(null);
  const previousTypeRef = useRef<PersonActivityType | null | undefined>(
    undefined,
  );
  const keepPreviousData =
    previousPersonIdRef.current === personId &&
    previousTypeRef.current === activityType;
  const safePage = Math.max(1, page);
  const safeSize = Math.max(1, pageSize);
  const normalizedType = activityType ?? undefined;

  useEffect(() => {
    previousPersonIdRef.current = personId;
    previousTypeRef.current = activityType;
  }, [personId, activityType]);

  const { data, isLoading, isFetching, error, refetch } = useQuery<
    PersonActivitiesResponse,
    Error
  >({
    queryKey: personsKeys.activitiesPage(personId, {
      page: safePage,
      size: safeSize,
      type: normalizedType ?? null,
    }),
    queryFn: () => {
      if (!personId) {
        return Promise.resolve({
          items: [],
          pagination: {
            page: safePage,
            size: safeSize,
            total: 0,
            pages: 0,
          },
          meta: {
            person_id: "",
            person_name: "",
            activity_type: normalizedType ?? null,
            timelog_count: 0,
            timelog_total_minutes: 0,
          },
        });
      }
      return personsApi.getActivities(
        personId,
        safePage,
        safeSize,
        normalizedType,
      );
    },
    enabled: !!personId,
    staleTime: 5 * 60 * 1000, // 5分钟缓存
    retry: 2,
    placeholderData: keepPreviousData
      ? (previousData) => previousData ?? undefined
      : undefined,
  });

  return {
    activities: data?.items ?? [],
    total: data?.pagination.total ?? 0,
    totalPages: data?.pagination.pages ?? 0,
    timelogStats:
      data?.meta.timelog_count !== undefined &&
      data?.meta.timelog_total_minutes !== undefined
        ? {
            count: data.meta.timelog_count ?? 0,
            totalMinutes: data.meta.timelog_total_minutes ?? 0,
          }
        : null,
    isLoading,
    isFetching,
    error,
    refetch,
  };
}
