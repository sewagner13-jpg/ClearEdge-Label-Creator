# Production Release

All production releases must use the repository gate. It runs the complete test suite, real-browser test, local Railway-parity check, clean-tree and production-branch checks, deployed-commit verification, and a live SDS/TDS label-generation smoke.

Verify without deploying:

```bash
PYTHON_BIN=.venv/bin/python ./scripts/release.sh --verify-only
```

Deploy and run the required live behavior smoke:

```bash
PYTHON_BIN=.venv/bin/python ./scripts/release.sh --deploy \
  --sds /absolute/path/product-sds.pdf \
  --tds /absolute/path/product-tds.pdf
```

The release command pushes the branch configured as `origin/HEAD`. Railway and Netlify must remain connected to that branch for automatic deployment. Railway provides `RAILWAY_GIT_COMMIT_SHA`; the gate waits for that exact commit before certifying the live app.

Do not deploy with a direct `git push`, Railway CLI, or Netlify CLI. Those paths bypass the required behavior evidence.
