# ClearEdge Label Creator State

## Production
- Frontend: https://clearedge-label-creator.netlify.app
- Backend: https://clearedgelabelcreator-production.up.railway.app
- Production branch: `claude/product-label-pipeline-Gw3uq`
- Current release verified from code commit `7725e8f7eff063c2525de221393ad2dbb2d5f9eb`.

## Active Ticket
- `T0004` - Generate And DOT Parse Visibility.
- Detail: `docs/tickets/T0004-generate-and-dot-parse-visibility.md`

## Open Defects
- `D0004-1` High: Generate Label appears broken because the disabled button cannot explain that required Net Weight is blank.
- `D0004-2` High: parsed SDS Section 14 status is populated into form controls without a visible parser-result summary or source evidence.

## Current Objective
- Make Generate prerequisites actionable and make DOT Section 14 parsing unambiguous without changing label or compliance rules.

## Verification State
- `T0004` browser/view-model regressions were proven red for the disabled Generate action, missing exact weight requirement, and absent Section 14 status/evidence panel.
- `PYTHON_BIN=./.venv/bin/python ./scripts/release.sh --verify-only`: 212 passed with 85% coverage on 2026-08-13.
- `T0004` browser E2E proved that clicking Generate with blank required weight focuses Net Weight without calling generation, and that SDS analysis renders a source-backed not-regulated Section 14 conclusion.
- `scripts/release.sh --deploy` passed for commit `7725e8f7eff063c2525de221393ad2dbb2d5f9eb`: 207 tests, 85% coverage, browser E2E, static checks, local Railway parity, exact-commit production wait, and real SDS/TDS generation.
- Live Edgemer label `label_EdgemerE618_76e35861` returned `status=ready`, `source_review.status=reviewed`, `source_review.provider=openai`, and a non-empty OpenAI response ID.
- Live preview and PDF were fetched and parsed. The PDF is one 864 x 648 pt page; the preview preserved the ClearEdge logo and purple layout, showed one GHS07 pictogram, one H317 statement, the approved `704-799-5769` contact, and the source-backed DOT not-regulated panel.
- Release artifacts: `test_output/release/7725e8f7eff0/`.
- First `T0003` live attempt on commit `a2753248484995951074f57b864f6d25a54a85a2` reached Railway but was rejected by the release gate because OpenAI returned `Invalid schema ... status ... must have a type key`; the existing label fallback remained available.
- The strict-schema regression was proven red with the production error and green after declaring `status` as a required patterned string.
- Post-fix `PYTHON_BIN=./.venv/bin/python ./scripts/release.sh --verify-only`: 207 passed with 85% coverage on 2026-08-13.
- `T0003` regressions were proven red before implementation for filename cleanup, duplicate H/P statements, ClearEdge emergency contact, OpenAI review routing, and the live-review release assertion.
- `PYTHON_BIN=./.venv/bin/python ./scripts/release.sh --verify-only`: 206 passed with 85% coverage on 2026-08-13.
- Browser E2E, Python compilation, all frontend JavaScript syntax checks, workflow YAML parsing, local Railway parity, and `git diff --check` passed for `T0003`.
- The OpenAI review uses strict Pydantic structured output through the Responses API and retains `agentcore_review` only as a temporary response alias for older consumers.
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
- Add failing browser/frontend regressions for `T0004`, implement the UI fix, then run the gated live release.
