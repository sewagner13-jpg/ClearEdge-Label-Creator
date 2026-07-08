# ClearEdge Label Creator UI/UX Review

Date: 2026-07-08

## Executive Summary

The ClearEdge Label Creator had a strong backend contract but a weak operator interface: every decision appeared in one long form, which made the product feel less trustworthy than the compliance pipeline behind it. The highest-risk UX problem was not visual taste; it was that DOT, GHS, branding, preview, and export decisions competed for attention before the operator could understand the workflow. The app needed a guided production flow that matches how labels are actually made: upload source documents, set label/shipment details, review compliance fields, then preview and export. The new build direction keeps the static Netlify/FastAPI architecture, but replaces the dense page with a four-step workspace and persistent preview rail. Canva remains a handoff/export workflow instead of becoming the primary renderer.

## Scorecard

| Category | Previous Score / 10 | Why It Scored This Way | 8+ Requirement |
|---|---:|---|---|
| Overall UX quality | 6 | Capable backend, overloaded frontend. | Guided workflow with preview-first output confidence. |
| First-impression clarity | 5 | “AI-powered compliant labels” copy overstated certainty and hid the operator steps. | State the actual job: upload SDS/TDS, review data, preview PDF. |
| Visual design quality | 6 | Brand color existed, but inline styles and card clutter weakened polish. | Tokenized ClearEdge system, restrained surfaces, consistent controls. |
| Information hierarchy | 4 | Upload, branding, shipment, GHS, DOT, and export all competed. | Four obvious steps with compliance review separated from setup. |
| Interaction quality | 5 | Generate button and preview were buried; error states were basic. | Persistent preview/status rail and staged processing feedback. |
| Accessibility | 5 | Labels existed, but inline layout and hidden file input patterns needed stronger focus/tap behavior. | Semantic sections, keyboard upload, visible focus, 44px controls. |
| Mobile/responsive quality | 5 | Existing grid collapse was broad and fragile. | One-column mobile workflow with no horizontal overflow. |
| Copy quality | 6 | Some copy implied automatic compliance rather than operator review. | Concrete, source-backed, review-focused microcopy. |
| Product trust | 6 | DOT sticker behavior existed, but not prominent enough. | Preview must explicitly show page count and DOT sticker status. |
| Engineering polish | 4 | Large `app.js`, large `index.html`, many inline styles. | Modular static JS and shell-only HTML. |

## Top Fixes

| Priority | Issue | Fix | Severity | Impact |
|---:|---|---|---|---|
| 1 | Dense one-page form hides the workflow. | Split into Upload, Setup, Compliance Review, Preview/Export. | Critical | Operators know where they are and what to do next. |
| 2 | Preview appears after a long form and is easy to miss. | Add persistent preview rail with empty, loading, and result states. | Critical | Operator sees label output before download. |
| 3 | DOT sticker page status is not visually dominant enough. | Show page count, DOT sticker preview card, and no-sticker reason in the preview rail. | High | Reduces confusion about the second page. |
| 4 | Canva handoff is buried with generic button labels. | Rename to Canva handoff and describe CSV/JSON/field-map purpose. | Medium | Keeps Canva useful without making it the renderer. |
| 5 | Manual correction flow is not obvious. | Add correction panel that calls the existing PATCH correction endpoint. | High | Operators can fix fields without restarting the workflow. |
| 6 | Inline styles make polish and responsive behavior fragile. | Move layout and component styling into `style.css` tokens. | High | Faster future UI changes and fewer visual regressions. |
| 7 | Large `app.js` mixes API, state, rendering, and formatting. | Split into controller, renderer, utilities, and view-model modules. | High | Easier testing and safer future work. |
| 8 | Processing feedback is too vague. | Show staged progress: upload, extract, analyze, render. | Medium | Reduces perceived hangs during OpenAI/PDF processing. |
| 9 | Custom branding is visually mixed into setup. | Group logo library, upload, suggested logo, and supplier info in one brand panel. | Medium | Fewer mistakes on customer labels. |
| 10 | Mobile layout depends on broad inline-style selectors. | Use named responsive grid classes and semantic sections. | Medium | Warehouse/tablet use becomes less brittle. |

