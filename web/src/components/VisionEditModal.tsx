import React, { useState, useEffect, useRef, useId } from "react";
import { useTranslation } from "react-i18next";
import ModalBase from "@/layouts/ModalBase";
import { visionsApi } from "@/services/api/visions";
import PersonSelector from "./selects/PersonSelector";
import type { Vision, VisionCreate, VisionUpdate } from "@/services/api";
import { logger } from "@/utils/core";
import { FormActions } from "./ActionButton";
import AreaSelect from "./selects/AreaSelect";
import { useModalState } from "@/hooks/useModalState";
import { useToast } from "@/contexts/ToastContext";
import EnumSelect from "./selects/EnumSelect";
import { FormField, TextInput, TextArea } from "./forms";
import { VISION_EXPERIENCE_RATE_MAX } from "@/utils/constants";

interface VisionEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (result?: { updatedVision?: Vision }) => void;
  vision?: Vision | null; // null for create, Vision object for edit
  onRequestDelete?: (vision: Vision) => void;
}

/**
 * VisionEditModal - Modal for creating and editing visions
 *
 * This modal provides a clean interface for vision management,
 * replacing the inline form approach with a modal dialog.
 */
const VisionEditModal: React.FC<VisionEditModalProps> = ({
  isOpen,
  onClose,
  onSave,
  vision,
  onRequestDelete,
}) => {
  const { t } = useTranslation();
  const { loading, error, setError, withLoading } = useModalState();
  const [formData, setFormData] = useState<VisionCreate>({
    name: "",
    description: "",
    person_ids: [],
    area_id: undefined,
    status: "active",
    experience_rate_per_hour: undefined,
  });
  const [personSelectionTouched, setPersonSelectionTouched] = useState(false);

  const visionNameInputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  // Generate unique IDs for form fields to prevent duplicates
  const uniqueId = useId();
  const visionNameId = `vision-name-${uniqueId}`;
  const visionDescriptionId = `vision-description-${uniqueId}`;
  const modalTitleId = `vision-edit-modal-title-${uniqueId}`;

  const attemptClose = () => {
    if (!loading) onClose();
  };

  // Initialize form data when modal opens or vision changes
  useEffect(() => {
    if (isOpen) {
      if (vision) {
        // Edit mode - populate form with existing data
        setFormData({
          name: vision.name,
          description: vision.description || "",
          person_ids: vision.people?.map((person) => person.id) || [],
          area_id: vision.area_id ?? undefined,
          status: vision.status,
          experience_rate_per_hour: vision.experience_rate_per_hour,
        });
        setPersonSelectionTouched(false);
      } else {
        // Create mode - reset form
        setFormData({
          name: "",
          description: "",
          person_ids: [],
          area_id: undefined,
          status: "active",
          experience_rate_per_hour: undefined,
        });
        setPersonSelectionTouched(false);
      }
      setError(null);

      // Auto focus on vision name input after a short delay to ensure modal is rendered
      setTimeout(() => {
        visionNameInputRef.current?.focus();
      }, 100);
    }
  }, [isOpen, vision, setError]);

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      setError(t("visions.form.nameRequired"));
      return;
    }

    try {
      if (
        formData.experience_rate_per_hour !== undefined &&
        formData.experience_rate_per_hour !== null
      ) {
        const rate = formData.experience_rate_per_hour;
        if (rate < 1 || rate > VISION_EXPERIENCE_RATE_MAX) {
          setError(t("visions.form.experienceRateInvalid"));
          return;
        }
      }

      await withLoading(async () => {
        let updatedVision: Vision | undefined;

        if (vision) {
          // Update existing vision
          const updateData: VisionUpdate = {
            name: formData.name.trim(),
            description: formData.description?.trim() || undefined,
            area_id:
              formData.area_id && formData.area_id !== ""
                ? formData.area_id
                : null,
            status: formData.status,
            experience_rate_per_hour: formData.experience_rate_per_hour ?? null,
          };

          if (personSelectionTouched) {
            updateData.person_ids = formData.person_ids;
          }

          updatedVision = await visionsApi.update(vision.id, updateData);

          toast.showSuccess(
            t("visions.messages.visionUpdated"),
            `${t("tagManager.entityTypes.vision")}"${formData.name.trim()}"${t("visions.messages.visionUpdated")}`,
          );
        } else {
          // Create new vision
          const createData: VisionCreate = {
            name: formData.name.trim(),
            description: formData.description?.trim() || undefined,
            person_ids: formData.person_ids,
            area_id:
              formData.area_id && formData.area_id !== ""
                ? formData.area_id
                : null,
            status: formData.status,
          };

          if (
            formData.experience_rate_per_hour !== undefined &&
            formData.experience_rate_per_hour !== null
          ) {
            createData.experience_rate_per_hour =
              formData.experience_rate_per_hour;
          }

          updatedVision = await visionsApi.create(createData);

          toast.showSuccess(
            t("visions.messages.visionCreated"),
            `${t("tagManager.entityTypes.vision")}"${formData.name.trim()}"${t("visions.messages.visionCreated")}`,
          );
        }

        onSave({ updatedVision });
        onClose();
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : t("common.operationFailed");
      setError(errorMessage);
      logger.error("Failed to save vision:", err);

      toast.showError(
        t("visions.messages.saveFailed"),
        `${t("common.operationFailed")}：${errorMessage}`,
      );
    }
  };

  // Removed dirty-state tracking for confirm dialog

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={() => {
        if (!loading) attemptClose();
      }}
      closeDisabled={loading}
      ariaLabelledBy={modalTitleId}
      loading={loading}
      error={error}
      onErrorDismiss={() => setError(null)}
      showLoadingOverlay={false}
      showLoadingSpinner={true}
      loadingSpinnerSize="md"
      showCloseButton={true}
      errorDisplayMode="inline"
      header={
        vision ? t("visions.modal.editVision") : t("visions.modal.createVision")
      }
      footer={
        <FormActions
          loading={loading}
          onCancel={attemptClose}
          onSubmit={() => document.querySelector("form")?.requestSubmit()}
          onDelete={
            vision && onRequestDelete
              ? () => {
                  attemptClose();
                  onRequestDelete(vision);
                }
              : undefined
          }
        />
      }
    >
      <form
        onSubmit={handleSubmit}
        className="space-y-3 sm:space-y-4 lg:space-y-5"
      >
        {/* Vision Name - Always full width */}
        <FormField
          label={t("visions.form.name")}
          htmlFor={visionNameId}
          required
        >
          <TextInput
            id={visionNameId}
            name="vision-name"
            ref={visionNameInputRef}
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder={t("visions.form.namePlaceholder")}
            required
            disabled={loading}
          />
        </FormField>

        {/* Vision Description - Always full width */}
        <FormField
          label={t("visions.form.description")}
          htmlFor={visionDescriptionId}
        >
          <TextArea
            id={visionDescriptionId}
            name="vision-description"
            value={formData.description ?? ""}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
            rows={3}
            placeholder={t("visions.form.descriptionPlaceholder")}
            disabled={loading}
          />
        </FormField>

        <FormField
          label={t("visions.form.experienceRate")}
          description={t("visions.form.experienceRateDescription")}
        >
          <TextInput
            inputMode="numeric"
            pattern="[0-9]*"
            value={
              formData.experience_rate_per_hour === undefined ||
              formData.experience_rate_per_hour === null
                ? ""
                : String(formData.experience_rate_per_hour)
            }
            onChange={(event) => {
              const { value } = event.target;
              if (value === "") {
                setFormData({
                  ...formData,
                  experience_rate_per_hour: null,
                });
                return;
              }

              const parsed = Number(value);
              if (!Number.isNaN(parsed)) {
                setFormData({
                  ...formData,
                  experience_rate_per_hour: parsed,
                });
              }
            }}
            placeholder={t("visions.form.experienceRatePlaceholder")}
            disabled={loading}
          />
        </FormField>

        {/* Responsive Grid Layout for Area and Status */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
          {/* Area (optional) */}
          <div className="w-full">
            <AreaSelect
              value={formData.area_id ?? undefined}
              onChange={(v) =>
                setFormData({
                  ...formData,
                  area_id: v ?? null,
                })
              }
              showNoneOption={true}
              clearBehavior="none"
              disabled={loading}
              id="vision-area"
              placeholder={t("common.none")}
            />
          </div>

          {/* Status Selection */}
          <div className="w-full">
            <EnumSelect
              id="vision-status"
              value={formData.status}
              onChange={(value) => {
                if (value) {
                  setFormData({ ...formData, status: value as string });
                }
              }}
              options={[
                {
                  value: "active",
                  label: t("status.active"),
                },
                {
                  value: "archived",
                  label: t("status.archived"),
                },
                {
                  value: "fruit",
                  label: t("status.fruit"),
                },
              ]}
              disabled={loading}
              label={t("visions.form.status")}
            />
          </div>
        </div>

        {/* Person Selector - Always full width */}
        <div className="w-full">
          <PersonSelector
            selectedPersonIds={formData.person_ids || []}
            onSelectionChange={(personIds) => {
              setPersonSelectionTouched(true);
              setFormData({ ...formData, person_ids: personIds });
            }}
            placeholder={t("common.none")}
            multiple={true}
            disabled={loading}
            variant="compact"
            usePortal={true}
            idPrefix="vision-person"
          />
        </div>
      </form>
    </ModalBase>
  );
};

export default VisionEditModal;
