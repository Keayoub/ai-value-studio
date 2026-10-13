import assert from "node:assert/strict";
import test from "node:test";
import type { AccountInfo } from "@azure/msal-node";

import { getSingleAccount, pruneCachedAccounts } from "../../src/main/auth-service";
import { listenForAuthorizationCode } from "../../src/main/entra-loopback";

function createAccount(homeAccountId: string, username = `${homeAccountId}@example.com`) {
  return {
    homeAccountId,
    username,
    environment: "login.microsoftonline.com",
    tenantId: "tenant-id",
    localAccountId: `${homeAccountId}-local`,
    name: username,
  } as AccountInfo;
}

test("rejects Entra callbacks whose state does not match the pending sign-in", async () => {
  const listener = await listenForAuthorizationCode("expected-state");

  try {
    const waitForCode = listener.waitForCode();
    const rejection = assert.rejects(waitForCode, /Invalid Entra callback state/);
    const response = await fetch(
      `${listener.redirectUri}?code=desktop-code&state=unexpected-state`,
    );

    assert.equal(response.status, 400);
    await rejection;
  } finally {
    await listener.close();
  }
});

test("ignores replay callbacks after a successful authorization code exchange", async () => {
  const listener = await listenForAuthorizationCode("expected-state");

  try {
    const waitForCode = listener.waitForCode();
    const firstResponse = await fetch(
      `${listener.redirectUri}?code=desktop-code&state=expected-state`,
    );

    assert.equal(firstResponse.status, 200);
    assert.equal(await waitForCode, "desktop-code");

    const replayResponse = await fetch(
      `${listener.redirectUri}?code=replayed-code&state=expected-state`,
    );
    assert.equal(replayResponse.status, 409);
  } finally {
    await listener.close();
  }
});

test("keeps the first cached account selection deterministic", async () => {
  const accounts = [createAccount("primary"), createAccount("secondary")];
  const client = {
    getTokenCache: () => ({
      getAllAccounts: () => Promise.resolve(accounts),
      removeAccount: () => Promise.resolve(),
    }),
  };

  assert.equal((await getSingleAccount(client))?.homeAccountId, "primary");
});

test("prunes cached accounts that do not match the retained desktop identity", async () => {
  const removedAccountIds: string[] = [];
  const accounts = [
    createAccount("primary"),
    createAccount("secondary"),
    createAccount("third"),
  ];
  const client = {
    getTokenCache: () => ({
      getAllAccounts: () => Promise.resolve(accounts),
      removeAccount: (account: AccountInfo) => {
        removedAccountIds.push(account.homeAccountId);
        return Promise.resolve();
      },
    }),
  };

  await pruneCachedAccounts(client, "secondary");

  assert.deepEqual(removedAccountIds, ["primary", "third"]);
});

test("clears every cached desktop account on sign-out cleanup", async () => {
  const removedAccountIds: string[] = [];
  const accounts = [createAccount("primary"), createAccount("secondary")];
  const client = {
    getTokenCache: () => ({
      getAllAccounts: () => Promise.resolve(accounts),
      removeAccount: (account: AccountInfo) => {
        removedAccountIds.push(account.homeAccountId);
        return Promise.resolve();
      },
    }),
  };

  await pruneCachedAccounts(client, null);

  assert.deepEqual(removedAccountIds, ["primary", "secondary"]);
});
