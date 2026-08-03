import React, { useState, useId, useMemo, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import type {
  Tag,
  TagBulkUpdateResponse,
  TagCategoryOption,
  TagCreate,
  TagUpdate,
} from "@/services/api/tags";
import { useToast } from "@/contexts/ToastContext";
import ConfirmDialog from "./ConfirmDialog";
import ActionButton, { EditButton, DeleteButton } from "./ActionButton";
import { Icon } from "./icons";
import EnumSelect from "./selects/EnumSelect";
import ModalBase from "@/layouts/ModalBase";
import Card from "@/layouts/Card";
import Surface from "@/layouts/Surface";
import Badge from "@/components/common/Badge";
import { useModalState } from "@/hooks/useModalState";
import { Checkbox, FormField, TextInput, TextArea } from "./forms";
import type { UUID } from "@/types/primitive";
import {
  useTagManagerController,
  type TagWithStats,
} from "@/features/tags/controller/useTagManagerController";

interface TagManagerProps {
  isOpen: boolean;
  onClose: () => void;
  onTagCreated?: (tag: Tag) => void;
  onTagUpdated?: (tag: Tag) => void;
  onTagDeleted?: (tagId: UUID) => void;
  title?: string;
  entityTypeScope: string;
}

interface TagGroup {
  entityType: string;
  tags: TagWithStats[];
  displayName: string;
}

const ENTITY_TYPE_DEFAULT_CATEGORIES: Record<string, string[]> = {
  person: ["location", "relation", "profession", "team"],
  note: ["topic"],
};

const ENTITY_VISUAL_THEMES = {
  person: {
    accent: "bg-primary",
    accentText: "text-primary-content",
    tag: "border-primary/40 bg-primary/20 hover:border-primary/60 hover:bg-primary/30",
    edit: "border-primary/50 bg-primary/10",
  },
  note: {
    accent: "bg-secondary",
    accentText: "text-secondary-content",
    tag: "border-secondary/40 bg-secondary/20 hover:border-secondary/60 hover:bg-secondary/30",
    edit: "border-secondary/50 bg-secondary/10",
  },
  task: {
    accent: "bg-accent",
    accentText: "text-accent-content",
    tag: "border-accent/40 bg-accent/20 hover:border-accent/60 hover:bg-accent/30",
    edit: "border-accent/50 bg-accent/10",
  },
  vision: {
    accent: "bg-info",
    accentText: "text-info-content",
    tag: "border-info/40 bg-info/20 hover:border-info/60 hover:bg-info/30",
    edit: "border-info/50 bg-info/10",
  },
  general: {
    accent: "bg-neutral",
    accentText: "text-neutral-content",
    tag: "border-neutral/40 bg-neutral/20 hover:border-neutral/60 hover:bg-neutral/30",
    edit: "border-neutral/50 bg-neutral/10",
  },
} as const;

const getEntityVisualTheme = (entityType: string) =>
  ENTITY_VISUAL_THEMES[
    entityType as keyof typeof ENTITY_VISUAL_THEMES
  ] || ENTITY_VISUAL_THEMES.general;

const getDefaultCategoryForEntityType = (
  entityType: string | null | undefined,
) => {
  const normalized = (entityType || "").trim();
  return ENTITY_TYPE_DEFAULT_CATEGORIES[normalized]?.[0] || "general";
};

const getBuiltinCategoriesForEntityType = (
  entityType: string | null | undefined,
) => {
  const normalized = (entityType || "").trim();
  return ENTITY_TYPE_DEFAULT_CATEGORIES[normalized] || [];
};

// Helper functions
const getEntityTypeDisplayName = (
  entityType: string,
  t: (key: string) => string,
): string => {
  const displayNames: Record<string, string> = {
    person: t("tagManager.entityTypes.person"),
    note: t("tagManager.entityTypes.note"),
    task: t("tagManager.entityTypes.task"),
    vision: t("tagManager.entityTypes.vision"),
    general: t("tagManager.entityTypes.general"),
  };
  return displayNames[entityType] || entityType;
};

const getCategoryDisplayName = (
  category: string,
  labelMap?: Map<string, string>,
): string => {
  return labelMap?.get(category) ?? category;
};

const sortTagsByUsageAndName = (tags: TagWithStats[]): TagWithStats[] => {
  return tags.sort((a, b) => {
    const aUsage = a.usageStats?.total_usage || 0;
    const bUsage = b.usageStats?.total_usage || 0;

    // First sort by usage count (descending)
    if (aUsage !== bUsage) {
      return bUsage - aUsage;
    }

    // If usage is the same, sort by name (ascending)
    return a.name.localeCompare(b.name);
  });
};

const getDefaultBulkTargetCategory = (
  sourceCategory: string,
  categoryOptions: TagCategoryOption[],
): string => {
  const nextCategory = categoryOptions.find(
    (option) => option.value !== sourceCategory,
  );
  return nextCategory?.value || categoryOptions[0]?.value || sourceCategory;
};

const normalizeTagCategory = (
  category: string | null | undefined,
  entityType: string | null | undefined,
) => category || getDefaultCategoryForEntityType(entityType);

const getDefaultCategoryForTag = (
  tagCategory: string | null | undefined,
  entityType: string | null | undefined,
) => normalizeTagCategory(tagCategory, entityType);

/**
 * TagManager - Unified component for managing all types of tags
 *
 * This component provides:
 * - Viewing all existing tags grouped by entity type
 * - Creating new tags with type selection
 * - Editing existing tag names (but not types)
 * - Deleting tags with confirmation
 * - Displaying tag usage statistics
 * - Built-in header with title and close button
 */
const TagManager: React.FC<TagManagerProps> = ({
  isOpen,
  onClose,
  onTagCreated,
  onTagUpdated,
  onTagDeleted,
  title,
  entityTypeScope,
}) => {
  const normalizedEntityTypeScope = useMemo(
    () => entityTypeScope.trim(),
    [entityTypeScope],
  );
  const defaultCategory = useMemo(
    () => getDefaultCategoryForEntityType(normalizedEntityTypeScope),
    [normalizedEntityTypeScope],
  );
  const { t } = useTranslation();
  // local UI-only states
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showCreateCategoryForm, setShowCreateCategoryForm] = useState(false);
  const [newCategoryLabel, setNewCategoryLabel] = useState("");
  const [renamingCategory, setRenamingCategory] = useState<string | null>(null);
  const [renameCategoryLabel, setRenameCategoryLabel] = useState("");
  const [editingTagId, setEditingTagId] = useState<UUID | null>(null);
  const [deletingTagId, setDeletingTagId] = useState<UUID | null>(null);
  const [selectedCategory, setSelectedCategory] =
    useState<string>(defaultCategory);
  const [createCategoryPreset, setCreateCategoryPreset] = useState<
    string | null
  >(null);
  const [createCategoryPresetVersion, setCreateCategoryPresetVersion] =
    useState(0);
  const [bulkEditCategory, setBulkEditCategory] = useState<string | null>(null);
  const [bulkSelectedTagIds, setBulkSelectedTagIds] = useState<Set<UUID>>(
    new Set(),
  );
  const [bulkTargetCategory, setBulkTargetCategory] = useState("");
  const [showBulkCategoryConfirm, setShowBulkCategoryConfirm] = useState(false);
  const [isApplyingBulkCategory, setIsApplyingBulkCategory] = useState(false);
  const modalTitleId = useId();

  // Toast notifications
  const toast = useToast();

  // Unified modal state (best practice aligning with TaskEditModal)
  const { loading, error, setError, withLoading } = useModalState();
  const {
    entityTypes,
    categoriesData,
    tagsData,
    tagsWithStats,
    typesLoading,
    categoriesLoading,
    tagsLoading,
    tagsFetching,
    statsLoading,
    statsFetching,
    typesError,
    categoriesError,
    tagsError,
    createCategoryMutation,
    renameCategoryMutation,
    createTag,
    createCategory,
    renameCategory,
    updateTag,
    deleteTag,
    bulkUpdateTagCategories,
  } = useTagManagerController({
    isOpen,
    entityTypeScope: normalizedEntityTypeScope,
    onTagCreated,
    onTagUpdated,
    onTagDeleted,
  });

  const combinedLoading =
    loading ||
    typesLoading ||
    categoriesLoading ||
    tagsLoading ||
    statsLoading ||
    tagsFetching ||
    statsFetching;
  const combinedError =
    error ||
    (typesError ? (typesError as Error).message : null) ||
    (categoriesError ? (categoriesError as Error).message : null) ||
    (tagsError ? (tagsError as Error).message : null) ||
    null;

  const categoryOptions = useMemo(() => {
    const raw =
      categoriesData && categoriesData.length > 0
        ? categoriesData
        : (() => {
            const fallbackValues = new Set<string>([defaultCategory]);
            tagsData.forEach((tag) => {
              fallbackValues.add(
                normalizeTagCategory(tag.category, tag.entity_type || ""),
              );
            });
            return Array.from(fallbackValues).map((value) => ({
              value,
              label: value,
            }));
          })();
    return raw.map((option) => {
      const key = `tagManager.categories.${option.value}`;
      const translated = t(key);
      return {
        value: option.value,
        label:
          translated && translated !== key
            ? translated
            : option.label || option.value,
      };
    });
  }, [categoriesData, tagsData, defaultCategory, t]);

  const categoryLabelMap = useMemo(
    () =>
      new Map(categoryOptions.map((option) => [option.value, option.label])),
    [categoryOptions],
  );

  const tagCountsByCategory = useMemo(() => {
    const counts = new Map<string, number>();
    (tagsWithStats as TagWithStats[]).forEach((tag) => {
      const category = normalizeTagCategory(tag.category, tag.entity_type);
      counts.set(category, (counts.get(category) ?? 0) + 1);
    });
    return counts;
  }, [tagsWithStats]);

  useEffect(() => {
    if (!isOpen) {
      setBulkEditCategory(null);
      setBulkSelectedTagIds(new Set());
      setBulkTargetCategory("");
      setShowBulkCategoryConfirm(false);
      setIsApplyingBulkCategory(false);
      return;
    }

    if (!categoryOptions.length) {
      if (selectedCategory !== defaultCategory) {
        setSelectedCategory(defaultCategory);
      }
      return;
    }

    if (!categoryOptions.some((opt) => opt.value === selectedCategory)) {
      const hasDefault = categoryOptions.some(
        (option) => option.value === defaultCategory,
      );
      setSelectedCategory(
        hasDefault ? defaultCategory : (categoryOptions[0]?.value ?? "general"),
      );
    }
  }, [categoryOptions, defaultCategory, isOpen, selectedCategory]);

  useEffect(() => {
    if (!isOpen || !bulkEditCategory) {
      return;
    }

    if (!categoryOptions.some((option) => option.value === bulkEditCategory)) {
      setBulkEditCategory(null);
      setBulkSelectedTagIds(new Set());
      setBulkTargetCategory("");
      setShowBulkCategoryConfirm(false);
      return;
    }

    if (bulkEditCategory !== selectedCategory) {
      setBulkEditCategory(null);
      setBulkSelectedTagIds(new Set());
      setShowBulkCategoryConfirm(false);
      return;
    }

    const fallbackTarget = getDefaultBulkTargetCategory(
      bulkEditCategory,
      categoryOptions,
    );
    if (
      !bulkTargetCategory ||
      bulkTargetCategory === bulkEditCategory ||
      !categoryOptions.some((option) => option.value === bulkTargetCategory)
    ) {
      setBulkTargetCategory(fallbackTarget);
    }
  }, [
    bulkEditCategory,
    categoryOptions,
    isOpen,
    bulkTargetCategory,
    selectedCategory,
  ]);

  useEffect(() => {
    if (combinedLoading) {
      setShowBulkCategoryConfirm(false);
    }
  }, [combinedLoading]);

  // Generic error handler
  const handleError = useCallback(
    (error: unknown, operation: string) => {
      const errorMessage =
        error instanceof Error ? error.message : `Failed to ${operation}`;
      console.error(errorMessage);
    },
    [],
  );

  const handleCreateCategory = useCallback(
    async (label: string) => {
      try {
        const createdCategory = await createCategory(label);
        setSelectedCategory(createdCategory.value);
        setNewCategoryLabel("");
        setShowCreateCategoryForm(false);
        setRenamingCategory(null);
        toast.showSuccess(
          t("tagManager.categoryManager.successTitle"),
          t("tagManager.categoryManager.successMessage", {
            name: createdCategory.label,
          }),
        );
      } catch (error) {
        const message =
          error instanceof Error ? error.message : t("common.operationFailed");
        toast.showError(t("tagManager.categoryManager.errorTitle"), message);
        setError(message);
      }
    },
    [createCategory, setError, t, toast],
  );

  const handleRenameCategory = useCallback(
    async ({ value, label }: { value: string; label: string }) => {
      try {
        const updatedCategory = await renameCategory({ value, label });
        setRenamingCategory(null);
        setRenameCategoryLabel("");
        toast.showSuccess(
          t("tagManager.categoryManager.renameSuccessTitle"),
          t("tagManager.categoryManager.renameSuccessMessage", {
            name: updatedCategory.label,
          }),
        );
      } catch (error) {
        const message =
          error instanceof Error ? error.message : t("common.operationFailed");
        toast.showError(
          t("tagManager.categoryManager.renameErrorTitle"),
          message,
        );
        setError(message);
      }
    },
    [renameCategory, setError, t, toast],
  );

  const openCreateTagFormForCategory = useCallback(
    (category?: string) => {
      const targetCategory =
        category ||
        selectedCategory ||
        categoryOptions[0]?.value ||
        defaultCategory;
      setSelectedCategory(targetCategory);
      setCreateCategoryPreset(targetCategory);
      setCreateCategoryPresetVersion((current) => current + 1);
      setShowCreateForm(true);
    },
    [categoryOptions, defaultCategory, selectedCategory],
  );

  const activeBulkTagIds = useMemo(() => {
    if (!bulkEditCategory) {
      return [] as UUID[];
    }
    return (tagsWithStats as TagWithStats[])
      .filter(
        (tag) =>
          getDefaultCategoryForTag(tag.category, tag.entity_type) ===
          bulkEditCategory,
      )
      .map((tag) => tag.id);
  }, [bulkEditCategory, tagsWithStats]);

  const activeBulkTagIdSet = useMemo(
    () => new Set(activeBulkTagIds),
    [activeBulkTagIds],
  );

  const currentBulkSelectedIds = useMemo(
    () =>
      new Set(
        Array.from(bulkSelectedTagIds).filter((tagId) =>
          activeBulkTagIdSet.has(tagId),
        ),
      ),
    [activeBulkTagIdSet, bulkSelectedTagIds],
  );

  const isBulkEditingCurrentCategory =
    bulkEditCategory ===
    (selectedCategory || categoryOptions[0]?.value || defaultCategory);

  const bulkSelectionCount = isBulkEditingCurrentCategory
    ? currentBulkSelectedIds.size
    : 0;

  const bulkTargetCategoryOptions = useMemo(
    () =>
      categoryOptions.filter(
        (option) => option.value !== bulkEditCategory && option.value !== "",
      ),
    [categoryOptions, bulkEditCategory],
  );

  useEffect(() => {
    if (!isBulkEditingCurrentCategory) {
      return;
    }

    setBulkSelectedTagIds((prev) => {
      const filtered = new Set<UUID>();
      prev.forEach((tagId) => {
        if (activeBulkTagIdSet.has(tagId)) {
          filtered.add(tagId);
        }
      });
      return filtered;
    });
  }, [activeBulkTagIdSet, isBulkEditingCurrentCategory]);

  const toggleBulkTag = useCallback((tagId: UUID, selected: boolean) => {
    setBulkSelectedTagIds((prev) => {
      const next = new Set(prev);
      if (selected) {
        next.add(tagId);
      } else {
        next.delete(tagId);
      }
      return next;
    });
  }, []);

  const selectAllCurrentCategoryBulkTags = useCallback(() => {
    if (!isBulkEditingCurrentCategory) {
      return;
    }
    setBulkSelectedTagIds(new Set(activeBulkTagIds));
  }, [activeBulkTagIds, isBulkEditingCurrentCategory]);

  const invertCurrentCategoryBulkTags = useCallback(() => {
    if (!isBulkEditingCurrentCategory) {
      return;
    }
    setBulkSelectedTagIds((prev) => {
      const next = new Set<UUID>();
      activeBulkTagIds.forEach((tagId) => {
        if (!prev.has(tagId)) {
          next.add(tagId);
        }
      });
      return next;
    });
  }, [activeBulkTagIds, isBulkEditingCurrentCategory]);

  const openBulkCategoryEdit = useCallback(
    (category: string) => {
      setBulkEditCategory(category);
      setBulkSelectedTagIds(new Set());
      setEditingTagId(null);
      setDeletingTagId(null);
      setBulkTargetCategory(
        getDefaultBulkTargetCategory(category, categoryOptions),
      );
      setShowBulkCategoryConfirm(false);
    },
    [categoryOptions],
  );

  const cancelBulkCategoryEdit = useCallback(() => {
    setBulkEditCategory(null);
    setBulkSelectedTagIds(new Set());
    setShowBulkCategoryConfirm(false);
  }, []);

  const requestBulkCategoryChange = useCallback(() => {
    if (!isBulkEditingCurrentCategory || bulkSelectionCount === 0) {
      return;
    }
    if (!bulkTargetCategory || bulkTargetCategory === bulkEditCategory) {
      return;
    }
    setShowBulkCategoryConfirm(true);
  }, [
    bulkEditCategory,
    bulkSelectionCount,
    bulkTargetCategory,
    isBulkEditingCurrentCategory,
  ]);

  const applyBulkCategoryChange = async () => {
    if (!isBulkEditingCurrentCategory) {
      setShowBulkCategoryConfirm(false);
      return;
    }
    if (!bulkTargetCategory || bulkTargetCategory === bulkEditCategory) {
      setShowBulkCategoryConfirm(false);
      return;
    }

    const targetIds = activeBulkTagIds.filter((tagId) =>
      currentBulkSelectedIds.has(tagId),
    );
    if (targetIds.length === 0) {
      setShowBulkCategoryConfirm(false);
      return;
    }

    setIsApplyingBulkCategory(true);
    try {
      const result: TagBulkUpdateResponse = await bulkUpdateTagCategories({
        ids: targetIds,
        category: bulkTargetCategory,
      });

      if (result.failed_ids.length > 0) {
        toast.showError(
          t("tagManager.categoryManager.bulkUpdatePartialErrorTitle"),
          t("tagManager.categoryManager.bulkUpdatePartialErrorMessage", {
            success: result.updated_count,
            failed: result.failed_ids.length,
          }),
        );
        setBulkSelectedTagIds(new Set(result.failed_ids));
        return;
      }

      toast.showSuccess(
        t("tagManager.categoryManager.bulkUpdateSuccessTitle"),
        t("tagManager.categoryManager.bulkUpdateSuccessMessage", {
          count: result.updated_count,
          target: getCategoryDisplayName(bulkTargetCategory, categoryLabelMap),
        }),
      );

      cancelBulkCategoryEdit();
    } catch (error) {
      const msg =
        error instanceof Error ? error.message : t("common.operationFailed");
      toast.showError(
        t("tagManager.categoryManager.bulkUpdatePartialErrorTitle"),
        msg,
      );
      setError(msg);
    } finally {
      setIsApplyingBulkCategory(false);
      setShowBulkCategoryConfirm(false);
    }
  };

  // Grouping is computed inline at render from query results

  // Handle tag creation
  const handleCreateTag = async (tagData: TagCreate) => {
    try {
      const scopedTagData: TagCreate = {
        ...tagData,
        ...(normalizedEntityTypeScope
          ? { entity_type: normalizedEntityTypeScope }
          : {}),
      };

      await withLoading(async () => {
        return await createTag(scopedTagData);
      });

      // list will be refreshed by invalidation

      toast.showSuccess(
        t("tagManager.success.createTitle"),
        t("tagManager.success.createMessage", { name: scopedTagData.name }),
      );

      // Close form
      setShowCreateForm(false);
      setCreateCategoryPreset(null);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to create tag";

      toast.showError(
        t("tagManager.errors.createTitle"),
        t("eventModal.errors.saveMessage", { error: errorMessage }),
      );
      handleError(err, "create tag");
      setError(errorMessage);
    }
  };

  // Handle tag update
  const handleUpdateTag = async (tagId: UUID, updates: TagUpdate) => {
    try {
      await withLoading(async () => {
        return await updateTag(tagId, updates);
      });

      // list will refresh via invalidation

      toast.showSuccess(
        t("tagManager.success.updateTitle"),
        t("tagManager.success.updateMessage", { name: updates.name }),
      );

      // Exit edit mode
      setEditingTagId(null);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to update tag";

      toast.showError(
        t("tagManager.errors.updateTitle"),
        t("eventModal.errors.saveMessage", { error: errorMessage }),
      );
      handleError(err, "update tag");
      setError(errorMessage);
    }
  };

  // Handle tag deletion
  const handleDeleteTag = useCallback(
    async (tagId: UUID) => {
      setDeletingTagId(null);
      try {
        await withLoading(async () => {
          await deleteTag(tagId);
        });

        toast.showSuccess(
          t("tagManager.success.deleteTitle"),
          t("tagManager.success.deleteMessage"),
        );
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to delete tag";

        toast.showError(
          t("tagManager.errors.deleteTitle"),
          t("eventModal.errors.saveMessage", { error: errorMessage }),
        );
        handleError(err, "delete tag");
        setError(errorMessage);
      }
    },
    [deleteTag, handleError, setError, t, toast, withLoading],
  );

  const attemptClose = () => {
    if (!combinedLoading) onClose();
  };

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={() => {
        if (!combinedLoading) attemptClose();
      }}
      closeDisabled={combinedLoading}
      header={
        title ||
        (normalizedEntityTypeScope
          ? t("tagManager.titleWithScope", {
              scope: getEntityTypeDisplayName(normalizedEntityTypeScope, t),
            })
          : t("tagManager.title"))
      }
      ariaLabelledBy={modalTitleId}
      loading={combinedLoading}
      error={combinedError}
      onErrorDismiss={() => setError(null)}
      showLoadingOverlay={false}
      showLoadingSpinner={true}
      loadingSpinnerSize="md"
      showCloseButton={true}
      errorDisplayMode="inline"
      size="xl"
    >
      <div className="space-y-4">
        {/* Create Form */}
        <TagCreateForm
          entityTypes={entityTypes}
          categoryOptions={categoryOptions}
          defaultCategory={
            selectedCategory || categoryOptions[0]?.value || defaultCategory
          }
          categoryPreset={createCategoryPreset}
          categoryPresetVersion={createCategoryPresetVersion}
          entityTypeScope={normalizedEntityTypeScope}
          onSubmit={handleCreateTag}
          onCancel={() => {
            setShowCreateForm(false);
            setCreateCategoryPreset(null);
          }}
          visible={showCreateForm}
        />

        {/* Create Button */}
        {!showCreateForm && (
          <div className="flex justify-center py-2">
            <ActionButton
              label={t("tagManager.createButton")}
              onClick={() => openCreateTagFormForCategory()}
              color="primary"
              variant="solid"
              iconName="sparkles"
              className="px-4 py-2 text-base font-medium shadow-md hover:shadow-lg transition-all duration-200"
            />
          </div>
        )}

        <Card
          title={t("tagManager.categoryManager.title")}
          description={t("tagManager.categoryManager.description")}
          className="h-auto mb-0"
          headerAction={
            <ActionButton
              label={
                showCreateCategoryForm
                  ? t("common.cancel")
                  : t("tagManager.categoryManager.addButton")
              }
              onClick={() => {
                setShowCreateCategoryForm((prev) => !prev);
                setNewCategoryLabel("");
              }}
              color="neutral"
              variant="outline"
              size="sm"
              iconName={showCreateCategoryForm ? "x-mark" : "plus"}
              disabled={categoriesLoading || combinedLoading}
            />
          }
        >
          <div className="space-y-3">
            {showCreateCategoryForm ? (
              <form
                className="flex flex-col sm:flex-row gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const label = newCategoryLabel.trim();
                  if (!label) {
                    toast.showError(
                      t("tagManager.categoryManager.errorTitle"),
                      t("tagManager.categoryManager.emptyError"),
                    );
                    return;
                  }
                  void handleCreateCategory(label);
                }}
              >
                <div className="flex-1">
                  <FormField
                    label={t("tagManager.categoryManager.newLabel")}
                    htmlFor="tag-category-new-label"
                  >
                    <TextInput
                      id="tag-category-new-label"
                      value={newCategoryLabel}
                      onChange={(e) => setNewCategoryLabel(e.target.value)}
                      placeholder={t("tagManager.categoryManager.placeholder")}
                      disabled={combinedLoading}
                    />
                  </FormField>
                </div>
                <div className="flex items-end">
                  <ActionButton
                    label={t("tagManager.categoryManager.createButton")}
                    color="primary"
                    variant="solid"
                    size="sm"
                    iconName="plus"
                    disabled={
                      combinedLoading ||
                      createCategoryMutation.isPending ||
                      !newCategoryLabel.trim()
                    }
                    onClick={() => {
                      const label = newCategoryLabel.trim();
                      if (!label) return;
                      void handleCreateCategory(label);
                    }}
                  />
                </div>
              </form>
            ) : null}

            <div className="flex flex-wrap gap-2">
              {categoryOptions.map((option) => {
                const active = option.value === selectedCategory;
                const count = tagCountsByCategory.get(option.value) ?? 0;
                const isBuiltin = getBuiltinCategoriesForEntityType(
                  normalizedEntityTypeScope,
                ).includes(option.value);
                const isRenaming = renamingCategory === option.value;
                const displayLabel = getCategoryDisplayName(
                  option.value,
                  categoryLabelMap,
                );
                const rowClasses = [
                  "inline-flex items-center gap-1 border rounded-full transition-all duration-200",
                  "px-3 py-2",
                  active
                    ? "bg-primary text-primary-content border-primary"
                    : "bg-base-100 text-base-content/80 border-base-300 hover:border-base-content/30 hover:text-base-content",
                ].join(" ");
                const actionsClasses =
                  "inline-flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-all duration-200 pointer-events-none group-hover:pointer-events-auto";

                if (isRenaming) {
                  return (
                    <div
                      key={option.value}
                      className="flex items-center gap-2 border border-base-300 bg-base-100 rounded-full px-3 py-2"
                    >
                      <TextInput
                        id={`tag-category-rename-${option.value}`}
                        value={renameCategoryLabel}
                        onChange={(e) => setRenameCategoryLabel(e.target.value)}
                        className="bg-transparent border-none outline-none text-sm font-medium min-w-[140px]"
                        autoFocus
                      />
                      <ActionButton
                        label={t("common.save")}
                        color="success"
                        variant="ghost"
                        iconName="check"
                        iconOnly
                        ariaLabel={t("common.save")}
                        disabled={
                          combinedLoading ||
                          renameCategoryMutation.isPending ||
                          !renameCategoryLabel.trim()
                        }
                        onClick={() => {
                          const label = renameCategoryLabel.trim();
                          if (!label) return;
                          void handleRenameCategory({
                            value: option.value,
                            label,
                          });
                        }}
                      />
                      <ActionButton
                        label={t("common.cancel")}
                        color="neutral"
                        variant="ghost"
                        iconName="x-mark"
                        iconOnly
                        ariaLabel={t("common.cancel")}
                        disabled={
                          combinedLoading || renameCategoryMutation.isPending
                        }
                        onClick={() => {
                          setRenamingCategory(null);
                          setRenameCategoryLabel("");
                        }}
                      />
                    </div>
                  );
                }

                return (
                  <div key={option.value} className={`group ${rowClasses}`}>
                    <button
                      type="button"
                      onClick={() => setSelectedCategory(option.value)}
                      aria-pressed={active}
                      className="inline-flex items-center gap-2 text-sm font-medium"
                    >
                      <span className="truncate max-w-[12rem]">
                        {displayLabel}
                      </span>
                      <span
                        className={[
                          "text-xs px-2 py-0.5 rounded-full",
                          active
                            ? "bg-primary-content/20 text-primary-content"
                            : "bg-base-200 text-base-content/70",
                        ].join(" ")}
                      >
                        {count}
                      </span>
                    </button>
                    <div className={actionsClasses}>
                      <ActionButton
                        label={t("tagManager.categoryManager.addTagButton")}
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        iconName="plus"
                        iconOnly
                        ariaLabel={t("tagManager.categoryManager.addTagButton")}
                        disabled={combinedLoading}
                        onClick={(e) => {
                          e.stopPropagation();
                          openCreateTagFormForCategory(option.value);
                        }}
                        className="p-0.5"
                      />
                      <ActionButton
                        label={t("tagManager.categoryManager.batchEditButton")}
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        iconName="repeat"
                        iconOnly
                        ariaLabel={t(
                          "tagManager.categoryManager.batchEditButton",
                        )}
                        disabled={combinedLoading || count === 0}
                        onClick={(e) => {
                          e.stopPropagation();
                          openBulkCategoryEdit(option.value);
                        }}
                        className="p-0.5"
                      />
                      {!isBuiltin ? (
                        <ActionButton
                          label={t("tagManager.categoryManager.renameButton")}
                          color="neutral"
                          variant="ghost"
                          size="sm"
                          iconName="edit"
                          iconOnly
                          ariaLabel={t(
                            "tagManager.categoryManager.renameButton",
                          )}
                          disabled={
                            combinedLoading || renameCategoryMutation.isPending
                          }
                          onClick={(e) => {
                            e.stopPropagation();
                            setRenamingCategory(option.value);
                            setRenameCategoryLabel(option.label);
                          }}
                          className="p-0.5"
                        />
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Card>

        {/* Tag Groups */}
        <div className="max-h-[48rem] overflow-y-auto space-y-4 pr-2 scrollbar-thin scrollbar-thumb-base-300 scrollbar-track-base-100 hover:scrollbar-thumb-base-content/30">
          {(() => {
            const activeCategory =
              selectedCategory || categoryOptions[0]?.value || defaultCategory;
            const filteredTags = (tagsWithStats as TagWithStats[]).filter(
              (tag) =>
                getDefaultCategoryForTag(tag.category, tag.entity_type) ===
                activeCategory,
            );
            const isBulkEditingActiveCategory =
              bulkEditCategory === activeCategory;

            if (filteredTags.length === 0) {
              return (
                <div className="text-center py-8">
                  <div className="w-12 h-12 bg-gradient-to-br from-base-200 to-base-300 rounded-full flex items-center justify-center mx-auto mb-3">
                    <Icon
                      name="tag"
                      size={24}
                      className="text-base-content/40"
                      aria-hidden
                    />
                  </div>
                  <p className="text-base font-medium text-base-content/70 mb-1">
                    {t("tagManager.noTags")}
                  </p>
                  <p className="text-sm text-base-content/50">
                    {t("tagManager.empty.createFirstTagHint")}
                  </p>
                </div>
              );
            }

            const unknownEntityTypes = Array.from(
              new Set(filteredTags.map((tag) => tag.entity_type)),
            ).filter((type) => !entityTypes.includes(type));
            const orderedEntityTypes = [
              ...(normalizedEntityTypeScope
                ? [normalizedEntityTypeScope]
                : entityTypes),
              ...unknownEntityTypes.sort(),
            ];
            const entityGroups: TagGroup[] = orderedEntityTypes
              .map((entityType) => {
                const groupTags = filteredTags.filter(
                  (tag) => tag.entity_type === entityType,
                );
                if (groupTags.length === 0) {
                  return null;
                }
                return {
                  entityType,
                  tags: sortTagsByUsageAndName(groupTags),
                  displayName: getEntityTypeDisplayName(entityType, t),
                };
              })
              .filter((value): value is TagGroup => value !== null);

            return (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-base font-semibold text-base-content">
                    {getCategoryDisplayName(activeCategory, categoryLabelMap)}
                  </h3>
                  <span className="text-xs font-medium text-base-content/70 bg-base-200 px-2 py-1 rounded-full">
                    {t("tagManager.ui.tagCount", {
                      count: filteredTags.length,
                    })}
                  </span>
                </div>
                {isBulkEditingActiveCategory ? (
                  <div className="rounded-lg border border-base-300 bg-base-100 px-3 py-2 space-y-2 md:space-y-0 md:flex md:items-center md:justify-between">
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="text-base-content/80">
                        {t("tagManager.categoryManager.bulkSelectionCount", {
                          selected: bulkSelectionCount,
                          total: filteredTags.length,
                        })}
                      </span>
                      <ActionButton
                        label={t("tagManager.categoryManager.bulkSelectAll")}
                        color="neutral"
                        variant="outline"
                        size="sm"
                        onClick={selectAllCurrentCategoryBulkTags}
                        disabled={combinedLoading || filteredTags.length === 0}
                        iconName="check"
                      />
                      <ActionButton
                        label={t(
                          "tagManager.categoryManager.bulkInvertSelection",
                        )}
                        color="neutral"
                        variant="outline"
                        size="sm"
                        onClick={invertCurrentCategoryBulkTags}
                        disabled={combinedLoading || filteredTags.length === 0}
                        iconName="switch"
                      />
                      <ActionButton
                        label={t("tagManager.categoryManager.cancelBulkEdit")}
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        onClick={cancelBulkCategoryEdit}
                        disabled={combinedLoading}
                        iconName="x-mark"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <EnumSelect
                        id="tag-bulk-target-category"
                        value={bulkTargetCategory}
                        onChange={(value) => {
                          if (value) {
                            setBulkTargetCategory(String(value));
                          }
                        }}
                        options={bulkTargetCategoryOptions.map((option) => ({
                          value: option.value,
                          label: option.label,
                        }))}
                        placeholder={t(
                          "tagManager.categoryManager.bulkTargetCategoryPlaceholder",
                        )}
                        disabled={
                          combinedLoading ||
                          bulkTargetCategoryOptions.length === 0
                        }
                        className="w-52"
                        showLabel={false}
                      />
                      <ActionButton
                        label={t("tagManager.categoryManager.bulkMoveButton")}
                        color="primary"
                        variant="solid"
                        size="sm"
                        onClick={requestBulkCategoryChange}
                        disabled={
                          combinedLoading ||
                          bulkSelectionCount === 0 ||
                          !bulkTargetCategory ||
                          bulkTargetCategory === activeCategory
                        }
                        iconName="repeat"
                      />
                    </div>
                  </div>
                ) : null}
                <div className="space-y-3">
                  {entityGroups.map((entityGroup) => (
                    <TagGroup
                      key={`${activeCategory}-${entityGroup.entityType}`}
                      group={entityGroup}
                      onTagUpdate={handleUpdateTag}
                      onTagDelete={handleDeleteTag}
                      editingTagId={editingTagId}
                      setEditingTagId={setEditingTagId}
                      deletingTagId={deletingTagId}
                      setDeletingTagId={setDeletingTagId}
                      bulkEditMode={isBulkEditingActiveCategory}
                      selectedTagIds={currentBulkSelectedIds}
                      onTagSelectionChange={toggleBulkTag}
                    />
                  ))}
                </div>
              </div>
            );
          })()}
        </div>

        {/* Delete Confirmation Dialog */}
        <ConfirmDialog
          isOpen={deletingTagId !== null}
          title={t("tagManager.confirmDelete.title")}
          message={t("tagManager.confirmDelete.message", {
            name: deletingTagId
              ? (tagsWithStats as TagWithStats[]).find(
                  (x: TagWithStats) => x.id === deletingTagId,
                )?.name || ""
              : "",
          })}
          confirmText={t("common.delete")}
          cancelText={t("common.cancel")}
          onConfirm={() => {
            if (deletingTagId) {
              void handleDeleteTag(deletingTagId);
            }
          }}
          onCancel={() => setDeletingTagId(null)}
        />

        <ConfirmDialog
          isOpen={showBulkCategoryConfirm}
          title={t("tagManager.categoryManager.bulkUpdateConfirmTitle")}
          message={t("tagManager.categoryManager.bulkUpdateConfirmMessage", {
            count: bulkSelectionCount,
            target: getCategoryDisplayName(
              bulkTargetCategory,
              categoryLabelMap,
            ),
          })}
          confirmText={t("tagManager.categoryManager.bulkMoveButton")}
          cancelText={t("common.cancel")}
          loading={isApplyingBulkCategory}
          onConfirm={() => {
            void applyBulkCategoryChange();
          }}
          onCancel={() => setShowBulkCategoryConfirm(false)}
        />
      </div>
    </ModalBase>
  );
};

// Tag Create Form Component
interface TagCreateFormProps {
  entityTypes: string[];
  categoryOptions: TagCategoryOption[];
  defaultCategory: string;
  categoryPreset?: string | null;
  categoryPresetVersion?: number;
  entityTypeScope?: string | null;
  onSubmit: (tagData: TagCreate) => Promise<void>;
  onCancel: () => void;
  visible: boolean;
}

const TagCreateForm: React.FC<TagCreateFormProps> = ({
  entityTypes,
  categoryOptions,
  defaultCategory,
  categoryPreset,
  categoryPresetVersion,
  entityTypeScope,
  onSubmit,
  onCancel,
  visible,
}) => {
  const { t } = useTranslation();
  const normalizedEntityType = entityTypeScope || "note";
  const [formData, setFormData] = useState<TagCreate>({
    name: "",
    entity_type: normalizedEntityType,
    category: defaultCategory,
    description: "",
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (
      !formData.category ||
      !categoryOptions.some((option) => option.value === formData.category)
    ) {
      setFormData((prev) => ({
        ...prev,
        category: defaultCategory,
      }));
    }
  }, [categoryOptions, defaultCategory, formData.category]);

  useEffect(() => {
    if (!visible || categoryPresetVersion == null || !categoryPreset) {
      return;
    }
    setFormData((prev) => ({
      ...prev,
      category: categoryPreset,
    }));
  }, [categoryPreset, categoryPresetVersion, visible]);

  useEffect(() => {
    setFormData((prev) => ({
      ...prev,
      entity_type: normalizedEntityType,
    }));
  }, [normalizedEntityType]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    try {
      setSubmitting(true);
      await onSubmit({
        ...formData,
        entity_type: normalizedEntityType,
        name: formData.name.trim().toLowerCase(),
      });

      // Reset form
      setFormData({
        name: "",
        entity_type: normalizedEntityType,
        category: defaultCategory,
        description: "",
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (!visible) return null;

  return (
    <Card
      title={t("tagManager.createNewTag")}
      footerActions={[
        {
          label: submitting
            ? t("tagManager.actions.creating")
            : t("common.submit"),
          onClick: () => {
            const form = document.getElementById(
              "tag-create-form",
            ) as HTMLFormElement;
            form?.requestSubmit();
          },
          color: "primary",
          variant: "solid",
          disabled: submitting || !formData.name.trim(),
        },
        {
          label: t("common.cancel"),
          onClick: onCancel,
          color: "neutral",
          variant: "outline",
        },
      ]}
      loading={submitting}
      className="mb-0"
    >
      <form id="tag-create-form" onSubmit={handleSubmit} className="space-y-4">
        <FormField
          label={t("tagManager.fields.name")}
          htmlFor="tag-name-input"
          required
        >
          <TextInput
            id="tag-name-input"
            name="tag-name-input"
            type="text"
            value={formData.name}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, name: e.target.value }))
            }
            placeholder={t("tagManager.fields.namePlaceholder")}
            required
            size="sm"
          />
        </FormField>

        {!entityTypeScope && (
          <div>
            <EnumSelect
              id="tag-entity-type-select"
              label={t("tagManager.fields.type")}
              value={formData.entity_type}
              onChange={(value) => {
                if (value) {
                  setFormData((prev) => ({
                    ...prev,
                    entity_type: value as string,
                  }));
                }
              }}
              options={entityTypes.map((type) => ({
                value: type,
                label: getEntityTypeDisplayName(type, t),
              }))}
            />
          </div>
        )}

        <div>
          <EnumSelect
            id="tag-category-select"
            label={t("tagManager.fields.category")}
            value={formData.category ?? ""}
            onChange={(value) => {
              if (value) {
                setFormData((prev) => ({
                  ...prev,
                  category: String(value),
                }));
              }
            }}
            options={categoryOptions.map((option) => ({
              value: option.value,
              label: option.label,
            }))}
            size="sm"
          />
        </div>

        <FormField
          label={t("tagManager.fields.description")}
          htmlFor="tag-description"
        >
          <TextArea
            id="tag-description"
            name="tag-description"
            value={formData.description || ""}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, description: e.target.value }))
            }
            placeholder={t("tagManager.fields.descriptionPlaceholder")}
            rows={2}
            size="sm"
          />
        </FormField>
      </form>
    </Card>
  );
};

