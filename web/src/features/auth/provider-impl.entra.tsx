"use client";

import { EntraAuthProvider } from "@/features/auth/entra-provider";
import type { PublicRuntimeConfig } from "@/features/auth/runtime";

export function ModeAuthProvider({
  config,
  children,
}: {
  config: PublicRuntimeConfig;
  children: React.ReactNode;
}) {
  return <EntraAuthProvider config={config}>{children}</EntraAuthProvider>;
}
