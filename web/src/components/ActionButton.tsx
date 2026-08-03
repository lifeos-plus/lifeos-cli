import React, { useCallback } from "react";
import { useTranslation } from "react-i18next";
import InlineTooltipTrigger from "./InlineTooltipTrigger";
import { Icon, type IconName } from "./icons";

type ActionColor = "primary" | "neutral" | "success" | "warning" | "error";
export type ActionSize = "xs" | "sm" | "md" | "lg";
type ActionVariant = "solid" | "outline" | "ghost";
type ActionShape = "default" | "square" | "circle";

interface ActionButtonProps {
  label: string;
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  color?: ActionColor;
  size?: ActionSize;
  variant?: ActionVariant;
  title?: string;
  disabled?: boolean;
  className?: string;
  icon?: React.ReactNode; // emoji or SVG/icon component
  iconName?: IconName; // standardized icon library name
  iconSize?: number;
  type?: "button" | "submit" | "reset";
  ariaLabel?: string; // accessibility label
  ariaHasPopup?: React.AriaAttributes["aria-haspopup"];
  ariaExpanded?: boolean;
  shape?: ActionShape;
  iconOnly?: boolean;
  form?: string;
}

interface ActionButtonGroupProps {
  children: React.ReactNode;
  gap?: "sm" | "md" | "lg";
  align?: "start" | "center" | "end";
  /**
   * Layout preset for opposite actions (e.g., Cancel on the left, Confirm on the right)
   * When true, the group renders a two-sided row: left slot (first child) and right slot (rest children)
   */
  splitOpposite?: boolean;
  /** Optional: render a top border and spacing commonly used in modals */
  withTopBorder?: boolean;
  /** Optional: additional CSS classes */
  className?: string;
}

interface FormActionsProps {
  // 基础配置
  loading?: boolean;
  disabled?: boolean;

  // 按钮文本
  submitText?: string;
  cancelText?: string;

  // 按钮图标
  submitIcon?: React.ReactNode;
  cancelIcon?: React.ReactNode;

  // 按钮颜色（daisyUI semantic colors）
  submitColor?: ActionColor;
  cancelColor?: ActionColor;

  // 按钮大小
  size?: "sm" | "md" | "lg";

  // 事件处理
  onSubmit?: () => void;
  onCancel?: () => void;
  /** edit-mode destructive action; replaces the default cancel action */
  onDelete?: () => void;
  deleteDisabled?: boolean;

  // 布局配置
  showTopBorder?: boolean;
  /** optional custom left slot; when provided, replaces the default cancel button */
  leftSlot?: React.ReactNode;

  // 样式配置
  className?: string;
}

function resolveBtnClasses(color: ActionColor, variant: ActionVariant): string {
  const base = "btn";
  const colorClass =
    color === "primary"
      ? "btn-primary"
      : color === "success"
        ? "btn-success"
        : color === "warning"
          ? "btn-warning"
          : color === "error"
            ? "btn-error"
            : "btn-neutral"; // default
  const variantClass =
    variant === "outline"
      ? "btn-outline"
      : variant === "ghost"
        ? "btn-ghost"
        : "";
  return [base, colorClass, variantClass].filter(Boolean).join(" ");
}

function resolveSizeClasses(size: ActionSize): string {
  switch (size) {
    case "xs":
      return "btn-xs text-[0.7rem] sm:text-xs";
    case "sm":
      return "btn-sm text-xs sm:text-sm";
    case "md":
      return "text-sm sm:text-base"; // default size with responsive text
    case "lg":
      return "btn-lg text-base sm:text-lg";
    default:
      return "text-sm sm:text-base";
  }
}

function resolveShapeClasses(shape: ActionShape): string {
  if (shape === "square") {
    return "btn-square";
  }
  if (shape === "circle") {
    return "btn-circle";
  }
  return "";
}

function resolveIconSize(size: ActionSize, iconOnly: boolean): number {
  if (iconOnly) {
    switch (size) {
      case "xs":
        return 16;
      case "sm":
        return 18;
      case "md":
        return 20;
      case "lg":
        return 24;
      default:
        return 18;
    }
  }

  switch (size) {
    case "xs":
      return 14;
    case "sm":
      return 16;
    case "md":
      return 18;
    case "lg":
      return 20;
    default:
      return 16;
  }
}

