# Gated Release And Live Smoke Implementation Plan

> **Ticket:** `T0002`

**Goal:** Release the XML-safe label renderer through one repeatable gate and prove the real Edgemer workflow in production.

**Architecture:** Add a small health build-identity contract and a single shell release orchestrator. The orchestrator reuses the repository's tests, starts the exact Railway command locally for parity, pushes the configured production branch, waits for that exact commit to appear in Railway health, and runs a real multipart label-generation smoke using user-provided SDS/TDS files.

## Task 1: Deployment identity
- Add a failing health-contract test for `build.commit_sha`.
- Read Railway's provided `RAILWAY_GIT_COMMIT_SHA` without exposing secrets.
- Prove the contract red, then green.

## Task 2: Canonical release gate
- Add `scripts/release.sh` with `--verify-only` and `--deploy` modes.
- Include the full Python suite, compile check, frontend syntax check, diff check, and exact local Railway start-command parity check.
- In deploy mode, require the remote production branch, a clean tree, the two SDS/TDS paths, and a pushed commit.
- Poll live health until it reports the exact commit, then run the real generation/preview/PDF smoke and retain non-secret evidence.
- Replace manual deployment instructions with the canonical command.

## Task 3: Prove and release
- Mutation-test the gate by temporarily restoring the broken renderer and observing failure.
- Restore the fix and run the gate successfully.
- Commit the ticket changes.
- Run the deploy mode and verify live frontend/backend behavior.
- Update `docs/STATE.md` and this ticket with exact evidence.
