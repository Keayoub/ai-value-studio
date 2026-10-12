"use client";

import { createContext, useContext } from "react";

import type { MeResponse } from "@/features/api/types";

export type AuthState = {
  status: "loading" | "authenticated" | "unauthenticated";
  mode: "dev" | "entra";
  me: MeResponse | null;
  displayName: string | null;
  roleLabel: string | null;
  error: string | null;
  ready: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  selectDevIdentity: (payload: {
    subjectId: string;
    displayName: string;
    role: "Consultant" | "Sponsor" | "Contributor" | "WorkspaceAdmin";
  }) => Promise<void>;
  getAuthHeaders: () => Promise<Record<string, string>>;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthContextProvider({
  children,
  value,
}: {
  children: React.ReactNode;
  value: AuthState;
}) {
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return value;
}
