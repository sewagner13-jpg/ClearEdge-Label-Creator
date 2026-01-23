# CLEAR EDGE – PRODUCT LABEL PIPELINE

**Production-grade automated system for DOT/OSHA-compliant chemical product label generation**

This system automates the complete lifecycle of chemical product labels:
- **Ingestion** from Google Drive Shared Drive or controlled web sources
- **Extraction** of structured data from SDS/TDS PDFs using Gemini AI
- **Validation** against DOT and OSHA compliance requirements
- **Generation** of SVG/PDF labels with audit trails
- **Storage** in Google Workspace Shared Drive as system of record

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Google Cloud Setup](#google-cloud-setup)
6. [Gemini API Setup](#gemini-api-setup)
7. [Google Drive Setup](#google-drive-setup)
8. [Configuration](#configuration)
9. [Running the System](#running-the-system)
10. [API Endpoints](#api-endpoints)
11. [CLI Usage](#cli-usage)
12. [Folder Structure](#folder-structure)
13. [Compliance Modes](#compliance-modes)
14. [Testing](#testing)
15. [Troubleshooting](#troubleshooting)

---

## Features

### Core Capabilities

- **Multi-Source Ingestion**
  - Scan Google Drive Shared Drive folders for SDS/TDS PDFs
  - Controlled web retrieval with domain allowlist and user approval
  - Automatic file hashing (SHA-256) and deduplication

- **Intelligent Text Extraction**
  - Primary extraction via pdfplumber
  - Automatic OCR fallback (Tesseract) for low-quality scans
  - Page-by-page processing with method tracking

- **AI-Powered Structured Extraction**
  - Gemini 1.5 Pro for parsing SDS/TDS documents
  - Strict JSON schema enforcement (Pydantic v2)
  - Evidence-based extraction with source citations
  - Confidence scoring per field
  - Automatic JSON repair on malformed responses

- **Compliance Validation**
  - **Shipped DOT Mode**: UN number, proper shipping name, hazard class validation
  - **Workplace Mode**: GHS hazard communication compliance
  - Pictogram overlap detection (DOT vs GHS)
  - Configurable error/warning severity

- **Label Generation**
  - SVG generation from Jinja2 templates
  - PDF export via CairoSVG
  - Purple header branding (#5A2D82)
  - GHS pictograms and DOT placards
  - QR code placeholders for SDS links

- **Complete Audit Trail**
  - Extraction metadata with file IDs and hashes
  - Evidence JSON with verbatim source quotes
  - Validation results
  - Label build reports
  - Timestamped dated folders (YYYY-MM-DD)

---

## Architecture

```
┌─────────────────┐
│  Google Drive   │
│  Shared Drive   │
│  (System of     │
│   Record)       │
└────────┬────────┘
         │
         ├─── SDS/TDS PDFs
         │
    ┌────▼────────────────────────────┐
    │  CLEAR EDGE Label Pipeline      │
    │                                 │
    │  ┌──────────────────────────┐  │
    │  │  PDF Extraction + OCR    │  │
    │  └──────────┬───────────────┘  │
    │             │                   │
    │  ┌──────────▼───────────────┐  │
    │  │  Gemini AI Extraction    │  │
    │  │  (Structured JSON)       │  │
    │  └──────────┬───────────────┘  │
    │             │                   │
    │  ┌──────────▼───────────────┐  │
    │  │  Validation Engine       │  │
    │  │  (DOT/OSHA/GHS)         │  │
    │  └──────────┬───────────────┘  │
    │             │                   │
    │  ┌──────────▼───────────────┐  │
    │  │  Label Generator         │  │
    │  │  (SVG → PDF)            │  │
    │  └──────────┬───────────────┘  │
    │             │                   │
    │  ┌──────────▼───────────────┐  │
    │  │  Audit Logger            │  │
    │  └──────────────────────────┘  │
    └─────────────┬──────────────────┘
                  │
         ┌────────▼────────┐
         │  Google Drive   │
         │  (Audit Trail   │
         │   + Labels)     │
         └─────────────────┘
```

**Tech Stack:**
- Python 3.11+
- FastAPI (REST API)
- Pydantic v2 (validation)
- Gemini 1.5 Pro (AI extraction)
- Google Drive API v3
- pdfplumber + Tesseract OCR
- svgwrite + CairoSVG

---

## Prerequisites

### System Requirements

- **Python**: 3.11 or higher
- **OS**: Linux, macOS, or Windows with WSL
- **Tesseract OCR**: 4.0 or higher
- **Poppler**: For PDF rasterization (pdf2image dependency)

### Accounts Required

1. **Google Cloud Project** with Drive API enabled
2. **Google Workspace** account with Shared Drive access
3. **Gemini API Key** from Google AI Studio

---

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd ClearEdge-Label-Creator
```

### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install System Dependencies

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils
```

#### macOS
```bash
brew install tesseract poppler
```

#### Verify Installation
```bash
tesseract --version
pdftoppm -v
```

---

## Google Cloud Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project: **"ClearEdge-Labels"**
3. Note the Project ID

### 2. Enable APIs

Enable the following APIs for your project:

```bash
gcloud services enable drive.googleapis.com
gcloud services enable admin.googleapis.com
```

Or via Console:
- Go to **APIs & Services → Library**
- Enable **Google Drive API**

### 3. Create Service Account

1. Go to **IAM & Admin → Service Accounts**
2. Click **Create Service Account**
   - Name: `clearedge-pipeline`
   - Description: "Service account for label pipeline"
3. Click **Create and Continue**
4. Skip role assignment (Shared Drive permissions handled separately)
5. Click **Done**

### 4. Generate Service Account Key

1. Click on the created service account
2. Go to **Keys** tab
3. Click **Add Key → Create New Key**
4. Select **JSON** format
5. Download the key file
6. **IMPORTANT**: Save as `service-account-key.json` in project root
7. **SECURITY**: Add to `.gitignore` (already configured)

### 5. Configure Domain-Wide Delegation (Optional)

Only needed if accessing user-owned files. For Shared Drive only, skip this.

1. Go to service account details
2. Click **Show Domain-Wide Delegation**
3. Enable **Enable Google Workspace Domain-wide Delegation**
4. Note the Client ID
5. In Google Workspace Admin:
   - **Security → API Controls → Domain-wide Delegation**
   - Add Client ID with scope: `https://www.googleapis.com/auth/drive`

---

## Gemini API Setup

### 1. Get API Key from Google AI Studio

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with Google account
3. Click **Get API Key**
4. Create new API key or use existing
5. Copy the API key

### 2. Store API Key

Add to `.env` file:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

**SECURITY**: Never commit API keys to version control.

---

## Google Drive Setup

### 1. Locate Shared Drive

The system uses this specific Shared Drive:

- **Shared Drive ID**: `0APFlqBVg60o6Uk9PVA`
- **Root Folder**: "Product Labels"

### 2. Grant Service Account Access

1. Open the Shared Drive in Google Drive
2. Right-click → **Share**
3. Add the service account email:
   - Found in `service-account-key.json` as `"client_email"`
   - Format: `clearedge-pipeline@project-id.iam.gserviceaccount.com`
4. Grant **Content Manager** or **Manager** permission
5. Click **Send**

### 3. Create Root Folder Structure

Inside the Shared Drive, create this structure:

```
Product Labels/          ← Root folder
  Templates/
    Assets/
      GHS_pictograms/
      DOT_placards/
```

Product-specific folders will be created automatically by the pipeline.

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Gemini AI
GEMINI_API_KEY=your_actual_gemini_key

# Google Drive
SHARED_DRIVE_ID=0APFlqBVg60o6Uk9PVA
GOOGLE_SERVICE_ACCOUNT_FILE=/absolute/path/to/service-account-key.json

# Application
ENV=development
LOG_LEVEL=INFO
API_PORT=8000

# OCR
TESSERACT_CMD=/usr/bin/tesseract
OCR_LANG=eng

# Web Retrieval Allowlist
ALLOWED_DOMAINS=msds.com,fishersci.com,sigmaaldrich.com,chemicalsafety.com
```

**Required Changes:**
- Set `GEMINI_API_KEY`
- Set `GOOGLE_SERVICE_ACCOUNT_FILE` to absolute path
- Adjust `TESSERACT_CMD` for your system (`which tesseract`)

---

## Running the System

### Start API Server

```bash
# Development mode (auto-reload)
python -m app.main

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Server starts at: `http://localhost:8000`

API Docs: `http://localhost:8000/docs`

### Health Check

```bash
curl http://localhost:8000/health
```

---

## API Endpoints

### GET /health

Health check and system info.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00",
  "gemini_model": "gemini-1.5-pro",
  "shared_drive_id": "0APFlqBVg60o6Uk9PVA"
}
```

### GET /products

List all products in Shared Drive.

**Response:**
```json
{
  "products": ["APS-100", "Turbo Klean", "Filter Cleaner X"]
}
```

### POST /ingest/drive

Scan product folder for SDS/TDS PDFs.

**Request:**
```json
{
  "product_name": "APS-100"
}
```

**Response:**
```json
{
  "product_name": "APS-100",
  "product_folder_id": "1abc...",
  "sds_files": 2,
  "tds_files": 1,
  "files": {
    "sds": [{"id": "file123", "name": "APS-100_SDS.pdf"}],
    "tds": [{"id": "file456", "name": "APS-100_TDS.pdf"}]
  }
}
```

### POST /ingest/url

Download PDF from approved URL.

**Request:**
```json
{
  "product_name": "APS-100",
  "url": "https://fishersci.com/sds/APS-100.pdf",
  "doc_type": "SDS",
  "user_approved": true
}
```

**Response:**
```json
{
  "product_name": "APS-100",
  "file_id": "file789",
  "filename": "APS-100_SDS_20240115.pdf",
  "size_bytes": 245678,
  "sha256": "a1b2c3...",
  "source_url": "https://fishersci.com/sds/APS-100.pdf"
}
```

### POST /extract/{product_name}

Extract structured data and generate label.

**Request:**
```bash
POST /extract/APS-100?mode=shipped_dot
```

**Response:**
```json
{
  "product_name": "APS-100",
  "mode": "shipped_dot",
  "extraction_duration_seconds": 12.5,
  "validation_passed": true,
  "errors": [],
  "warnings": [],
  "audit_files": {
    "extraction_meta": "file_id_1",
    "extracted_fields": "file_id_2",
    "evidence": "file_id_3",
    "validation": "file_id_4"
  },
  "label_files": {
    "svg": "file_id_5",
    "pdf": "file_id_6",
    "report": "file_id_7"
  },
  "extracted_data": { ... }
}
```

---

## CLI Usage

The CLI provides batch operations and testing capabilities.

### Scan Shared Drive

```bash
python pipeline_cli.py scan-drive
```

Lists all product folders.

### Ingest from URL

```bash
python pipeline_cli.py ingest-url \
  --product "APS-100" \
  --url "https://fishersci.com/sds/aps100.pdf" \
  --doc-type SDS \
  --approve
```

**Note:** `--approve` flag is required for security.

### Extract and Validate

```bash
# Shipped DOT mode (default)
python pipeline_cli.py extract --product "APS-100"

# Workplace mode
python pipeline_cli.py extract --product "APS-100" --mode workplace

# Force re-extraction
python pipeline_cli.py extract --product "APS-100" --reextract
```

### Product Info

```bash
python pipeline_cli.py info --product "APS-100"
```

Shows folder structure and file counts.

---

## Folder Structure

### Per-Product Structure

```
Product Labels/
  {Product Name}/              ← Exact product name
    SDS/
      product_SDS_20240115.pdf
    TDS/
      product_TDS_20240115.pdf
    Extracted/
      2024-01-15/              ← Dated folder
        extracted_text.json
        extracted_fields.json
        evidence.json
        validation.json
        extraction_meta.json
    Labels/
      2024-01-15/
        label.svg
        label.pdf
        label_build_report.json
    product.json               ← Product manifest
```

### Global Templates

```
Product Labels/
  Templates/
    default_template.json
    aps_style_template_v1.json
    Assets/
      ClearEdge_logo.svg
      GHS_pictograms/
        GHS01.svg
        GHS02.svg
        ...
      DOT_placards/
        class_3.svg
        class_8.svg
        ...
```

---

## Compliance Modes

### Shipped DOT Mode

For products being transported.

**Required Fields:**
- `transport.un_number`
- `transport.proper_shipping_name`
- `transport.hazard_class`

**Warnings:**
- Missing `packing_group`
- DOT/GHS pictogram overlap

**Label Features:**
- DOT hazard class diamond
- UN number prominence
- Packing group display
- Emergency contact

### Workplace Mode

For workplace container labels.

**Required Fields:**
- `product.name`

**Warnings:**
- Hazard statements without signal word
- Missing supplier information

**Label Features:**
- Full GHS pictogram set
- All hazard/precautionary statements
- Supplier contact info
- QR code for SDS

---

## Testing

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=app --cov-report=html
```

View coverage report: `htmlcov/index.html`

### Run Specific Test Files

```bash
# Schema validation tests
pytest tests/test_schema.py

# Validator tests
pytest tests/test_validator.py

# Audit tests
pytest tests/test_audit.py
```

### Test Categories

- **Schema Tests**: Pydantic model validation
- **Validator Tests**: Compliance rule enforcement
- **Audit Tests**: SHA-256 hashing, metadata creation
- **Web Retrieval Tests**: Domain allowlist, approval workflow

---

## Troubleshooting

### Common Issues

#### 1. "Shared Drive folder not found"

**Cause**: Service account lacks access to Shared Drive.

**Solution:**
1. Verify service account email in `service-account-key.json`
2. Share the Shared Drive with this email
3. Grant **Content Manager** permission

#### 2. "Gemini API authentication failed"

**Cause**: Invalid or missing API key.

**Solution:**
1. Verify `GEMINI_API_KEY` in `.env`
2. Check key at [Google AI Studio](https://aistudio.google.com/app/apikey)
3. Ensure no extra spaces or quotes

#### 3. "Tesseract not found"

**Cause**: Tesseract OCR not installed or wrong path.

**Solution:**
```bash
# Find tesseract path
which tesseract

# Update .env
TESSERACT_CMD=/usr/local/bin/tesseract  # or your path
```

#### 4. "PDF extraction returned empty text"

**Cause**: Scanned PDF requires OCR.

**Solution:**
- OCR should auto-trigger if < 100 chars/page
- Check logs for "attempting OCR"
- Verify Tesseract installation
- Lower `OCR_THRESHOLD_CHARS` in config if needed

#### 5. "Validation failed: UN number required"

**Cause**: Extracting in `shipped_dot` mode without transport data.

**Solution:**
- Verify SDS has Section 14 (Transport Information)
- Check extraction warnings for missing data
- Use `--mode workplace` if not for shipping

#### 6. "Drive API quota exceeded"

**Cause**: Too many API calls.

**Solution:**
- Batch operations instead of individual calls
- Enable caching in Drive client
- Request quota increase in Google Cloud Console

### Debug Mode

Enable detailed logging:

```bash
# In .env
LOG_LEVEL=DEBUG
```

Logs will show:
- Drive API calls with parameters
- PDF extraction method (text/OCR)
- Gemini prompts and responses
- Validation rule evaluations

### Getting Help

1. Check logs in console output
2. Review extraction warnings in audit files
3. Inspect `evidence.json` for data source issues
4. Test Gemini extraction with minimal SDS first

---

## Security Notes

- **Never commit**:
  - `.env` files
  - Service account keys (`*-key.json`)
  - Gemini API keys
- **Service account permissions**:
  - Limit to specific Shared Drive
  - Use Content Manager role (not Owner)
- **Web retrieval**:
  - Domain allowlist enforced
  - Explicit user approval required
  - No automatic downloads
- **Audit trail**:
  - All operations logged with timestamps
  - File hashes prevent tampering
  - Source evidence preserved

---

## Production Deployment

For production deployment:

1. **Environment**:
   - Set `ENV=production` in `.env`
   - Use dedicated service account
   - Enable Cloud Logging

2. **Security**:
   - Rotate API keys regularly
   - Use Secret Manager for credentials
   - Implement rate limiting

3. **Monitoring**:
   - Set up health check monitoring
   - Alert on validation failures
   - Track Gemini API usage

4. **Backup**:
   - Shared Drive provides version history
   - Export audit logs periodically
   - Backup service account keys securely

---

## License

Copyright © 2024 Clear Edge Filtration Products

---

## Support

For issues or questions:
- **Technical Issues**: Check troubleshooting section
- **Feature Requests**: Submit via issue tracker
- **Security Concerns**: Contact security team directly

**Version**: 1.0.0
**Last Updated**: 2024-01-15
