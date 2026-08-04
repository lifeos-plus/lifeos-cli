import React, { useEffect, useId, useRef, useState } from "react";
import Container from "./Container";
import { useEscapeToClose } from "@/hooks/useEscapeToClose";
import { createPortal } from "react-dom";
import { useModalStack } from "@/contexts/ModalStackContext";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { useTranslation } from "react-i18next";
import ActionButton from "@/components/ActionButton";
import ErrorDisplay from "@/components/ErrorDisplay";

// 尺寸配置常量
const SIZE_CONFIG = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
  "2xl": "max-w-6xl",
} as const;

// 响应式样式计算工具函数
const getResponsiveClasses = (size: keyof typeof SIZE_CONFIG) => {
  const baseSize = SIZE_CONFIG[size];
  // 使用DaisyUI标准的高度类，提供更好的响应式支持
  // 移动端使用更保守的高度限制，确保标题和footer可见
  const minHeight =
    size === "sm" ? "min-h-48" : size === "2xl" ? "min-h-[28rem]" : "min-h-80";
  const maxHeight =
    size === "2xl"
      ? "max-h-screen lg:max-h-[90vh]"
      : "max-h-screen lg:max-h-[80vh]";
  return `${baseSize} w-full ${minHeight} ${maxHeight} mx-2 sm:mx-0`;
};

// 模态框内容组件
interface ModalContentProps {
  children: React.ReactNode;
  error?: string | null;
  onErrorDismiss?: () => void;
  errorDisplayMode?: "inline" | "toast" | "none";
  loading?: boolean;
  showLoadingOverlay?: boolean;
  loadingOverlayText?: string;
  showLoadingSpinner?: boolean;
  loadingSpinnerSize?: "sm" | "md" | "lg";
  overflow?: "visible" | "auto" | "hidden" | "scroll";
  className?: string;
}

const ModalContent: React.FC<ModalContentProps> = ({
  children,
  error,
  onErrorDismiss,
  errorDisplayMode = "inline",
  loading = false,
  showLoadingOverlay = false,
  loadingOverlayText = "加载中...",
  showLoadingSpinner = false,
  loadingSpinnerSize = "md",
  overflow = "auto",
  className = "",
}) => {
  const { t } = useTranslation();
  const dismissLabel = t("common.close");

  return (
    <Container
      className={`flex-1 min-h-0 bg-transparent border-0 shadow-none rounded-none ${
        overflow === "auto" || overflow === "scroll"
          ? "scrollbar-gutter-stable-both overscroll-contain"
          : ""
      } ${className}`.trim()}
      overflow={overflow}
      maxHeight="none"
      padding="none"
      minWidth={false}
      maxWidth={false}
      flex="1"
      minHeight="0"
    >
      {/* 错误提示 - 内联模式 */}
      {error && errorDisplayMode === "inline" && (
        <ErrorDisplay
          error={error}
          className="mb-3"
          action={
            onErrorDismiss ? (
              <ActionButton
                onClick={onErrorDismiss}
                label={dismissLabel}
                iconName="x-mark"
                size="xs"
                variant="ghost"
                shape="circle"
                iconOnly
                ariaLabel={dismissLabel}
              />
            ) : null
          }
        />
      )}

      {/* 加载遮罩 */}
      {showLoadingOverlay && loading && (
        <div className="absolute inset-0 bg-base-100/80 flex items-center justify-center z-loading-overlay rounded-lg">
          <div className="flex flex-col items-center gap-2">
            <span className="loading loading-spinner loading-md text-primary"></span>
            <p className="text-sm">{loadingOverlayText}</p>
          </div>
        </div>
      )}

      {/* 加载指示器 */}
      {showLoadingSpinner && loading && (
        <div className="flex justify-center items-center py-3">
          <span
            className={`loading loading-spinner ${
              loadingSpinnerSize === "sm"
                ? "loading-xs"
                : loadingSpinnerSize === "lg"
                  ? "loading-lg"
                  : "loading-md"
            } text-primary`}
          ></span>
        </div>
      )}

      {children}
    </Container>
  );
};

interface ModalBaseProps {
  isOpen: boolean;
  onClose: () => void;
  closeDisabled?: boolean;
  children: React.ReactNode;
  /** class applied to the dialog container */
  className?: string;
  /** class applied to the overlay */
  overlayClassName?: string;
  /** optional preset size for container width */
  size?: "sm" | "md" | "lg" | "xl" | "2xl";
  role?: "dialog" | "alertdialog";
  ariaLabel?: string;
  ariaLabelledBy?: string;
  /** an optional title to be displayed in the modal header */
  title?: React.ReactNode;
  /** optional header node; if provided, it overrides title rendering */
  header?: React.ReactNode;
  /** optional footer node; if provided, ModalBase renders a unified footer */
  footer?: React.ReactNode;
  /** whether clicking overlay closes the modal (default: false) */
  overlayClosable?: boolean;

  // 新增：状态管理相关props
  /** 加载状态 */
  loading?: boolean;
  /** 错误信息 */
  error?: string | null;
  /** 错误信息关闭回调 */
  onErrorDismiss?: () => void;
  /** 是否显示加载遮罩 */
  showLoadingOverlay?: boolean;
  /** 加载遮罩文本 */
  loadingOverlayText?: string;
  /** 错误显示模式 */
  errorDisplayMode?: "inline" | "toast" | "none";

  // 新增：加载指示器相关props
  /** 是否显示加载指示器 */
  showLoadingSpinner?: boolean;
  /** 加载指示器大小 */
  loadingSpinnerSize?: "sm" | "md" | "lg";

