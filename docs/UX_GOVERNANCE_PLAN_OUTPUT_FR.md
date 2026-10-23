# AVS — AI Governance Plan in the document outputs flow

Status: implementation-ready UX packet
Scope: existing `/studio/use-case?workspaceId={…}&programId={…}&useCaseId={…}` Document Centre only. FR-first. This is a generated client deliverable, not a governance product area.

## 1. Decision, user, and job

**Decision.** Add **Plan de gouvernance de l’IA** as a third document type beside **Note exécutive** and **Charte pilote** inside the existing `DocumentCentre`. The user selects one document type, chooses Markdown or PDF, generates it, reads a sponsor-oriented preview, then exports it. It must not introduce approval gates, operational controls, evidence tracking, audit screens, or a separate governance route.

**Primary user / job.** A Consultant needs to turn the completed use-case inputs into a clear, client-ready governance plan. A Sponsor needs to read the plan, understand the recommended safeguards and ownership, and export it for offline review. The plan is explicitly a draft to validate with Legal/DPO; that notice is informative and never an acknowledgement, approval, or workflow transition.

**Target surface.** The Document Centre rendered from `web/src/features/studio/document-centre.tsx` on the existing use-case route.

## 2. Verified observations (repository evidence)

| Observation | Evidence |
| --- | --- |
| The product has one existing Document Centre in the use-case flow; it already uses `Card`, `CardHeader`, `Badge`, `Button`, `EmptyState`, `Skeleton`, toast and tokenized Tailwind classes. | `web/src/features/studio/document-centre.tsx`; `web/src/components/ui/*.tsx` |
| Current UI shows a separate section per returned document, with Markdown/PDF generation and download; it has no document-type selector or readable preview. | `web/src/features/studio/document-centre.tsx:589-799` |
| The client only recognizes `ExecutiveBrief`, `PilotCharter`, `AMOAImplementationPlan`; FR/EN document labels are local to `document-centre.tsx`. | `web/src/features/api/types.ts:137-139`; `web/src/features/studio/document-centre.tsx:72-95, 140-163` |
| The current backend list and generation service intentionally supports only Executive Brief and Pilot Charter. | `backend/app/documents/service.py:47-49, 70-115` |
| Existing document download returns a blob and filename; neither list nor version response contains preview content. | `web/src/features/api/browser-api-client.ts:532-608`; `backend/app/schemas/document.py` |
| The current service couples PDF eligibility to approved review and exposes document approval. That is existing product behavior, not appropriate as a new governance-plan workflow. | `web/src/features/studio/document-centre.tsx:38-41, 302-319`; `backend/app/documents/service.py:274` |
| Design tokens provide the calm B2B palette, 40 px minimum button height and visible focus ring. | `web/src/app/globals.css`; `web/src/components/ui/button.tsx` |
| The current UI is FR/EN only (`StudioLocale = "fr" | "en"`); no AR locale/RTL system is present in this surface. | `web/src/features/studio/copy.ts`; `web/src/features/studio/document-centre.tsx:29` |

## 3. Prioritized UX issues

| Severity | Issue | Why it matters |
| --- | --- | --- |
| P0 | Governance Plan is not a supported document type or rendered output. | The requested client deliverable cannot be selected, generated, previewed, or exported. |
| P0 | Document Centre has no preview; download is the first readable moment. | A Sponsor cannot assess the generated plan in context before exporting it. |
| P1 | Current document cards conflate generation, status and approval, and PDF is described as approval-dependent. | Reusing that pattern would falsely imply that the Governance Plan itself needs approval or is a governance workflow. |
| P1 | The current two-document loading skeleton and empty copy do not describe selectable output types or Legal/DPO validation. | Empty/loading states would be misleading once a third, advisory deliverable exists. |
| P1 | Generation feedback is a generic busy button/toast only. | Users need an explicit in-progress and completion state for an artifact they may immediately preview/export. |
| P2 | No AR/RTL localization foundation exists in the target surface. | FR-first can ship, but Arabic is a future dependency rather than a claim of readiness. |

## 4. Recommended interaction and visual design

### 4.1 Information architecture and flow

Keep the single `DocumentCentre` card. Replace the repeated full-width document sections with a **selection → output detail** arrangement:

