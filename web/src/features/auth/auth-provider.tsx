"use client";

import { ModeAuthProvider } from "@/features/auth/provider-impl";
import { getPublicRuntimeConfig } from "@/features/auth/runtime";

const runtimeConfig = getPublicRuntimeConfig(process.env);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return <ModeAuthProvider config={runtimeConfig}>{children}</ModeAuthProvider>;
}
