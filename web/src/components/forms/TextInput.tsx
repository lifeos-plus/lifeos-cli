import React, { forwardRef } from "react";

type TextInputProps = Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  "size"
> & {
  /** DaisyUI control size. */
  size?: "sm" | "md" | "lg";
};

/**
 * Standard DaisyUI text input.
 */
const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  ({ className = "", size = "md", type = "text", ...rest }, ref) => {
    const sizeClasses = {
      sm: "input-sm text-sm",
      md: "input-md text-sm",
      lg: "input-lg text-base",
    } as const;

    const baseClasses = `input input-bordered w-full ${sizeClasses[size]}`;
    const finalClasses = `${baseClasses} ${className}`.trim();

    return <input ref={ref} type={type} className={finalClasses} {...rest} />;
  },
);

TextInput.displayName = "TextInput";
export default TextInput;
