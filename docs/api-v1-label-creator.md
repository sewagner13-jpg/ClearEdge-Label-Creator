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

plus a unified response payload shape for frontend consumption (`status`, `extracted`, `validation`, `label`, `download`, `source_review`, `warnings`, `errors`, `audit`).

## Phase 3 lifecycle and override workflow

### Label lifecycle status
- `ready`: validation passed, download enabled.
- `needs_review`: OpenAI source review or local validation requires operator correction or override.
- `blocked`: retained for compatibility with older metadata; current generation returns a preview and download with visible review issues.
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

## OpenAI source review

When `OPENAI_REVIEW_ENABLED=true`, the backend invokes an independent OpenAI Responses API review after primary extraction and deterministic source reconciliation, before local validation.

Generation responses include:

```json
{
  "status": "ready | needs_review | blocked",
  "download": {
    "available": true,
    "url": "/api/v1/labels/{id}/download",
    "reason": null
  },
  "source_review": {
    "status": "reviewed | disabled | unavailable",
    "provider": "openai",
    "review_type": "source_review",
    "field_reviews": [],
    "label_inclusion_decisions": [],
    "critical_issues": [],
    "warnings": [],
    "openai_response_id": null
  }
}
```

Second-pass failures degrade to primary OpenAI extraction plus deterministic reconciliation with a warning. Source-backed critical conflicts force `needs_review` while preserving preview and PDF availability. For compatibility, responses currently mirror `source_review` into the legacy `agentcore_review` field.

If OpenAI extraction is unavailable, the backend returns a normal generation response using deterministic source-text extraction. The response records the AI failure under `extracted.warnings`, and validation still blocks download when required DOT/GHS fields are missing or incomplete.

## Persistent runtime storage
For multi-instance and restart-safe behavior, runtime label artifacts + metadata now default to:
- `<repo>/runtime_data/labels`

Override location with:
- `CLEAREDGE_DATA_DIR=/path/to/persistent/volume`

This path should be mounted to persistent storage in production.
