# AI Value Studio MVP — Architecture Decision Packet

Status: implementation-ready. Repository evidence inspected 2026-10-11. This packet is intentionally limited to the owner-approved MVP journey; Kaizen is a future extension hook only.

## 0. Baseline and non-negotiable corrections

Observed baseline:
- `web/` is Next 16.3.6 / React 19 and already has `output: 'export'`; it must remain a client-only static application. There is no Next.js server/API route option.
- `backend/` is an untracked FastAPI + SQLModel service with SQLite, permissive CORS, unauthenticated `/projects`, `/wizard`, `/docs` and `/kickstart` endpoints, and three overlapping `kickstart*.py` implementations.
- The durable framework engine already has the correct six default weights and value formulas in `src/ai_value_studio/{models,scoring}.py`; promote those rules into the API domain service rather than duplicating them in the UI.
- `electron-app/` is an untracked Electron Forge 5 scaffold that loads a local HTML file and opens DevTools. It is not yet a desktop product.
- The existing five-step UI is being edited by another agent. Do not overwrite it; introduce the eight-step shell and API contracts in a coordinated follow-up slice.

Decision: retain FastAPI/SQLModel and the static Next export; replace the current ad-hoc persistence model (`Client > Project > WizardSession`) with the MVP domain below using Alembic migrations.

Rejected: a Next server/BFF (incompatible with static export), and an Electron-embedded SQLite/FastAPI instance (breaks shared multi-tenant collaboration, approvals, auditability and hosted documents).

## 1. Target architecture and runtime boundaries

```text
Browser static export                         Electron desktop shell
Next/React + MSAL Browser                     Main process: MSAL Node + loopback callback
      | HTTPS Bearer access token                    | encrypted token cache + IPC token broker
      +-------------------------------+--------------+
                                      |
                              FastAPI `/api/v1`
    JWT authentication -> workspace context -> authorization -> scoped repositories
                                      |
         PostgreSQL (production)              Object storage (PDF/MD immutable versions)
         SQLite (local dev only)               local filesystem adapter (local dev only)
                                      |
         Domain services: wizard / score / review / documents / audit / LLM
                                      |
                   Provider-agnostic LLM adapter (server-side only)
              OpenAI default; Azure OpenAI and Anthropic plug-ins
```

Component responsibilities:
- `web/`: French-first UI, MSAL browser sign-in, token acquisition, route guards, autosave and API client. It never evaluates authorization or stores secrets. `NEXT_PUBLIC_*` values are public configuration only.
- `electron-app/`: a thin, hardened desktop shell loading the deployed static web URL (or a packaged static export for offline display only). It owns desktop login/token brokering, external navigation policy and secure storage; it does not host the API or database.
- `backend/`: the sole policy enforcement point. It validates Entra access tokens, resolves membership/active workspace, applies authorization and tenant scoping, persists data, produces documents and invokes LLMs.
- PostgreSQL: production source of truth. SQLite is only `AUTH_MODE=dev` local development/test storage, never a desktop collaboration database.
- Object storage: content-addressed document artifacts, private only. The DB stores immutable metadata and object key; download is streamed by an authorized API endpoint or time-limited signed URL after authorization.

Request data flow:
1. Client signs in and requests the API scope from Entra.
2. Client calls FastAPI with `Authorization: Bearer <access token>`; it does not send a trusted workspace/user/role header.
3. `AuthContext` verifies signature/JWKS, issuer, audience, tenant and time claims; `WorkspaceContext` resolves the selected workspace only if an active `WorkspaceMembership` exists.
4. A scoped transaction sets `app.workspace_id`; repository methods require that context and always filter by it. PostgreSQL RLS is the second line of defense.
5. Mutation service validates state transition, writes domain row(s) and append-only audit event in the same transaction. PDF/LLM work writes a job/audit record and creates a new immutable artifact version.

Deployment topology: static web hosted behind HTTPS/CDN; FastAPI container behind HTTPS reverse proxy/API hostname; managed PostgreSQL and private Blob/S3-compatible object storage on private network. Electron points to the same production web/API origins. No CORS wildcard, no database exposure, no LLM key in a client binary.

## 2. Authentication and authorization

### Decision
Use one Microsoft Entra workforce tenant for MVP. Consultants authenticate as workforce members; customer Sponsors and Contributors are provisioned as Entra B2B guest users in that tenant and receive product access through database membership. Do not introduce External ID in the MVP.

Rationale: it produces one issuer, one token-validation path, one administration plane and supports client collaboration immediately. External ID is appropriate when TIFINIA needs self-service client/social/passwordless identity lifecycle at scale; adding it now creates a second issuer, app registration, account linking and support model without an MVP requirement.

Rejected: local JWT/password auth (violates the approved Entra decision), and tenant-specific Entra roles/groups (does not scale and conflates identity with workspace membership).

