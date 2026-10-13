import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "min-h-10 w-full rounded-xl border border-[var(--studio-border)] bg-[var(--studio-surface)] px-3 py-2 text-sm text-[var(--studio-foreground)] outline-none ring-0 placeholder:text-[var(--studio-muted)] focus:border-[var(--studio-focus)] focus-visible:ring-2 focus-visible:ring-[var(--studio-focus)]",
        className,
      )}
      {...props}
    />
  ),
);

Input.displayName = "Input";
