from contextlib import asynccontextmanager
from datetime import datetime

from fastapi.testclient import TestClient

from app import main


@asynccontextmanager
async def no_lifespan(app):
    yield


def test_health_contract_fields_and_timestamp_format():
    main.app.router.lifespan_context = no_lifespan

    with TestClient(main.app) as client:
        response = client.get('/api/v1/health')
        assert response.status_code == 200

        payload = response.json()
        for key in ['status', 'version', 'timestamp', 'ai_provider', 'openai_model']:
            assert key in payload

        assert payload['status'] == 'healthy'
        assert payload['ai_provider'] == 'openai'
        # Validate ISO-ish timestamp parseability
        datetime.fromisoformat(payload['timestamp'])
