import { cn } from "@/lib/cn";

export function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface)] p-5 shadow-[var(--shadow-md)]",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function CardHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="mb-4 flex flex-col gap-3 border-b border-[var(--studio-border)] pb-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold text-[var(--studio-foreground)]">{title}</h2>
        {description ? <p className="text-sm text-[var(--studio-muted)]">{description}</p> : null}
      </div>
      {action}
    </header>
  );
}
