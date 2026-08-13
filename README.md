# CLEAR EDGE Label Creator

OpenAI-powered SDS/TDS extraction and DOT/OSHA label generation.

For the current restart handoff, deployment status, capabilities, and known limitations, read:

- `docs/current-state.md`

## Current Architecture

- Frontend: static site in `netlify-frontend/`, deployed to Netlify.
- Backend: FastAPI service deployed to Railway.
- AI extraction: OpenAI via `OPENAI_API_KEY`.
- Optional second-pass review: Amazon Bedrock AgentCore via `AGENTCORE_*` variables.
- Degraded mode: if OpenAI is unavailable, a deterministic source-text fallback extracts only visibly present PDF values and keeps validation gates active.
- Label artifacts: generated PDF files are stored on the app filesystem under `runtime_data/labels` unless `CLEAREDGE_DATA_DIR` is set.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then run:

```bash
./run-local.sh
```

Backend health:

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/readiness
```

## Deploy

Backend deployment is configured by `railway.json`.

Required Railway variables:

```bash
OPENAI_API_KEY=<secret>
OPENAI_MODEL=gpt-4o
ALLOWED_ORIGINS=https://clearedge-label-creator.netlify.app
```

Optional AgentCore variables:

```bash
AGENTCORE_ENABLED=true
AGENTCORE_RUNTIME_ARN=<bedrock-agentcore-runtime-arn>
AGENTCORE_REGION=<aws-region>
AGENTCORE_QUALIFIER=<optional-runtime-qualifier>
AGENTCORE_TIMEOUT_SECONDS=60
```

Frontend deployment is configured by root `netlify.toml`, which publishes `netlify-frontend/`.

`netlify-frontend/config.js` must point to the Railway backend:

```js
window.CLEAREDGE_API_URL = 'https://clearedgelabelcreator-production.up.railway.app';
```

## Main API

- `GET /api/v1/health`
- `GET /api/v1/readiness`
- `POST /api/v1/labels/generate`
- `GET /api/v1/labels/{label_id}`
- `GET /api/v1/labels/{label_id}/download`
- `PATCH /api/v1/labels/{label_id}/corrections`
- `POST /api/v1/labels/{label_id}/override-approval`

## Tests

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest
```
