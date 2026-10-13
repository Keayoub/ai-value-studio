"use client";

import { DesktopAuthProvider } from "@/features/auth/desktop-provider";
import { EntraAuthProvider } from "@/features/auth/entra-provider";
import { isDesktopRuntime, type PublicRuntimeConfig } from "@/features/auth/runtime";

export function ModeAuthProvider({
  config,
  children,
}: {
  config: PublicRuntimeConfig;
  children: React.ReactNode;
}) {
  if (isDesktopRuntime()) {
    return <DesktopAuthProvider config={config}>{children}</DesktopAuthProvider>;
  }

  return <EntraAuthProvider config={config}>{children}</EntraAuthProvider>;
}
