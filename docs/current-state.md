# ClearEdge Label Creator Current State

Updated: 2026-06-28

## Where The App Is

- Local repo: `/Users/seanwagner/Desktop/ClearEdge-Label-Creator`
- Current branch: `claude/product-label-pipeline-Gw3uq`
- Frontend: `https://clearedge-label-creator.netlify.app`
- Backend: `https://clearedgelabelcreator-production.up.railway.app`
- Backend health: `GET /api/v1/health`
- Backend readiness: `GET /api/v1/readiness`
- Static frontend source: `netlify-frontend/`
- FastAPI backend source: `app/`
- Generated PDFs and metadata: `runtime_data/labels` unless `CLEAREDGE_DATA_DIR` is set

## What It Does Today

The app creates ClearEdge chemical product labels from SDS/TDS PDF uploads.

Operator workflow:

1. Upload one or more PDFs.
2. Enter the ClearEdge product name.
3. Choose label mode: shipped DOT or workplace.
4. Choose pail or drum layout.
5. Enter optional lot number, expiration date, and fill amount.
6. Optionally choose GHS pictograms from the approved dropdown.
7. Generate a label.
8. Review local validation plus optional AgentCore review findings.
9. Download the PDF if validation passes, correct fields, or approve an override if validation blocks download.
10. Export Canva Bulk Create data as CSV/JSON after validation pass or override approval.

Current label behavior:

- Uses the official ClearEdge logo.
- Product name is prominent and brand-purple.
- Lot number, expiration date, and net weight are large enough for quick visual checks.
- Pail/drum wording is not printed on the label; fill amount is the size cue.
- Signal word is printed in the pictogram panel, while the purple strip is blank.
- GHS pictograms render only from the approved packaged pictogram images.
- NFPA 704 diamond prints on every label and defaults missing SDS values to 0 by ClearEdge policy.
- Shipped DOT labels show the DOT transport panel when regulated.
- Products explicitly stated as not regulated for transport render a not-regulated transport state.
- API responses include `status` values: `ready`, `needs_review`, `blocked`, or `override_approved`.

## Current Compliance Guardrails

Validation currently blocks shipped DOT download when a regulated product is missing:

- UN/NA/ID number.
- Proper shipping name.
- Hazard class.
- A supported DOT hazard label asset.
- Required parenthetical technical name for an `n.o.s.` proper shipping name.

Validation currently warns, but does not block, when:

- Packing group is missing.
- Emergency phone is missing.
- GHS pictograms overlap with DOT hazard class.
- Workplace label has hazard statements but no signal word.
- Workplace label has a signal word but no pictograms.

Supported packaged DOT hazard label assets today:

- Class 3: Flammable liquid.
- Class 8: Corrosive.
- Class 9: Miscellaneous.

If another DOT hazard class is extracted, validation blocks download until the required DOT label asset is added and mapped.

## AgentCore Review

OpenAI remains the primary SDS/TDS extractor. Amazon Bedrock AgentCore can optionally run as a second-pass parser/reviewer after OpenAI extraction and before local validation.

If OpenAI extraction is unavailable, for example because the API account is out of quota, the backend falls back to a deterministic source-text parser. That fallback only uses values visibly present in the uploaded PDF text and still lets validation block incomplete DOT/GHS data.

AgentCore is disabled by default. Enable it only after deploying an AgentCore Runtime and configuring:

- `AGENTCORE_ENABLED=true`
- `AGENTCORE_RUNTIME_ARN`
- `AGENTCORE_REGION`
- `AGENTCORE_QUALIFIER` optional
- `AGENTCORE_TIMEOUT_SECONDS=60`

When enabled, AgentCore receives extracted PDF page text, OpenAI structured fields, label mode, shipment fields, approved GHS pictogram options, supported DOT classes, and validation-rule context. Its output is recorded in `agentcore_review`.

Reconciliation behavior:

