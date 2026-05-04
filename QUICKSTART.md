# Quick Start Guide

Get the CLEAR EDGE Label Pipeline running in 10 minutes.

## Prerequisites

- Python 3.11+
- Google Cloud account
- Gemini API key
- Shared Drive access

## Step 1: Install Dependencies

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install tesseract-ocr poppler-utils
```

## Step 2: Get Credentials

### Gemini API Key
1. Visit https://aistudio.google.com/app/apikey
2. Create or copy API key
3. Save for next step

### Google Service Account
1. Go to https://console.cloud.google.com/
2. Create new project
3. Enable Google Drive API
4. Create service account
5. Download JSON key file
6. Save as `service-account-key.json`

## Step 3: Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env
nano .env
```

**Required changes:**
```bash
GEMINI_API_KEY=your_gemini_key_here
GOOGLE_SERVICE_ACCOUNT_FILE=/full/path/to/service-account-key.json
```

## Step 4: Grant Drive Access

1. Open Shared Drive in Google Drive
2. Click Share
3. Add service account email (from JSON key file)
4. Grant "Content Manager" permission

## Step 5: Verify Setup

```bash
# Start API server
python -m app.main
```

In another terminal:
```bash
# Health check
curl http://localhost:8000/health

# List products
curl http://localhost:8000/products
```

## Step 6: First Extraction

### Option A: Using CLI

```bash
# Scan for products
python pipeline_cli.py scan-drive

# Extract a product
python pipeline_cli.py extract --product "YOUR-PRODUCT-NAME"
```

### Option B: Using API

```bash
# Extract via API
curl -X POST "http://localhost:8000/extract/YOUR-PRODUCT-NAME?mode=shipped_dot"
```

## Expected Output

If successful, you'll see:
- ✓ Extraction complete
- ✓ Validation PASSED
- Files saved to Drive in `Extracted/` and `Labels/` folders

## Next Steps

- Review extracted data in Drive
- Check validation warnings
- Generate labels for all products
- Customize label templates

## Troubleshooting

### "Product not found"
Run `python pipeline_cli.py scan-drive` to see available products.

### "Permission denied" errors
Verify service account has Shared Drive access.

### "Tesseract not found"
Install: `sudo apt-get install tesseract-ocr`

### "Gemini API error"
Check API key in `.env` is correct.

## Need Help?

See full README.md for detailed documentation.

## Fast local start helper

Use the helper script to start backend + print health/docs URLs:

```bash
./run-local.sh
```

Optional env overrides:

```bash
HOST=127.0.0.1 PORT=8000 ./run-local.sh
```

## Desktop icon launcher (Linux)

To add a clickable desktop icon:

```bash
./install-desktop-icon.sh
```

This installs `ClearEdge-Label-Creator.desktop` to your Desktop and launches `run-local.sh` in a terminal.
