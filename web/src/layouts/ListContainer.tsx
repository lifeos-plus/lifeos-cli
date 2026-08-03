import React from "react";
import Container from "./Container";

interface ListContainerProps {
  /** 列表标题 */
  title: string;
  /** 是否隐藏头部（在外层已有标题/工具栏时使用） */
  hideHeader?: boolean;
  /** 标题右侧的操作按钮 */
  headerAction?: React.ReactNode;
  /** 列表内容 */
  children: React.ReactNode;
  /** 空状态时的内容 */
  emptyState?: React.ReactNode;
  /** 是否显示边框 */
  bordered?: boolean;
  /** 容器尺寸 */
  size?: "sm" | "md" | "lg";
  /** 额外的 CSS 类名 */
  className?: string;
  /** Extra class names for the content region. */
  contentClassName?: string;
  /** 是否显示顶部边框（用于分隔） */
  withTopBorder?: boolean;
  /** 是否显示阴影 */
  shadow?: boolean | "none" | "sm" | "md" | "lg";
  /** 边框风格：none 取消；subtle 弱化；default 默认 */
  borderVariant?: "none" | "subtle" | "default";
  /** 列标题配置（用于表格布局） */
  columns?: Array<{
    key: string;
    label: string;
    width?: string;
    align?: "left" | "center" | "right";
  }>;
}

const ListContainer: React.FC<ListContainerProps> = ({
  title,
  hideHeader,
  headerAction,
  children,
  emptyState,
  size = "md",
  className = "",
  contentClassName = "",
  withTopBorder = false,
  shadow = true,
  borderVariant = "default",
  columns,
}) => {
  // 构建容器的基础类名 - 使用统一的卡片设计规范
  const containerClasses = [
    withTopBorder ? "border-t-2 border-t-primary" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const resolvedShadow =
    typeof shadow === "string" ? shadow : shadow === false ? "none" : "md";

  // 标题尺寸
  const titleSizeClass =
    size === "sm" ? "text-base" : size === "lg" ? "text-lg" : "text-base";
  const contentClasses = `min-w-0 flex-1 text-sm ${contentClassName || "overflow-auto"}`;

  // 获取列对齐样式
  const getColumnAlignClass = (align?: "left" | "center" | "right") => {
    switch (align) {
      case "center":
        return "text-center";
      case "right":
        return "text-right";
      default:
        return "text-left";
    }
  };

  return (
    <Container
      className={containerClasses}
      borderVariant={borderVariant}
      shadow={resolvedShadow}
      overflow="hidden"
    >
      {/* Header */}
      {!hideHeader && (
        <div className="px-6 py-4 border-b border-base-300">
          <div className="flex min-w-0 flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2
              className={`${titleSizeClass} min-w-0 break-words font-medium text-base-content`}
            >
              {title}
            </h2>
            {headerAction && (
              <div className="min-w-0 flex-shrink-0 sm:ml-4">
                {headerAction}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Column Headers */}
      {columns && columns.length > 0 && (
        <div className="px-6 py-3 bg-primary/10 border-b border-primary/20">
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: columns
                .map((col) => col.width || "1fr")
                .join(" "),
            }}
          >
            {columns.map((column) => (
              <div
                key={column.key}
                className={`text-sm font-medium text-base-content/70 ${getColumnAlignClass(column.align)}`}
              >
                {column.label}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Content */}
      <div className={contentClasses}>{children || emptyState}</div>
    </Container>
  );
};

export default ListContainer;
