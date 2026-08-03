import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { areasApi } from "@/services/api/areas";
import { areasKeys } from "@/services/api/queryKeys";
import type { UUID } from "@/types/primitive";
import { DEFAULT_AREA_COLOR } from "@/utils/areaColors";

export function useAreas(options?: {
  ttlMs?: number;
  includeInactive?: boolean;
}) {
  const { t } = useTranslation();
  const page = 1;
  const size = 100;

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: areasKeys.list({
      include_inactive: options?.includeInactive ?? false,
      page,
      size,
    }),
    queryFn: () =>
      areasApi.getAreas(
        options?.includeInactive ?? false,
        page,
        size,
      ),
    staleTime: options?.ttlMs ?? 5 * 60 * 1000,
  });

  const areaItems = useMemo(() => data?.items ?? [], [data?.items]);

  const areaMap = useMemo(() => {
    const map = new Map<UUID, { name: string; color: string }>();
    for (const d of areaItems) {
      map.set(d.id, { name: d.name, color: d.color || DEFAULT_AREA_COLOR });
    }
    return map;
  }, [areaItems]);

  return {
    areas: areaItems,
    areaMap,
    loading: isLoading,
    error: error
      ? error instanceof Error
        ? error.message
        : t("common.loading")
      : null,
    refresh: () => refetch(),
  };
}
