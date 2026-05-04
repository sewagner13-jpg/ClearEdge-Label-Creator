#!/bin/bash

##############################################################################
# CLEAR EDGE Label Pipeline - Keyless Deployment Script
#
# This script deploys to Cloud Run WITHOUT service account keys,
# using Application Default Credentials (ADC).
#
# Works within organizations that block service account key creation.
#
# Prerequisites:
# - gcloud CLI installed and authenticated
# - Google Cloud project created
# - Billing enabled
#
# Usage:
#   ./deploy-no-keys.sh [PROJECT_ID] [REGION]
#
# Example:
#   ./deploy-no-keys.sh my-project-123 us-central1
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${1:-}"
REGION="${2:-us-central1}"
SERVICE_NAME="clearedge-pipeline"
GEMINI_API_KEY="${GEMINI_API_KEY:-}"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

check_prerequisites() {
    log_step "Step 1/7: Checking Prerequisites"

    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    # Check if project ID is provided
    if [ -z "$PROJECT_ID" ]; then
        log_error "Project ID not provided."
        echo "Usage: ./deploy-no-keys.sh [PROJECT_ID] [REGION]"
        echo "Example: ./deploy-no-keys.sh my-project-123 us-central1"
        exit 1
    fi

    log_success "Prerequisites OK"
}

configure_project() {
    log_step "Step 2/7: Configuring Google Cloud Project"

    log_info "Setting project: ${PROJECT_ID}"
    gcloud config set project "${PROJECT_ID}"
    gcloud config set run/region "${REGION}"

    log_success "Project configured"
}

enable_apis() {
    log_step "Step 3/7: Enabling Required APIs"

    log_info "Enabling APIs (this may take a minute)..."

    gcloud services enable \
        run.googleapis.com \
        containerregistry.googleapis.com \
        cloudbuild.googleapis.com \
        secretmanager.googleapis.com \
        drive.googleapis.com \
        --project="${PROJECT_ID}"

    log_success "APIs enabled"
}

get_service_account() {
    log_step "Step 4/7: Getting Default Service Account"

    # Get the default compute service account
    SA_EMAIL="${PROJECT_ID}-compute@developer.gserviceaccount.com"

    log_info "Default Compute Service Account:"
    echo -e "${CYAN}${SA_EMAIL}${NC}"
    echo ""

    log_warning "IMPORTANT: You must share your Shared Drive with this service account!"
    echo ""
    echo "Instructions:"
    echo "  1. Copy this email: ${SA_EMAIL}"
    echo "  2. Go to Google Drive"
    echo "  3. Open Shared Drive: 0APFlqBVg60o6Uk9PVA"
    echo "  4. Click 'Share' → Paste the email"
    echo "  5. Grant 'Content Manager' permission"
    echo "  6. Click 'Send'"
    echo ""

    read -p "Press Enter after you've shared the Drive with the service account..."

    log_success "Service account configured: ${SA_EMAIL}"
}

setup_secrets() {
    log_step "Step 5/7: Setting Up Secrets"

    if [ -z "$GEMINI_API_KEY" ]; then
        log_error "GEMINI_API_KEY is required. Export it before deploying:"
        echo "  export GEMINI_API_KEY='your_gemini_api_key_here'"
        exit 1
    fi

    # Check if Gemini secret exists
    if gcloud secrets describe gemini-api-key --project="${PROJECT_ID}" &> /dev/null; then
        log_warning "Secret 'gemini-api-key' already exists, updating..."
        echo -n "$GEMINI_API_KEY" | gcloud secrets versions add gemini-api-key \
            --data-file=- \
            --project="${PROJECT_ID}"
    else
        log_info "Creating Gemini API key secret..."
        echo -n "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
            --data-file=- \
            --replication-policy="automatic" \
            --project="${PROJECT_ID}"
    fi

    # Grant access to the compute service account
    log_info "Granting secret access to service account..."
    gcloud secrets add-iam-policy-binding gemini-api-key \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/secretmanager.secretAccessor" \
        --project="${PROJECT_ID}" \
        &> /dev/null || true

    log_success "Secrets configured"
}

build_and_deploy() {
    log_step "Step 6/7: Building and Deploying to Cloud Run"

    log_info "Starting Cloud Build (this takes 5-10 minutes)..."
    log_info "Building Docker image..."

    # Deploy using source-based deployment (Cloud Build)
    gcloud run deploy "${SERVICE_NAME}" \
        --source . \
        --platform=managed \
        --region="${REGION}" \
        --allow-unauthenticated \
        --timeout=3600 \
        --memory=2Gi \
        --cpu=2 \
        --min-instances=0 \
        --max-instances=10 \
        --set-env-vars="ENV=production,LOG_LEVEL=INFO,SHARED_DRIVE_ID=0APFlqBVg60o6Uk9PVA,ROOT_FOLDER_NAME=Product Labels,GEMINI_MODEL=gemini-1.5-pro" \
        --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
        --project="${PROJECT_ID}"

    log_success "Service deployed!"
}

verify_deployment() {
    log_step "Step 7/7: Verifying Deployment"

    SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --format="value(status.url)")

    log_info "Testing health endpoint..."

    sleep 5  # Give it a moment to warm up

    if curl -sf "${SERVICE_URL}/health" > /dev/null; then
        log_success "Health check passed!"
    else
        log_warning "Health check didn't respond immediately (this is normal)"
        log_info "The service may still be starting up"
    fi

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}🚀 DEPLOYMENT SUCCESSFUL!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Service URL: ${CYAN}${SERVICE_URL}${NC}"
    echo ""
    echo "Quick Tests:"
    echo "  # Health check"
    echo "  curl ${SERVICE_URL}/health"
    echo ""
    echo "  # List products"
    echo "  curl ${SERVICE_URL}/products"
    echo ""
    echo "  # API Documentation"
    echo "  ${SERVICE_URL}/docs"
    echo ""
    echo "View logs:"
    echo "  gcloud run services logs read ${SERVICE_NAME} --region=${REGION}"
    echo ""
    log_success "All done! 🎉"
}

# Main execution
main() {
    echo ""
    log_info "CLEAR EDGE Label Pipeline - Keyless Deployment"
    log_info "Using Application Default Credentials (no service account keys)"
    echo ""

    check_prerequisites
    configure_project
    enable_apis
    get_service_account
    setup_secrets
    build_and_deploy
    verify_deployment
}

# Run main function
main
