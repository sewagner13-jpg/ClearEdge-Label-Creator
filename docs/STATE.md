# ClearEdge Label Creator State

## Production
- Frontend: https://clearedge-label-creator.netlify.app
- Backend: https://clearedgelabelcreator-production.up.railway.app
- Branch observed at task start: `claude/product-label-pipeline-Gw3uq`
- Live production still has `D0001`; `T0002` is authorized to deploy the verified fix.

## Active Ticket
- `T0002` - Add the mandatory release gate and deploy the `D0001` fix.
- Detail: `docs/tickets/T0002-gated-release-and-live-smoke.md`

## Open Defects
- `D0001` - High - Production Generate Label returns `LABEL_RENDERING_FAILED` for XML-sensitive text.

## Current Objective
- The user can generate the Edgemer E618 label in production without the SVG invalid-token failure.

## Verification State
- `tests/test_state_contract.py` was proven red while this file was absent.
- Root cause: `Resins of Coating & Ink` reached a Jinja SVG template with autoescape disabled.
- Renderer regression was proven red with the production error, then green after centralized XML autoescaping.
- Browser E2E was mutation-tested red with autoescape disabled, then green after restoration.
- `python -m pytest -q`: 195 passed on 2026-08-13.
- Compileall, frontend JavaScript syntax, workflow YAML, dependency dry-run, and `git diff --check` passed.
- Artifacts: `test_output/browser/T0001-label-preview.png` and `T0001-coating-and-ink-label.pdf`.

## Blockers
- Repository has no `main` branch. Its configured remote production branch is `claude/product-label-pipeline-Gw3uq`.
- The gated release workflow has not yet been implemented or proven.

## Next Action
- Implement and negative-probe the release gate, commit, push, then run the Edgemer E618 live smoke test.
