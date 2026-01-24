#!/bin/bash

##############################################################################
# CLEAR EDGE Label Pipeline - Secret Manager Setup Script
#
# This script helps you create and manage secrets in Google Secret Manager
# for secure credential storage.
#
# Usage:
#   ./setup-secrets.sh [PROJECT_ID]
#
# Example:
#   ./setup-secrets.sh my-project-123
##############################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ID="${1:-}"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if project ID provided
if [ -z "$PROJECT_ID" ]; then
    log_error "Project ID required"
    echo "Usage: ./setup-secrets.sh [PROJECT_ID]"
    exit 1
fi

log_info "Setting up secrets for project: ${PROJECT_ID}"

# Enable Secret Manager API
log_info "Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project="${PROJECT_ID}"
log_success "Secret Manager API enabled"

# Create Gemini API Key secret
log_info "Setting up Gemini API key secret..."
if gcloud secrets describe gemini-api-key --project="${PROJECT_ID}" &> /dev/null; then
    log_warning "Secret 'gemini-api-key' already exists"
    read -p "Do you want to update it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -s -p "Enter your Gemini API key: " GEMINI_KEY
        echo
        echo -n "$GEMINI_KEY" | gcloud secrets versions add gemini-api-key \
            --data-file=- \
            --project="${PROJECT_ID}"
        log_success "Gemini API key updated"
    fi
else
    read -s -p "Enter your Gemini API key: " GEMINI_KEY
    echo
    echo -n "$GEMINI_KEY" | gcloud secrets create gemini-api-key \
        --data-file=- \
        --replication-policy="automatic" \
        --project="${PROJECT_ID}"
    log_success "Gemini API key created"
fi

# Create Service Account JSON secret
log_info "Setting up service account JSON secret..."
if gcloud secrets describe service-account-json --project="${PROJECT_ID}" &> /dev/null; then
    log_warning "Secret 'service-account-json' already exists"
    read -p "Do you want to update it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f "service-account-key.json" ]; then
            gcloud secrets versions add service-account-json \
                --data-file=service-account-key.json \
                --project="${PROJECT_ID}"
            log_success "Service account JSON updated"
        else
            log_error "service-account-key.json not found in current directory"
            exit 1
        fi
    fi
else
    if [ -f "service-account-key.json" ]; then
        gcloud secrets create service-account-json \
            --data-file=service-account-key.json \
            --replication-policy="automatic" \
            --project="${PROJECT_ID}"
        log_success "Service account JSON created"
    else
        log_error "service-account-key.json not found in current directory"
        log_info "Please download your service account key file and name it 'service-account-key.json'"
        exit 1
    fi
fi

# Grant Cloud Run service account access to secrets
log_info "Granting Cloud Run access to secrets..."

# Get compute service account
COMPUTE_SA="${PROJECT_ID}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}"

gcloud secrets add-iam-policy-binding service-account-json \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}"

log_success "Access granted to Cloud Run service account"

# Summary
echo ""
echo "=========================================="
log_success "Secret setup complete!"
echo "=========================================="
echo ""
echo "Created secrets:"
echo "  1. gemini-api-key"
echo "  2. service-account-json"
echo ""
echo "These secrets are accessible by Cloud Run."
echo ""
echo "Next steps:"
echo "  1. Run: ./deploy.sh ${PROJECT_ID}"
echo ""