Future hook: make `IdentitySubject(provider, issuer, tenant_id, oid)` unique, not just email. A later External ID issuer is added as an explicitly configured trusted issuer/provider; existing B2B users are migrated/linked deliberately. Never accept arbitrary Entra tenants.

### Entra registrations and grants

Create two registrations in the same Entra tenant:

1. `avs-web-spa`
   - Platform: Single-page application.
   - Redirect URIs: exact production and preview/dev origins, e.g. `https://studio.tifinia.com/`, `http://localhost:3000/`.
   - Public client; authorization code flow + PKCE only; no client secret.
   - Delegated permission: `api://<avs-api-client-id>/access_as_user`.

2. `avs-api`
   - Expose scope: `access_as_user` (admin/user consent as tenant policy requires).
   - Application ID URI: `api://<avs-api-client-id>`.
   - Access token version 2; accepted audience exactly the API client ID/Application ID URI.
   - No application permission is required for the MVP API.

Define app roles on the API resource and assign them to users/groups:
- `WorkspaceAdmin`: manage workspace profile, members, templates and scoring configuration.
- `Consultant`: create/manage programmes and use cases; score, submit, request information, generate draft documents.
- `Sponsor`: view assigned programmes/use cases; comment; approve/reject/request modification; download approved documents.
- `Contributor`: view assigned programme/use case and submit/edit assigned wizard answers/comments only.

Claim mapping:
- stable identity: `(iss, tid, oid)`; use `preferred_username`/`name` only as display data.
- top-level eligibility: Entra `roles` claim must contain at least one known product role. Groups are accepted only through an explicit `GROUP_TO_PRODUCT_ROLE` configuration map; reject group overage tokens rather than querying Graph synchronously.
- fine-grained access: `WorkspaceMembership.role` and optional `ProgramMember` assignment in the DB are authoritative. Effective role is the least-privileged intersection of Entra role and membership role; Entra does not encode workspace IDs.
- token validator checks `alg` allowlist, JWKS `kid`, signature, `exp`/`nbf`, exact `iss` for configured tenant, exact `aud`, `tid`, and scope `access_as_user`. Never authorize from an ID token.

### Browser vs Electron

Browser: `@azure/msal-browser`, authorization-code + PKCE, redirect flow (not implicit), short-lived in-memory access token preferred; session/local cache only if justified and protected by CSP/XSS controls. The static export exposes only `NEXT_PUBLIC_ENTRA_CLIENT_ID`, `NEXT_PUBLIC_ENTRA_TENANT_ID`, `NEXT_PUBLIC_API_SCOPE`, `NEXT_PUBLIC_API_BASE_URL`, and `NEXT_PUBLIC_AUTH_MODE`.

Electron: add `@azure/msal-node` in the main process. Use the system browser and a loopback callback on `http://127.0.0.1:<ephemeral-port>` registered as the desktop redirect URI; complete auth code + PKCE in the main process. The renderer asks through narrow IPC for an access token; it never receives refresh tokens and never runs a Node client secret. Persist MSAL cache only through OS encrypted storage (`safeStorage`/keychain) with least-privilege file permissions. Use `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`, a validated preload API, navigation/new-window allowlists for TIFINIA/Entra origins, and no DevTools in packaged builds.

Rejected Electron alternatives:
- embedded webview login: weaker Conditional Access/SSO compatibility and higher credential-phishing risk.
- custom protocol redirect: viable later but requires platform-specific registration/ownership; loopback is simpler and standards-aligned for the MVP.

### Explicit local development mode

`AUTH_MODE=dev` means no Entra call. Backend constructs a synthetic subject from a server-controlled dev header/cookie and exposes a local-only endpoint to select one of the four roles and a seeded workspace. UI shows a persistent high-contrast `LOCAL DEVELOPMENT — AUTH DISABLED` banner and includes the selected identity/role in every page header.

Guardrails:
- Startup must refuse `AUTH_MODE=dev` unless `APP_ENV` is exactly `local` or `test`, `DEBUG=true`, `DATABASE_URL` is SQLite or a test database, and allowed origins are loopback only. Any production/staging/unknown environment exits non-zero before listening.
- CI production-config test asserts that `AUTH_MODE=dev` causes startup refusal. Deployment manifests set `AUTH_MODE=entra` explicitly and do not mount dev configuration.
- Production auth code refuses an `X-Dev-*` header. Dev selector is compiled/configured out of release web builds; it is not merely hidden.
- Dev identities use reserved `dev:` subject values and cannot coexist with production database/object-storage configuration.

### Configuration matrix (examples; values only in secret store or deployment config)

