import React, { useCallback, useMemo, useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import ModalBase from "@/layouts/ModalBase";
import { personsApi } from "@/services/api/persons";
import { tagsApi } from "@/services/api/tags";
import TagSelector from "./selects/TagSelector";
import UnifiedTag from "./UnifiedTag";
import { FormActions, CreateNewButton } from "./ActionButton";
import { FormField, InputGroup, TextInput } from "./forms";
import type { Person, PersonCreate } from "@/services/api/persons";
import { useModalState } from "@/hooks/useModalState";
import { useToast } from "@/contexts/ToastContext";
import type { UUID } from "@/types/primitive";
import { useTagSelectorSource } from "@/hooks/selectors/useTagSelectorSource";

interface PersonFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (result?: { updatedPerson?: Person; created?: boolean }) => void;
  editingPerson?: Person | null;
  onRequestDelete?: (person: Person) => void;
}

/**
 * PersonFormModal - Modal component for creating/editing persons
 *
 * This component provides a modal interface for:
 * - Creating new persons
 * - Editing existing persons
 * - Managing person tags and relationships
 */
const PersonFormModal: React.FC<PersonFormModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  editingPerson,
  onRequestDelete,
}) => {
  const { t } = useTranslation();

  // Form state
  const [formData, setFormData] = useState<PersonCreate>({
    name: "",
    nicknames: [],
    birth_date: "",
    location: "",
    tag_ids: [],
  });

  const [nicknameInput, setNicknameInput] = useState("");
  const [locationTagIds, setLocationTagIds] = useState<UUID[]>([]);
  const { loading, error, setError, withLoading } = useModalState();
  const toast = useToast();
  const {
    tags: availablePersonTags,
    loading: tagsLoading,
    createTag: createPersonTag,
    refresh: refreshPersonTags,
  } = useTagSelectorSource({ entityType: "person" });
  const availableRelationshipTags = useMemo(() => {
    const toSortableCategory = (category: string | null | undefined): string =>
      category?.trim() || "general";

    const selectedRelationshipTags =
      editingPerson?.tags?.filter((tag) => tag.category !== "location") ?? [];
    const tagById = new Map(
      [...availablePersonTags, ...selectedRelationshipTags].map((tag) => [
        tag.id,
        tag,
      ]),
    );
    const tagsWithLabel = availablePersonTags
      .concat(selectedRelationshipTags)
      .filter((tag) => tag.category !== "location")
      .filter(
        (tag, index, tags) =>
          tags.findIndex((item) => item.id === tag.id) === index,
      )
      .map((tag) => ({
        tag: tagById.get(tag.id) ?? tag,
        category: toSortableCategory(tag.category),
        label: `${toSortableCategory(tag.category)}-${tag.name}`,
      }))
      .sort((a, b) => {
        if (a.category !== b.category) {
          return a.category.localeCompare(b.category);
        }
        return a.tag.name.localeCompare(b.tag.name);
      });

    return tagsWithLabel.map(({ tag, label }) => ({
      ...tag,
      name: label,
    }));
  }, [availablePersonTags, editingPerson?.tags]);
  const availableLocationTags = useMemo(() => {
    const selectedLocationTags =
      editingPerson?.tags?.filter((tag) => tag.category === "location") ?? [];
    return availablePersonTags
      .concat(selectedLocationTags)
      .filter((tag) => tag.category === "location")
      .filter(
        (tag, index, tags) =>
          tags.findIndex((item) => item.id === tag.id) === index,
      );
  }, [availablePersonTags, editingPerson?.tags]);
  const createLocationTag = useCallback(
    async (tagName: string) => {
      const created = await tagsApi.create({
        name: tagName,
        entity_type: "person",
        category: "location",
      });
      await refreshPersonTags();
      return created;
    },
    [refreshPersonTags],
  );
  // Removed local formError; rely on modal state's error

  const handleClose = () => {
    if (!loading) {
      setError(null);
      onClose();
    }
  };

  // Initialize form data when editing person changes
  useEffect(() => {
    if (editingPerson) {
      const locationTags =
        editingPerson.tags?.filter((tag) => tag.category === "location") ?? [];
      const relationshipTags =
        editingPerson.tags?.filter((tag) => tag.category !== "location") ?? [];
      setFormData({
        name: editingPerson.name || "",
        nicknames: editingPerson.nicknames || [],
        birth_date: editingPerson.birth_date || "",
        location: editingPerson.location || "",
        tag_ids: relationshipTags.map((tag) => tag.id),
      });
      setLocationTagIds(locationTags.map((tag) => tag.id));
    } else {
      setFormData({
        name: "",
        nicknames: [],
        birth_date: "",
        location: "",
        tag_ids: [],
      });
      setLocationTagIds([]);
    }
    setNicknameInput("");
    setError(null);
  }, [editingPerson, isOpen, setError]);

  // Handle form input changes
  const handleInputChange = (
    field: keyof PersonCreate,
    value: string | string[] | number[],
  ) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  // Handle nickname input
  const addNickname = () => {
    if (
      nicknameInput.trim() &&
      !formData.nicknames?.includes(nicknameInput.trim())
    ) {
      handleInputChange("nicknames", [
        ...(formData.nicknames || []),
        nicknameInput.trim(),
      ]);
      setNicknameInput("");
    }
  };

  const removeNickname = (nickname: string) => {
    handleInputChange(
      "nicknames",
      formData.nicknames?.filter((n) => n !== nickname) || [],
    );
  };

  // Handle tag changes from TagSelector
  const handleTagsChange = (tagIds: UUID[]) => {
    handleInputChange("tag_ids", tagIds);
  };

  const handleLocationTagsChange = (tagIds: UUID[]) => {
    setLocationTagIds(tagIds);
  };

  // Handle creating new tag
  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await withLoading(async () => {
        // Clean up form data - convert empty strings to undefined
        const mergedTagIds = Array.from(
          new Set([...(formData.tag_ids || []), ...locationTagIds]),
        );
        const cleanedData = {
          ...formData,
          name: formData.name?.trim() || "",
          birth_date: formData.birth_date?.trim() || undefined,
          location: formData.location?.trim() || undefined,
          nicknames: formData.nicknames?.filter((n) => n.trim()) || undefined,
          tag_ids: editingPerson
            ? mergedTagIds
            : mergedTagIds.length
              ? mergedTagIds
              : undefined,
        };

        let saved: Person | null = null;
        if (editingPerson) {
          saved = await personsApi.update(editingPerson.id, cleanedData);
          onSuccess({ updatedPerson: saved, created: false });

          // 显示成功提示
          toast.showSuccess(
            t("personForm.updateSuccess"),
            t("personForm.updateSuccessMessage", { name: cleanedData.name }),
          );
        } else {
          saved = (await personsApi.create(cleanedData)) as unknown as Person;
          onSuccess({ updatedPerson: saved, created: true });

          // 显示成功提示
          toast.showSuccess(
            t("personForm.createSuccess"),
            t("personForm.createSuccessMessage", { name: cleanedData.name }),
          );
        }

        onClose();
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to save person";
      setError(errorMessage);

      // 显示错误提示
      toast.showError(
        t("personForm.saveError"),
        t("eventModal.errors.saveMessage", { error: errorMessage }),
      );
    }
  };

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={handleClose}
      ariaLabelledBy="person-form-modal-title"
      size="lg"
      title={
        editingPerson ? t("personForm.editContact") : t("personForm.addContact")
      }
      footer={
        <FormActions
          loading={loading}
          onCancel={handleClose}
          onSubmit={() => document.querySelector("form")?.requestSubmit()}
          onDelete={
            editingPerson && onRequestDelete
              ? () => {
                  handleClose();
                  onRequestDelete(editingPerson);
                }
              : undefined
          }
        />
      }
      loading={loading}
      error={error}
      onErrorDismiss={() => setError(null)}
      showLoadingOverlay={false}
      showLoadingSpinner={true}
      loadingSpinnerSize="md"
      showCloseButton={true}
      errorDisplayMode="inline"
    >
      <form
        onSubmit={handleSubmit}
        className="space-y-3 sm:space-y-4 lg:space-y-5"
      >
        {/* Name Field */}
        <FormField label={t("personDetail.name")} htmlFor="person-name-input">
          <TextInput
            id="person-name-input"
            name="person-name-input"
            type="text"
            value={formData.name}
            onChange={(e) => handleInputChange("name", e.target.value)}
            placeholder={t("personForm.namePlaceholder")}
            disabled={loading}
          />
        </FormField>

        {/* Nicknames Field */}
        <FormField
          label={t("personDetail.nicknames")}
          htmlFor="person-nickname-input"
        >
          <InputGroup>
            <TextInput
              id="person-nickname-input"
              name="person-nickname-input"
              type="text"
              value={nicknameInput}
              onChange={(e) => setNicknameInput(e.target.value)}
              onKeyDown={(e) =>
                e.key === "Enter" && (e.preventDefault(), addNickname())
              }
              placeholder={t("personForm.nicknamePlaceholder")}
              disabled={loading}
              className="flex-1"
            />
            <CreateNewButton
              onClick={addNickname}
              disabled={loading}
              mode="subtle"
            />
          </InputGroup>
          <div className="flex flex-wrap gap-1 sm:gap-2 mt-2">
            {formData.nicknames?.map((nickname, index) => (
              <UnifiedTag
                key={index}
                type="nickname"
                size="md"
                onRemove={() => removeNickname(nickname)}
              >
                {nickname}
              </UnifiedTag>
            ))}
          </div>
        </FormField>

        {/* Birth Date Field */}
        <FormField
          label={t("personDetail.birthDate")}
          htmlFor="person-birth-date-input"
        >
          <TextInput
            id="person-birth-date-input"
            name="person-birth-date-input"
            type="date"
            value={formData.birth_date ?? ""}
            onChange={(e) => handleInputChange("birth_date", e.target.value)}
            disabled={loading}
          />
        </FormField>

        {/* Location Tags Field */}
        <div>
          <TagSelector
            availableTags={availableLocationTags}
            selectedTagIds={locationTagIds}
            onTagsChange={handleLocationTagsChange}
            onCreateTag={createLocationTag}
            disabled={loading || tagsLoading}
            idPrefix="location-tag-selector"
            label={t("personForm.locationTagsLabel")}
            dropdownZIndexClassName="z-modal"
            selectedPlacement="below"
          />
        </div>

        {/* Tags Field */}
        <div>
          <TagSelector
            availableTags={availableRelationshipTags}
            selectedTagIds={formData.tag_ids || []}
            onTagsChange={handleTagsChange}
            onCreateTag={createPersonTag}
            disabled={loading || tagsLoading}
            idPrefix="tag-selector"
            label={t("personDetail.relationshipTags")}
            dropdownZIndexClassName="z-modal"
            selectedPlacement="below"
          />
        </div>
      </form>
    </ModalBase>
  );
};

export default PersonFormModal;
