# Deployment Quick Reference

## Prerequisites Checklist

- [ ] Google Cloud project created
- [ ] Billing enabled
- [ ] gcloud CLI installed
- [ ] Gemini API key obtained
- [ ] Service account JSON key downloaded
- [ ] Shared Drive access granted to service account

## One-Command Deploy

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Setup secrets (first time only)
./setup-secrets.sh $PROJECT_ID

# Deploy
./deploy.sh $PROJECT_ID us-central1
```

## Verify Deployment

```bash
./verify-deployment.sh https://YOUR-SERVICE-URL
```

## Common Commands

### View Logs
```bash
gcloud run services logs read clearedge-pipeline \
  --region=us-central1 \
  --project=$PROJECT_ID \
  --limit=50
```

### Update Secrets
```bash
# Update Gemini API key
echo -n "NEW_KEY" | gcloud secrets versions add gemini-api-key --data-file=-

# Force redeploy to use new secret
gcloud run services update clearedge-pipeline --region=us-central1
```

### Scale Configuration
```bash
# Increase max instances
gcloud run services update clearedge-pipeline \
  --max-instances=20 \
  --region=us-central1

# Set minimum instances (always warm)
gcloud run services update clearedge-pipeline \
  --min-instances=1 \
  --region=us-central1
```

### Enable Authentication
```bash
gcloud run services update clearedge-pipeline \
  --no-allow-unauthenticated \
  --region=us-central1
```

### Get Service URL
```bash
gcloud run services describe clearedge-pipeline \
  --region=us-central1 \
  --format="value(status.url)"
```

## Rollback

```bash
# List revisions
gcloud run revisions list \
  --service=clearedge-pipeline \
  --region=us-central1

# Rollback to previous
gcloud run services update-traffic clearedge-pipeline \
  --to-revisions=REVISION_NAME=100 \
  --region=us-central1
```

## Cost Optimization

```bash
# Minimum cost configuration
gcloud run services update clearedge-pipeline \
  --min-instances=0 \
  --max-instances=5 \
  --memory=1Gi \
  --cpu=1 \
  --region=us-central1
```

## Monitoring

### View Metrics
```bash
gcloud run services describe clearedge-pipeline \
  --region=us-central1 \
  --format=yaml
```

### Stream Logs
```bash
gcloud run services logs tail clearedge-pipeline \
  --region=us-central1
```

## Environment Variables

Set additional environment variables:
```bash
gcloud run services update clearedge-pipeline \
  --update-env-vars="KEY=VALUE,KEY2=VALUE2" \
  --region=us-central1
```

## Troubleshooting

### Check Service Status
```bash
gcloud run services describe clearedge-pipeline --region=us-central1
```

### Test Locally with Docker
```bash
docker build -t test .
docker run -p 8080:8080 \
  -e GEMINI_API_KEY="key" \
  -e GOOGLE_SERVICE_ACCOUNT_FILE=/app/key.json \
  test
```

### View Recent Errors
```bash
gcloud run services logs read clearedge-pipeline \
  --region=us-central1 \
  --limit=20 \
  --format="table(timestamp,severity,textPayload)"
```

## Support Links

- **Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Cloud Run Docs**: https://cloud.google.com/run/docs
- **Pricing**: https://cloud.google.com/run/pricing
- **Quotas**: https://cloud.google.com/run/quotas
