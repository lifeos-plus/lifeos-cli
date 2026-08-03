import React from "react";
import { useTranslation } from "react-i18next";
import ModalBase from "@/layouts/ModalBase";
import ActionButton, {
  ActionButtonGroup,
  FormActions,
  EditButton,
  DeleteButton,
  CreateNewButton,
} from "./ActionButton";
import ConfirmDialog from "./ConfirmDialog";
import EnumSelect from "./selects/EnumSelect";
import { FormField, TextInput, TextArea, Checkbox } from "./forms";
import { FORM_LABEL_COMPACT_CLASS } from "./forms/styles";
import { useAreaManagerController } from "@/features/areas/controller/useAreaManagerController";
import { AREA_COLOR_PALETTE } from "@/utils/areaColors";

interface AreaManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * AreaManagerModal
 * A comprehensive modal component for managing life areas.
 * Handles all area CRUD operations with a unified interface.
 */
const AreaManagerModal: React.FC<AreaManagerModalProps> = ({
  isOpen,
  onClose,
}) => {
  const { t } = useTranslation();
  const {
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
    clearDeletingArea,
  } = useAreaManagerController({
    isOpen,
    onClose,
  });

  // Common icons for areas
  const iconOptions = [
    { value: "work", label: t("areaManager.icons.work") },
    { value: "health", label: t("areaManager.icons.health") },
    { value: "family", label: t("areaManager.icons.family") },
    { value: "learning", label: t("areaManager.icons.learning") },
    { value: "creativity", label: t("areaManager.icons.creativity") },
    { value: "social", label: t("areaManager.icons.social") },
    { value: "finance", label: t("areaManager.icons.finance") },
    { value: "hobby", label: t("areaManager.icons.hobby") },
    { value: "travel", label: t("areaManager.icons.travel") },
    { value: "spirituality", label: t("areaManager.icons.spirituality") },
  ];

  if (loading) {
    return (
      <ModalBase
        isOpen={isOpen}
        onClose={onClose}
        ariaLabelledBy="area-manager-title"
        size="xl"
        header={t("areaManager.title")}
      >
        <div className="flex items-center justify-center h-64 text-base-content/60">
          {t("areaManager.loadingAreas")}
        </div>
      </ModalBase>
    );
  }

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={handleClose}
      ariaLabelledBy="area-manager-title"
      size="2xl"
      header={t("areaManager.title")}
      loading={loading}
      showLoadingOverlay={false}
      showLoadingSpinner={true}
      loadingSpinnerSize="md"
      showCloseButton={true}
      errorDisplayMode="none"
    >
      <div className="flex justify-center mb-6">
        <CreateNewButton
          label={t("areaManager.addNewArea")}
          onClick={() => setShowForm(true)}
        />
      </div>

      {/* Areas Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {areas.map((area) => (
          <div
            key={area.id}
            className={`p-4 rounded-lg border-2 transition-all ${
              area.is_active
                ? "border-base-200 bg-base-100 shadow-sm"
                : "border-base-200 bg-base-200 opacity-60"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <div
                  className="w-4 h-4 rounded-full"
                  style={{ backgroundColor: area.color }}
                />
                <h3 className="font-semibold text-base-content">
                  {area.name}
                </h3>
              </div>
              <ActionButtonGroup gap="sm" align="end">
                <EditButton onClick={() => handleEdit(area)} />
                <ActionButton
                  label={area.is_active ? "" : ""}
                  iconName="eye"
                  color="neutral"
                  size="sm"
                  onClick={() => void toggleActive(area)}
                  title={
                    area.is_active
                      ? t("areaManager.toggleActive")
                      : t("areaManager.toggleInactive")
                  }
                />
                <DeleteButton onClick={() => requestDelete(area)} />
              </ActionButtonGroup>
            </div>

            {area.description && (
              <p className="text-base text-base-content mb-2">
                {area.description}
              </p>
            )}

            {area.icon && (
              <div className="text-base text-base-content/60">
                {t("areaManager.iconLabel")}{" "}
                {iconOptions.find((opt) => opt.value === area.icon)
                  ?.label || area.icon}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Form Modal */}
      {showForm && (
        <ModalBase
          isOpen={showForm}
          onClose={resetForm}
          title={
            editingArea
              ? t("areaManager.editArea")
              : t("areaManager.addNewArea")
          }
          size="sm"
          nested
          loading={loading}
          showLoadingOverlay={false}
          showLoadingSpinner={true}
          loadingSpinnerSize="md"
          showCloseButton={true}
          errorDisplayMode="none"
        >
          <form onSubmit={saveArea} className="space-y-4">
            <FormField
              label={t("areaManager.areaName")}
              htmlFor="area-name"
              required
            >
              <TextInput
                id="area-name"
                name="area-name"
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
                required
                placeholder={t("areaManager.areaNamePlaceholder")}
                size="sm"
              />
            </FormField>

            <FormField
              label={t("visions.vision.description")}
              htmlFor="area-description"
            >
              <TextArea
                id="area-description"
                name="area-description"
                value={formData.description}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    description: e.target.value,
                  }))
                }
                rows={2}
                placeholder={t("areaManager.descriptionPlaceholder")}
                size="sm"
              />
            </FormField>

            <div>
              <label className={FORM_LABEL_COMPACT_CLASS}>
                {t("areaManager.color")}
              </label>
              <div className="flex space-x-2 mb-2">
                {AREA_COLOR_PALETTE.map((color) => (
                  <button
                    key={color}
                    type="button"
                    aria-label={color}
                    onClick={() => setFormData((prev) => ({ ...prev, color }))}
                    className={`w-8 h-8 rounded-full border-2 ${
                      formData.color === color
                        ? "border-base-content"
                        : "border-base-300"
                    }`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
              <input
                id="area-color"
                name="area-color"
                type="color"
                value={formData.color}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, color: e.target.value }))
                }
                className="w-full h-10 border border-base-300 rounded-md"
              />
            </div>

            <div>
              <div className="min-w-[180px]">
                <EnumSelect
                  id="area-manager-icon"
                  value={formData.icon}
                  onChange={(value) =>
                    setFormData((prev) => ({
                      ...prev,
                      icon: value as string,
                    }))
                  }
                  options={[
                    {
                      value: "",
                      label: t("areaManager.iconPlaceholder"),
                    },
                    ...iconOptions,
                  ]}
                  showLabel={true}
                  label={t("areaManager.icon")}
                />
              </div>
            </div>

            <Checkbox
              id="is_active"
              name="is_active"
              checked={formData.is_active}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({
                  ...prev,
                  is_active: checked,
                }))
              }
              label={t("areaManager.enableArea")}
              variant="primary"
              size="md"
            />

            <FormActions
              onCancel={resetForm}
              onSubmit={() => document.querySelector("form")?.requestSubmit()}
            />
          </form>
        </ModalBase>
      )}

      {/* Confirmation Dialog */}
      {deletingArea && (
        <ConfirmDialog
          isOpen={!!deletingArea}
          title={t("areaManager.deleteConfirmTitle")}
          message={t("areaManager.deleteConfirmMessage", {
            name: deletingArea.name,
          })}
          confirmText={t("common.delete")}
          onConfirm={() => void confirmDelete()}
          onCancel={clearDeletingArea}
        />
      )}
    </ModalBase>
  );
};

export default AreaManagerModal;