// Tag Group Component
interface TagGroupProps {
  group: TagGroup;
  onTagUpdate: (tagId: UUID, updates: TagUpdate) => Promise<void>;
  onTagDelete: (tagId: UUID) => Promise<void>;
  editingTagId: UUID | null;
  setEditingTagId: (tagId: UUID | null) => void;
  deletingTagId: UUID | null;
  setDeletingTagId: (tagId: UUID | null) => void;
  bulkEditMode: boolean;
  selectedTagIds: Set<UUID>;
  onTagSelectionChange: (tagId: UUID, selected: boolean) => void;
}

const TagGroup: React.FC<TagGroupProps> = ({
  group,
  onTagUpdate,
  onTagDelete,
  editingTagId,
  setEditingTagId,
  deletingTagId,
  setDeletingTagId,
  bulkEditMode,
  selectedTagIds,
  onTagSelectionChange,
}) => {
  const { t } = useTranslation();

  const theme = getEntityVisualTheme(group.entityType);
  const iconName =
    group.entityType === "person"
      ? "people"
      : group.entityType === "note"
        ? "document-text"
        : group.entityType === "task"
          ? "check"
          : group.entityType === "vision"
            ? "sparkles"
            : "tag";

  return (
    <Surface padding="md" border="subtle" elevation="subtle">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className={`w-6 h-6 ${theme.accent} rounded-full flex items-center justify-center shadow-sm`}
          >
            <Icon
              name={iconName}
              size={16}
              className={theme.accentText}
              aria-hidden
            />
          </div>
          <h4 className="text-lg font-medium font-semibold text-base-content">
            {group.displayName}
          </h4>
        </div>
        <Badge tone="ghost" size="sm">
          {t("tagManager.ui.tagCount", { count: group.tags.length })}
        </Badge>
      </div>

      <div className="flex flex-wrap gap-2">
        {group.tags.map((tag) => (
          <TagItem
            key={tag.id}
            tag={tag}
            onUpdate={onTagUpdate}
            onDelete={onTagDelete}
            isEditing={editingTagId === tag.id}
            onEditStart={() => setEditingTagId(tag.id)}
            onEditCancel={() => setEditingTagId(null)}
            isDeleting={deletingTagId === tag.id}
            onDeleteStart={() => setDeletingTagId(tag.id)}
            onDeleteCancel={() => setDeletingTagId(null)}
            entityType={group.entityType}
            bulkEditMode={bulkEditMode}
            isBulkSelected={selectedTagIds.has(tag.id)}
            onBulkSelectionChange={(checked) =>
              onTagSelectionChange(tag.id, checked)
            }
          />
        ))}
      </div>
    </Surface>
  );
};