- Matching OpenAI/AgentCore values proceed normally.
- Missing critical OpenAI values can be filled only when AgentCore provides source evidence with confidence `>= 0.85`.
- Conflicting critical fields become `needs_review` and block download until correction or override.
- AgentCore failure or timeout does not stop label generation; the app falls back to OpenAI plus local validation and records a warning.
- OpenAI failure does not create fabricated values; the app uses source-visible deterministic extraction, records the AI failure in extraction warnings, and keeps normal validation/download gates.

## Canva Handoff

The app does not currently create/edit a Canva design directly through the Canva API.

It produces Canva-ready data after validation pass or override:

- `GET /api/v1/labels/{label_id}/canva-export.csv`
- `GET /api/v1/labels/{label_id}/canva-export.json`

These exports are meant for Canva Bulk Create or manual template entry.

## Important Limitations

- OpenAI extraction is JSON-based but not yet a strict field-by-field evidence model.
- AgentCore review can expose source-backed evidence for reviewed fields, but it requires separate AWS AgentCore Runtime configuration.
- Extracted evidence exists in the schema, but the UI does not yet expose every OpenAI evidence quote to the operator.
- Runtime storage is filesystem-backed. Railway filesystem storage is not ideal for permanent retention.
- The renderer is still named `label_stub.py` and contains a large inline SVG template. It works, but should eventually be split into a renderer module plus external template files.
- OCR exists as a fallback path but scanned PDF handling should be tested more heavily before relying on it.
- The frontend is functional but still a static JavaScript file with inline HTML snippets and inline styles.
- Google/Gemini files still exist as untracked local leftovers, but the active backend runtime uses OpenAI, not Google.

## Code Map

Backend:

- `app/main.py`: FastAPI routes, app startup, label generation endpoint, override endpoint, downloads, Canva export endpoints.
- `app/api_models.py`: API request/response models and enums.
- `app/canva_export.py`: Canva CSV/JSON field flattening and operator field parsing.
- `app/label_storage.py`: metadata persistence and label ID validation helpers.
- `app/label_pipeline.py`: generation, AgentCore review, validation, rendering, correction, and response orchestration.
- `app/agentcore_client.py`: optional Amazon Bedrock AgentCore Runtime invocation and JSON parsing.
- `app/rule_based_extractor.py`: deterministic source-text fallback used only when OpenAI extraction is unavailable.
- `app/openai_client.py`: OpenAI SDS/TDS extraction prompt and response parsing.
- `app/pdf_extract.py`: PDF text extraction and OCR fallback path.
- `app/validator.py`: DOT/workplace validation rules.
- `app/label_stub.py`: SVG/PDF renderer and packaged asset loading.
- `app/schema.py`: Pydantic models for extracted product, GHS, transport, NFPA, shipment, evidence, and validation data.

Frontend:

- `netlify-frontend/index.html`: static app shell.
- `netlify-frontend/app.js`: upload flow, generation request, validation display, override flow, Canva links.
- `netlify-frontend/style.css`: app styling.
- `netlify-frontend/config.js`: production backend URL.

Deploy:

- `railway.json`: Railway backend start command.
- `netlify.toml`: Netlify static frontend publish config.

Tests:

- `tests/test_label_stub.py`: renderer behavior.
- `tests/test_validator.py`: compliance validation.
- `tests/test_api_journey_e2e.py`: operator journey from generate to override/download.
- `tests/test_api_integration_phase3.py`: API lifecycle checks.
- `tests/test_schema.py`: model validation.
- `tests/test_openai_client.py`: extraction parser behavior.
- `tests/test_metadata_persistence.py`: filesystem metadata persistence.

## Suggested Next Cleanup

1. Move the large SVG template out of `app/label_stub.py` into a template file.
2. Rename `app/label_stub.py` to `app/label_renderer.py` while keeping an import shim for compatibility.
3. Expand DOT label assets beyond classes 3, 8, and 9.
4. Replace filesystem metadata with object storage or a database before production retention matters.
5. Split the frontend into smaller modules or move to a simple build system once UI work accelerates.
