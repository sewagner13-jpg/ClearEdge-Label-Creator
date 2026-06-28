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
  "ai_provider": "openai",
  "openai_model": "gpt-4o"
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
    "pdf_extractor_initialized": true,
    "openai_client_initialized": true,
    "validator_initialized": true,
    "web_retriever_initialized": true,
    "label_generator_initialized": true,
    "openai_api_key_present": true
  }
}
```

If one or more checks fail, status returns `degraded`.

## Compatibility
Existing health endpoint remains available:
- `/health`

## Phase 1 preview
Phase 1 will add and stabilize:
- `POST /api/v1/labels/generate`
- `GET /api/v1/labels/{id}`
- `GET /api/v1/labels/{id}/download`
- `PATCH /api/v1/labels/{id}/corrections`

plus a unified response payload shape for frontend consumption (`status`, `extracted`, `validation`, `label`, `download`, `agentcore_review`, `warnings`, `errors`, `audit`).

## Phase 3 lifecycle and override workflow

### Label lifecycle status
- `ready`: validation passed, download enabled.
- `needs_review`: AgentCore or validation review requires operator correction or override.
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

### `PATCH /api/v1/labels/{id}/corrections`
Apply operator-confirmed field corrections, rerun validation, and rerender the PDF.

Request body:
```json
{
  "updated_by": "Jane Doe",
  "reason": "Confirmed against SDS Section 14",
  "fields": {
    "transport.un_number": "UN1263"
  }
}
```

Supported correction fields are two-level extracted data paths such as `product.emergency_phone`, `ghs.signal_word`, `transport.un_number`, and `nfpa.health`.

## Optional AgentCore review

When `AGENTCORE_ENABLED=true`, the backend invokes an Amazon Bedrock AgentCore Runtime after OpenAI extraction and before local validation.

Generation responses include:

```json
{
  "status": "ready | needs_review | blocked",
  "download": {
    "available": true,
    "url": "/api/v1/labels/{id}/download",
    "reason": null
  },
  "agentcore_review": {
    "status": "reviewed | disabled | unavailable",
    "field_reviews": [],
    "label_inclusion_decisions": [],
    "critical_issues": [],
    "warnings": [],
    "agentcore_trace_id": null
  }
}
```

AgentCore failures degrade to OpenAI-only extraction with a warning. AgentCore conflicts on critical fields force `needs_review` and block download until correction or override.

## Persistent runtime storage
For multi-instance and restart-safe behavior, runtime label artifacts + metadata now default to:
- `<repo>/runtime_data/labels`

Override location with:
- `CLEAREDGE_DATA_DIR=/path/to/persistent/volume`

This path should be mounted to persistent storage in production.
