# Build Status

Current runtime target:

- Backend: Railway
- Frontend: Netlify
- AI provider: OpenAI
- Required secret: `OPENAI_API_KEY`

Verification:

```bash
pytest
curl https://clearedgelabelcreator-production.up.railway.app/api/v1/health
curl https://clearedge-label-creator.netlify.app/
```
