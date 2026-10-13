# Electron desktop shell

The S10 desktop shell packages the existing static `web/out` export behind a privileged `app://studio` protocol. The renderer stays sandboxed and client-only; the main process owns PKCE sign-in, secure token caching, file-save dialogs, and every privileged capability.

## Runtime model

- **Renderer origin:** `app://studio`
- **Static assets:** `web/out`, copied into packaged builds as `resources/renderer`
- **Authentication:** `@azure/msal-node` public client in the main process, authorization code + PKCE, system browser, loopback callback on `127.0.0.1`
- **Token exposure:** renderer receives only short-lived access tokens through the preload bridge; refresh tokens never leave the main process
- **Cache persistence:** MSAL cache is encrypted with Electron `safeStorage` when the OS secret store is available; otherwise tokens remain session-only in memory
- **Navigation:** only `app://studio` stays in-app; configured Entra/API origins open externally; everything else is denied
- **Downloads:** the desktop shell saves document bytes through a native save dialog instead of renderer-triggered `file://` downloads

## Renderer build inputs

`web` still builds the static export and remains the source of truth for the baked desktop renderer mode and API origin:

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_AUTH_MODE` | `entra` for production desktop builds, `dev` only for local backend development |
| `NEXT_PUBLIC_API_BASE_URL` | FastAPI `/api/v1` base URL |
| `NEXT_PUBLIC_ENTRA_CLIENT_ID` | SPA/browser client ID baked into the renderer metadata |
| `NEXT_PUBLIC_ENTRA_TENANT_ID` | Entra tenant ID |
| `NEXT_PUBLIC_API_SCOPE` | API delegated scope |
| `DESKTOP_ALLOWED_EXTERNAL_ORIGINS` | Optional comma-separated allowlist appended to API + Entra origins |

After `next build`, the export now includes `web/out/desktop-public-build.json`. The packaged shell reads that file at startup and fails closed if the desktop runtime config does not match the baked renderer `authMode` or API origin.

## Packaged app runtime config

Packaged builds no longer depend on launch-time `process.env`. Instead, create `desktop-public.json` next to the packaged executable from the bundled `desktop-public.template.json`.

Linux unpacked example:

```text
electron-app/release/linux-unpacked/
├── AI Value Studio Desktop
├── desktop-public.json
└── desktop-public.template.json
```

`desktop-public.json` must contain:

```json
{
  "authMode": "entra",
  "apiBaseUrl": "https://api.example.com/api/v1",
  "entra": {
    "clientId": "00000000-0000-0000-0000-000000000000",
    "tenantId": "common",
    "scope": "api://avs-api/access_as_user"
  }
}
```

Rules enforced at launch:

- `authMode` must be `dev` or `entra`
- `apiBaseUrl` must be an absolute `http` or `https` URL with no embedded credentials, query string, or fragment
- `entra.clientId`, `entra.tenantId`, and `entra.scope` are required in `entra` mode
- packaged startup aborts if `desktop-public.json` is missing, invalid, or its `authMode` / API origin diverges from `web/out/desktop-public-build.json`

In `dev` mode, keep `authMode: "dev"` and point `apiBaseUrl` to the real local backend, for example `http://127.0.0.1:8010/api/v1`.

The configured API origin must expose the unauthenticated health probe at `/health`. The desktop renderer derives that endpoint from `apiBaseUrl` and uses it to distinguish "internet offline" from "API unreachable" before asking the user to retry.

The API must also allow `app://studio` in its CORS configuration. Without that origin, the desktop shell can load its local renderer but API calls and the `/health` reachability probe will fail in the packaged app.

`DESKTOP_ALLOW_RENDERER_DEBUG_TOOLS=1` is a **test-only** switch for packaged smoke and similar automation. The desktop shell now ignores it unless the verified desktop public config is also in `authMode: "dev"`, so packaged Entra/production builds still launch with DevTools disabled.

## Build and validation

1. Package a Linux unpacked desktop release from `electron-app` in one command:

   ```bash
   cd electron-app && NEXT_PUBLIC_AUTH_MODE=entra NEXT_PUBLIC_API_BASE_URL=https://api.example.com/api/v1 NEXT_PUBLIC_ENTRA_CLIENT_ID=00000000-0000-0000-0000-000000000000 NEXT_PUBLIC_ENTRA_TENANT_ID=common NEXT_PUBLIC_API_SCOPE=api://avs-api/access_as_user npm run package:release
   ```

   `npm run package:release` rebuilds `../web/out` with the caller-provided public environment and then runs the existing `npm run pack` flow unchanged. It fails closed unless all of those release inputs are explicitly present and `NEXT_PUBLIC_AUTH_MODE=entra`.

2. Create or update the packaged desktop config after `npm run package:release` or `npm run pack`:

   ```bash
   cp electron-app/release/linux-unpacked/desktop-public.template.json \
     electron-app/release/linux-unpacked/desktop-public.json
   ```

3. Validate the desktop shell:

   ```bash
   cd electron-app
   npm run typecheck
   npm run lint
   npm run test:unit
   npm run test:smoke
   ```

For Linux smoke coverage against the real seeded backend, build a dev renderer first:

```bash
cd web
NEXT_PUBLIC_AUTH_MODE=dev NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010/api/v1 npm run build
cd ../electron-app
npm run pack
npm run test:smoke
```

`npm run pack` produces a Linux unpacked directory on Linux and keeps Windows NSIS configuration in `electron-app/package.json` for release pipelines. `npm run test:smoke` launches the actual `release/linux-unpacked/AI Value Studio Desktop` executable, writes `release/linux-unpacked/desktop-public.json` for dev auth smoke, auto-starts the real local backend with a repository-local SQLite database, and auto-uses `xvfb-run` on headless Linux when it is available.

## Security controls

- Privileged `app://studio` responses reject traversal and unknown routes and set a route-specific CSP with hashed inline Next scripts/styles plus a narrow `connect-src`
- The renderer manifest and packaged `desktop-public.json` must agree on auth mode and API origin before the app window opens
- `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`, and packaged builds disable DevTools
- the loopback Entra callback validates cryptographic `state` before exchanging the authorization code and rejects replayed or mismatched callbacks
- Permission requests, `<webview>` attachment, non-`/studio` app frames, and untrusted IPC callers are denied
- desktop sign-in now prunes stale cached MSAL accounts so sign-out clears every local desktop session and future launches do not silently pick an older cached user
- The preload bridge exposes only:
  - desktop auth state/sign-in/sign-out/access-token
  - app version
  - document save dialog

## Release follow-ups

- **Platform code signing:** not implemented yet. Sign the Windows installer/binaries and any future macOS artifacts before distribution so desktop auth and update surfaces are trusted by the host OS.
- **Auto-update:** not implemented yet. Add a signed update channel plus rollout/rollback policy before treating packaged desktop releases as self-updating.
- **Manual Entra validation:** still required. There is no tenant-backed evidence in this repository/session that the packaged PKCE loopback flow succeeds against the target Entra app registration.

## Manual Entra evidence

The repository now includes the production PKCE loopback flow, but the real interactive Entra login has **not** been exercised end-to-end in this environment because no non-production tenant credentials or registered desktop redirect URI were available during implementation. Treat the loopback flow as implementation-complete and manually verify it against the intended tenant before release.
