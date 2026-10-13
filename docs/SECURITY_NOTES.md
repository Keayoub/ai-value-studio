# Security notes

## Static-host response header contract

The web app is shipped as a static export, so it cannot set response headers itself. The deployment host or CDN **must** enforce these headers for every HTML/document response:

- `Content-Security-Policy`: include a strict `script-src` policy and a `connect-src` allowlist limited to the deployed API origin and `https://login.microsoftonline.com`.
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`: a strict policy such as `strict-origin-when-cross-origin`
- `Permissions-Policy`: disable browser features that are not explicitly required
- `frame-ancestors 'none'` in the CSP policy

Example production header set with deploy-time placeholders:

```text
Content-Security-Policy:
  default-src 'self';
  base-uri 'self';
  script-src 'self' 'nonce-__CSP_NONCE__';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob:;
  font-src 'self' data:;
  connect-src 'self' __API_ORIGIN__ https://login.microsoftonline.com;
  frame-ancestors 'none';
  object-src 'none';
  form-action 'self';
  manifest-src 'self';
  worker-src 'self' blob:;
  upgrade-insecure-requests
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
X-Frame-Options: DENY
```

Notes:

- Replace `__API_ORIGIN__` with the deployed backend origin, for example `https://api.example.com`.
- Replace `__CSP_NONCE__` with a per-response nonce if any bootstrap script must remain inline; otherwise keep scripts fully external and omit the nonce token rather than adding `unsafe-inline` or `unsafe-eval`.
- If a CDN or auth proxy terminates login flows on another origin, review and explicitly add only that origin to `connect-src`.

Any relaxation to support new integrations should be reviewed as a security change before deployment.

## Backend tenancy follow-up

Row-level security still needs to be tracked and enforced for **all business tenant tables**, not only the currently protected subset. This remains a required follow-up item before broader production rollout.

## Current dev-only advisory status

`npm audit --audit-level=high --omit=dev` is clean after the Next.js runtime upgrade. A remaining **dev-only** advisory still affects `eslint-config-next@16.3.8` through the chain `@next/eslint-plugin-next -> fast-glob -> micromatch -> braces`:

- Advisory: `GHSA-vfj7-8cjw-p6xm` (`braces`, high severity)
- Scope: lint-time only, not shipped in the static export/runtime bundle
- Constraint: npm currently resolves `eslint-config-next@16.3.8` to `braces@3.0.3`, and `npm audit fix --force` only offers an incompatible downgrade to `eslint-config-next@14.2.35`

We checked the safe override path before documenting this as unresolved:

- `fast-glob@3.3.3` is newer than the currently resolved `3.3.1`, but it still depends on `micromatch@^4.0.8`.
- `micromatch@4.0.8` still depends on `braces@^3.0.3`.
- `npm view braces version` currently reports `3.0.3`, so there is no published patched `braces` release to force via `overrides`.

Until the upstream Next.js lint dependency chain ships a compatible fix on the 16.x line, keep CI enforcement on the runtime dependency audit (`--omit=dev`) and track the upstream fix before re-enabling a blocking full dev-dependency audit.
