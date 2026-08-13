from contextlib import asynccontextmanager
from datetime import datetime

from fastapi.testclient import TestClient

from app import main


@asynccontextmanager
async def no_lifespan(app):
    yield


def test_health_contract_fields_and_timestamp_format(monkeypatch):
    monkeypatch.setenv('RAILWAY_GIT_COMMIT_SHA', 'a1b2c3d4e5f6')
    main.app.router.lifespan_context = no_lifespan

    with TestClient(main.app) as client:
        response = client.get('/api/v1/health')
        assert response.status_code == 200

        payload = response.json()
        for key in ['status', 'version', 'timestamp', 'ai_provider', 'openai_model', 'build']:
            assert key in payload

        assert payload['status'] == 'healthy'
        assert payload['ai_provider'] == 'openai'
        assert payload['build'] == {
            'commit_sha': 'a1b2c3d4e5f6',
            'branch': 'unknown',
        }
        # Validate ISO-ish timestamp parseability
        datetime.fromisoformat(payload['timestamp'])


def test_health_contract_marks_local_build_identity_unknown(monkeypatch):
    monkeypatch.delenv('RAILWAY_GIT_COMMIT_SHA', raising=False)
    monkeypatch.delenv('RAILWAY_GIT_BRANCH', raising=False)

    payload = main._health_payload()

    assert payload['build'] == {
        'commit_sha': 'unknown',
        'branch': 'unknown',
    }
