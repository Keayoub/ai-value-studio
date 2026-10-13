"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { BrowserApiClient } from "@/features/api/browser-api-client";
import type { MeResponse } from "@/features/api/types";
import { AuthContextProvider, type AuthState } from "@/features/auth/auth-context";
import {
  getDesktopBridge,
  type DesktopBridge,
  type PublicRuntimeConfig,
} from "@/features/auth/runtime";

type DesktopAccount = {
  homeAccountId: string;
  username: string;
  name: string | null;
};

function mapDisplayName(account: DesktopAccount | null) {
  return account?.name ?? account?.username ?? null;
}

export function DesktopAuthProvider({
  config,
  children,
}: {
  config: PublicRuntimeConfig;
  children: React.ReactNode;
}) {
  const [bridge] = useState<DesktopBridge | null>(() => getDesktopBridge());
  const [account, setAccount] = useState<DesktopAccount | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>(
    bridge ? "loading" : "unauthenticated",
  );
  const [error, setError] = useState<string | null>(
    bridge ? null : "Desktop bridge unavailable.",
  );

  useEffect(() => {
    if (!bridge) {
      return;
    }

    let active = true;
    void bridge.auth
      .getState()
      .then((nextState) => {
        if (!active) {
          return;
        }
        setAccount(nextState.account);
        setStatus(nextState.status === "authenticated" ? "authenticated" : "unauthenticated");
      })
      .catch((initializationError: unknown) => {
        if (!active) {
          return;
        }
        setError(
          initializationError instanceof Error
            ? initializationError.message
            : "Desktop authentication failed.",
        );
        setStatus("unauthenticated");
      });

    return () => {
      active = false;
    };
  }, [bridge]);

  const getAuthHeaders = useCallback(async () => {
    if (!bridge || !account) {
      return {} as Record<string, string>;
    }

    const accessToken = await bridge.auth.getAccessToken();
    return { Authorization: "Bearer " + accessToken };
  }, [account, bridge]);

  const apiClient = useMemo(
    () => new BrowserApiClient(config.apiBaseUrl, getAuthHeaders),
    [config.apiBaseUrl, getAuthHeaders],
  );

  const refreshMe = useCallback(async () => {
    if (!bridge || !account) {
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
      setError(requestError instanceof Error ? requestError.message : "Profile lookup failed.");
      setStatus("unauthenticated");
    }
  }, [account, apiClient, bridge]);

  useEffect(() => {
    if (!bridge || !account) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void refreshMe();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [account, bridge, refreshMe]);

  const signIn = useCallback(async () => {
    if (!bridge) {
      return;
    }

    setStatus("loading");
    const nextState = await bridge.auth.signIn();
    setAccount(nextState.account);
    setStatus(nextState.status === "authenticated" ? "authenticated" : "unauthenticated");
    setError(null);
  }, [bridge]);

  const signOut = useCallback(async () => {
    if (!bridge) {
      return;
    }

    await bridge.auth.signOut();
    setAccount(null);
    setMe(null);
    setStatus("unauthenticated");
  }, [bridge]);

  const value: AuthState = {
    status,
    mode: "entra",
    me,
    displayName: mapDisplayName(account),
    roleLabel: me?.memberships[0]?.role ?? null,
    error,
    ready: bridge !== null,
    signIn,
    signOut,
    selectDevIdentity: async () => {
      throw new Error("Dev identity selection is unavailable in desktop Entra mode.");
    },
    getAuthHeaders,
    refreshMe,
  };

  return <AuthContextProvider value={value}>{children}</AuthContextProvider>;
}