## Flow Review

### Upload SDS/TDS

The upload area is the true start of the workflow and must remain visually dominant. The operator should understand that PDFs are the source of truth and that the app will not fabricate missing label data. The upload control needs keyboard activation, drag/drop feedback, file list removal, and a disabled Generate state until a product name exists.

### Label Setup

Product name, brand, logo, lot, expiration, weight, size, orientation, and mode belong together. The product name is the label title, not necessarily the SDS product name. Custom-company labels require a logo/supplier workflow, while ClearEdge labels should default to official ClearEdge identity without asking the operator to retype it.

### Compliance Review

GHS and DOT fields are operator review inputs, not casual optional fields. They should be visually grouped under compliance. DOT fields need to communicate that SDS Section 14 is the source, and that supported DOT sticker assets are limited to mapped classes. GHS pictograms must use the approved dropdown and packaged images only.

### Preview And Export

Preview is the proof surface. It must show page count, Page 1 Product Label, Page 2 DOT Sticker Sheet when required, and a clear no-page-2 explanation when not required. Full Label PDF is the primary export. DOT Stickers PDF and Canva handoff are secondary but visible when available.

## Accessibility Review

| Issue | Concern | Fix | Severity |
|---|---|---|---|
| Upload relied mostly on click behavior. | Keyboard users could miss the file input. | Make upload area role button, tabindex 0, Enter/Space activation. | High |
| Inline grids caused unpredictable mobile order. | Screen magnification and mobile users could lose context. | Use semantic sections and named responsive grid classes. | High |
| Buttons and links had mixed visual styles. | Ambiguous affordances and weak focus recovery. | Standardize `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`. | Medium |
| Processing state was generic. | Assistive tech users lacked meaningful status. | Use role status, staged progress copy, and aria-live result containers. | Medium |
| Preview and result panels were not clearly separated. | Users could confuse source data, review notes, and exports. | Use labeled preview rail plus result sections. | Medium |

## Implementation Backlog

| Priority | Task | Owner | Severity | Effort | Impact | Acceptance Criteria |
|---:|---|---|---|---|---|---|
| 1 | Convert page shell to four-step workflow. | Engineering | Critical | Medium | High | The page contains Upload, Setup, Compliance Review, and Preview/Export sections. |
| 2 | Add persistent preview rail. | Engineering | Critical | Medium | High | Empty, processing, success, and error preview states render. |
| 3 | Split frontend JavaScript into modules. | Engineering | High | Medium | High | `app.js` imports controller module; rendering and view-model logic live under `netlify-frontend/js/`. |
| 4 | Add view-model tests for preview/export. | Engineering | High | Small | High | Node-imported view-model maps page count, DOT sticker page, and Canva handoff booleans. |
| 5 | Add correction panel using PATCH endpoint. | Engineering | High | Medium | High | Generated result includes correction form and submits `updated_by`, `reason`, and `fields`. |
| 6 | Clean Canva handoff panel. | Product/Engineering | Medium | Small | Medium | CSV, JSON, template, and field map actions are explained and grouped. |
| 7 | Improve staged processing copy. | Copy/Engineering | Medium | Small | Medium | Loading state lists upload, extraction, analysis, and rendering stages. |
| 8 | Verify responsive behavior. | Design/Engineering | Medium | Small | Medium | Mobile layout is one column with no horizontal scrolling. |

## Final Verdict

Before this update, the app was functionally strong but visually and structurally under-presented. The highest-leverage change is the guided workflow plus persistent preview rail because it makes the system feel like a controlled production tool instead of a long experimental form. The biggest risk if shipped without this redesign is operator distrust: users may assume the backend is unreliable because the frontend does not clearly separate input, review, preview, and export states.