  // 新增：关闭按钮相关props
  /** 是否显示内置关闭按钮 */
  showCloseButton?: boolean;
  /** Modal 主体滚动策略 */
  bodyOverflow?: "visible" | "auto" | "hidden" | "scroll";
  /** Modal 主体额外类名 */
  bodyClassName?: string;
  /** Render above an existing modal while preserving the shared modal shell. */
  nested?: boolean;
}

/**
 * ModalBase
 *
 * A11y-friendly base modal with ESC-to-close, overlay click to close,
 * body scroll locking, and built-in state management for loading and error states.
 * Use this as a wrapper for all modals.
 */
const ModalBase: React.FC<ModalBaseProps> = ({
  isOpen,
  onClose,
  closeDisabled = false,
  children,
  className,
  overlayClassName,
  size = "lg",
  role = "dialog",
  ariaLabel,
  ariaLabelledBy,
  title,
  header,
  footer,
  overlayClosable = false,

  // 新增状态管理props
  loading = false,
  error = null,
  onErrorDismiss,
  showLoadingOverlay = false,
  loadingOverlayText = "加载中...",
  errorDisplayMode = "inline",

  // 新增加载指示器props
  showLoadingSpinner = false,
  loadingSpinnerSize = "md",

  // 新增关闭按钮props
  showCloseButton = true,
  bodyOverflow = "auto",
  bodyClassName,
  nested = false,
}) => {
  const previouslyFocusedElementRef = useRef<HTMLElement | null>(null);
  const modalId = useId();
  const titleId = useId();
  const { register, unregister, isTop } = useModalStack();
  const [isVisible, setIsVisible] = useState(false);

  // Focus trap on container (must be declared before any conditional return)
  const containerRef = useRef<HTMLDivElement>(null);
  useFocusTrap(isOpen, containerRef);

  // ESC support: only top-most modal responds
  useEscapeToClose(
    isOpen,
    () => {
      if (!closeDisabled && isTop(modalId)) onClose();
    },
    { disabled: closeDisabled, useCapture: false },
  );

  // Handle visibility state for smooth animations
  useEffect(() => {
    if (isOpen) {
      setIsVisible(true);
    } else {
      const timer = setTimeout(() => setIsVisible(false), 200);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Register into modal stack and handle focus restore
  useEffect(() => {
    if (!isOpen) return;
    previouslyFocusedElementRef.current = document.activeElement as HTMLElement;
    register(modalId);
    return () => {
      unregister(modalId);
      previouslyFocusedElementRef.current?.focus?.();
    };
  }, [isOpen, modalId, register, unregister]);

  if (!isOpen && !isVisible) return null;

  const overlayCls =
    `fixed inset-0 bg-base-content/50 flex items-center justify-center ${
      nested ? "z-modal-nested" : "z-modal-overlay"
    } p-1 sm:p-2 md:p-4 transition-opacity duration-200 ${
      isVisible ? "opacity-100" : "opacity-0"
    } ${overlayClassName || ""}`.trim();

  const wrapperCls = "flex items-center justify-center w-full h-full";

  // 使用工具函数计算响应式样式
  const responsiveClasses = getResponsiveClasses(size);
  const containerCls =
    `bg-base-100 rounded-lg shadow ${responsiveClasses} flex flex-col border border-base-300 transition-opacity duration-200 ${
      isVisible ? "opacity-100" : "opacity-0"
    } ${className || ""}`.trim();

  const handleOverlayClick: React.MouseEventHandler<HTMLDivElement> = (
    _event,
  ) => {
    if (!overlayClosable || closeDisabled) return;
    onClose();
  };

  const stopPropagation: React.MouseEventHandler<HTMLDivElement> = (event) => {
    event.stopPropagation();
  };

  const tree = (
    <div
      className={overlayCls}
      onClick={handleOverlayClick}
      aria-hidden={false}
    >
      <div
        className={wrapperCls}
        role={role}
        aria-modal={true}
        aria-label={ariaLabel}
        aria-labelledby={header || title ? titleId : ariaLabelledBy}
        data-modal-id={modalId}
      >
        <div
          ref={containerRef}
          className={containerCls}
          onClick={stopPropagation}
          style={{ position: "relative" }}
        >
          {/* 内置关闭按钮 - 右上角 */}
          {showCloseButton && (
            <ActionButton
              label={ariaLabel || "关闭"}
              iconName="x-mark"
              onClick={onClose}
              disabled={closeDisabled}
              size="md"
              variant="ghost"
              className="absolute top-4 right-4 z-button -m-2"
              iconOnly
            />
          )}
          {/* Content wrapper: unified paddings and gaps for header/body/footer */}
          <div className="flex flex-col gap-y-2 sm:gap-y-3 px-3 py-3 sm:px-5 sm:py-4 md:px-6 md:py-5 h-full min-h-0">
            {/* Header - unified style */}
            {(header || title) && (
              <div className="flex-shrink-0 pl-2">
                <h2
                  id={titleId}
                  className="text-xl font-semibold text-base-content"
                >
                  {header || title}
                </h2>
              </div>
            )}

            {/* Body with scrolling (unified) - 使用新的内容组件 */}
            <ModalContent
              error={error}
              onErrorDismiss={onErrorDismiss}
              errorDisplayMode={errorDisplayMode}
              loading={loading}
              showLoadingOverlay={showLoadingOverlay}
              loadingOverlayText={loadingOverlayText}
              showLoadingSpinner={showLoadingSpinner}
              loadingSpinnerSize={loadingSpinnerSize}
              overflow={bodyOverflow}
              className={bodyClassName}
            >
              <div className="p-2">{children}</div>
            </ModalContent>

            {/* Footer - unified style */}
            {footer && <div className="flex-shrink-0">{footer}</div>}
          </div>
        </div>
      </div>
    </div>
  );

  // Render via portal to body for better layering
  return createPortal(tree, document.body);
};

export default ModalBase;
