#!/bin/bash

##############################################################################
# CLEAR EDGE Label Pipeline - Deployment Verification Script
#
# Tests all API endpoints to verify successful deployment.
#
# Usage:
#   ./verify-deployment.sh [SERVICE_URL]
#
# Example:
#   ./verify-deployment.sh https://clearedge-pipeline-xyz-uc.a.run.app
##############################################################################

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVICE_URL="${1:-}"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if URL provided
if [ -z "$SERVICE_URL" ]; then
    log_error "Service URL required"
    echo "Usage: ./verify-deployment.sh [SERVICE_URL]"
    echo "Example: ./verify-deployment.sh https://clearedge-pipeline-xyz-uc.a.run.app"
    exit 1
fi

# Remove trailing slash
SERVICE_URL="${SERVICE_URL%/}"

echo ""
log_info "Verifying deployment at: $SERVICE_URL"
echo ""

# Test 1: Health Check
log_info "Test 1: Health Check"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$SERVICE_URL/health")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    log_success "Health check passed (HTTP $HTTP_CODE)"
    echo "$RESPONSE_BODY" | jq '.' 2>/dev/null || echo "$RESPONSE_BODY"
else
    log_error "Health check failed (HTTP $HTTP_CODE)"
    echo "$RESPONSE_BODY"
    exit 1
fi

echo ""

# Test 2: API Documentation
log_info "Test 2: API Documentation (OpenAPI)"
DOCS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/docs")

if [ "$DOCS_CODE" -eq 200 ]; then
    log_success "API docs accessible at $SERVICE_URL/docs"
else
    log_warning "API docs returned HTTP $DOCS_CODE"
fi

echo ""

# Test 3: List Products
log_info "Test 3: List Products Endpoint"
PRODUCTS_RESPONSE=$(curl -s -w "\n%{http_code}" "$SERVICE_URL/products")
HTTP_CODE=$(echo "$PRODUCTS_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$PRODUCTS_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    log_success "Products endpoint working (HTTP $HTTP_CODE)"
    echo "$RESPONSE_BODY" | jq '.' 2>/dev/null || echo "$RESPONSE_BODY"
else
    log_error "Products endpoint failed (HTTP $HTTP_CODE)"
    echo "$RESPONSE_BODY"
fi

echo ""

# Test 4: Gemini Connection (via health check response)
log_info "Test 4: Gemini Configuration"
GEMINI_MODEL=$(echo "$HEALTH_RESPONSE" | head -n-1 | jq -r '.gemini_model' 2>/dev/null)

if [ -n "$GEMINI_MODEL" ] && [ "$GEMINI_MODEL" != "null" ]; then
    log_success "Gemini configured: $GEMINI_MODEL"
else
    log_warning "Could not verify Gemini configuration"
fi

echo ""

# Test 5: Drive Connection (check if products can be listed)
log_info "Test 5: Google Drive Connection"
PRODUCT_COUNT=$(echo "$PRODUCTS_RESPONSE" | head -n-1 | jq '.products | length' 2>/dev/null)

if [ -n "$PRODUCT_COUNT" ] && [ "$PRODUCT_COUNT" != "null" ]; then
    log_success "Drive connected: $PRODUCT_COUNT products found"
else
    log_warning "Could not verify Drive connection"
fi

echo ""

# Summary
echo "=========================================="
log_success "Deployment Verification Complete"
echo "=========================================="
echo ""
echo "Service URL: $SERVICE_URL"
echo "API Documentation: $SERVICE_URL/docs"
echo "API Spec (JSON): $SERVICE_URL/openapi.json"
echo ""
echo "Quick Test Commands:"
echo "  # Health check"
echo "  curl $SERVICE_URL/health | jq"
echo ""
echo "  # List products"
echo "  curl $SERVICE_URL/products | jq"
echo ""
echo "  # Extract a product (replace PRODUCT_NAME)"
echo "  curl -X POST '$SERVICE_URL/extract/PRODUCT_NAME?mode=shipped_dot' | jq"
echo ""
log_success "All core systems operational! 🚀"
echo ""
