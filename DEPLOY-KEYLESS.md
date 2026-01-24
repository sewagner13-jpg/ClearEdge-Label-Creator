# Keyless Deployment Guide

## For Organizations That Block Service Account Key Creation

If your organization has the `iam.disableServiceAccountKeyCreation` policy enforced, use this guide.

This deployment method uses **Application Default Credentials (ADC)** - no service account keys required!

---

## 🚀 Quick Deploy (5 Commands)

```bash
cd /home/user/ClearEdge-Label-Creator

# 1. Set your project ID
export PROJECT_ID="your-project-id"

# 2. Run keyless deployment
./deploy-no-keys.sh $PROJECT_ID us-central1
```

**During deployment**, you'll be prompted to:
1. Share your Shared Drive with the service account email
2. Wait for the build to complete (~5-10 minutes)

That's it! ✅

---

## 📋 What This Does

### Authentication Method: Application Default Credentials (ADC)

Cloud Run services automatically have access to a **default service account**:
- Email: `{PROJECT_ID}-compute@developer.gserviceaccount.com`
- No keys needed - credentials are automatically available via the metadata server
- More secure than using service account keys

### What Gets Created

1. **Gemini API Key Secret** - Stored in Google Secret Manager
2. **Cloud Run Service** - Running your application
3. **Container Image** - Built and stored in Container Registry

### What Doesn't Get Created

- ❌ No service account keys (blocked by org policy)
- ❌ No service account JSON secrets
- ❌ No downloadable credentials

---

## 🔐 How Authentication Works

### Cloud Run → Drive API

```
Cloud Run Service
    ↓ (uses)
Default Compute Service Account
    ↓ (authenticates via)
Google Metadata Server (automatic)
    ↓ (calls)
Google Drive API
```

**No keys or secrets involved!**

### Application Code

The `drive_client.py` automatically detects the environment:

```python
# Cloud Run (keyless)
credentials, project = google.auth.default(scopes=SCOPES)

# Uses metadata server - no keys needed!
```

---

## 📝 Prerequisites

Before running `deploy-no-keys.sh`:

1. **Google Cloud Project**
   ```bash
   gcloud projects list
   # or create new:
   gcloud projects create my-project-id
   ```

2. **Billing Enabled**
   - Go to: https://console.cloud.google.com/billing
   - Link billing account to your project

3. **gcloud CLI Authenticated**
   ```bash
   gcloud auth login
   ```

4. **Shared Drive Access**
   - You must be able to share the Shared Drive (0APFlqBVg60o6Uk9PVA)
   - You'll share it with the compute service account during deployment

---

## 🎯 Deployment Steps (Detailed)

### Step 1: Prepare Your Project

```bash
# List your projects
gcloud projects list

# Set your project
export PROJECT_ID="your-actual-project-id"
```

### Step 2: Run Deployment Script

```bash
cd /home/user/ClearEdge-Label-Creator
./deploy-no-keys.sh $PROJECT_ID us-central1
```

### Step 3: Share Shared Drive

When prompted during deployment:

1. **Copy the service account email** shown on screen
   - Format: `{PROJECT_ID}-compute@developer.gserviceaccount.com`

2. **Go to Google Drive**
   - Open Shared Drive with ID: `0APFlqBVg60o6Uk9PVA`

3. **Click Share**
   - Paste the service account email
   - Grant **"Content Manager"** permission
   - Click **Send**

4. **Press Enter** in the terminal to continue

### Step 4: Wait for Build

The script will:
- Enable required APIs (~1 min)
- Build Docker container (~5-7 min)
- Deploy to Cloud Run (~2 min)
- Verify deployment (~30 sec)

**Total time: ~10 minutes**

### Step 5: Verify

After deployment completes, test your service:

```bash
# Get service URL from deployment output
export SERVICE_URL="https://your-service-url"

# Test health
curl $SERVICE_URL/health

# Test products
curl $SERVICE_URL/products

# Open API docs
open $SERVICE_URL/docs  # or visit in browser
```

---

## 🔧 Troubleshooting

### "Permission denied" errors

**Cause:** Default service account doesn't have Drive access.

**Fix:**
1. Get service account email:
   ```bash
   echo "${PROJECT_ID}-compute@developer.gserviceaccount.com"
   ```
2. Share Shared Drive with this email
3. Grant "Content Manager" permission

