# T0004 - Generate And DOT Parse Visibility

## User-Observable Outcome
The operator can click Generate Label and immediately see the exact missing requirement, and can clearly see whether SDS Section 14 parsed as DOT regulated, not regulated, or undetermined before generating a label.

## Root Cause
- The Generate Label button is disabled whenever weight, product name, or PDFs are missing. A disabled control cannot run the existing validation handler, so the operator only sees a generic message and the action appears broken.
- SDS analysis populates the DOT form fields, but the UI does not label the populated transport status as a parser result or show Section 14 evidence. A parsed `not_regulated` result is visually indistinguishable from a manual dropdown selection.

## Scope
- Keep net weight required for every non-sample label.
- Keep backend extraction, validation, branding, rendering, PDF, DOT sticker, and Canva behavior unchanged.
- Let Generate Label remain clickable when idle so its existing guard can route the operator to the first missing field.
- Show an exact missing-requirements message beside Generate.
- Show a live SDS Section 14 parse summary beside the DOT fields and in the analysis result, including a short source citation when evidence is available.

## Non-Goals
- No DOT rule changes.
- No weight-policy changes.
- No label renderer or brand changes.
- No regulatory conclusions beyond the uploaded SDS evidence.

## Deployment
Deployment is in scope under the standing deploy-after-change instruction. Use only `scripts/release.sh --deploy` after verification.

## Acceptance Tests
- With PDFs and product name present but weight blank, Generate Label is clickable and identifies Net Weight as the only missing requirement.
- Clicking Generate focuses the weight field and does not call label generation.
- A Section 14 `not_regulated=true` analysis visibly says the SDS parsed as not regulated and explains that UN/NA, class, and packing group are not required by that source result.
- A regulated result lists the parsed UN/NA number, shipping name, class, packing group, and missing critical fields.
- An undetermined result explicitly asks for Section 14 review instead of implying a successful parse.
- Existing label generation, branding, previews, PDFs, and DOT sticker tests remain green.

## Status
Complete and production-verified on 2026-08-13 at code commit `ead56a2235bdfc3e6f84d967d33decb49e6ae8de`. Live proof used the Edgemer SDS/TDS pair and confirmed actionable missing-weight guidance plus a source-backed Section 14 not-regulated result.
