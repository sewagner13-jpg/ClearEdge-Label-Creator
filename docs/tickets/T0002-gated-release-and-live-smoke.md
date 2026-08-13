# T0002 - Gated Release And Live Smoke

## User-Observable Outcome
The user can generate, preview, and download the Edgemer E618 label in the production app without an XML invalid-token error.

## Scope
- Add one canonical release command that runs the full suite, browser E2E, local Railway-parity check, clean-tree check, production-branch push, deployed-commit check, and live behavior smoke.
- Expose the Railway Git commit SHA in the health response so the gate cannot certify an old deployment.
- Deploy the completed `T0001` renderer fix.
- Generate a live label from the provided Edgemer SDS/TDS pair and verify its preview SVG and PDF.

## Deployment
Deployment is explicitly authorized for this ticket. The only authorized path is the new gated release command.

## Acceptance Evidence
- Full release gate: 199 tests passed with 84% coverage, including the real-browser label workflow.
- Local parity started the Railway command and served the production frontend shell and JavaScript.
- Negative proof: disabling SVG autoescape caused the gate to stop on both renderer and browser regressions before deployment.
- Production health reported `40b0b806fbf772a77a0f882b36bd0a3415d634fd` on the production branch.
- GitHub Actions run `31719304661` passed after the Docker image-load regression was proven red and fixed.
- Live generation succeeded as `label_EdgemerE618_2b9c3a5a` with status `ready`.
- Live preview parsed as SVG and visibly rendered `Resins of Coating & Ink`.
- Live PDF starts with `%PDF`, is 263,150 bytes, and has one 864 x 648 pt page.
- Evidence is retained under `test_output/release/40b0b806fbf7/`.

## Status
Complete on 2026-08-13.