```text
Centre documentaire
Préparez des livrables à partir du cas d’usage et de ses informations validées.

[ Sélectionner un livrable ]
  (•) Note exécutive              [Prêt / Dernière version]
  ( ) Charte pilote               [Prêt / Dernière version]
  ( ) Plan de gouvernance de l’IA [Nouveau]

┌ Details for selected document ──────────────────────────────────────┐
│ Plan de gouvernance de l’IA        Brouillon v1                     │
│ Recommandations de gouvernance pour ce cas d’usage.                 │
│                                                                      │
│ [Information] À valider avec votre direction juridique et votre DPO.│
│ Ce document formule des recommandations; il ne vaut pas avis légal. │
│                                                                      │
│ Format de génération:  (•) Markdown  ( ) PDF  [Générer le document]│
│                                                                      │
│ Aperçu                                                              │
│ Plan de gouvernance de l’IA                                         │
│ 1. Synthèse pour la direction                                       │
│ 2. Périmètre, finalité et acteurs                                   │
│ 3. Données et limites d’usage                                       │
│ 4. Supervision humaine et escalade                                  │
│ 5. Risques, mesures recommandées et décisions à confirmer           │
│ 6. Plan de validation juridique / DPO                               │
│                                                                      │
│ [Télécharger .md]  [Télécharger PDF]  [Historique des versions]     │
└──────────────────────────────────────────────────────────────────────┘
```

1. The list is a single-select radio group, initially selecting the first eligible or most recently used document type. It is not a multi-select batch generator.
2. Each option is a compact existing-card treatment: title, one-line purpose, and a non-colour-only status label (`Nouveau`, `Brouillon v2`, `Prêt à générer`). Selecting an option updates the detail panel without a route change.
3. Select **Plan de gouvernance de l’IA** to expose its description, notice, format choice, latest version metadata, preview and exports. The legal/DPO notice is directly below its title and before any generation/export action.
4. User selects one format and activates **Générer le document**. On success, update only the selected output detail, focus its version/status summary, announce completion, and show the generated preview. Do not redirect, request approval, or change use-case/review status.
5. **Aperçu** displays the selected current version. It is read-only, visibly labelled `Aperçu — version {n} · {format}` and has a secondary **Ouvrir l’aperçu complet** control when inline content is truncated. Preview is for reading, not editing.
6. Export buttons are explicit per artifact: **Télécharger le fichier Markdown** and **Télécharger le PDF**. They download the selected/current immutable version and retain existing native/desktop save behavior.
7. Put version history behind a semantic disclosure (`<details>/<summary>` or an existing accessible disclosure primitive), collapsed by default. It is supporting information, not the primary task.

### 4.2 Governance Plan content for sponsor readability

The generated output and preview should use these FR headings, in this exact sponsor-readable order. Keep paragraphs short, lead with decisions, and mark incomplete inputs as `À confirmer` rather than inventing content.

1. `Synthèse pour la direction` — intended use, expected value, risk level, named owner.
2. `Périmètre et finalité` — use case, users/affected people, intended and prohibited uses.
3. `Données et limites d’usage` — data categories, sensitivity, sources, access boundary, retention questions to confirm.
4. `Rôles et supervision humaine` — business owner, system/data owner where known, human review point, escalation path.
5. `Risques et mesures recommandées` — plain-language risk / recommendation pairs; do not imply controls are implemented.
6. `Décisions à confirmer` — concise owner-oriented checklist of unanswered legal, DPO, security, or operational decisions.
7. `Prochaines étapes de validation` — `À valider avec la direction juridique et le DPO avant mise en œuvre.`
8. `Sources et limites` — assessment/scorecard version, generated date, author, `Sections assistées par IA` where relevant.

Do not use `approved`, `compliant`, `certified`, `control evidence`, or a green compliance state in this document. A document version can be generated and exported; it is not proof of legal or regulatory compliance.

### 4.3 FR product copy (ship)

| Element | FR copy |
| --- | --- |
| Selector label | `Sélectionner un livrable` |
| Type title | `Plan de gouvernance de l’IA` |
| Type description | `Recommandations de gouvernance adaptées à ce cas d’usage.` |
| Notice label | `À valider avec le juridique et le DPO` |
| Notice body | `Ce document propose un cadrage de gouvernance. Il doit être revu et adapté par votre direction juridique et votre DPO avant toute mise en œuvre.` |
| Format label | `Format de génération` |
| Primary action | `Générer le document` |
| In progress | `Génération du plan de gouvernance de l’IA…` |
| Preview label | `Aperçu` |
| No version yet | `Aucune version générée` |
| No version detail | `Choisissez un format pour produire un premier brouillon à partir du cas d’usage.` |
| Preview unavailable | `L’aperçu n’est pas disponible pour le moment. Vous pouvez télécharger le fichier dès que la génération est terminée.` |
| Markdown export | `Télécharger le fichier Markdown` |
| PDF export | `Télécharger le PDF` |
| Success toast | `Plan de gouvernance de l’IA généré` |
| Generation error | `Le plan n’a pas pu être généré. Vos données de cas d’usage n’ont pas été modifiées.` |

EN parity should be added in the same local copy object: `AI Governance Plan`; `To validate with Legal and the DPO`; `This document proposes a governance framing. It must be reviewed and adapted by your Legal team and DPO before implementation.` Arabic/RTL is not in scope until AVS exposes Arabic locale resources; then use logical CSS properties and mirror option/action order without changing document language direction.

