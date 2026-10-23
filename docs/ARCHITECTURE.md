# Architecture

## Pointer summary

- **Source of truth**: the architecture decision packet for Slice S1 is stored in `docs/architecture/decision-packet.md`.
- **Backend**: FastAPI app in `backend/` keeps the legacy CRUD and kickstart surfaces, with explicit local CORS configuration and a health endpoint for CI/runtime checks.
- **Framework package**: reusable scoring, document generation, and kickstart logic remains in `src/ai_value_studio/`.
- **Web**: Next.js static export lives in `web/`, built with `npm ci`, typecheck, lint, build, and Playwright e2e validation.
- **Desktop shell**: Electron stays isolated in `electron-app/`, keeps `yarn.lock`, and consumes the exported web build without S1 modernization work.
- **Delivery foundation**: CI covers backend, web, e2e, and hygiene checks; Dependabot tracks pip, npm, Electron, and GitHub Action dependencies.

## Decision packet

See `docs/architecture/decision-packet.md` for the verbatim architecture packet copy used by this slice.

For the planned, standalone **AI Governance Plan generated deliverable** (not a governance platform), see the [authoritative future deliverable decision packet](architecture/ai-governance-plan-decision-packet.md). It does not change the current document implementation.
