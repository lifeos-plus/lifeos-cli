import React, { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useVisions } from "@/hooks/queries/useVisions";
import { useDefaultInboxVision } from "@/hooks/queries/useDefaultInboxVision";
import type { Vision } from "@/services/api";
import AsyncEntitySelect from "./AsyncEntitySelect";
import type { SelectorValue } from "./selectorTypes";
import type { UUID } from "@/types/primitive";

type SelectSize = "sm" | "md" | "lg";

interface VisionSelectorProps {
  value?: string | null;
  onChange: (visionId: UUID | null) => void;
  placeholder?: string;
  disabled?: boolean;
  size?: SelectSize;
  className?: string;
  allowUndefined?: boolean; // when true, empty value maps to null
  fullWidth?: boolean; // when false, do not force w-full
  idPrefix?: string; // prefix for generating unique IDs
  label?: string; // optional label for the select field
  showLabel?: boolean; // whether to show the label (default: false for inline usage)
  showDefaultOption?: boolean; // whether to show "使用默认愿景" option
  defaultToInboxVision?: boolean; // whether to default to inbox vision when no value is set
  filterStatus?: string[]; // filter visions by status (default: ["active"])
  showStatus?: boolean; // whether to show status prefix in format [status]title (default: false)
  error?: string | null; // error message to display
}

// Stable default to avoid creating a new array on every render
const DEFAULT_VISION_FILTER_STATUS: string[] = ["active"];

const VisionSelector: React.FC<VisionSelectorProps> = React.memo(
  ({
    value,
    onChange,
    placeholder,
    disabled = false,
    size = "sm",
    className = "",
    allowUndefined = true,
    fullWidth = true,
    idPrefix = "vision-select",
    label,
    showLabel = false,
    showDefaultOption = false,
    defaultToInboxVision = false,
    filterStatus = DEFAULT_VISION_FILTER_STATUS,
    showStatus = false,
    error,
  }) => {
    const { t } = useTranslation();
    const hasAutoSelectedRef = useRef(false);

    // Use i18n translation as default placeholder if not provided
    const finalPlaceholder = placeholder || t("common.please_select");

    const {
      defaultInboxVision,
      loading: defaultVisionLoading,
      error: defaultVisionError,
    } = useDefaultInboxVision();

    const {
      visions,
      loading: loadingVisions,
      error: visionsError,
    } = useVisions({ ttlMs: 5 * 60 * 1000 });

    const availableVisions = useMemo(() => {
      const all = (visions as Vision[]) || [];
      if (!filterStatus || filterStatus.length === 0) {
        return all;
      }
      return all.filter((v) => filterStatus.includes(v.status));
    }, [visions, filterStatus]);

    // Auto-select default inbox vision if requested and no value is set
    useEffect(() => {
      if (
        defaultToInboxVision &&
        defaultInboxVision &&
        value === null &&
        !loadingVisions &&
        !defaultVisionLoading &&
        !hasAutoSelectedRef.current
      ) {
        hasAutoSelectedRef.current = true;
        onChange(defaultInboxVision);
      }
    }, [
      defaultToInboxVision,
      defaultInboxVision,
      value,
      loadingVisions,
      defaultVisionLoading,
      onChange,
    ]);

    // Build options for AsyncEntitySelect
    const options = useMemo(() => {
      const items: {
        id: UUID | string;
        label: string;
        disabled?: boolean;
      }[] = [];

      if (showDefaultOption && defaultInboxVision) {
        const def = availableVisions.find((v) => v.id === defaultInboxVision);
        if (def) {
          items.push({
            id: defaultInboxVision,
            label: `${def.name} (${t("common.default")})`,
          });
        }
      }

      // Do NOT add an extra empty option when allowUndefined is true,
      // AsyncEntitySelect already renders an empty placeholder as a separate item.
      if (!allowUndefined) {
        items.push({ id: "", label: finalPlaceholder });
      }

      availableVisions.forEach((v) => {
        if (showDefaultOption && v.id === defaultInboxVision) return;

        // Format label with status prefix if showStatus is enabled
        const label = showStatus
          ? `[${t(`status.${v.status}`)}] ${v.name}`
          : v.name;

        items.push({ id: v.id, label });
      });

      return items;
    }, [
      availableVisions,
      allowUndefined,
      finalPlaceholder,
      showDefaultOption,
      defaultInboxVision,
      showStatus,
      t,
    ]);

    const handleChange = (val: SelectorValue) => {
      if (val === undefined || val === "") {
        onChange(allowUndefined ? null : "");
        return;
      }
      const parsed = typeof val === "string" ? val : String(val);
      onChange(parsed);
    };

    const hasError = error || visionsError || defaultVisionError;
    const errorMessage = error || visionsError || defaultVisionError;

    return (
      <div className={`form-control ${fullWidth ? "w-full" : ""}`}>
        <AsyncEntitySelect
          value={value ?? (allowUndefined ? undefined : "")}
          onChange={handleChange}
          options={options}
          placeholder={finalPlaceholder}
          disabled={disabled || loadingVisions || defaultVisionLoading}
          size={size}
          className={className}
          allowUndefined={allowUndefined}
          fullWidth={fullWidth}
          idPrefix={idPrefix}
          label={label}
          showLabel={showLabel}
          usePortal
        />
        {hasError && (
          <div className="label">
            <span className="label-text-alt text-xs text-error">
              {errorMessage}
            </span>
          </div>
        )}
      </div>
    );
  },
);

VisionSelector.displayName = "VisionSelector";

export default VisionSelector;