const ActionButton = React.forwardRef<HTMLButtonElement, ActionButtonProps>(
  (
    {
      label,
      onClick,
      color = "neutral",
      size = "sm",
      variant = "ghost",
      title,
      disabled,
      className,
      icon,
      iconName,
      iconSize,
      type = "button",
      ariaLabel,
      ariaHasPopup,
      ariaExpanded,
      shape = "default",
      iconOnly,
      form,
    },
    ref,
  ) => {
    const hasIcon = Boolean(icon || iconName);
    const computedIconOnly = iconOnly ?? (!label && hasIcon);
    const computedShape =
      shape === "default" && computedIconOnly ? "square" : shape;

    const baseClasses = [
      resolveBtnClasses(color, variant),
      resolveSizeClasses(size),
      resolveShapeClasses(computedShape),
      disabled ? "opacity-60 cursor-not-allowed" : "",
      className || "",
    ]
      .filter(Boolean)
      .join(" ");

    // Keep click handling local and avoid extra global DOM lookups.
    const handleClick = useCallback(
      (e: React.MouseEvent<HTMLButtonElement>) => {
        // Prevent duplicate clicks.
        if (disabled) return;

        // Run the original click handler.
        if (onClick) {
          onClick(e);
        }

        // Clear DaisyUI active/focus state from the current button.
        const current = e.currentTarget;
        current.classList.remove("active");
        current.blur();
      },
      [onClick, disabled],
    );

    const combinedAriaLabel = ariaLabel || label || title;
    const tooltipContent = title?.trim();
    const finalIconSize = iconSize ?? resolveIconSize(size, computedIconOnly);
    const resolvedIcon =
      icon ??
      (iconName ? (
        <Icon name={iconName} size={finalIconSize} aria-hidden />
      ) : null);

    const buttonElement = (
      <button
        ref={ref}
        type={type}
        className={baseClasses}
        onClick={handleClick}
        disabled={disabled}
        aria-label={combinedAriaLabel}
        aria-haspopup={ariaHasPopup}
        aria-expanded={ariaExpanded}
        form={form}
      >
        <span
          className={`flex items-center whitespace-nowrap ${
            computedIconOnly ? "justify-center" : ""
          }`}
        >
          {resolvedIcon ? (
            <span
              className={`inline-flex items-center flex-shrink-0 ${
                computedIconOnly ? "" : "mr-1 sm:mr-2"
              }`}
            >
              {resolvedIcon}
            </span>
          ) : null}
          {!computedIconOnly && label ? (
            <span className="truncate">{label}</span>
          ) : null}
          {computedIconOnly && (label || combinedAriaLabel) ? (
            <span className="sr-only">{label || combinedAriaLabel}</span>
          ) : null}
        </span>
      </button>
    );

    if (!tooltipContent) {
      return buttonElement;
    }

    return (
      <InlineTooltipTrigger content={tooltipContent} className="">
        {buttonElement}
      </InlineTooltipTrigger>
    );
  },
);

const ActionButtonGroup: React.FC<ActionButtonGroupProps> = ({
  children,
  gap = "md",
  align = "end",
  splitOpposite = false,
  withTopBorder = false,
  className = "",
}) => {
  const gapClass =
    gap === "lg"
      ? "gap-2 sm:gap-3"
      : gap === "sm"
        ? "gap-1 sm:gap-1.5"
        : "gap-1.5 sm:gap-2";
  const justifyClass =
    align === "start"
      ? "justify-start"
      : align === "center"
        ? "justify-center"
        : "justify-end";

  if (splitOpposite) {
    const items = React.Children.toArray(children);
    const left = items[0] ?? null;
    const right = items.slice(1);
    return (
      <div
        className={`${withTopBorder ? "pt-3 sm:pt-4 border-t border-base-300" : ""} flex items-center justify-between px-2 sm:px-4 ${className}`}
      >
        <div className={`flex ${gapClass}`}>{left}</div>
        <div className={`flex ${gapClass}`}>{right}</div>
      </div>
    );
  }

  return (
    <div
      className={`${withTopBorder ? "pt-3 sm:pt-4 border-t border-base-300" : ""} flex ${justifyClass} ${gapClass} ${className}`}
    >
      {children}
    </div>
  );
};

function FormActions({
  loading = false,
  disabled = false,
  submitText,
  cancelText,
  submitIcon = <Icon name="check" size={16} />,
  cancelIcon = <Icon name="x-mark" size={16} />,
  submitColor = "primary",
  cancelColor = "neutral",
  size = "sm",
  onSubmit,
  onCancel,
  onDelete,
  deleteDisabled = false,
  showTopBorder = false,
  leftSlot,
  className = "",
}: FormActionsProps) {
  const { t } = useTranslation();
  // 渲染提交按钮图标
  const renderSubmitIcon = () => {
    if (loading) {
      return <span className="loading loading-spinner loading-xs"></span>;
    }
    return submitIcon;
  };

  return (
    <ActionButtonGroup
      splitOpposite
      withTopBorder={showTopBorder}
      className={className}
    >
      {/* Custom action, edit-mode delete, or the default create-mode cancel action. */}
      {leftSlot ?? (
        onDelete ? (
          <DeleteButton
            showLabel
            size={size}
            onClick={() => onDelete()}
            disabled={loading || deleteDisabled}
          />
        ) : (
          <ActionButton
            label={cancelText || t("common.cancel")}
            icon={cancelIcon}
            color={cancelColor}
            size={size}
            onClick={onCancel}
            disabled={loading || disabled}
            variant="ghost"
          />
        )
      )}

      {/* 提交按钮 */}
      <ActionButton
        label={submitText || t("common.submit")}
        icon={renderSubmitIcon()}
        color={submitColor}
        size={size}
        onClick={onSubmit}
        disabled={loading || disabled}
        type="submit"
        variant="solid"
      />
    </ActionButtonGroup>
  );
}

