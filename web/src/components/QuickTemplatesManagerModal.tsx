import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import ModalBase from "@/layouts/ModalBase";
import ActionButton, { DeleteButton, EditButton } from "./ActionButton";
import QuickTemplateEditorModal, {
  type QuickTemplateEditorValues,
} from "./QuickTemplateEditorModal";
import { useToast } from "@/contexts/ToastContext";
import { useAreas } from "@/hooks/queries/useAreas";
import { useTimelogTemplates } from "@/hooks/queries/useTimelogTemplates";
import type { TimelogTemplate } from "@/services/api/timelogTemplates";
import { UNKNOWN_AREA_COLOR } from "@/utils/areaColors";

interface QuickTemplatesManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const QuickTemplatesManagerModal = ({
  isOpen,
  onClose,
}: QuickTemplatesManagerModalProps) => {
  const { t } = useTranslation();
  const toast = useToast();
  const {
    templates,
    loading,
    error,
    createTemplate,
    updateTemplate,
    deleteTemplate,
  } = useTimelogTemplates();
  const { areaMap } = useAreas();

  const [editorOpen, setEditorOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] =
    useState<TimelogTemplate | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [editorSubmitting, setEditorSubmitting] = useState(false);

  const sortedTemplates = useMemo(
    () => [...templates].sort((a, b) => a.position - b.position),
    [templates],
  );

  const closeEditor = useCallback(() => {
    setEditorOpen(false);
    setEditingTemplate(null);
    setEditorError(null);
    setEditorSubmitting(false);
  }, []);

  const handleCreateClick = () => {
    setEditingTemplate(null);
    setEditorError(null);
    setEditorOpen(true);
  };

  const handleEditClick = (template: TimelogTemplate) => {
    setEditingTemplate(template);
    setEditorError(null);
    setEditorOpen(true);
  };

  const handleDelete = async (template: TimelogTemplate) => {
    try {
      await deleteTemplate(template.id);
      toast.showSuccess(t("quickTemplatesManager.messages.deleteSuccess"));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : String(err ?? "unknown error");
      toast.showError(
        t("quickTemplatesManager.messages.actionFailed"),
        message,
      );
    }
  };

  const handleEditorSubmit = async (values: QuickTemplateEditorValues) => {
    setEditorSubmitting(true);
    setEditorError(null);
    try {
      if (editingTemplate) {
        await updateTemplate({
          id: editingTemplate.id,
          payload: {
            title: values.title,
            area_id: values.area_id ?? null,
            person_ids: values.person_ids,
            default_duration_minutes: values.default_duration_minutes ?? null,
          },
        });
        toast.showSuccess(t("quickTemplatesManager.messages.updateSuccess"));
      } else {
        await createTemplate({
          title: values.title,
          area_id: values.area_id ?? null,
          person_ids: values.person_ids,
          default_duration_minutes: values.default_duration_minutes ?? null,
        });
        toast.showSuccess(t("quickTemplatesManager.messages.createSuccess"));
      }
      closeEditor();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : String(err ?? "unknown error");
      setEditorError(message);
      toast.showError(
        t("quickTemplatesManager.messages.actionFailed"),
        message,
      );
    } finally {
      setEditorSubmitting(false);
    }
  };

  return (
    <>
      <ModalBase
        isOpen={isOpen}
        onClose={onClose}
        header={t("quickTemplatesManager.title")}
        size="xl"
        loading={loading}
        showLoadingSpinner={loading}
        error={error ?? undefined}
        onErrorDismiss={undefined}
        showCloseButton={true}
      >
        <div className="space-y-6">
          <div className="flex items-center justify-center">
            <ActionButton
              label={t("quickTemplatesManager.addTemplate")}
              iconName="plus"
              color="primary"
              variant="solid"
              onClick={handleCreateClick}
            />
          </div>

          {sortedTemplates.length === 0 ? (
            <div className="text-xs text-base-content bg-base-200 border border-base-300 rounded p-4 text-center">
              {t("quickTemplatesManager.noTemplates")}
            </div>
          ) : (
            <div className="border border-base-300 rounded-lg divide-y divide-base-200 max-h-[55vh] overflow-y-auto">
              {sortedTemplates.map((template) => {
                const area = template.area_id
                  ? areaMap.get(template.area_id)
                  : template.area_name
                    ? {
                        name: template.area_name,
                        color: template.area_color,
                      }
                    : undefined;
                const color =
                  area?.color || template.area_color || UNKNOWN_AREA_COLOR;
                const areaLabel =
                  area?.name ??
                  template.area_name ??
                  t("common.none");
                const durationLabel = template.default_duration_minutes
                  ? `${template.default_duration_minutes} ${t("quickTemplatesManager.minutes")}`
                  : t("common.none");
                const personLabel =
                  template.people && template.people.length > 0
                    ? template.people
                        .map((person) => person.display_name)
                        .join(", ")
                    : t("common.none");

                return (
                  <div
                    key={template.id}
                    className="flex items-center gap-3 px-3 py-2 bg-base-100"
                  >
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: color }}
                    />
                    <span className="w-28 text-sm text-base-content/80 truncate">
                      {areaLabel}
                    </span>
                    <span className="flex-1 min-w-0 text-sm font-medium text-base-content truncate">
                      {template.title}
                    </span>
                    <span className="w-24 text-xs text-base-content/70 truncate">
                      {durationLabel}
                    </span>
                    <span className="w-32 text-xs text-base-content/70 truncate">
                      {personLabel}
                    </span>
                    <div className="flex items-center gap-1 ml-2">
                      <EditButton
                        onClick={() => handleEditClick(template)}
                        size="sm"
                      />
                      <DeleteButton
                        onClick={() => handleDelete(template)}
                        size="sm"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </ModalBase>

      <QuickTemplateEditorModal
        isOpen={editorOpen}
        onClose={closeEditor}
        onSubmit={handleEditorSubmit}
        initialTemplate={editingTemplate}
        submitting={editorSubmitting}
        errorMessage={editorError}
      />
    </>
  );
};

export default QuickTemplatesManagerModal;
