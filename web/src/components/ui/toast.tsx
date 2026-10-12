"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { cn } from "@/lib/cn";

type ToastTone = "success" | "error";
type ToastItem = { id: number; title: string; detail?: string; tone: ToastTone };

const ToastContext = createContext<{
  push: (toast: Omit<ToastItem, "id">) => void;
} | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((toast: Omit<ToastItem, "id">) => {
    const item = { ...toast, id: Date.now() + Math.random() };
    setItems((current) => [...current, item]);
    window.setTimeout(() => {
      setItems((current) => current.filter((entry) => entry.id !== item.id));
    }, 4000);
  }, []);

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed top-4 z-50 flex w-full max-w-sm flex-col gap-3"
        style={{ insetInlineEnd: "1rem" }}
      >
        {items.map((item) => (
          <div
            key={item.id}
            className={cn(
              "rounded-2xl border px-4 py-3 shadow-[var(--shadow-lg)]",
              item.tone === "success"
                ? "border-[var(--studio-success)]/20 bg-[var(--studio-success-soft)] text-[var(--studio-success)]"
                : "border-[var(--studio-danger)]/20 bg-[var(--studio-danger-soft)] text-[var(--studio-danger)]",
            )}
          >
            <p className="text-sm font-semibold">{item.title}</p>
            {item.detail ? <p className="mt-1 text-sm">{item.detail}</p> : null}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const value = useContext(ToastContext);
  if (!value) {
    throw new Error("useToast must be used within ToastProvider.");
  }
  return value;
}
