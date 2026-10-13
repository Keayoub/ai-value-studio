import crypto from "node:crypto";
import path from "node:path";

import { app, shell } from "electron";
import {
  CryptoProvider,
  InteractionRequiredAuthError,
  PublicClientApplication,
} from "@azure/msal-node";
import type { AccountInfo } from "@azure/msal-node";

import type { DesktopAuthState } from "../shared/desktop-bridge";
import type { DesktopEnvironment } from "./environment";
import { listenForAuthorizationCode } from "./entra-loopback";
import { createEncryptedTokenCache } from "./token-cache";

type DesktopAuthService = {
  getState: () => Promise<DesktopAuthState>;
  signIn: () => Promise<DesktopAuthState>;
  signOut: () => Promise<DesktopAuthState>;
  getAccessToken: () => Promise<string>;
};

type AccountCacheClient = {
  getTokenCache: () => {
    getAllAccounts: () => Promise<AccountInfo[]>;
    removeAccount: (account: AccountInfo) => Promise<void>;
  };
};

function mapAccountToState(account: AccountInfo | null): DesktopAuthState {
  if (!account) {
    return {
      status: "unauthenticated",
      account: null,
    };
  }

  return {
    status: "authenticated",
    account: {
      homeAccountId: account.homeAccountId,
      username: account.username,
      name: account.name ?? null,
    },
  };
}

async function getSingleAccount(client: AccountCacheClient) {
  const accounts = await client.getTokenCache().getAllAccounts();
  return accounts[0] ?? null;
}

async function pruneCachedAccounts(
  client: AccountCacheClient,
  keepHomeAccountId: string | null,
) {
  const tokenCache = client.getTokenCache();
  const accounts = await tokenCache.getAllAccounts();
  const removals = accounts
    .filter((account) => keepHomeAccountId === null || account.homeAccountId !== keepHomeAccountId)
    .map(async (account) => {
      await tokenCache.removeAccount(account);
    });

  await Promise.all(removals);
}

export function createDesktopAuthService(environment: DesktopEnvironment): DesktopAuthService {
  if (!environment.entra) {
    return {
      getState: () => Promise.resolve({ status: "unauthenticated", account: null }),
      signIn: () => Promise.resolve({ status: "unauthenticated", account: null }),
      signOut: () => Promise.resolve({ status: "unauthenticated", account: null }),
      getAccessToken: () =>
        Promise.reject(
          new Error(
            "Desktop Entra authentication is unavailable because NEXT_PUBLIC_AUTH_MODE is not entra.",
          ),
        ),
    };
  }
  const entraConfig = environment.entra;

  const client = new PublicClientApplication({
    auth: {
      clientId: entraConfig.clientId,
      authority: `https://login.microsoftonline.com/${entraConfig.tenantId}`,
    },
    cache: {
      cachePlugin: createEncryptedTokenCache(path.join(app.getPath("userData"), "msal-cache.json")),
    },
  });

  const cryptoProvider = new CryptoProvider();
  let signInInFlight: Promise<DesktopAuthState> | null = null;

  async function completeInteractiveSignIn() {
    const state = crypto.randomBytes(32).toString("base64url");
    const loopback = await listenForAuthorizationCode(state);
    const pkceCodes = await cryptoProvider.generatePkceCodes();

    try {
      const authUrl = await client.getAuthCodeUrl({
        scopes: [entraConfig.apiScope],
        redirectUri: loopback.redirectUri,
        codeChallenge: pkceCodes.challenge,
        codeChallengeMethod: "S256",
        prompt: "select_account",
        state,
      });

      await shell.openExternal(authUrl);

      const code = await Promise.race([
        loopback.waitForCode(),
        new Promise<string>((_, reject) => {
          setTimeout(() => reject(new Error("Timed out waiting for Entra sign-in.")), 180_000);
        }),
      ]);

      const result = await client.acquireTokenByCode({
        code,
        scopes: [entraConfig.apiScope],
        redirectUri: loopback.redirectUri,
        codeVerifier: pkceCodes.verifier,
      });

      const account = result?.account ?? (await getSingleAccount(client));
      if (account) {
        await pruneCachedAccounts(client, account.homeAccountId);
      }

      return mapAccountToState(account);
    } finally {
      await loopback.close();
    }
  }

  async function acquireTokenSilent() {
    const account = await getSingleAccount(client);
    if (!account) {
      throw new Error("Interactive sign-in is required.");
    }

    const result = await client.acquireTokenSilent({
      account,
      scopes: [entraConfig.apiScope],
    });

    if (!result?.accessToken) {
      throw new Error("No access token was returned by Entra.");
    }

    return result;
  }

  return {
    getState: async () => mapAccountToState(await getSingleAccount(client)),
    signIn: async () => {
      if (!signInInFlight) {
        signInInFlight = completeInteractiveSignIn().finally(() => {
          signInInFlight = null;
        });
      }

      return signInInFlight;
    },
    signOut: async () => {
      await pruneCachedAccounts(client, null);

      return { status: "unauthenticated", account: null };
    },
    getAccessToken: async () => {
      try {
        const token = await acquireTokenSilent();
        return token.accessToken;
      } catch (error) {
        if (error instanceof InteractionRequiredAuthError) {
          throw new Error("Interactive sign-in is required.");
        }

        throw error;
      }
    },
  };
}

export type { DesktopAuthService };
export { getSingleAccount, pruneCachedAccounts };
