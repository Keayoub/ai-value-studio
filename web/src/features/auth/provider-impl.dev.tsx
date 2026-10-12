"use client";

import { DevAuthProvider } from "@/features/auth/dev-provider";
import type { PublicRuntimeConfig } from "@/features/auth/runtime";

export function ModeAuthProvider({
  config,
  children,
}: {
  config: PublicRuntimeConfig;
  children: React.ReactNode;
}) {
  return <DevAuthProvider config={config}>{children}</DevAuthProvider>;
}
