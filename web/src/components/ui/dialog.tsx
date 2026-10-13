"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export function Dialog({
  open,
  title,
  description,
  children,
  onClose,
  closeLabel = "Fermer",
  hideDefaultClose = false,
}: {
  open: boolean;
  title: string;
  description?: string;
  children: React.ReactNode;
  onClose: () => void;
  closeLabel?: string;
  hideDefaultClose?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }
    if (open && !element.open) {
      element.showModal();
    }
    if (!open && element.open) {
      element.close();
    }
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={cn(
        "w-full max-w-xl rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface)] p-0 text-[var(--studio-foreground)] shadow-[var(--shadow-lg)] backdrop:bg-[rgb(16_42_67_/_0.45)]",
      )}
      onClose={onClose}
    >
      <div className="space-y-4 p-6">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">{title}</h2>
          {description ? <p className="text-sm text-[var(--studio-muted)]">{description}</p> : null}
        </div>
        {children}
        {hideDefaultClose ? null : (
          <div className="flex justify-end">
            <Button variant="secondary" onClick={onClose}>
              {closeLabel}
            </Button>
          </div>
        )}
      </div>
    </dialog>
  );
}