export { ActionButtonGroup, FormActions };
export default ActionButton;

export const EditButton: React.FC<
  Omit<ActionButtonProps, "label" | "icon" | "color"> & {
    onClick: (event: React.MouseEvent<HTMLButtonElement>) => void;
  }
> = ({
  onClick,
  size = "sm",
  disabled = false,
  className = "",
  ariaLabel,
  ...props
}) => {
  const { t } = useTranslation();

  return (
    <ActionButton
      label={t("common.edit")}
      iconName="edit"
      color="neutral"
      size={size}
      onClick={onClick}
      disabled={disabled}
      className={className}
      ariaLabel={ariaLabel || t("common.edit")}
      iconOnly
      {...props}
    />
  );
};

export const DeleteButton: React.FC<
  Omit<ActionButtonProps, "label" | "icon" | "color"> & {
    onClick: (event: React.MouseEvent<HTMLButtonElement>) => void;
    showLabel?: boolean;
  }
> = ({
  onClick,
  size = "sm",
  disabled = false,
  className = "",
  ariaLabel,
  showLabel = false,
  ...props
}) => {
  const { t } = useTranslation();

  return (
    <ActionButton
      label={t("common.delete")}
      iconName="trash"
      color="error"
      size={size}
      onClick={onClick}
      disabled={disabled}
      className={className}
      ariaLabel={ariaLabel || t("common.delete")}
      iconOnly={!showLabel}
      {...props}
    />
  );
};

interface CreateNewButtonProps {
  // 基础配置
  onClick: (event: React.MouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
  loading?: boolean;

  // 文本配置
  label?: string; // 默认使用 t("common.add")
  title?: string; // tooltip 文本
  showLabel?: boolean; // 默认 true

  // 图标配置
  icon?: React.ReactNode; // 默认使用 PlusIcon
  showIcon?: boolean; // 是否显示图标，默认 true

  // 样式配置
  color?: ActionColor; // 默认 "primary"
  size?: ActionSize; // 默认 "sm"
  variant?: ActionVariant; // 默认 "ghost"

  // 预设样式模式
  mode?: "subtle" | "prominent"; // 默认 "subtle"

  // 其他配置
  className?: string;
  ariaLabel?: string;
}

interface ExpandButtonProps {
  isExpanded: boolean;
  onClick: (event: React.MouseEvent<HTMLButtonElement>) => void;
  size?: ActionSize;
  disabled?: boolean;
  title?: string;
  className?: string;
  ariaLabel?: string;
  expandedLabel?: string;
  collapsedLabel?: string;
}

export const CreateNewButton: React.FC<CreateNewButtonProps> = ({
  onClick,
  disabled = false,
  loading = false,
  label,
  icon,
  showIcon = true,
  color,
  size = "sm",
  variant,
  mode = "prominent",
  className = "",
  ariaLabel,
  showLabel = true,
  ...props
}) => {
  const { t } = useTranslation();

  // 根据模式确定样式配置
  const getStyleConfig = () => {
    if (mode === "prominent") {
      return {
        color: color || "primary",
        variant: variant || "solid",
      };
    } else {
      // subtle 模式
      return {
        color: color || "primary",
        variant: variant || "ghost",
      };
    }
  };

  const styleConfig = getStyleConfig();

  // 渲染图标
  const renderIcon = () => {
    if (loading) {
      return <span className="loading loading-spinner loading-xs"></span>;
    }
    if (showIcon) {
      const defaultIconSize = resolveIconSize(size, false);
      return icon || <Icon name="plus" size={defaultIconSize} aria-hidden />;
    }
    return null;
  };

  // 确定按钮文本
  const resolvedLabel = label ?? t("common.add");
  const buttonLabel = showLabel ? resolvedLabel : "";

  // 确定 aria-label
  const buttonAriaLabel = ariaLabel || resolvedLabel || t("common.add");

  return (
    <ActionButton
      label={buttonLabel}
      icon={renderIcon()}
      color={styleConfig.color}
      size={size}
      variant={styleConfig.variant}
      onClick={onClick}
      disabled={disabled || loading}
      className={className}
      ariaLabel={buttonAriaLabel}
      {...props}
    />
  );
};

export const ExpandButton: React.FC<ExpandButtonProps> = ({
  isExpanded,
  onClick,
  disabled = false,
  title,
  className = "",
  ariaLabel,
  expandedLabel,
  collapsedLabel,
}) => {
  const { t } = useTranslation();
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    onClick(e);
  };

  const buttonTitle =
    title ||
    (isExpanded
      ? expandedLabel || t("common.collapse")
      : collapsedLabel || t("common.expand"));
  const buttonAriaLabel =
    ariaLabel || (isExpanded ? t("common.expand") : t("common.collapse"));

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      className={`p-1 rounded hover-button transition-colors touch-target disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
      title={buttonTitle}
      aria-label={buttonAriaLabel}
    >
      <svg
        className={`w-4 h-4 text-base-content transition-transform ${
          isExpanded ? "rotate-90" : ""
        }`}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 5l7 7-7 7"
        />
      </svg>
    </button>
  );
};
