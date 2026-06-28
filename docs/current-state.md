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
8. Download the PDF if validation passes, or approve an override if validation blocks download.
9. Export Canva Bulk Create data as CSV/JSON after validation pass or override approval.

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

## Canva Handoff

The app does not currently create/edit a Canva design directly through the Canva API.

It produces Canva-ready data after validation pass or override:

- `GET /api/v1/labels/{label_id}/canva-export.csv`
- `GET /api/v1/labels/{label_id}/canva-export.json`

These exports are meant for Canva Bulk Create or manual template entry.

## Important Limitations

- OpenAI extraction is JSON-based but not yet a strict field-by-field evidence model.
- Extracted evidence exists in the schema, but the UI does not yet expose every evidence quote to the operator.
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
3. Move label-generation orchestration out of `app/main.py` into a `label_pipeline.py` service.
4. Add file upload limits and explicit PDF error codes.
5. Expand DOT label assets beyond classes 3, 8, and 9.
6. Replace filesystem metadata with object storage or a database before production retention matters.
7. Split the frontend into smaller modules or move to a simple build system once UI work accelerates.
