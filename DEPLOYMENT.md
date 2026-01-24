# Deployment Guide - Google Cloud Run

This guide walks you through deploying the CLEAR EDGE Label Pipeline to Google Cloud Run.

## Prerequisites

✅ **Google Cloud Account** with billing enabled
✅ **gcloud CLI** installed ([Install Guide](https://cloud.google.com/sdk/docs/install))
✅ **Docker** installed ([Install Guide](https://docs.docker.com/get-docker/))
✅ **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/app/apikey)
✅ **Service Account JSON** key file for Drive API

---

## Quick Deploy (5 Minutes)

### Step 1: Set Your Project ID

```bash
export PROJECT_ID="your-project-id-here"
export REGION="us-central1"  # or your preferred region
```

### Step 2: Authenticate

```bash
# Login to Google Cloud
gcloud auth login

# Set default project
gcloud config set project $PROJECT_ID
```

### Step 3: Setup Secrets

```bash
# Run the secret setup script
./setup-secrets.sh $PROJECT_ID
```

When prompted:
- Enter your **Gemini API Key**
- Ensure **service-account-key.json** is in the current directory

### Step 4: Deploy

```bash
# Run the deployment script
./deploy.sh $PROJECT_ID $REGION
```

This will:
1. Enable required APIs
2. Build Docker image
3. Deploy to Cloud Run
4. Configure secrets
5. Return your service URL

### Step 5: Verify

```bash
# Test the health endpoint
curl https://YOUR-SERVICE-URL/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00",
  "gemini_model": "gemini-1.5-pro",
  "shared_drive_id": "0APFlqBVg60o6Uk9PVA"
}
```

---

## Manual Deployment (Step-by-Step)

If you prefer manual control or the scripts fail:

### 1. Enable APIs

```bash
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  drive.googleapis.com \
  --project=$PROJECT_ID
```

### 2. Create Secrets

**Gemini API Key:**
```bash
echo -n "YOUR_GEMINI_API_KEY" | \
  gcloud secrets create gemini-api-key \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID
```

**Service Account JSON:**
```bash
gcloud secrets create service-account-json \
  --data-file=service-account-key.json \
  --replication-policy="automatic" \
  --project=$PROJECT_ID
```

**Grant Access:**
```bash
# Get compute service account
COMPUTE_SA="${PROJECT_ID}-compute@developer.gserviceaccount.com"

# Grant access to secrets
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID

gcloud secrets add-iam-policy-binding service-account-json \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID
```

### 3. Build Docker Image

```bash
# Build and push to Container Registry
gcloud builds submit \
  --tag gcr.io/$PROJECT_ID/clearedge-pipeline:latest \
  --project=$PROJECT_ID
```

### 4. Deploy to Cloud Run

```bash
gcloud run deploy clearedge-pipeline \
  --image=gcr.io/$PROJECT_ID/clearedge-pipeline:latest \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --timeout=3600 \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=10 \
  --set-env-vars="ENV=production,LOG_LEVEL=INFO,SHARED_DRIVE_ID=0APFlqBVg60o6Uk9PVA,ROOT_FOLDER_NAME=Product Labels" \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_SERVICE_ACCOUNT_JSON=service-account-json:latest" \
  --project=$PROJECT_ID
```

### 5. Get Service URL

```bash
gcloud run services describe clearedge-pipeline \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="value(status.url)"
```

---

## Configuration Options

### Environment Variables

Set via `--set-env-vars` flag:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | production | Environment mode |
| `LOG_LEVEL` | INFO | Logging level |
| `SHARED_DRIVE_ID` | 0APFlqBVg60o6Uk9PVA | Shared Drive ID |
| `ROOT_FOLDER_NAME` | Product Labels | Root folder name |
| `GEMINI_MODEL` | gemini-1.5-pro | Gemini model |
| `TESSERACT_CMD` | /usr/bin/tesseract | Tesseract path |

### Secrets

Set via `--set-secrets` flag:

| Secret | Description |
|--------|-------------|
| `GEMINI_API_KEY` | Gemini API key from AI Studio |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account credentials |

### Resource Limits

Adjust for your workload:

```bash
--memory=2Gi          # RAM allocation
--cpu=2               # CPU cores
--timeout=3600        # Max request timeout (1 hour)
--min-instances=0     # Min instances (0 = scale to zero)
--max-instances=10    # Max instances for scaling
```

---

## Cost Estimation

### Free Tier (Monthly)
- 2 million requests
- 360,000 GB-seconds
- 180,000 vCPU-seconds
- 1 GB network egress

### Estimated Costs (After Free Tier)

**Light Usage** (~100 extractions/month):
- ~$2-5/month

**Moderate Usage** (~500 extractions/month):
- ~$10-20/month

**Heavy Usage** (~2000 extractions/month):
- ~$40-80/month

**Cost Optimization:**
- Set `--min-instances=0` to scale to zero
- Use smaller memory if possible (`--memory=1Gi`)
- Set appropriate `--max-instances` limit

---

## Post-Deployment

### Testing the API

```bash
# Set service URL
SERVICE_URL="https://your-service-url"

# Health check
curl $SERVICE_URL/health

# List products
curl $SERVICE_URL/products

# Extract a product
curl -X POST "$SERVICE_URL/extract/APS-100?mode=shipped_dot"
```

### Monitoring

View logs:
```bash
gcloud run services logs read clearedge-pipeline \
  --region=$REGION \
  --project=$PROJECT_ID
```

View metrics:
```bash
gcloud run services describe clearedge-pipeline \
  --region=$REGION \
  --project=$PROJECT_ID
```

### Updating

Rebuild and redeploy:
```bash
# Build new image
gcloud builds submit --tag gcr.io/$PROJECT_ID/clearedge-pipeline:latest

# Redeploy (uses latest image)
gcloud run services update clearedge-pipeline \
  --image=gcr.io/$PROJECT_ID/clearedge-pipeline:latest \
  --region=$REGION \
  --project=$PROJECT_ID
```

Or use the deploy script:
```bash
./deploy.sh $PROJECT_ID $REGION
```

---

## Security Best Practices

### 1. Restrict Access

By default, the service allows unauthenticated access. For production:

```bash
# Require authentication
gcloud run services update clearedge-pipeline \
  --no-allow-unauthenticated \
  --region=$REGION \
  --project=$PROJECT_ID
```

Then access with:
```bash
# Get auth token
TOKEN=$(gcloud auth print-identity-token)

# Call API with token
curl -H "Authorization: Bearer $TOKEN" $SERVICE_URL/health
```

### 2. Use Custom Domain

```bash
# Map custom domain
gcloud run domain-mappings create \
  --service=clearedge-pipeline \
  --domain=api.yourdomain.com \
  --region=$REGION \
  --project=$PROJECT_ID
```

### 3. Rotate Secrets

```bash
# Update Gemini API key
echo -n "NEW_API_KEY" | \
  gcloud secrets versions add gemini-api-key \
  --data-file=- \
  --project=$PROJECT_ID

# Force new deployment to use updated secret
gcloud run services update clearedge-pipeline \
  --region=$REGION \
  --project=$PROJECT_ID
```

### 4. Enable VPC

For additional security, deploy to VPC:

```bash
gcloud run services update clearedge-pipeline \
  --vpc-connector=YOUR_VPC_CONNECTOR \
  --vpc-egress=all-traffic \
  --region=$REGION \
  --project=$PROJECT_ID
```

---

## Troubleshooting

### "Permission denied" errors

**Cause:** Service account lacks Drive access.

**Fix:**
1. Get service account email from `service-account-key.json`
2. Share Shared Drive with this email
3. Grant "Content Manager" permission

### "Secret not found" errors

**Cause:** Secrets not created or inaccessible.

**Fix:**
```bash
# List secrets
gcloud secrets list --project=$PROJECT_ID

# Verify access
gcloud secrets get-iam-policy gemini-api-key --project=$PROJECT_ID

# Re-run setup
./setup-secrets.sh $PROJECT_ID
```

### "Container startup failed" errors

**Cause:** Missing dependencies or configuration issues.

**Fix:**
1. Check logs: `gcloud run services logs read clearedge-pipeline`
2. Verify environment variables are set
3. Test Docker image locally:
   ```bash
   docker build -t test .
   docker run -p 8080:8080 \
     -e GEMINI_API_KEY="your_key" \
     -e GOOGLE_SERVICE_ACCOUNT_FILE=/app/key.json \
     test
   ```

### "Timeout" errors during extraction

**Cause:** Request exceeds timeout limit.

**Fix:**
```bash
# Increase timeout (max 3600s)
gcloud run services update clearedge-pipeline \
  --timeout=3600 \
  --region=$REGION \
  --project=$PROJECT_ID
```

---

## Rollback

If deployment fails, rollback to previous version:

```bash
# List revisions
gcloud run revisions list \
  --service=clearedge-pipeline \
  --region=$REGION \
  --project=$PROJECT_ID

# Rollback to specific revision
gcloud run services update-traffic clearedge-pipeline \
  --to-revisions=REVISION_NAME=100 \
  --region=$REGION \
  --project=$PROJECT_ID
```

---

## Alternative: Deploy Using YAML

```bash
# Edit cloudrun.yaml with your PROJECT_ID
sed -i "s/PROJECT_ID/$PROJECT_ID/g" cloudrun.yaml

# Deploy from YAML
gcloud run services replace cloudrun.yaml \
  --region=$REGION \
  --project=$PROJECT_ID
```

---

## Next Steps

✅ Deploy completed successfully
✅ Service is running
✅ Credentials configured

**Now:**
1. Test all API endpoints
2. Set up monitoring alerts
3. Configure custom domain (optional)
4. Implement authentication (production)
5. Set up CI/CD for automatic deployments

**For CI/CD**, see [GitHub Actions deployment example](https://cloud.google.com/run/docs/continuous-deployment-with-github-actions).

---

## Support

- **Cloud Run Docs**: https://cloud.google.com/run/docs
- **Pricing Calculator**: https://cloud.google.com/products/calculator
- **Status Dashboard**: https://status.cloud.google.com

**Need help?** Check the main [README.md](README.md) or [QUICKSTART.md](QUICKSTART.md).
