import React, { forwardRef } from "react";

type TextAreaResize = "none" | "both" | "horizontal" | "vertical" | "y";

type TextAreaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  /** DaisyUI control size. */
  size?: "sm" | "md" | "lg";
  /** CSS resize behavior. */
  resize?: TextAreaResize;
};

/**
 * Standard DaisyUI textarea.
 */
const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(
  (
    { className = "", size = "md", resize = "none", rows = 3, ...rest },
    ref,
  ) => {
    const sizeClasses = {
      sm: "textarea-sm min-h-16 text-sm",
      md: "textarea-md min-h-24 text-sm",
      lg: "textarea-lg min-h-32 text-base",
    } as const;

    const resizeClasses: Record<TextAreaResize, string> = {
      none: "resize-none",
      both: "resize",
      horizontal: "resize-x",
      vertical: "resize-y",
      y: "resize-y",
    };

    const baseClasses = `textarea textarea-bordered w-full ${sizeClasses[size]} ${resizeClasses[resize]}`;
    const finalClasses = `${baseClasses} ${className}`.trim();

    return (
      <textarea ref={ref} rows={rows} className={finalClasses} {...rest} />
    );
  },
);

TextArea.displayName = "TextArea";
export default TextArea;