## 5. States and responsive behavior

| State | Required behavior |
| --- | --- |
| Initial / no generated version | Show all three selector options. In selected detail show the notice, format radios and generation CTA. Do not use the global `Aucun document généré` empty state because output selection remains actionable. |
| Loading list | Keep the `CardHeader`; use three `aria-hidden` selector skeleton rows and a detail skeleton. Announce `Chargement des livrables…` once with `aria-live="polite"`. |
| Generating | Disable only the selected output’s format choice and generation CTA; set `aria-busy="true"` on its detail panel and replace CTA text with the in-progress copy. Other document options remain selectable but their actions must not start a second request if the API only supports one in-flight request. |
| Generated successfully | Move focus to the selected version summary (`tabIndex={-1}`); announce type, version and format with `role="status"`; render fresh preview and enable its matching export. |
| No preview returned / unsupported preview format | Preserve version metadata and exports; show the preview-unavailable empty state inside the preview region, not an error page. |
| Generation error | Preserve selection and user-selected format; show a non-destructive inline `role="alert"` with server detail when safe plus retry CTA. Do not clear existing versions or imply input loss. |
| Load error | Retain existing `EmptyState` retry pattern, titled `Impossible de charger les livrables.` Do not show stale or fabricated eligibility. |
| Export error/cancel | Keep the preview; announce failure/cancel via toast/status only. Never mark the artifact unavailable after a local save dialog is cancelled. |
| Permission denied | Render an explanatory `EmptyState` / alert: `Vous pouvez consulter les livrables auxquels votre rôle donne accès.` Omit generation CTA based on backend capability, not just client role. Existing business permissions need a separate API capability field before this is trustworthy. |
| Narrow mobile (<640 px) | Selector options stack full width; format radios stack; primary CTA full width; export actions stack in source order; preview remains one column. No horizontal scroll or clipped SHA/metadata. |
| Desktop (>=1024 px) | Use a 4/8 or 3/9 grid only within the existing card: compact selector rail, wide detail/preview panel. Keep the legal/DPO notice at the top of detail, never in a sidebar below the fold. |

## 6. Accessibility requirements

- Use a native `<fieldset><legend>Sélectionner un livrable</legend>` with one radio input per document type. The visible card label activates its radio; arrow keys change choice natively.
- The selected detail panel uses `aria-labelledby` connected to its document title; switching selection updates a short polite status (`Plan de gouvernance de l’IA sélectionné`). Do not move focus simply for changing a radio.
- Use native radio inputs for format selection with a programmatic label. The CTA has a specific accessible name, for example `Générer le Plan de gouvernance de l’IA au format PDF`.
- A loading/generating region uses `aria-busy`; completion uses `role="status"`; errors use `role="alert"`. Do not use toast as the only error or completion signal.
- The legal/DPO notice is persistent text with an information icon only as supplementary decoration. Its meaning cannot depend on colour or icon.
- Preview uses semantic headings (`h2` document title then `h3` sections), lists and tables with headers. Provide a real text alternative for any generated visual. Markdown must be sanitized/allowlisted before rendering; never inject raw generated HTML.
- Preview iframe/object, if used for PDF, needs a unique `title` naming document and version. Offer the direct PDF download immediately next to it.
- Visible keyboard focus must retain the existing `--studio-focus` 2 px ring and meet non-text contrast requirements. Disabled/unavailable actions must expose explanatory text using `aria-describedby`; do not rely on opacity alone.
- Meet WCAG 2.2 AA: semantic labels, 4.5:1 text contrast, 3:1 component/focus contrast, logical tab order, no keyboard trap, and target size at least the existing 40 px minimum.

## 7. Implementation handoff for Coder (English)

### Reuse, do not create a product area

- Extend `web/src/features/studio/document-centre.tsx`; retain `Card`, `CardHeader`, `Badge`, `Button`, `EmptyState`, `Skeleton`, `useToast`, existing download bridge and `DocumentCentre` route placement.
- Keep the new type local to the existing output flow. Do not add a sidebar entry, `/governance` route, review/approval action, audit/control dashboard, or a checkbox that records Legal/DPO acceptance.
- Preserve immutable artifact/version behavior. The document is a generated deliverable; its notice is editorial disclosure only.

### Known affected paths

