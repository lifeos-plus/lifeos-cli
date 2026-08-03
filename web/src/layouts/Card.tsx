import React from "react";
import ActionButton from "@/components/ActionButton";
import { ActionButtonGroup } from "@/components/ActionButton";
import ErrorDisplay from "@/components/ErrorDisplay";
import Container from "./Container";

const getCardStyles = (size: string, className: string) => {
  const titleSizeClass =
    {
      sm: "text-base",
      md: "text-base",
      lg: "text-lg",
    }[size] || "text-base";

  const buttonSize = ({
    sm: "sm",
    md: "md",
    lg: "lg",
  }[size] || "md") as "sm" | "md" | "lg";

  const containerClasses = [
    "flex flex-col",
    !className.includes("h-auto") ? "h-full" : "",
    !className.includes("mb-0") ? "mb-6" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return { titleSizeClass, buttonSize, containerClasses };
};

// 内容区域组件
interface ContentAreaProps {
  children: React.ReactNode;
  loading: boolean;
  disabled: boolean;
  error?: string | null;
  overflowClassName: string;
  contentClassName?: string;
}

const ContentArea: React.FC<ContentAreaProps> = ({
  children,
  loading,
  disabled,
  error,
  overflowClassName,
  contentClassName = "",
}) => (
  <div
    className={`min-h-0 min-w-0 flex-1 ${overflowClassName} ${contentClassName}`.trim()}
  >
    <ErrorDisplay error={error ?? null} className="mb-4" />
    <div
      className={`${loading || disabled ? "opacity-60 pointer-events-none" : ""}`}
    >
      {children}
    </div>
  </div>
);

export interface CardAction {
  label: string;
  onClick?: () => void;
  color?: "primary" | "neutral" | "success" | "warning" | "error";
  variant?: "solid" | "outline" | "ghost";
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  icon?: React.ReactNode;
}

interface CardProps {
  /** 卡片标题（可为空；可为字符串或 React 元素；为空时不显示 Header 区域） */
  title?: string | React.ReactNode;
  /** 卡片描述文本 */
  description?: string;
  /** Header 右侧的功能按钮 */
  headerAction?: React.ReactNode;
  /** Footer 操作按钮列表 */
  footerActions?: CardAction[];
  /** 错误信息，显示在内容区域顶部 */
  error?: string | null;
  /** 加载状态，禁用所有交互 */
  loading?: boolean;
  /** 禁用状态 */
  disabled?: boolean;
  /** 额外的 CSS 类名 */
  className?: string;
  /** 卡片内容 */
  children: React.ReactNode;
  /** 是否显示顶部边框（用于分隔） */
  withTopBorder?: boolean;
  /** 卡片尺寸变体 */
  size?: "sm" | "md" | "lg";
  /**
   * 质感等级 - 渐进式质感增强系统
   * - subtle: 基础质感，轻微增强（适用于密集布局）
   * - moderate: 中等质感，标准卡片（默认）
   * - elevated: 高级质感，焦点卡片（重要内容、悬浮状态）
   */
  elevation?: "subtle" | "moderate" | "elevated";
  /** 内容区域溢出策略（默认可见） */
  contentOverflow?: "visible" | "auto" | "hidden" | "scroll";
  /** 追加到内容区域容器的类名 */
  contentClassName?: string;
}

const Card: React.FC<CardProps> = ({
  title,
  description,
  headerAction,
  footerActions = [],
  error,
  loading = false,
  disabled = false,
  className: _className = "",
  children,
  withTopBorder: _withTopBorder = false,
  size = "md",
  elevation: _elevation = "moderate",
  contentOverflow = "visible",
  contentClassName,
}) => {
  // 使用工具函数计算样式
  const { titleSizeClass, buttonSize, containerClasses } = getCardStyles(
    size,
    _className,
  );

  const resolveContentOverflow = () => {
    switch (contentOverflow) {
      case "auto":
        return "overflow-y-auto overflow-x-hidden scrollbar-gutter-stable-both";
      case "scroll":
        return "overflow-y-scroll overflow-x-hidden scrollbar-gutter-stable-both";
      case "hidden":
        return "overflow-hidden";
      default:
        return "overflow-visible";
    }
  };

  return (
    <Container
      className={containerClasses}
      overflow="hidden"
      shadow={
        _elevation === "subtle"
          ? "sm"
          : _elevation === "elevated"
            ? "lg"
            : "md"
      }
      borderVariant="default"
    >
      {/* Header */}
      {title ? (
        <div className="flex items-center justify-between mb-4">
          <div className="flex-1 min-w-0">
            {typeof title === "string" ? (
              <h3 className={`card-title ${titleSizeClass}`}>{title}</h3>
            ) : (
              <div className={`card-title ${titleSizeClass}`}>{title}</div>
            )}
            {description && <p className="text-sm mt-1">{description}</p>}
          </div>
          {headerAction && (
            <div className="flex-shrink-0 ml-4">{headerAction}</div>
          )}
        </div>
      ) : null}

      {/* Content - 使用新的内容区域组件 */}
      <ContentArea
        loading={loading}
        disabled={disabled}
        error={error}
        overflowClassName={resolveContentOverflow()}
        contentClassName={`${_withTopBorder ? "border-t border-base-300 pt-4" : ""} ${
          contentClassName || ""
        }`.trim()}
      >
        {children}
      </ContentArea>

      {/* Footer */}
      {footerActions.length > 0 && (
        <div className="mt-4">
          {footerActions.length === 1 ? (
            <div className="card-actions justify-end">
              <ActionButton
                {...footerActions[0]}
                size={buttonSize}
                disabled={loading || disabled || footerActions[0].disabled}
              />
            </div>
          ) : (
            <ActionButtonGroup align="end" gap="md" className="justify-end">
              {footerActions.map((action, index) => (
                <ActionButton
                  key={index}
                  {...action}
                  size={buttonSize}
                  disabled={loading || disabled || action.disabled}
                />
              ))}
            </ActionButtonGroup>
          )}
        </div>
      )}
    </Container>
  );
};

export default Card;
