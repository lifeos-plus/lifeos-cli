import React from "react";
import { useTranslation } from "react-i18next";
import { formatDateTime } from "@/utils/datetime";
import type { Tag } from "@/services/api";

interface TagTooltipContentProps {
  tag: Tag;
}

const TagTooltipContent: React.FC<TagTooltipContentProps> = ({ tag }) => {
  const { t } = useTranslation();
  const description =
    tag.description && tag.description.trim().length > 0
      ? tag.description.trim()
      : null;

  return (
    <div className="space-y-2">
      <div className="text-base font-semibold text-base-content">
        {t("notes.tooltip.tag.title", { name: tag.name })}
      </div>
      <dl className="space-y-1 text-sm text-base-content/80">
        <div className="flex items-start gap-2">
          <dt className="font-medium text-base-content/70">
            {t("notes.tooltip.tag.entityType")}:
          </dt>
          <dd className="text-base-content">
            {tag.entity_type ?? t("notes.tooltip.tag.unknown")}
          </dd>
        </div>
        <div className="flex items-start gap-2">
          <dt className="font-medium text-base-content/70">
            {t("notes.tooltip.tag.description")}:
          </dt>
          <dd className="text-base-content">
            {description ?? t("notes.tooltip.tag.noDescription")}
          </dd>
        </div>
        {tag.color ? (
          <div className="flex items-start gap-2">
            <dt className="font-medium text-base-content/70">
              {t("notes.tooltip.tag.color")}:
            </dt>
            <dd className="text-base-content">{tag.color}</dd>
          </div>
        ) : null}
        <div className="flex items-start gap-2">
          <dt className="font-medium text-base-content/70">
            {t("notes.tooltip.tag.createdAt")}:
          </dt>
          <dd className="text-base-content">
            {formatDateTime(tag.created_at ?? "")}
          </dd>
        </div>
        <div className="flex items-start gap-2">
          <dt className="font-medium text-base-content/70">
            {t("notes.tooltip.tag.updatedAt")}:
          </dt>
          <dd className="text-base-content">
            {formatDateTime(tag.updated_at ?? "")}
          </dd>
        </div>
      </dl>
    </div>
  );
};

export default TagTooltipContent;
