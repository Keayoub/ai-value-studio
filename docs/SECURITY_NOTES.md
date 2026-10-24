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

PostgreSQL business-table RLS is enforced with `ENABLE` and `FORCE` for every table from migrations `20261011_0001` through `20261012_0009`:

- Workspace roots and membership: `workspaces`, `workspace_memberships`, `audit_events`.
- Lifecycle: `programs`, `program_members`, `use_cases`.
- Wizard: `questionnaire_template_versions`, `question_definitions`, `assessment_versions`, `answers`, `hypotheses`.
- Value: `value_assessments`, `score_configuration_versions`, `scorecard_versions`, `dimension_scores`.
- Review: `reviews`, `review_comments`, `approvals`.
- Documents: `documents`, `document_versions`.
- AI controls: `llm_rate_limit_buckets`, `llm_circuit_breakers`.

`question_definitions` inherits its template's workspace policy; global baseline templates and their questions remain readable in a verified workspace context but cannot be modified by the application role. Scoped reads/writes require an active membership for the bound actor, in addition to the existing transaction-local workspace verification. Membership policies check the persisted enum name `ACTIVE`; discovery of the actor's own active memberships remains available before verification, and the first membership can be inserted when creating a workspace. Workspace-bearing child writes also validate same-workspace parent references (global templates excepted), preventing cross-tenant FK links. `identity_subjects` is a shared identity directory, not a tenant business table; `alembic_version` is migration metadata.

The `20261012_0010` migration creates a `SECURITY DEFINER` membership check with `row_security = off`: the migration/function owner must have `BYPASSRLS` (for example a PostgreSQL superuser), while the application login must **not** own the tables, have `BYPASSRLS`, or be a superuser. The API binds actor/workspace settings inside the transaction after authentication; application database credentials must never be exposed to untrusted SQL clients, since PostgreSQL custom settings can be changed by the connected role. CI runs PostgreSQL isolation tests against a separate non-owner application login; local tests explicitly skip PostgreSQL coverage when `POSTGRES_TEST_URL` is unset.

## Current dev-only advisory status

`npm audit --audit-level=high --omit=dev` is clean after the Next.js runtime upgrade. A remaining **dev-only** advisory still affects `eslint-config-next@16.4.0` through the chain `@next/eslint-plugin-next -> fast-glob -> micromatch -> braces`:

- Advisory: `GHSA-vfj7-8cjw-p6xm` (`braces`, high severity)
- Scope: lint-time only, not shipped in the static export/runtime bundle
- Constraint: npm currently resolves `eslint-config-next@16.4.0` to `braces@3.0.3`, and `npm audit fix --force` only offers an incompatible downgrade to `eslint-config-next@14.2.35`

We checked the safe override path before documenting this as unresolved:

- `fast-glob@3.3.3` is newer than the currently resolved `3.3.1`, but it still depends on `micromatch@^4.0.8`.
- `micromatch@4.0.8` still depends on `braces@^3.0.3`.
- `npm view braces version` currently reports `3.0.3`, so there is no published patched `braces` release to force via `overrides`.

Until the upstream Next.js lint dependency chain ships a compatible fix on the 16.x line, keep CI enforcement on the runtime dependency audit (`--omit=dev`) and track the upstream fix before re-enabling a blocking full dev-dependency audit.

## ESLint 10 trial blocker

We also trialed `eslint@10.12.0` alongside `next@16.4.0` and `eslint-config-next@16.4.0`. The app still typechecks, lints, and builds, but the toolchain is not yet peer-clean:

- `eslint-plugin-import@2.32.0` peers `eslint` only through `^9`
- `eslint-plugin-jsx-a11y@6.10.2` peers `eslint` only through `^9`
- `eslint-plugin-react@7.37.5` peers `eslint` only through `^9.7`

`npm ci` completes only with peer override warnings, and `npm ls eslint eslint-plugin-import eslint-plugin-jsx-a11y eslint-plugin-react` exits with `ELSPROBLEMS`. Keep `eslint` on 9.x until the Next 16 lint dependency stack publishes ESLint 10-compatible peer ranges.

## Dependabot #14 WeasyPrint deferral

Dependabot update #14 changes only the `weasyprint` range, and that expansion remains deferred after measured PDF pagination differences between `66.0` and `70.0` on core deliverables.

- Executive Brief stayed at 6 pages in both renders.
- Pilot Charter changed from 7 pages on WeasyPrint 66.0 to 6 pages on WeasyPrint 70.0.
- Both renders still embedded Inter and Source Serif 4, and both reports recorded `validation_errors: []`.

Because this changes pagination for a core PDF output without any corresponding validation error, keep `weasyprint` pinned at `>=66,<67` until the layout shift is understood and accepted.
