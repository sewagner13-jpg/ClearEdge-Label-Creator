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
- Full test suite passes, including the real-browser label workflow.
- The parity check starts the app using the Railway start command and verifies the production frontend files locally.
- The release gate is mutation-tested red, restored, and green.
- The production health endpoint reports the released Git commit SHA.
- A live Edgemer E618 generation request succeeds.
- The returned preview is valid SVG and the full download starts with `%PDF`.
- A browser screenshot or equivalent live HTTP transcript is retained under `test_output/release/`.

## Status
In progress.
