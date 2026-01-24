#!/bin/bash

##############################################################################
# CLEAR EDGE Label Pipeline - Cloud Run Deployment Script
#
# This script deploys the application to Google Cloud Run with all
# necessary configurations.
#
# Prerequisites:
# - gcloud CLI installed and authenticated
# - Google Cloud project created
# - APIs enabled (Run, Secret Manager, Container Registry)
# - Secrets created (gemini-api-key, service-account-key)
#
# Usage:
#   ./deploy.sh [PROJECT_ID] [REGION]
#
# Example:
#   ./deploy.sh my-project-123 us-central1
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${1:-}"
REGION="${2:-us-central1}"
SERVICE_NAME="clearedge-pipeline"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Functions
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

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Install from: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Check if project ID is provided
    if [ -z "$PROJECT_ID" ]; then
        log_error "Project ID not provided."
        echo "Usage: ./deploy.sh [PROJECT_ID] [REGION]"
        echo "Example: ./deploy.sh my-project-123 us-central1"
        exit 1
    fi

    log_success "Prerequisites OK"
}

configure_project() {
    log_info "Configuring Google Cloud project: ${PROJECT_ID}"

    gcloud config set project "${PROJECT_ID}"
    gcloud config set run/region "${REGION}"

    log_success "Project configured"
}

enable_apis() {
    log_info "Enabling required APIs..."

    gcloud services enable \
        run.googleapis.com \
        containerregistry.googleapis.com \
        cloudbuild.googleapis.com \
        secretmanager.googleapis.com \
        drive.googleapis.com \
        --project="${PROJECT_ID}"

    log_success "APIs enabled"
}

check_secrets() {
    log_info "Checking for required secrets..."

    # Check for Gemini API key
    if ! gcloud secrets describe gemini-api-key --project="${PROJECT_ID}" &> /dev/null; then
        log_warning "Secret 'gemini-api-key' not found."
        log_info "Creating secret (you'll need to add the value manually)..."
        echo -n "REPLACE_WITH_YOUR_GEMINI_API_KEY" | \
            gcloud secrets create gemini-api-key \
            --data-file=- \
            --project="${PROJECT_ID}"
        log_warning "Remember to update the secret value with your actual Gemini API key"
    fi

    # Check for service account key
    if ! gcloud secrets describe service-account-json --project="${PROJECT_ID}" &> /dev/null; then
        log_warning "Secret 'service-account-json' not found."
        if [ -f "service-account-key.json" ]; then
            log_info "Creating secret from service-account-key.json..."
            gcloud secrets create service-account-json \
                --data-file=service-account-key.json \
                --project="${PROJECT_ID}"
        else
            log_warning "service-account-key.json not found. You'll need to create this secret manually."
        fi
    fi

    log_success "Secrets checked"
}

build_image() {
    log_info "Building Docker image..."

    # Submit build to Cloud Build
    gcloud builds submit \
        --tag "${IMAGE_NAME}:latest" \
        --project="${PROJECT_ID}" \
        .

    log_success "Image built: ${IMAGE_NAME}:latest"
}

deploy_service() {
    log_info "Deploying to Cloud Run..."

    gcloud run deploy "${SERVICE_NAME}" \
        --image="${IMAGE_NAME}:latest" \
        --platform=managed \
        --region="${REGION}" \
        --allow-unauthenticated \
        --timeout=3600 \
        --memory=2Gi \
        --cpu=2 \
        --min-instances=0 \
        --max-instances=10 \
        --set-env-vars="ENV=production,LOG_LEVEL=INFO,SHARED_DRIVE_ID=0APFlqBVg60o6Uk9PVA,ROOT_FOLDER_NAME=Product Labels" \
        --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_SERVICE_ACCOUNT_JSON=service-account-json:latest" \
        --project="${PROJECT_ID}"

    log_success "Service deployed"
}

get_service_url() {
    SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --format="value(status.url)")

    log_success "Deployment complete!"
    echo ""
    echo "=========================================="
    echo "Service URL: ${SERVICE_URL}"
    echo "=========================================="
    echo ""
    echo "Test with:"
    echo "  curl ${SERVICE_URL}/health"
    echo ""
}

# Main execution
main() {
    echo ""
    log_info "Starting deployment of CLEAR EDGE Label Pipeline"
    echo ""

    check_prerequisites
    configure_project
    enable_apis
    check_secrets
    build_image
    deploy_service
    get_service_url

    log_success "All done! 🚀"
}

# Run main function
main
