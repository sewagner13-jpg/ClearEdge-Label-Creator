# T0003 - OpenAI Source Review And Extraction Corrections

## User-Observable Outcome
The user can analyze an SDS/TDS pair through the OpenAI platform and receive source-backed label data without losing existing branding, layouts, validation, previews, PDF exports, or DOT sticker behavior.

## Scope
- Replace the optional AWS AgentCore second-pass reviewer with an OpenAI Responses API reviewer.
- Preserve the existing extraction schema and API response compatibility while exposing an OpenAI review status.
- Keep deterministic SDS/TDS reconciliation between primary extraction and the OpenAI review.
- Normalize uploaded SDS/MSDS filenames into clean product-name suggestions.
- Deduplicate equivalent coded and code-less hazard/precautionary statements.
- For ClearEdge branding, render the approved ClearEdge emergency number `704-799-5769` while preserving source-document emergency data in extraction evidence.
- Preserve all official logos, colors, GHS/DOT/NFPA assets, label sizes, orientations, custom branding, Canva handoff, previews, and PDF downloads.

## Non-Goals
- No renderer redesign.
- No regulatory asset changes.
- No new Google, AWS, Canva, or storage dependency.
- No automatic regulatory approval or silent conflict resolution.

## Deployment
Deployment is explicitly in scope under the project's standing deploy-after-change instruction. The only authorized path is `scripts/release.sh --deploy` after all ticket checks pass.

## Acceptance Tests
- OpenAI review is invoked through the existing OpenAI client and returns strict structured review data.
- Disabled/missing OpenAI review degrades safely without breaking primary extraction.
- Critical extraction/review conflicts remain visible and do not silently overwrite source-backed SDS values.
- Product name suggestion for `Edgemer E618_MSDS (1).pdf` is `Edgemer E618`.
- Duplicate H317 representations collapse to one printed statement.
- ClearEdge labels print `704-799-5769`; custom labels keep their source/operator emergency contact.
- Existing branding/rendering/API/DOT regression tests remain green.
- Real browser E2E and release gate pass before deploy.

## Status
Complete and production-verified on 2026-08-13 at commit `7725e8f7eff063c2525de221393ad2dbb2d5f9eb`. Live proof: `label_EdgemerE618_76e35861` with a reviewed OpenAI source-review response, parsed SVG preview, and parsed PDF download.
