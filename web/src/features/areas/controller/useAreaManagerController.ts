import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useToast } from "@/contexts/ToastContext";
import { logger } from "@/utils/core";
import { areasApi, type Area } from "@/services/api/areas";
import { useModalState } from "@/hooks/useModalState";
import {
  invalidateAreaDetail,
  invalidateAreaOrder,
  invalidateAreasLists,
  removeAreaDetailCache,
  setAreaDetailCache,
} from "@/services/api/cacheInvalidation/areas";
import { DEFAULT_NEW_AREA_COLOR } from "@/utils/areaColors";

interface AreaFormData {
  name: string;
  description: string;
  color: string;
  icon: string;
  is_active: boolean;
  display_order: number;
}

interface UseAreaManagerControllerParams {
  isOpen: boolean;
  onClose: () => void;
}

const DEFAULT_FORM_DATA: AreaFormData = {
  name: "",
  description: "",
  color: DEFAULT_NEW_AREA_COLOR,
  icon: "",
  is_active: true,
  display_order: 0,
};

export function useAreaManagerController({
  isOpen,
  onClose,
}: UseAreaManagerControllerParams) {
  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { loading, withLoading } = useModalState();

  const [areas, setAreas] = useState<Area[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingArea, setEditingArea] = useState<Area | null>(
    null,
  );
  const [deletingArea, setDeletingArea] = useState<Area | null>(
    null,
  );
  const [formData, setFormData] =
    useState<AreaFormData>(DEFAULT_FORM_DATA);

  const fetchAreas = useCallback(async () => {
    try {
      await withLoading(async () => {
        const response = await areasApi.getAreas();
        setAreas(
          (response.items ?? []).sort(
            (a, b) => (a.display_order || 0) - (b.display_order || 0),
          ),
        );
      });
    } catch (error) {
      logger.error("Failed to fetch areas:", error);
    }
  }, [withLoading]);

  useEffect(() => {
    if (isOpen) {
      void fetchAreas();
    }
  }, [fetchAreas, isOpen]);

  const resetForm = useCallback(() => {
    setFormData(DEFAULT_FORM_DATA);
    setEditingArea(null);
    setShowForm(false);
  }, []);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [onClose, resetForm]);

  const handleEdit = useCallback((area: Area) => {
    setEditingArea(area);
    setFormData({
      name: area.name,
      description: area.description || "",
      color: area.color || DEFAULT_NEW_AREA_COLOR,
      icon: area.icon || "",
      is_active: area.is_active,
      display_order: area.display_order || 0,
    });
    setShowForm(true);
  }, []);

  const requestDelete = useCallback((area: Area) => {
    setDeletingArea(area);
  }, []);

  const saveArea = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();

      try {
        await withLoading(async () => {
          let persisted: Area | null = null;

          if (editingArea) {
            const updated = await areasApi.updateArea(
              editingArea.id,
              formData,
            );
            setAreas((prev) =>
              prev.map((area) =>
                area.id === updated.id ? updated : area,
              ),
            );
            persisted = updated;
          } else {
            const created = await areasApi.createArea({
              ...formData,
              display_order: areas.length,
            });
            setAreas((prev) => [...prev, created]);
            persisted = created;
          }

          if (persisted) {
            setAreaDetailCache(queryClient, persisted);
            await Promise.all([
              invalidateAreasLists(queryClient),
              invalidateAreaDetail(queryClient, persisted.id),
              invalidateAreaOrder(queryClient),
            ]);
          }

          resetForm();
          toast.showSuccess(
            editingArea
              ? t("areaManager.areaUpdated")
              : t("areaManager.areaCreated"),
            editingArea
              ? t("areaManager.areaUpdateSuccess")
              : t("areaManager.areaCreateSuccess"),
          );
        });
      } catch (error) {
        logger.error("Failed to save area:", error);
        const errorMessage =
          error instanceof Error
            ? error.message
            : t("areaManager.retryLater");
        toast.showError(
          t("areaManager.saveError"),
          `${t("areaManager.operationFailed")}${errorMessage}`,
        );
      }
    },
    [
      areas.length,
      editingArea,
      formData,
      queryClient,
      resetForm,
      t,
      toast,
      withLoading,
    ],
  );

  const confirmDelete = useCallback(async () => {
    if (!deletingArea) return;

    try {
      await withLoading(async () => {
        await areasApi.deleteArea(deletingArea.id);
        setAreas((prev) =>
          prev.filter((area) => area.id !== deletingArea.id),
        );
        removeAreaDetailCache(queryClient, deletingArea.id);
        toast.showSuccess(
          t("areaManager.areaDeleted"),
          `"${deletingArea.name}"${t("areaManager.areaDeleteSuccess")}`,
        );
        await Promise.all([
          invalidateAreasLists(queryClient),
          invalidateAreaOrder(queryClient),
        ]);
      });
    } catch (error) {
      logger.error("Failed to delete area:", error);
      toast.showError(
        t("areaManager.deleteError"),
        t("areaManager.retryLater"),
      );
    } finally {
      setDeletingArea(null);
    }
  }, [deletingArea, queryClient, t, toast, withLoading]);

  const toggleActive = useCallback(
    async (area: Area) => {
      try {
        await withLoading(async () => {
          const updated = await areasApi.updateArea(area.id, {
            is_active: !area.is_active,
          });
          setAreas((prev) =>
            prev.map((item) => (item.id === updated.id ? updated : item)),
          );
          setAreaDetailCache(queryClient, updated);
          await Promise.all([
            invalidateAreasLists(queryClient),
            invalidateAreaDetail(queryClient, updated.id),
          ]);
        });
      } catch (error) {
        logger.error("Failed to toggle area:", error);
      }
    },
    [queryClient, withLoading],
  );

  return {
    loading,
    areas,
    showForm,
    setShowForm,
    editingArea,
    deletingArea,
    formData,
    setFormData,
    resetForm,
    handleClose,
    handleEdit,
    requestDelete,
    saveArea,
    confirmDelete,
    toggleActive,
    clearDeletingArea: () => setDeletingArea(null),
  };
}
