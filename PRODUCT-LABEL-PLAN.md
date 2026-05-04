# ClearEdge Label Creator – Product Plan (May 4, 2026)

## 1) Current reality (what works vs. what blocks production)

### Working foundations
- FastAPI backend exists for both enterprise pipeline (`app/main.py`) and a simpler upload flow (`simple_app.py`).
- PDF extraction, OCR fallback, structured schema validation, and a label generator stub are already in place.
- Branded frontend exists (Netlify static app) with upload UX and generated-label download flow.

### Key blockers to “actually works”
1. **Architecture split/confusion**: two API apps with overlapping goals (`app/main.py` vs `simple_app.py`) causes deployment and routing mismatch.
2. **Frontend/API contract drift**: Netlify frontend calls `/api/generate-label`, but core app routes focus on `/ingest`, `/extract`, `/validate`, etc.; contract is not unified.
3. **Label engine is still a stub**: output consistency, print fidelity, and compliance layout rules are not fully productionized.
4. **No deterministic compliance gate in UI flow**: user can generate without clear pass/warn/fail workflow and remediation guidance.
5. **Weak productized “brand system”**: ClearEdge visual tokens (purple header, hierarchy, typography, icon style) are not centralized as reusable template config.

---

## 2) Product direction for ClearEdge

Build **one reliable “Label Creator API + Web App”** optimized for operations staff:
- Upload SDS/TDS PDFs.
- Review extracted facts + confidence + source snippets.
- Resolve flagged fields.
- Generate print-ready labels (PDF/SVG) in approved ClearEdge templates.
- Store audit package for traceability.

**Primary success metric:** “first-pass compliant label rate” and “time-to-label” per product.

---

## 3) Implementation plan (phased)

## Phase 0 — Stabilize foundations (1 week)
- Choose a single runtime entrypoint for production (recommend converging on `app/main.py` and porting simple upload endpoints into it).
- Define one versioned API contract: `/api/v1/...`.
- Add OpenAPI examples for request/response objects used by frontend.
- Add health/readiness checks with dependency diagnostics (Gemini key present, OCR tool available, template registry loaded).

**Exit criteria:** one deployed backend, one contract doc, frontend successfully calls the same environment.

## Phase 1 — Unify frontend + backend contract (1–2 weeks)
- Implement backend endpoints expected by UI:
  - `POST /api/v1/labels/generate`
  - `GET /api/v1/labels/{id}` metadata
  - `GET /api/v1/labels/{id}/download`
- Return structured result object:
  - `extracted`, `validation`, `label`, `audit`, `warnings`, `errors`.
- Update `netlify-frontend/app.js` to consume this schema and render:
  - extraction confidence badges,
  - compliance status pills (Pass/Warning/Fail),
  - actionable fixes.

**Exit criteria:** end-to-end happy path from upload to downloadable PDF with explicit validation state.

## Phase 2 — Brand-quality label templates (1–2 weeks)
- Replace stub generator with template system:
  - `template_id` (e.g., `clearedge_pail_v1`, `clearedge_drum_v1`),
  - print dimensions + bleed/safe areas,
  - brand token map (colors, typography, spacing, icon scale).
- Add deterministic text wrapping, overflow handling, and truncation rules.
- Add QR area + lot/batch/date placeholders.
- Snapshot tests for rendered SVG/PDF against golden outputs.

**Exit criteria:** repeatable, visually consistent, print-ready labels matching ClearEdge brand rules.

## Phase 3 — Compliance UX and data integrity (1 week)
- Add “must-fix before generate final” policy:
  - hard failures block final output,
  - warnings allow draft but not production export unless approved.
- Surface evidence traces (which SDS page/quote drove each extracted field).
- Add manual override workflow with reason logging and operator attribution.

**Exit criteria:** auditable decision trail for every label field and override.

## Phase 4 — Ops hardening + scale (1 week)
- Background job queue for long PDF/OCR tasks.
- Idempotency keys for repeat submissions.
- Retry/error taxonomy and user-friendly failure messages.
- Observability dashboard: throughput, extraction failure rate, validation failure rate, mean generation time.

**Exit criteria:** reliable performance under concurrent usage with clear operator telemetry.

---

## 4) Recommended target architecture

- **Backend:** FastAPI monolith with clear modules (`ingest`, `extract`, `validate`, `render`, `audit`).
- **Storage:** local temp for transient files + Drive/object storage for final artifacts and audit packages.
- **AI extraction:** Gemini client with strict schema validation + repair + confidence fields.
- **Rendering:** template-driven SVG renderer then PDF export; deterministic fonts and layout rules.
- **Frontend:** static Netlify app or lightweight React/Vue refactor once API stabilizes.

---

## 5) Immediate backlog (next 10 tasks)

1. Create API contract doc (`docs/api-v1-label-creator.md`).
2. Add `/api/v1/labels/generate` endpoint in canonical backend.
3. Move/reuse logic from `simple_app.py` into canonical backend service layer.
4. Standardize response payload schema with `status`, `warnings`, `errors`, and `artifacts`.
5. Add frontend environment config for API URL (no hardcoded production URL).
6. Build validation status panel in frontend with rule IDs.
7. Implement template registry and `template_id` selection.
8. Add 5 golden-file snapshot tests for label rendering.
9. Add structured logging with request correlation IDs.
10. Add operator-facing error codes and help text.

---

## 6) ClearEdge brand guidance translated into product requirements

- **Trust & compliance first:** always show validation state before download CTA.
- **Industrial clarity:** prioritize readable hazard hierarchy over decorative elements.
- **Purple brand anchor:** keep header and key CTA accents on brand purple while preserving OSHA/DOT color semantics for safety content.
- **Operator speed:** default to minimal required inputs, auto-fill from extraction, and provide one-click “Fix required fields.”
- **Auditability as a feature:** make evidence and change history visible, not hidden.

---

## 7) Definition of done for “good label creator”

A release is “good” when:
- A first-time operator can generate a valid draft label from SDS/TDS in <5 minutes.
- The system blocks non-compliant production exports by rule.
- Generated labels are visually consistent across products/sizes.
- Every key field has provenance (source + confidence + override history).
- Failures are understandable and recoverable without engineering support.