// Tag Item Component
interface TagItemProps {
  tag: TagWithStats;
  onUpdate: (tagId: UUID, updates: TagUpdate) => Promise<void>;
  onDelete: (tagId: UUID) => Promise<void>;
  isEditing: boolean;
  onEditStart: () => void;
  onEditCancel: () => void;
  isDeleting: boolean;
  onDeleteStart: () => void;
  onDeleteCancel: () => void;
  entityType: string;
  bulkEditMode: boolean;
  isBulkSelected: boolean;
  onBulkSelectionChange: (checked: boolean) => void;
}

const TagItem: React.FC<TagItemProps> = ({
  tag,
  onUpdate,
  onDelete,
  isEditing,
  onEditStart,
  onEditCancel,
  isDeleting,
  onDeleteStart,
  onDeleteCancel,
  entityType,
  bulkEditMode,
  isBulkSelected,
  onBulkSelectionChange,
}) => {
  const { t } = useTranslation();
  const [editName, setEditName] = useState(tag.name);
  const [updating, setUpdating] = useState(false);

  const theme = getEntityVisualTheme(entityType);

  const handleSave = async () => {
    if (editName.trim() === tag.name) {
      onEditCancel();
      return;
    }

    try {
      setUpdating(true);
      await onUpdate(tag.id, {
        name: editName.trim(),
      });
    } finally {
      setUpdating(false);
    }
  };

  const handleCancel = () => {
    setEditName(tag.name);
    onEditCancel();
  };

  const handleDelete = async () => {
    try {
      await onDelete(tag.id);
    } catch (err) {
      // Error is handled by parent component
      console.error("Failed to delete tag:", err);
    }
  };

  if (bulkEditMode) {
    return (
      <label
        className={`inline-flex items-center gap-2 border rounded-lg px-2 py-1 cursor-pointer ${theme.tag}`}
      >
        <Checkbox
          checked={isBulkSelected}
          onCheckedChange={onBulkSelectionChange}
          disabled={false}
          onClick={(e) => e.stopPropagation()}
        />
        <span className="text-base-content text-sm font-medium select-none">
          {tag.name}
        </span>
        {tag.usageStats && (
          <Badge tone="ghost" size="xs">
            {tag.usageStats.total_usage}
          </Badge>
        )}
      </label>
    );
  }

  if (isEditing) {
    return (
      <div
        className={`inline-flex items-center gap-2 border rounded-lg px-2 py-1 ${theme.edit}`}
      >
        <div className="flex items-center gap-2">
          <TextInput
            id="tag-edit-name-input"
            name="tag-edit-name-input"
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            className="bg-transparent border-none outline-none text-base-content text-sm font-medium min-w-[60px] max-w-[140px] placeholder:text-base-content/50"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSave();
              if (e.key === "Escape") handleCancel();
            }}
            placeholder={t("tagManager.ui.tagNamePlaceholder")}
          />
        </div>
        <ActionButton
          label={t("common.save")}
          onClick={handleSave}
          disabled={updating || !editName.trim()}
          color="success"
          variant="ghost"
          icon={
            updating ? (
              <span
                className="loading loading-spinner loading-xs"
                aria-hidden
              />
            ) : (
              <Icon name="check" size={14} />
            )
          }
          className="ml-1 p-0.5"
          iconOnly
          ariaLabel={t("common.save")}
        />
        <ActionButton
          label={t("common.cancel")}
          onClick={handleCancel}
          color="error"
          variant="ghost"
          iconName="x-mark"
          className="ml-0.5 p-0.5"
          iconOnly
          ariaLabel={t("common.cancel")}
        />
      </div>
    );
  }

  if (isDeleting) {
    return (
      <div
        className="inline-flex items-center rounded-lg border border-error/50 bg-error/10 px-2 py-1"
      >
        <span className="text-error text-sm font-medium">
          {t("common.deleting")}
        </span>
        <ActionButton
          label={t("common.confirm")}
          onClick={handleDelete}
          color="error"
          variant="ghost"
          iconName="check"
          className="ml-1 p-0.5"
          iconOnly
          ariaLabel={t("common.confirm")}
        />
        <ActionButton
          label={t("common.cancel")}
          onClick={onDeleteCancel}
          color="neutral"
          variant="ghost"
          iconName="x-mark"
          className="ml-0.5 p-0.5"
          iconOnly
          ariaLabel={t("common.cancel")}
        />
      </div>
    );
  }

  return (
    <div
      className={`group inline-flex cursor-pointer items-center gap-1 rounded-lg border px-2 py-1 transition-colors ${theme.tag}`}
      onClick={onEditStart}
    >
      <span className="text-base-content text-sm font-medium select-none">
        {tag.name}
      </span>

      {/* Usage Statistics */}
      {tag.usageStats && (
        <Badge tone="ghost" size="xs">
          {tag.usageStats.total_usage}
        </Badge>
      )}

      {/* Interactive Icons */}
      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-all duration-200">
        <EditButton onClick={onEditStart} size="sm" className="p-0.5" />
        <DeleteButton
          onClick={(e) => {
            e.stopPropagation();
            onDeleteStart();
          }}
          size="sm"
          className="p-0.5"
        />
      </div>
    </div>
  );
};

export default TagManager;
