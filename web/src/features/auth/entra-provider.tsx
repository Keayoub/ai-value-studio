"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  BrowserCacheLocation,
  EventType,
  PublicClientApplication,
  type AccountInfo,
} from "@azure/msal-browser";

import { BrowserApiClient } from "@/features/api/browser-api-client";
import type { MeResponse } from "@/features/api/types";
import { AuthContextProvider, type AuthState } from "@/features/auth/auth-context";
import type { PublicRuntimeConfig } from "@/features/auth/runtime";

function buildMsalClient(config: PublicRuntimeConfig): PublicClientApplication {
  return new PublicClientApplication({
    auth: {
      clientId: config.entra.clientId,
      authority: `https://login.microsoftonline.com/${config.entra.tenantId}`,
      redirectUri: window.location.origin + "/studio",
      navigateToLoginRequestUrl: false,
    },
    cache: {
      cacheLocation: BrowserCacheLocation.MemoryStorage,
      temporaryCacheLocation: BrowserCacheLocation.MemoryStorage,
    },
  });
}

export function EntraAuthProvider({
  config,
  children,
}: {
  config: PublicRuntimeConfig;
  children: React.ReactNode;
}) {
  const [client] = useState<PublicClientApplication | null>(() =>
    typeof window === "undefined" ? null : buildMsalClient(config),
  );
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!client) {
      return;
    }

    let active = true;
    const callbackId = client.addEventCallback((event) => {
      if (!active) {
        return;
      }

      if (
        event.eventType === EventType.LOGIN_SUCCESS &&
        event.payload &&
        "account" in event.payload &&
        event.payload.account
      ) {
        setAccount(event.payload.account);
      }

      if (event.eventType === EventType.LOGOUT_SUCCESS) {
        setAccount(null);
        setMe(null);
        setStatus("unauthenticated");
      }
    });

    void client
      .initialize()
      .then(async () => {
        const redirect = await client.handleRedirectPromise();
        const resolvedAccount =
          redirect?.account ??
          client.getActiveAccount() ??
          client.getAllAccounts()[0] ??
          null;
        if (resolvedAccount) {
          client.setActiveAccount(resolvedAccount);
        }
        setAccount(resolvedAccount);
        setStatus(resolvedAccount ? "authenticated" : "unauthenticated");
      })
      .catch((initializationError: unknown) => {
        setError(
          initializationError instanceof Error
            ? initializationError.message
            : "Authentication failed.",
        );
        setStatus("unauthenticated");
      });

    return () => {
      active = false;
      if (callbackId) {
        client.removeEventCallback(callbackId);
      }
    };
  }, [client]);

  const getAuthHeaders = useCallback(async () => {
    if (!client || !account) {
      return {} as Record<string, string>;
    }
    const token = await client.acquireTokenSilent({
      account,
      scopes: [config.entra.scope],
    });
    return { Authorization: "Bearer " + token.accessToken };
  }, [account, client, config.entra.scope]);

  const apiClient = useMemo(
    () => new BrowserApiClient(config.apiBaseUrl, getAuthHeaders),
    [config.apiBaseUrl, getAuthHeaders],
  );

  const refreshMe = useCallback(async () => {
    if (!client || !account) {
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
  }, [account, apiClient, client]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void refreshMe();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [refreshMe]);

  const signIn = useCallback(async () => {
    if (!client) {
      return;
    }
    await client.loginRedirect({ scopes: [config.entra.scope] });
  }, [client, config.entra.scope]);

  const signOut = useCallback(async () => {
    if (!client || !account) {
      return;
    }
    await client.logoutRedirect({
      account,
      postLogoutRedirectUri: window.location.origin + "/studio",
    });
  }, [account, client]);

  const value: AuthState = {
    status,
    mode: "entra",
    me,
    displayName: account?.name ?? null,
    roleLabel: me?.memberships[0]?.role ?? null,
    error,
    ready: Boolean(client),
    signIn,
    signOut,
    selectDevIdentity: async () => {
      throw new Error("Dev identity selection is unavailable in Entra mode.");
    },
    getAuthHeaders,
    refreshMe,
  };

  return <AuthContextProvider value={value}>{children}</AuthContextProvider>;
}
