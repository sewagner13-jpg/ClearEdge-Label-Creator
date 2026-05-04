# ClearEdge Label Creator API v1 Contract (Phase 0 Baseline)

_Date: May 4, 2026_

## Base URL
- Local: `http://localhost:8000`
- Versioned prefix: `/api/v1`

## Phase 0 endpoints

### `GET /api/v1/health`
Liveness endpoint for load balancers and uptime checks.

**Response**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-05-04T00:00:00Z",
  "gemini_model": "...",
  "shared_drive_id": "..."
}
```

### `GET /api/v1/readiness`
Dependency-oriented readiness endpoint for deployment diagnostics.

**Response**
```json
{
  "status": "ready",
  "timestamp": "2026-05-04T00:00:00Z",
  "checks": {
    "drive_client_initialized": true,
    "pdf_extractor_initialized": true,
    "gemini_client_initialized": true,
    "validator_initialized": true,
    "web_retriever_initialized": true,
    "label_generator_initialized": true,
    "gemini_api_key_present": true,
    "shared_drive_id_present": true
  }
}
```

If one or more checks fail, status returns `degraded`.

## Legacy compatibility
Existing non-versioned endpoints remain available during migration:
- `/health`
- `/products`
- `/ingest/drive`
- `/ingest/url`
- `/extract/{product_name}`

## Phase 1 preview
Phase 1 will add and stabilize:
- `POST /api/v1/labels/generate`
- `GET /api/v1/labels/{id}`
- `GET /api/v1/labels/{id}/download`

plus a unified response payload shape for frontend consumption (`extracted`, `validation`, `label`, `warnings`, `errors`, `audit`).

## Phase 3 lifecycle and override workflow

### Label lifecycle status
- `approved`: validation passed, download enabled.
- `blocked`: validation failed, download blocked.
- `override_approved`: validation failed but manually approved with audit reason.

### Metadata fields
`GET /api/v1/labels/{id}` now includes:
- `status`
- `override_approved`
- `override_reason`
- `override_approver`
- `override_timestamp`

### `POST /api/v1/labels/{id}/override-approval`
Approve a blocked label when business exception requires release.

Request body:
```json
{
  "approver": "Jane Doe",
  "reason": "Customer shipment hold; temporary controlled release approved by EHS lead"
}
```

Behavior:
- Requires both fields.
- Stores audit metadata.
- Enables `download_url` for that label.

## Persistent runtime storage
For multi-instance and restart-safe behavior, runtime label artifacts + metadata now default to:
- `<repo>/runtime_data/labels`

Override location with:
- `CLEAREDGE_DATA_DIR=/path/to/persistent/volume`

This path should be mounted to persistent storage in production.
