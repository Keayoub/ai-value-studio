import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "min-h-[44px] w-full rounded-lg border border-[var(--studio-border)] bg-[var(--studio-surface)] px-3 py-2 text-sm text-[var(--studio-foreground)] outline-none focus:border-[var(--studio-focus)] focus-visible:ring-2 focus-visible:ring-[var(--studio-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--studio-surface)] disabled:cursor-not-allowed disabled:bg-[var(--studio-surface-subtle)] disabled:text-[var(--studio-muted)]",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
);

Select.displayName = "Select";