### "Billing must be enabled"

**Fix:**
```bash
# Open billing page
echo "https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
```

Visit that URL and link a billing account.

### "Service fails to start"

Check logs:
```bash
gcloud run services logs read clearedge-pipeline \
  --region=us-central1 \
  --limit=50
```

Common issues:
- Shared Drive not shared with service account
- Wrong Shared Drive ID
- Gemini API key invalid

### "Health check fails"

Wait 30 seconds for the service to warm up:
```bash
sleep 30
curl $SERVICE_URL/health
```

If still failing:
```bash
# Check service status
gcloud run services describe clearedge-pipeline \
  --region=us-central1 \
  --format=yaml
```

---

## 🔄 Updating Your Deployment

### Update Code

```bash
# Make changes to your code
git pull  # or edit files

# Redeploy (same command)
./deploy-no-keys.sh $PROJECT_ID us-central1
```

### Update Gemini API Key

```bash
# Update the key in the script or:
echo -n "NEW_API_KEY" | \
  gcloud secrets versions add gemini-api-key \
  --data-file=- \
  --project=$PROJECT_ID

# Force redeploy
gcloud run services update clearedge-pipeline \
  --region=us-central1
```

---

## 💰 Cost Estimate

**Free Tier (Monthly):**
- 2 million requests
- 360,000 GB-seconds
- 180,000 vCPU-seconds

**Paid Usage:**
- ~$5-20/month for moderate use
- Scales to zero when idle (no cost)
- Auto-scaling 0-10 instances

---

## 🎯 Comparison: Keyless vs Key-Based

| Feature | Keyless (ADC) | Key-Based |
|---------|---------------|-----------|
| Security | ✅ More secure | ⚠️ Keys can leak |
| Setup | ✅ Simpler | ❌ More complex |
| Org Policy | ✅ Works | ❌ May be blocked |
| Key Management | ✅ None needed | ❌ Rotation required |
| Authentication | ✅ Automatic | ❌ Manual |

**Recommendation:** Always use keyless deployment when possible!

---

## 📚 Technical Details

### Service Account Permissions

The default compute service account automatically has:
- ✅ Access to Google APIs in the same project
- ✅ Secret Manager secret accessor (granted by script)
- ✅ Drive API access (after sharing Shared Drive)

### Code Changes

Updated `app/drive_client.py`:

```python
# Fallback to Application Default Credentials
else:
    logger.info("Using Application Default Credentials")
    credentials, project = google.auth.default(scopes=self.SCOPES)
```

No other code changes needed!

### Environment Variables

Required (set by deployment script):
- `GEMINI_API_KEY` - From Secret Manager
- `SHARED_DRIVE_ID` - Set to: 0APFlqBVg60o6Uk9PVA
- `ENV` - Set to: production
- `LOG_LEVEL` - Set to: INFO

Not required (handled automatically):
- ~~`GOOGLE_SERVICE_ACCOUNT_FILE`~~ - Not used in Cloud Run
- ~~`GOOGLE_SERVICE_ACCOUNT_JSON`~~ - Not needed with ADC

---

## ✅ Success Checklist

After deployment, verify:

- [ ] Service is running: `gcloud run services list`
- [ ] Health check passes: `curl $SERVICE_URL/health`
- [ ] Products endpoint works: `curl $SERVICE_URL/products`
- [ ] API docs accessible: Visit `$SERVICE_URL/docs`
- [ ] Logs are clean: `gcloud run services logs read clearedge-pipeline`

---

## 🆘 Get Help

- **Cloud Run Docs**: https://cloud.google.com/run/docs
- **ADC Docs**: https://cloud.google.com/docs/authentication/production
- **Drive API**: https://developers.google.com/drive/api/guides/about-auth

**Need more help?** Check the main [DEPLOYMENT.md](DEPLOYMENT.md) or [README.md](README.md).

---

## 🎉 Next Steps

After successful deployment:

1. **Test all endpoints** - See [DEPLOYMENT.md](DEPLOYMENT.md#post-deployment)
2. **Set up monitoring** - Enable Cloud Monitoring alerts
3. **Configure authentication** - Add IAM if needed
4. **Set up CI/CD** - Use GitHub Actions (already configured)

**Ready to deploy?** Run:

```bash
./deploy-no-keys.sh YOUR_PROJECT_ID us-central1
```

Good luck! 🚀
