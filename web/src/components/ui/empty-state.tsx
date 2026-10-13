import { Button } from "@/components/ui/button";

export function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] p-6 text-center">
      <h3 className="text-base font-semibold text-[var(--studio-foreground)]">{title}</h3>
      <p className="mt-2 text-sm text-[var(--studio-muted)]">{description}</p>
      {actionLabel && onAction ? (
        <div className="mt-4">
          <Button variant="secondary" onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
