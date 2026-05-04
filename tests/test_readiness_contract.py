from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from app import main


@asynccontextmanager
async def no_lifespan(app):
    yield


def _set_deps(healthy: bool):
    main.app.router.lifespan_context = no_lifespan
    sentinel = object() if healthy else None
    main.drive_client = sentinel
    main.pdf_extractor = sentinel
    main.gemini_client = sentinel
    main.validator = sentinel
    main.web_retriever = sentinel
    main.label_generator = sentinel


def test_readiness_contract_includes_expected_checks_and_status_ready():
    _set_deps(healthy=True)

    with TestClient(main.app) as client:
        res = client.get('/api/v1/readiness')
        assert res.status_code == 200
        payload = res.json()

        assert payload['status'] in {'ready', 'degraded'}
        checks = payload['checks']
        expected_keys = {
            'drive_client_initialized',
            'pdf_extractor_initialized',
            'gemini_client_initialized',
            'validator_initialized',
            'web_retriever_initialized',
            'label_generator_initialized',
            'gemini_api_key_present',
            'shared_drive_id_present',
        }
        assert expected_keys.issubset(checks.keys())


def test_readiness_status_degraded_when_dependencies_missing():
    _set_deps(healthy=False)

    with TestClient(main.app) as client:
        res = client.get('/api/v1/readiness')
        assert res.status_code == 200
        payload = res.json()
        assert payload['status'] == 'degraded'
        assert payload['checks']['drive_client_initialized'] is False
