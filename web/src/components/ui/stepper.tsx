import { cn } from "@/lib/cn";

export function Stepper({
  steps,
  activeStep,
}: {
  steps: Array<{ id: string; label: string }>;
  activeStep: string;
}) {
  return (
    <nav aria-label="Parcours studio">
      <ol className="flex flex-wrap gap-3">
        {steps.map((step, index) => {
          const isActive = step.id === activeStep;
          return (
            <li
              key={step.id}
              aria-current={isActive ? "step" : undefined}
              className={cn(
                "flex items-center gap-2 rounded-full px-3 py-2 text-sm",
                isActive
                  ? "bg-[var(--studio-brand)] text-white"
                  : "bg-[var(--studio-surface-subtle)] text-[var(--studio-muted)]",
              )}
            >
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-black/10 text-xs font-semibold">
                {index + 1}
              </span>
              <span>{step.label}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
