# Deploy Now

## Backend

Railway uses `railway.json`:

```json
{
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port 8000"
  }
}
```

Set these Railway variables:

```bash
OPENAI_API_KEY=<secret>
OPENAI_MODEL=gpt-4o
ALLOWED_ORIGINS=https://clearedge-label-creator.netlify.app,http://localhost:8000,http://127.0.0.1:8000
```

Verify:

```bash
curl https://clearedgelabelcreator-production.up.railway.app/api/v1/health
curl https://clearedgelabelcreator-production.up.railway.app/api/v1/readiness
```

## Frontend

Netlify publishes `netlify-frontend/` via root `netlify.toml`.

Verify:

```bash
curl https://clearedge-label-creator.netlify.app/
curl https://clearedge-label-creator.netlify.app/config.js
```
