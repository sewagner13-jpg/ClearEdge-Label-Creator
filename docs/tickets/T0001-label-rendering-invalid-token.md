# T0001 - Fix Label Rendering Invalid Token

## User-Observable Outcome
The user can generate, preview, and export a PDF label even when SDS/TDS or operator-entered text contains XML-sensitive characters.

## Reported Failure
`{"detail":"LABEL_RENDERING_FAILED: not well-formed (invalid token): line 109, column 25"}`

## Scope
- Find the exact renderer input that creates malformed SVG/XML.
- Add a regression using the real rendering path.
- Fix escaping or sanitization at the correct renderer boundary.
- Verify the preview SVG and downloaded PDF.

## Deployment
Not deployed. Production release is blocked because the repository does not have the mandatory single gated deployment script with full tests, browser E2E, environment parity, and a live behavior smoke check.

## Evidence
- Live reproduction used `Edgemer E618 TDS (1).pdf` and `Edgemer E618_MSDS (1).pdf`.
- Root cause: the source-backed product use `Resins of Coating & Ink` rendered as raw XML because `jinja2.Template` had autoescaping disabled.
- Exact local reproduction: `not well-formed (invalid token): line 109, column 25`.
- Regression: `tests/test_label_stub.py::test_standard_label_escapes_xml_sensitive_dynamic_text_before_pdf_rendering` was red before the fix and green afterward.
- Browser E2E: `tests/test_browser_label_creation_e2e.py` drives the real local UI and renderer. It was mutation-tested red with autoescape disabled and green after restoration.
- Full suite: 195 passed on 2026-08-13.
- Static checks: compileall, frontend JavaScript syntax, workflow YAML, development dependency dry-run, and `git diff --check` passed.
- Browser artifact: `test_output/browser/T0001-label-preview.png`.
- PDF artifact: `test_output/browser/T0001-coating-and-ink-label.pdf`.

## Changed Files
- `app/label_stub.py`
- `tests/test_label_stub.py`
- `tests/test_browser_label_creation_e2e.py`
- `tests/test_state_contract.py`
- `docs/STATE.md`
- `docs/tickets/T0001-label-rendering-invalid-token.md`
- `requirements-dev.txt`
- `pytest.ini`
- `.github/workflows/test.yml`
- `README.md`
