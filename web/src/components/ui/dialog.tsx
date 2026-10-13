"use client";

import { useEffect, useId, useRef } from "react";

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
  className,
  contentClassName,
  titleClassName,
  initialFocusRef,
  restoreFocusRef,
}: {
  open: boolean;
  title: string;
  description?: string;
  children: React.ReactNode;
  onClose: () => void;
  closeLabel?: string;
  hideDefaultClose?: boolean;
  className?: string;
  contentClassName?: string;
  titleClassName?: string;
  initialFocusRef?: React.RefObject<HTMLElement | null>;
  restoreFocusRef?: React.RefObject<HTMLElement | null>;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const previousOpenRef = useRef(open);
  const lastActiveElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }
    if (open && !element.open) {
      lastActiveElementRef.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null;
      element.showModal();
    }
    if (!open && element.open) {
      element.close();
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    const previousOpen = previousOpenRef.current;
    previousOpenRef.current = open;

    if (open && !previousOpen) {
      const frame = window.requestAnimationFrame(() => {
        (initialFocusRef?.current ?? ref.current)?.focus();
      });

      return () => {
        window.cancelAnimationFrame(frame);
      };
    }

    if (!open && previousOpen) {
      const frame = window.requestAnimationFrame(() => {
        (restoreFocusRef?.current ?? lastActiveElementRef.current)?.focus();
      });

      return () => {
        window.cancelAnimationFrame(frame);
      };
    }
  }, [initialFocusRef, open, restoreFocusRef]);

  return (
    <dialog
      ref={ref}
      aria-describedby={description ? descriptionId : undefined}
      aria-labelledby={titleId}
      aria-modal="true"
      className={cn(
        "w-full max-w-xl rounded-2xl border border-[var(--studio-border)] bg-[var(--studio-surface)] p-0 text-[var(--studio-foreground)] shadow-[var(--shadow-lg)] backdrop:bg-[rgb(16_42_67_/_0.45)]",
        className,
      )}
      tabIndex={-1}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
    >
      <div className={cn("space-y-4 p-6", contentClassName)}>
        <div className="space-y-1">
          <h2 id={titleId} className={cn("text-lg font-semibold", titleClassName)}>
            {title}
          </h2>
          {description ? (
            <p id={descriptionId} className="text-sm text-[var(--studio-muted)]">
              {description}
            </p>
          ) : null}
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
