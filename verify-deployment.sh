#!/bin/bash

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVICE_URL="${1:-}"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_error() { echo -e "${RED}[ERR]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }

if [ -z "$SERVICE_URL" ]; then
    log_error "Service URL required"
    echo "Usage: ./verify-deployment.sh [SERVICE_URL]"
    exit 1
fi

SERVICE_URL="${SERVICE_URL%/}"

log_info "Verifying deployment at: $SERVICE_URL"

HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$SERVICE_URL/api/v1/health")
HEALTH_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
HEALTH_BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)

if [ "$HEALTH_CODE" -eq 200 ]; then
    log_success "Health check passed"
    echo "$HEALTH_BODY" | jq '.' 2>/dev/null || echo "$HEALTH_BODY"
else
    log_error "Health check failed with HTTP $HEALTH_CODE"
    echo "$HEALTH_BODY"
    exit 1
fi

READINESS_RESPONSE=$(curl -s -w "\n%{http_code}" "$SERVICE_URL/api/v1/readiness")
READINESS_CODE=$(echo "$READINESS_RESPONSE" | tail -n1)
READINESS_BODY=$(echo "$READINESS_RESPONSE" | head -n-1)

if [ "$READINESS_CODE" -eq 200 ]; then
    STATUS=$(echo "$READINESS_BODY" | jq -r '.status' 2>/dev/null || true)
    if [ "$STATUS" = "ready" ]; then
        log_success "Readiness is ready"
    else
        log_warning "Readiness is $STATUS"
    fi
    echo "$READINESS_BODY" | jq '.' 2>/dev/null || echo "$READINESS_BODY"
else
    log_error "Readiness failed with HTTP $READINESS_CODE"
    echo "$READINESS_BODY"
    exit 1
fi

DOCS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/docs")
if [ "$DOCS_CODE" -eq 200 ]; then
    log_success "API docs accessible"
else
    log_warning "API docs returned HTTP $DOCS_CODE"
fi

MODEL=$(echo "$HEALTH_BODY" | jq -r '.openai_model' 2>/dev/null || true)
if [ -n "$MODEL" ] && [ "$MODEL" != "null" ]; then
    log_success "OpenAI model configured: $MODEL"
else
    log_warning "OpenAI model was not reported"
fi

COMMIT_SHA=$(echo "$HEALTH_BODY" | jq -r '.build.commit_sha' 2>/dev/null || true)
if [ -n "$COMMIT_SHA" ] && [ "$COMMIT_SHA" != "null" ] && [ "$COMMIT_SHA" != "unknown" ]; then
    log_success "Deployed commit: $COMMIT_SHA"
else
    log_warning "Deployment commit identity was not reported"
fi

echo
log_success "Deployment verification complete"