| Area | Paths / change |
| --- | --- |
| Frontend document model | `web/src/features/api/types.ts`: add `AIGovernancePlan` to `DocumentType`; introduce response capability/preview fields only after backend contract is agreed. |
| Frontend transport | `web/src/features/api/browser-api-client.ts`: keep existing generate/download path; add a preview retrieval method only with the backend contract below. |
| Frontend UI + copy | `web/src/features/studio/document-centre.tsx`: selector/detail composition, FR/EN copy, notice, generation status, preview and accessible export labels. |
| UI primitives/tokens | Reuse `web/src/components/ui/{card,button,badge,empty-state,skeleton}.tsx` and `web/src/app/globals.css`; do not add one-off colours. Add a disclosure primitive only if no accessible existing pattern is available. |
| Backend enum/schema | `backend/app/db/models/lifecycle.py`, `backend/app/schemas/document.py`: add `AIGovernancePlan` and schema support. |
| Backend listing/generation | `backend/app/documents/service.py`: include type in the supported list, generation dispatch, label/template slug, eligibility; explicit decision required to remove the current review/approval prerequisite only for this document type. |
| Output rendering | `backend/app/documents/templates/fr/`: add Markdown/PDF source templates following the section order in §4.2 and place the legal/DPO notice in the rendered document. |
| Tests | `web/tests/wizard.e2e.spec.ts`, `backend/tests/test_documents_api.py`, document render samples: add FR selection, generation, preview, Markdown/PDF exports, legal/DPO notice, error and keyboard assertions. |

### API and backend gaps to resolve before UI implementation

1. **Document type:** Current supported list returns only two types, so the list must include a placeholder/eligibility response for `AIGovernancePlan`; otherwise a selector cannot truthfully show it.
2. **Capabilities:** Current client infers availability from eligibility and role. Return server-authoritative `can_generate`, `can_download`, and reasons per type/version, particularly if the Governance Plan has different eligibility from legacy document approvals.
3. **Preview:** No preview data/API exists. Preferred contract: `GET .../document-versions/{versionId}/preview` returns an authorized, sanitized structured/Markdown preview with `version_id`, `format`, `content`, `is_truncated`, and `download_available`. Same authorization as download; do not expose storage keys or public artifact URLs. PDF can render in a titled blob iframe only after an authorized fetch.
4. **Generation state:** Current POST is synchronous. If rendering can exceed a short interaction, return a durable job state (`queued|running|succeeded|failed`) and poll/subscribe; do not fabricate progress. If it remains synchronous, UI may only show indeterminate busy state.
5. **No Governance Plan approval workflow:** Decide and implement this explicitly server-side. For this type, `can_generate_pdf` must not be coupled to a document approval state. It may still require completed/locked inputs, but the API must return that reason in plain language.

## 8. Acceptance criteria and validation

### Acceptance criteria

1. On the existing use-case Document Centre, a keyboard user can select **Note exécutive**, **Charte pilote**, or **Plan de gouvernance de l’IA** through a labelled native radio group; no new route or navigation item appears.
2. Selecting the Governance Plan shows the FR title, explanatory description, persistent Legal/DPO notice, format choice and a generation CTA. No approval, evidence, audit, control-tracking, or compliance-certification UI is present for this deliverable.
3. A generated Governance Plan exposes an in-context, sponsor-readable preview with the seven required sections; missing inputs render as `À confirmer`, never fabricated facts.
4. The user can export the current immutable version as Markdown and PDF with explicit accessible labels. Export errors/cancellation do not destroy preview or document state.
5. Initial, loading, generation, success, preview-unavailable, error, permission-denied and narrow-mobile states match §5.
6. Generation state announces progress and result without relying only on colour/toast; error is programmatically associated with the affected action.
7. Keyboard traversal works through selection, format radios, generate, preview/disclosure and exports; focus is visible and lands on fresh version summary after a successful generation.
8. FR is complete. EN strings are added in the same locale object. AR/RTL is recorded as unsupported/not shipped, not silently broken.
9. Existing Executive Brief and Pilot Charter generation/download behavior remains intact.

### Validation method

- Unit test type labels, selector default/changes, generation busy/error/success states and copy completeness.
- Playwright at desktop and 375 px: choose Governance Plan via keyboard, choose Markdown, generate (mock/API fixture), confirm status announcement and preview headings, export Markdown/PDF, exercise server error and permission fixture.
- Run axe on initial, selected, generating and generated states; manually verify native radio arrow navigation, visible focus, screen-reader announcements, text zoom at 200%, and no horizontal scroll at 320 px.
- Backend/API tests confirm the third type is listed, only authorized roles can generate/download, output is immutable/versioned, preview obeys the same authorization, and Governance Plan generation does not create an approval workflow.

## 9. Out of scope

- Legal/DPO approval capture, review queues, evidence/control register, runtime enforcement, compliance certification, audit log UI, regulatory decision engine, and a standalone Governance workspace.
- Editing the generated plan inline. A revised plan is a regenerated immutable version sourced from updated use-case inputs.
- Arabic UI/content until AVS implements an Arabic locale and RTL baseline.
