import { forwardRef, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "min-h-28 w-full rounded-lg border border-[var(--studio-border)] bg-[var(--studio-surface)] px-3 py-2 text-sm text-[var(--studio-foreground)] outline-none placeholder:text-[var(--studio-muted)] focus:border-[var(--studio-focus)] focus-visible:ring-2 focus-visible:ring-[var(--studio-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--studio-surface)] disabled:cursor-not-allowed disabled:bg-[var(--studio-surface-subtle)] disabled:text-[var(--studio-muted)]",
      className,
    )}
    {...props}
  />
));

Textarea.displayName = "Textarea";