| Area | Required configuration | Secret? |
|---|---|---|
| Backend common | `APP_ENV`, `DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, `AUTH_MODE`, `DOCUMENT_STORAGE_DRIVER` | DB URL/password only |
| Entra API | `ENTRA_TENANT_ID`, `ENTRA_API_CLIENT_ID`, `ENTRA_API_AUDIENCE`, `ENTRA_REQUIRED_SCOPE`, `ENTRA_JWKS_CACHE_TTL` | no |
| Web public | `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_AUTH_MODE`, SPA client/tenant/scope values | no |
| Electron | desktop client ID, tenant ID, API scope, authorized URL origins | no |
| LLM | `LLM_PROVIDER`, model/deployment names | provider key/managed identity credential |
| Documents | storage account/container/key prefix | managed identity/credential |
| Dev only | `DEV_USER_ROLE`, `DEV_WORKSPACE_ID` | no |

Do not commit `.env`, Entra client secrets, OpenAI/Anthropic keys, database passwords, generated PDFs, `.db`, `server.out/err`, token cache, `node_modules`, `out`, `.next`, or recovery backup files.

## 3. Domain model, lifecycle, and tenancy

### Core tables

All PKs are UUID. All tenant-owned tables include non-null `workspace_id`, `created_at`, `updated_at`, and where applicable `created_by_subject`; use UTC. Add `workspace_id` indexes first in composite indexes.

- `identity_subject`: `id`, `issuer`, `tenant_id`, `oid`, `display_name`, `email_snapshot`, `last_seen_at`; unique `(issuer, tenant_id, oid)`.
- `workspace`: `id`, organization profile (`name`, `sector`, `country_region`, `size_band`, `default_language`, `description`), `branding_json`, `confidentiality_policy`, `status`.
- `workspace_membership`: `workspace_id`, `identity_subject_id`, `role`, `status`, `invited_by`, `joined_at`; unique `(workspace_id, identity_subject_id)`.
- `program`: `workspace_id`, `name`, `strategic_objective`, `departments_json`, `period_start/end`, `sponsor_membership_id`, `consultant_membership_id`, `target_use_case_count`, `questionnaire_template_version_id`, `confidentiality_level`, `status`. State: `Draft|Discovery|Assessment|Prioritization|Decision|Closed`.
- `program_member`: `workspace_id`, `program_id`, `membership_id`, `assignment_role`; unique `(program_id, membership_id)`; required for Contributor visibility.
- `use_case`: `workspace_id`, `program_id`, `title`, `department`, `owner_membership_id`, `status`, `recommendation`, `category`, `priority_score`, `score_version`, `confidence_level`, `submitted_at`, `approved_at`, `current_assessment_version`. State: `Draft|InProgress|Submitted|ChangesRequested|Approved|Rejected`.
- `assessment_version`: `workspace_id`, `use_case_id`, `version`, `template_version`, `status`, `interview_mode`, `created_by`, `submitted_by/at`, `approved_by/at`; unique `(use_case_id, version)`. Immutable after submit; changes create a new draft version.
- `questionnaire_template_version` and `question_definition`: workspace/global template scope, version, step (1–8), `question_key`, label/help/example, field type, required expression, schema JSON. Seed the baseline template; do not hard-code question strings across React and API.
- `answer`: `workspace_id`, `assessment_version_id`, `question_key`, `value_json`, `evidence_text`, `confidence`, `entered_by`, `captured_for_membership_id`, `source` (`human|ai_assisted`), `updated_at`; unique `(assessment_version_id, question_key)`. `captured_for` supports interview mode.
- `hypothesis`: `workspace_id`, `use_case_id`, `assessment_version_id`, `statement`, `kind` (`value|risk|assumption`), `status`, `owner`, `evidence_ref`, `validated_at`.
- `value_assessment`: `workspace_id`, `use_case_id`, `assessment_version_id`, normalized inputs, computed money values, currency, `calculation_version` and input snapshot. Computed fields are server-derived, never accepted from the client.
- `score_configuration_version`: `workspace_id`, `version`, six weights, category thresholds, effective state. Default weights are 25/15/15/15/10/20; total must equal 1.00.
- `scorecard_version` and `dimension_score`: `workspace_id`, `use_case_id`, assessment/config version, dimension, weight snapshot, score 1–5, justification, confidence, author, computed/manual override flags and override reason. Unique score dimension per scorecard version.
- `review`: `workspace_id`, `use_case_id`, `assessment_version_id`, `status`, `recommendation`, `submitted_by/at`, `decided_by/at`, decision reason. `comment` is append-only: `workspace_id`, target type/id, body, author, parent comment id.
- `approval`: `workspace_id`, `use_case_id`, `review_id`, `decision` (`Approved|Rejected|ChangesRequested`), `decision_reason`, `approver`, `decided_at`; only Sponsor can create final approval.
- `document`: `workspace_id`, optional `program_id/use_case_id`, `type`, `language`, `status` (`Draft|InReview|Approved|Superseded`), `current_version_no`. Metadata only.
- `document_version`: `workspace_id`, `document_id`, `version_no`, `source_assessment_version`, `source_scorecard_version`, `format` (`markdown|pdf`), `storage_key`, `sha256`, `generated_by`, `generated_at`, `ai_assisted_sections_json`, `approved_by/at`; unique `(document_id, version_no, format)`. Never update artifact content in place.
- `audit_event`: `workspace_id`, `actor_subject_id`, `action`, `entity_type`, `entity_id`, `request_id`, `occurred_at`, `before_hash`, `after_hash`, `metadata_json`, `ip_hash`. Append only; no UI/API update/delete route.

Kaizen hook only: reserve `measurement_snapshot` / `improvement_cycle` migrations for post-MVP; do not add screens, scheduling or scoring behavior now.

### Tenancy enforcement

Create `backend/app/security/tenancy.py` with `WorkspaceContext` and one `ScopedRepository`/query factory. Route dependencies construct it only after `require_workspace_access(workspace_id)` has checked membership and program assignment. Repositories cannot take raw arbitrary workspace IDs; their constructor takes the resolved context and applies `Model.workspace_id == context.workspace_id` to every read/update/delete.

In production PostgreSQL, the same request transaction executes `SET LOCAL app.workspace_id = '<uuid>'`; Alembic enables RLS and policies comparing each tenant table to `current_setting('app.workspace_id', true)::uuid`. The application role is not `BYPASSRLS`. This preserves a single request-context enforcement point while providing database defense in depth. SQLite test/dev relies on the repository contract and mandatory cross-tenant negative tests.

DB decision: PostgreSQL 16 target; SQLite only dev/test. PostgreSQL supports concurrent multi-user writes, JSONB/indexes, transactional locking, reliable migrations and RLS. SQLite is retained to keep zero-cost local development. Use Alembic; replace `SQLModel.metadata.create_all()` startup creation with `alembic upgrade head` in deployment/bootstrap. Never auto-migrate schema on production app startup.

## 4. API surface (`/api/v1`)

Conventions: JSON API, Pydantic request/response schemas, RFC 7807-like stable errors, cursor pagination for lists, `Idempotency-Key` for document generation/submission, request correlation ID. All routes require Entra access token unless explicitly listed as local-dev-only. Workspace ID in path is verified against token-derived membership; backend never trusts a body/query workspace ID.

### Identity and workspaces
- `GET /me` — any authenticated user; returns normalized identity, memberships and permitted workspace IDs.
- `GET /workspaces` — authenticated; own memberships only.
- `POST /workspaces` — Consultant or WorkspaceAdmin; creator becomes WorkspaceAdmin; audit.
- `GET/PATCH /workspaces/{workspaceId}` — member / WorkspaceAdmin; PATCH audited.
- `GET/POST/PATCH /workspaces/{workspaceId}/members` — WorkspaceAdmin only; invitation/provisioning has no privilege escalation; audit.

### Program and use-case slice
- `GET/POST /workspaces/{workspaceId}/programs` — member list; Consultant/Admin create.
- `GET/PATCH /workspaces/{workspaceId}/programs/{programId}` — member + program assignment; Consultant/Admin edit; Sponsor read; Contributor assigned read.
- `POST /.../programs/{programId}/members` — Consultant/Admin; assignment scoped and audited.
- `GET/POST /.../programs/{programId}/use-cases` — assigned member list; Consultant/Admin create, Contributor only when assigned and policy permits.
- `GET/PATCH /.../use-cases/{useCaseId}` — assigned visibility; Consultant edit base metadata; Contributor restricted to assigned fields; status transitions only through dedicated actions.

### Wizard and assessment slice
- `POST /.../use-cases/{id}/assessments` — Consultant; creates draft version from template.
- `GET /.../assessments/{assessmentId}` — assigned member.
- `PUT /.../assessments/{assessmentId}/answers/{questionKey}` — Consultant or assigned Contributor; server validates step/schema, field authorization and draft state; records `captured_for` in interview mode.
- `POST /.../assessments/{assessmentId}/validate-step/{step}` — assigned editor; deterministic required/conditional validation response.
- `POST /.../assessments/{assessmentId}/submit` — Consultant only; validates all eight steps, snapshots inputs, transitions atomically to Submitted.
- `POST /.../assessments/{assessmentId}/kickstart` — Consultant only; optional LLM; rate-limited, content is marked `ai_assisted`, no automatic overwrite.

### Value and score slice
- `PUT /.../use-cases/{id}/value-assessment` — Consultant; validates bounded numeric values and recalculates server-side.
- `POST /.../use-cases/{id}/scorecards/recalculate` — Consultant; deterministic score/card/category calculation.
- `POST /.../use-cases/{id}/scorecards/override` — Consultant; requires dimension, value 1–5 and non-empty reason; creates new scorecard version/audit event.
- `GET /.../use-cases/{id}/scorecards` — assigned member; Sponsor read-only.
- `GET /.../portfolio` — workspace member, limited to assigned programmes for Contributor; query filters permitted programme/status/department/risk; response contains matrix points only from authorized use cases.

### Review, approval and documents
- `POST /.../use-cases/{id}/comments` and `GET .../comments` — assigned member; append-only author identity.
- `POST /.../use-cases/{id}/reviews` — Consultant submits recommendation (`Go|Pilot|Defer|Reject`).
- `POST /.../reviews/{reviewId}/request-changes` — Sponsor; status transition and audit.
- `POST /.../reviews/{reviewId}/approve|reject` — Sponsor assigned to programme; only one terminal decision per review, idempotent replay behavior; audit.
- `POST /.../use-cases/{id}/documents` — Consultant; accepts `ExecutiveBrief|PilotCharter|AMOAImplementationPlan`, language/format and source version. Approved source/review requirement for Executive Brief and Pilot Charter PDF.
- `GET /.../documents` / `GET .../documents/{id}/versions` — assigned member; Sponsor can download approved version only.
- `GET /.../document-versions/{id}/download` — authorization first, then stream/private signed URL; no public storage URL.
- `POST /.../documents/{id}/approve` — Sponsor; changes document status only, never its content.
- `GET /.../audit-events` — WorkspaceAdmin and Consultant, paginated/read-only; redact sensitive payload fields.

## 5. Wizard, scoring and portfolio contract

### Eight mandatory wizard steps

0. Optional Kickstart: strategic objective, target process, main friction, department/population, critical regulatory/security/SLA constraints. Output: editable problem statement, AI solution, KPI proposals, value hypotheses, risks, missing information; every inserted value has `source=ai_assisted`.

1. Context and process: target process, team, current actors, trigger, principal steps, systems, volume/frequency, duration per occurrence. Required: process, team, trigger, at least one step/system, volume and duration. Output: simplified process map.
2. Problem and friction: precise problem, delay/cost/risk causes, error points, missing knowledge, cost of inaction, reason now, supporting evidence. Required: problem, one quantified or explicit qualitative impact, reason now. Output: evidenced problem statement.
3. Intended AI solution: task performed by AI, inputs, expected outputs, autonomy (`assist|recommend|execute_with_approval`), mandatory human validation, languages, prohibited behavior. Required: task/input/output/autonomy/human validation/prohibited behavior. `autonomous` is not an MVP option for impactful decisions.
4. Business value: annual/monthly volume, current minutes/transaction, expected minutes saved, hourly/transaction cost, error rate, expected error reduction, error cost, revenue/capacity impact, annual solution cost, time-to-impact, primary KPI and target. Required: annualized volume, one value lever, cost estimate, KPI and hypothesis confidence. Formulae remain deterministic:
   - `Annual Time Value = annual_volume × time_saved_hours × hourly_cost`
   - `Error Avoidance = annual_volume × error_reduction_rate × average_error_cost`
   - `Gross = time + error avoidance + revenue/capacity`
   - `Net = gross − estimated_annual_cost`
5. Data readiness: sources, availability, type (`structured|document|multimodal`), quality 1–5, owner, pilot accessibility, personal/sensitive data flags, needed connectors. Required: at least one source/owner, availability, quality, accessibility and sensitivity declaration. Output: gaps and data-feasibility evidence.
6. Technical and operational readiness: systems/integrations, accepted deployment environment, latency/availability, team skills, support owner, training, dependencies, effort/investment. Required: environment, support owner, one dependency/none declared, effort band. Output: readiness/dependency list.
7. Risk and governance: bad-answer impact, affected-person decision flag, explanation requirement, human review, data egress restrictions, required logs/audit, access model, compliance constraints. Required: impact level, human-validation policy, data boundary, access model, risk owner. Output: `Low|Medium|High|Critical` risk profile. High/Critical requires explicit mitigation before submission; a person-impacting decision requires human validation.
8. Review and submission: rendered immutable summary of 1–7, value, scorecards, risks, hypotheses, missing information, preliminary recommendation. Required: all blocking validation passed, a recommendation, Sponsor identified, success KPI, accessible data source and accepted risk for `Go/Pilot`. Actions: save draft, request information, submit for review.

AI Case Processing is a conditional template pack, not a ninth wizard step. When selected, require dossier type, volume, documents per dossier, mandatory documents, extracted fields, inconsistency checks, next action, SLA, human validation level, cost of poor/incomplete processing, and personal/medical/financial data flags.

### Priority score and scorecards

Decision: default weights are versioned workspace configuration, seeded from the existing engine: Business Value 0.25, Current Friction 0.15, Data Feasibility 0.15, Technical Feasibility 0.15, Adoption 0.10, Risk & Governance 0.20. The API validates six dimensions exactly, score range 1–5, non-empty justification/confidence, and weights total exactly 1.00.

`PriorityScore = round(sum(dimension_score × weight), 3)` on the 1–5 scale. Changing a score or configuration creates a new scorecard version; manual override is consultant-only and must include a reason. The UI displays the formula, input snapshot and confidence, never a black-box recommendation.

Scorecard outputs:
- Value: gross/net estimate, currency, KPI target, value confidence, hypothesis list.
- Readiness: data, technical, operational/adoption; `readiness_average = mean(data, technical, adoption)`.
- Risk: 1–5 controllability/readiness score plus explicit `Low|Medium|High|Critical` risk profile. Lower controllability cannot be silently compensated by gross value.

Portfolio matrix contract:
- X axis: feasibility/readiness = average of Data Feasibility, Technical Feasibility and Adoption (1–5).
- Y axis: Business Value score (1–5); show net value as tooltip, not the axis, to preserve comparable scale.
- Bubble size: effort/investment band/value from step 6.
- Bubble colour: risk profile.
- Category: Quick Win when value >=4, readiness >=3.8 and governance >=3; Strategic Bet when value/priority is high but readiness <3.8; Foundation when readiness <3.0; Reject when priority <2.8 and governance <=2; otherwise Defer. Render the rule explanation alongside the category.

## 6. Documents and PDF generation

Decision: generate documents server-side from a versioned domain snapshot using Jinja2 HTML templates and WeasyPrint PDF rendering. Store both the rendered Markdown and PDF artifact as independent immutable `document_version` records.

Why: HTML/CSS templates provide maintainable French typography, print layout, tables, page headers/footers and branded artefacts. The server retains a reproducible input snapshot and does not expose document data/storage access to the static UI. ReportLab is rejected for MVP because it produces more imperative, less maintainable layout code; browser-only PDF is rejected because it is non-reproducible and leaks authorization/data responsibility to the client.

Create templates under `backend/app/documents/templates/fr/`:
- `executive_brief.html.j2` and `pilot_charter.html.j2`; Markdown counterparts if markdown output is retained.
- Reuse the existing French Executive Opportunity Brief structure. Pilot Charter must contain scope, pilot users, source/environment, human-in-the-loop rule, KPI baseline/target, timeline, dependencies, owner, risk controls, test plan, go/no-go and scale conditions.

Generation rules:
- Generate only from a locked assessment/scorecard snapshot. Executive Brief and Pilot Charter PDF require an approved review; draft Markdown may be generated before approval but is conspicuously labelled Draft.
- Every document separates `Facts`, `Hypotheses to validate`, and `Recommendations`; scores/calculations list their source version.
- AI-derived paragraphs bear `AI-assisted — human review required` and their source fields/section IDs are in `ai_assisted_sections_json`.
- Regeneration increments version and creates new immutable storage keys. An approved version is never overwritten; superseding it requires a new assessment/review/document version.
- Compute SHA-256 after rendering; include document version, generated date, author and approval state in footer/metadata.

## 7. LLM abstraction

Decision: remove `backend/services/kickstart.py`, `kickstart_service.py`, and `kickstart_langchain.py` after migration to one domain-facing abstraction:

```text
backend/app/llm/
  contracts.py       # LlmProvider protocol; typed request/result
  service.py         # AiAssistanceService, business policy and audit
  prompts/kickstart_fr.py
  providers/openai.py
  providers/azure_openai.py
  providers/anthropic.py
  schemas.py         # Pydantic output models
