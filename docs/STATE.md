# ClearEdge Label Creator State

## Production
- Frontend: https://clearedge-label-creator.netlify.app
- Backend: https://clearedgelabelcreator-production.up.railway.app
- Production branch: `claude/product-label-pipeline-Gw3uq`
- Renderer release verified from code commit `40b0b806fbf772a77a0f882b36bd0a3415d634fd`.

## Active Ticket
- None. `T0002` completed on 2026-08-13.
- Detail: `docs/tickets/T0002-gated-release-and-live-smoke.md`

## Open Defects
- None.

## Current Objective
- Await the next operator-observed defect or bounded product ticket.

## Verification State
- `tests/test_state_contract.py` was proven red while this file was absent.
- Root cause: `Resins of Coating & Ink` reached a Jinja SVG template with autoescape disabled.
- Renderer regression was proven red with the production error, then green after centralized XML autoescaping.
- Browser E2E was mutation-tested red with autoescape disabled, then green after restoration.
- Release gate was mutation-tested red with autoescape disabled, then green after restoration.
- `scripts/release.sh --deploy`: 199 passed with 84% coverage on 2026-08-13.
- Compileall, frontend JavaScript syntax, workflow YAML, local Railway parity, and `git diff --check` passed.
- GitHub Actions run `31719304661` passed, including Python 3.11, Python 3.12, and Docker jobs.
- Live Edgemer label: `label_EdgemerE618_2b9c3a5a`, status `ready`.
- Live preview parsed as SVG; PDF is 263,150 bytes, one 864 x 648 pt page.
- Artifacts: `test_output/browser/T0001-label-preview.png` and `T0001-coating-and-ink-label.pdf`.
- Release artifacts: `test_output/release/40b0b806fbf7/`.

## Blockers
- None.

## Next Action
- Hard refresh the production frontend and continue operator testing with real SDS/TDS documents.
