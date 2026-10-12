import { cn } from "@/lib/cn";

export function Badge({
  children,
  tone = "default",
}: {
  children: React.ReactNode;
  tone?: "default" | "success" | "warning" | "danger" | "info";
}) {
  const toneClasses = {
    default: "bg-[var(--studio-surface-subtle)] text-[var(--studio-foreground)]",
    success: "bg-[var(--studio-success-soft)] text-[var(--studio-success)]",
    warning: "bg-[var(--studio-warning-soft)] text-[var(--studio-warning)]",
    danger: "bg-[var(--studio-danger-soft)] text-[var(--studio-danger)]",
    info: "bg-[var(--studio-info-soft)] text-[var(--studio-info)]",
  }[tone];
  return (
    <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-medium", toneClasses)}>
      {children}
    </span>
  );
}
