import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
};

const variants: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "bg-[var(--studio-brand)] text-white shadow-[var(--shadow-sm)] hover:bg-[var(--studio-brand-hover)] focus-visible:ring-2 focus-visible:ring-[var(--studio-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--studio-surface)]",
  secondary:
    "bg-[var(--studio-surface-subtle)] text-[var(--studio-foreground)] hover:bg-[var(--studio-background)] focus-visible:ring-2 focus-visible:ring-[var(--studio-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--studio-surface)]",
  ghost:
    "bg-transparent text-[var(--studio-foreground)] hover:bg-[var(--studio-surface-subtle)] focus-visible:ring-2 focus-visible:ring-[var(--studio-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--studio-surface)]",
  danger:
    "bg-[var(--studio-danger)] text-white hover:opacity-95 focus-visible:ring-2 focus-visible:ring-[var(--studio-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--studio-surface)]",
};

export function Button({ className, type = "button", variant = "primary", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex min-h-[44px] items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold outline-none transition disabled:cursor-not-allowed disabled:border-[var(--studio-border)] disabled:bg-[var(--studio-surface-subtle)] disabled:text-[var(--studio-muted)]",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