```

Default: direct OpenAI SDK provider using a configured server-side key. Azure OpenAI and Anthropic implement the same `LlmProvider` protocol and are selected by `LLM_PROVIDER`; keys/managed identities remain backend/runtime-only. Do not make LangChain a required abstraction layer for this bounded MVP; it adds version churn and hides provider failure semantics.

Input policy: typed, size-bounded and PII-safe summary inputs only; reject direct credentials/secrets and disclose that client data must be authorized for provider processing. Output policy: require provider structured JSON/schema where supported; parse with strict Pydantic models; validate allowed enums, max lengths and required arrays; on invalid response retry once with a repair prompt, then return a safe actionable error—not invented content.

AI-assisted MVP operations: Kickstart only, and optionally executive-summary wording. Deterministic operations: required-field validation, business-value formulas, weighted score/category, state transitions, approval, access control, document source snapshots and PDF rendering. AI never approves, assigns a final score, mutates answers without explicit user acceptance, or determines access.

Log provider/model/template version, input/output hashes, latency, token/cost metadata and outcome status in audit/LLM telemetry; do not persist raw sensitive prompts/responses by default. Rate-limit by workspace/user and enforce timeouts/circuit-breaking.

## 8. Security and operational controls

Top risks and mandatory mitigations:
1. Cross-workspace IDOR: token-derived membership, scoped repository, PostgreSQL RLS, no unscoped `session.get`, and two-workspace negative tests for every resource family.
2. Forged/misvalidated Entra tokens: JWKS signature + issuer/audience/tenant/scope/time validation; allowlisted algorithms; cache JWKS with rotation; reject ID tokens and unknown issuers.
3. Role escalation and stale access: Entra top-level role plus DB membership intersection; server-side role checks on every mutation; membership revocation effective on next request; audit member/role changes.
4. Static-client/XSS token theft: CSP, no secrets in `NEXT_PUBLIC_*`, avoid unsafe HTML, sanitize markdown preview, strict dependency updates, short-lived access tokens; Electron isolation/preload allowlist.
5. LLM data leakage/prompt injection: minimum contextual summary, no tools/agent execution, typed output, workspace policy flag, provider key server-side, no customer training consent by default, content/log redaction.
6. Document leakage/tampering: private object storage, API-authorized download, immutable version/object key/checksum, no public bucket, approved artifacts write-protected.
7. Abuse/availability: per-IP and per-subject rate limits, tighter LLM/PDF limits, body size/time limits, pagination, structured errors, request IDs and health/readiness endpoints.
8. Dev-mode exposure: startup fail-closed guard, loopback-only origins/db, release build omission, CI production-config test.

CORS: exact configured web origin(s); methods/headers limited to API requirements; credentials false for Bearer-token API unless a later cookie flow is deliberately introduced. Never use `allow_origins=['*']` with credentials.

Audit: append-only security/business events include sign-in identity seen, membership changes, create/update/submit, score override, review/approval, document generation/approval/download and LLM invocation metadata. Avoid raw PII or access token capture; access is privileged and paginated.

Observability: JSON logs with request ID/workspace ID hashed or controlled; OpenTelemetry traces across API/DB/LLM/PDF; metrics for auth failures, authorization denials, cross-tenant test results, errors/latency, document/LLM success, token/cost and migration version. Alert on auth/JWKS failure bursts, RLS violations, document failures and LLM spend/error thresholds. Back up PostgreSQL and object storage; periodically restore-test.

## 9. Delivery plan: independently shippable slices

All implementation work goes through Coder/Copilot. Do not mix it with the concurrent `web/src/app/page.tsx`/`electron-app` edits; first establish a clean handoff/branch and inventory untracked artefacts. Each slice requires reviewable API/OpenAPI changes, migration, tests and a short evidence record.

### S1 — Repository and delivery foundation (qa-sec review: no; sre: no)
Create tracked backend/electron source boundaries, `.gitignore`, Python/Node lockfile policy, `.env.example` without values, formatting/lint scripts, Docker development topology and GitHub Actions. Remove only confirmed generated/recovery artefacts; preserve active coder changes.

Acceptance: clean clone can run existing tests; CI runs `pytest -q`, web lint/typecheck/build and package checks; no database/log/node_modules/output/backup artefact can be committed. Validate with Git status/diff and CI.

### S2 — Production data/auth foundation (qa-sec review: required before public exposure; sre: PostgreSQL/secret deployment preparation)
Add Alembic, SQLModel domain tables, PostgreSQL RLS migrations, SQLite local test path, workspace scoped repository, audit event writer, Entra JWT validation and fail-closed dev auth mode. Replace startup `create_all`; do not retain unauthenticated old routes.

Acceptance: Entra-valid request reaches `/me`; invalid issuer/audience/scope and role-less user get 401/403; synthetic dev identity works only local/test and production guard refuses to start; member of workspace A cannot enumerate/read/mutate workspace B by altered IDs. Pytest covers all cases.

### S3 — Workspace/program/use-case lifecycle (qa-sec review: authorization-focused review; sre: no)
Implement memberships/program assignments, CRUD API and static UI routing for login → workspace → program → use case. Migrate or discard existing `Client/Project` data only through an explicit local-dev migration script; do not claim production migration compatibility for the untracked schema.

Acceptance: Consultant creates workspace/program/use case; Sponsor sees only assigned program; Contributor sees only assigned use case; all mutations audited. Playwright dev-mode happy path plus API negative tests pass.

### S4 — Eight-step persisted wizard (qa-sec review: no; sre: no)
Create seed versioned questionnaire, assessment/answer/hypothesis APIs and React wizard routes/components. Implement debounced autosave, resume, visible progress, step validation, interview attribution and AI Case Processing conditional questions. Coordinate integration with the current page recovery owner.

Acceptance: consultant completes/reopens eight steps without loss; invalid required/conditional field has actionable error; assigned contributor can answer but cannot edit prohibited fields; interview answer records actual capture actor/subject. Pytest schema/service tests and Playwright resume test pass.

### S5 — Deterministic value and scoring (qa-sec review: no; sre: no)
Move existing framework scoring/value functions behind API service; add score/value tables, configuration version and UI scorecards. Keep calculation entirely server-side.

Acceptance: formula/rounding tests cover valid edges, missing dimension, weights not totaling 1, score bounds and manual override reason/version history; score changes update category/matrix response deterministically. UI exposes inputs, assumptions and confidence.

### S6 — Portfolio matrix (qa-sec review: authorization regression review; sre: no)
Implement portfolio query/filter API and matrix/list UI with specified axes, bubble semantics, category explanation and permission-aware result set.

Acceptance: matrix includes only permitted use cases; filters work server-side; a user cannot infer another workspace's title/count through totals or errors. Playwright verifies approved journey reaches a populated portfolio.

### S7 — Review, comments and approval (qa-sec review: required; sre: no)
Implement review state machine, append-only comments, Sponsor-only terminal decision, changes-request loop and audit controls.

Acceptance: Consultant can submit; Sponsor comments/approves/rejects/requests change; Contributor cannot approve; duplicate approval/replay is safe; approved assessment cannot be edited in place. API state-machine and authorization-negative tests pass.

### S8 — Versioned documents and PDFs (qa-sec review: required for storage/access; sre: object storage/configuration work)
Implement snapshot document generator, French Executive Brief/Pilot Charter templates, WeasyPrint worker/service, private storage adapter, metadata/version/download APIs and document centre UI.

Acceptance: approved use case produces both French PDFs; PDF contains snapshot/version/status/facts-hypotheses-recommendations and AI marker; approved document content cannot be overwritten; unauthorized download is denied; checksum/artifact exists. Test template rendering and Playwright download via authorized API.

### S9 — LLM assistance hardening (qa-sec review: required; sre: secret store/egress configuration)
Replace all `kickstart*.py` services with the single provider interface, OpenAI default, strict schemas, redaction/audit/rate limiting and provider failure behavior.

Acceptance: no LLM secret reaches browser/Electron; valid structured output is labelled AI-assisted and remains editable; malformed/provider failure returns safe error without fake content; deterministic MVP continues when LLM is disabled. Contract tests use a fake provider; provider integration test is opt-in and never uses production client data.

### S10 — Electron production shell (qa-sec review: required; sre: no except release hosting origin)
Modernize Electron tooling as needed, load allowed static production app origin, implement main-process MSAL Node loopback auth, token IPC broker, secure cache, navigation policy and signed packaging pipeline for Windows/Linux.

Acceptance: interactive desktop sign-in returns API access token; renderer has no Node access/refresh token; unauthorized external navigation and IPC payload are rejected; packaged build has DevTools disabled. Electron smoke test and manual Entra test evidence required.

### S11 — Release proof and operations (qa-sec final review: required; sre: required)
Provision production config through secret manager, database/RLS, private object storage, TLS/reverse proxy, static hosting and monitoring. Run migration and rollout with backup/rollback procedure.

Acceptance: production smoke journey exactly matches DoD: login → workspace → program → use case → eight steps → value/scores → submit → approve → both PDFs → portfolio; telemetry and backups verified; no dev banner/mode; deployment is HTTPS-only. SRE provides environment evidence; QA-Sec signs off auth/tenancy/document tests.

### Test strategy and CI gates
- Backend: pytest unit tests for formulas/state machines/template schemas; API integration tests on SQLite plus PostgreSQL/RLS test service; token-verification fixtures; two-workspace IDOR matrix for every endpoint group.
- Web: React component tests for wizard validation/autosave; Playwright critical journey using `AUTH_MODE=dev` only under local CI; separate API authz-negative suite.
- Electron: main/preload unit tests plus a packaged/smoke workflow; real Entra UI test is protected/manual or a dedicated non-production tenant.
- GitHub Actions: independent backend, web, Electron and security jobs; dependency review/SBOM, secret scan, `alembic upgrade head` on disposable Postgres, `pytest`, lint/typecheck/static export, Playwright, artifact retention for reports. Required checks block merge. No test may point at production Entra, DB, object store or OpenAI key.

## 10. Open risks requiring owner input (maximum 3)

1. Client identity onboarding. Recommended default: Entra B2B guest invitations in the workforce tenant for MVP; defer External ID until client self-service/social identity is a commercial requirement. Trade-off: controlled onboarding now vs future CIAM convenience.

2. Production hosting baseline. Recommended default: static web + FastAPI container + managed PostgreSQL + private Blob storage on Azure, with Electron as a connected client. Trade-off: small Azure/SRE setup now vs avoiding ungoverned desktop data silos and making collaboration/approvals real.

3. AI data-processing boundary. Recommended default: OpenAI API server-side only, disabled per workspace by default until customer consent/data-processing terms are recorded; offer Azure OpenAI adapter for customers requiring Azure residency. Trade-off: fastest MVP assistance vs procurement/residency flexibility.

No other owner decision is needed to begin S1–S5.
