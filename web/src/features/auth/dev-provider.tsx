"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { BrowserApiClient } from "@/features/api/browser-api-client";
import type { MeResponse } from "@/features/api/types";
import { AuthContextProvider, type AuthState } from "@/features/auth/auth-context";
import type { PublicRuntimeConfig } from "@/features/auth/runtime";

const STORAGE_KEY = "avs.dev.identity";

type StoredIdentity = {
  subjectId: string;
  displayName: string;
  role: "Consultant" | "Sponsor" | "Contributor" | "WorkspaceAdmin";
  headers: Record<string, string>;
};

function readStoredIdentity(): StoredIdentity | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as StoredIdentity;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function DevAuthProvider({
  config,
  children,
}: {
  config: PublicRuntimeConfig;
  children: React.ReactNode;
}) {
  const [storedIdentity, setStoredIdentity] = useState<StoredIdentity | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("unauthenticated");
  const [error, setError] = useState<string | null>(null);
  const [storageLoaded, setStorageLoaded] = useState(false);

  const getAuthHeaders = useCallback(async () => storedIdentity?.headers ?? {}, [storedIdentity]);
  const apiClient = useMemo(
    () => new BrowserApiClient(config.apiBaseUrl, getAuthHeaders),
    [config.apiBaseUrl, getAuthHeaders],
  );

  const refreshMe = useCallback(async () => {
    if (!storedIdentity) {
      setMe(null);
      setStatus("unauthenticated");
      return;
    }
    setStatus("loading");
    try {
      const payload = await apiClient.getMe();
      setMe(payload);
      setStatus("authenticated");
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Authentication failed.");
      setMe(null);
      setStatus("unauthenticated");
    }
  }, [apiClient, storedIdentity]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      const persistedIdentity = readStoredIdentity();
      if (persistedIdentity) {
        setStoredIdentity(persistedIdentity);
        setStatus("loading");
      }
      setStorageLoaded(true);
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, []);

  useEffect(() => {
    if (!storageLoaded) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      void refreshMe();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [refreshMe, storageLoaded]);

  const selectDevIdentity = useCallback<AuthState["selectDevIdentity"]>(
    async ({ subjectId, displayName, role }) => {
      setStatus("loading");
      setError(null);
      try {
        const response = await fetch(`${config.apiBaseUrl}/dev/identity`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ subject_id: subjectId, display_name: displayName, role }),
        });
        if (!response.ok) {
          setStatus("unauthenticated");
          throw new Error(`Dev identity selection failed with ${response.status}.`);
        }
        const payload = (await response.json()) as {
          display_name: string;
          headers: Record<string, string>;
          oid: string;
        };
        const nextValue: StoredIdentity = {
          subjectId: payload.oid,
          displayName: payload.display_name,
          role,
          headers: payload.headers,
        };
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextValue));
        setStoredIdentity(nextValue);
        setStatus("authenticated");
      } catch (requestError) {
        setStatus("unauthenticated");
        setStoredIdentity(null);
        setMe(null);
        setError(requestError instanceof Error ? requestError.message : "Authentication failed.");
        throw requestError;
      }
    },
    [config.apiBaseUrl],
  );

  const signOut = useCallback(async () => {
    window.localStorage.removeItem(STORAGE_KEY);
    setStoredIdentity(null);
    setMe(null);
    setStatus("unauthenticated");
  }, []);

  const value: AuthState = {
    status,
    mode: "dev",
    me,
    displayName: storedIdentity?.displayName ?? null,
    roleLabel: storedIdentity?.role ?? null,
    error,
    ready: storageLoaded,
    signIn: async () => undefined,
    signOut,
    selectDevIdentity,
    getAuthHeaders,
    refreshMe,
  };

  return <AuthContextProvider value={value}>{children}</AuthContextProvider>;
}
