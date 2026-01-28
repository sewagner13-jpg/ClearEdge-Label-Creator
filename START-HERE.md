# 🚀 START HERE - Simple Label Creator

**The easiest way to create DOT/OSHA compliant chemical labels!**

---

## ⚡ Quick Start (3 steps)

### 1️⃣ Install Prerequisites (One-time)

**On Mac:**
```bash
brew install tesseract poppler
```

**On Linux:**
```bash
sudo apt-get install tesseract-ocr poppler-utils
```

### 2️⃣ Start the Application

Open Terminal in this directory and run:

```bash
./run-simple.sh
```

The script will:
- ✅ Create virtual environment
- ✅ Install all Python dependencies
- ✅ Configure your Gemini API key
- ✅ Start the web server

### 3️⃣ Open Your Browser

Go to: **http://localhost:8000**

---

## 🎯 How It Works

1. **Upload** your SDS/TDS PDF files (drag & drop)
2. **AI extracts** hazard information automatically (Gemini 1.5 Pro)
3. **Generate** professional DOW/BASF/Evonik-style labels
4. **Download** PDF ready to print

---

## 📋 What Gets Extracted

The AI automatically finds and extracts:

- ✓ Product name & supplier information
- ✓ GHS signal word (Danger/Warning)
- ✓ GHS pictograms (GHS01-GHS09)
- ✓ Hazard statements (H-codes)
- ✓ Precautionary statements (P-codes)
- ✓ UN number & DOT shipping class
- ✓ Emergency contact information

---

## 🎨 Label Modes

### Shipped/DOT Mode (Default)
For products being transported:
- Full DOT compliance
- UN number prominent display
- Hazard class diamond
- Packing group
- Transport pictograms

### Workplace Mode
For workplace containers:
- Full GHS pictogram display
- Complete hazard/precautionary statements
- QR code for SDS access
- Detailed supplier information

---

## 🔍 Testing Your Setup

Run the verification script:

```bash
./test-simple.sh
```

This checks:
- Python version (3.11+)
- System dependencies
- File structure
- Python syntax

---

## 🛑 Stopping the Server

Press **Ctrl+C** in the terminal where it's running

---

## 💡 Tips for Best Results

### PDF Quality
- ✅ **Best:** Searchable PDFs (text-based)
- ⚠️ **OK:** Scanned PDFs (OCR will be used)
- ❌ **Avoid:** Very low-resolution scans

### File Naming
- Name files with "SDS" or "TDS" for auto-detection
- Examples: `product_sds.pdf`, `chemical_tds.pdf`

### Multiple Products
- Upload multiple PDFs at once
- Each will be processed separately

---

## 🔧 Troubleshooting

### Port 8000 Already in Use

```bash
# Option 1: Stop other service on port 8000
lsof -ti:8000 | xargs kill

# Option 2: Use different port
python -m uvicorn simple_app:app --port 8001
```

### Tesseract Not Found

```bash
# Mac
brew install tesseract

# Linux
sudo apt-get install tesseract-ocr
```

### Python Version Too Old

```bash
# Mac (install via Homebrew)
brew install python@3.11

# Linux (use pyenv or deadsnakes PPA)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.11
```

### Gemini API Errors

Check your API key in `.env` file:

```bash
cat .env | grep GEMINI_API_KEY
```

If needed, get a new key:
1. Go to https://aistudio.google.com/app/apikey
2. Click "Get API Key"
3. Update `.env` file

### Dependencies Won't Install

```bash
# Clean start
rm -rf venv
./run-simple.sh
```

---

## 📁 Where Are Files Saved?

Generated labels are temporarily saved in:
- **Mac:** `/tmp/clearedge_labels/`
- **Linux:** `/tmp/clearedge_labels/`

⚠️ **Important:** Download labels before closing the app! Temp files may be deleted on system restart.

---

## 🎓 Understanding the Output

### Extracted Data Preview
After processing, you'll see:
- Product name
- Signal word (color-coded: red=Danger, yellow=Warning)
- GHS pictograms
- Top hazard statements
- UN number (if applicable)

### Label PDF
Professional multi-section layout:
1. **Header:** Product name, signal word (Clear Edge purple branding)
2. **Pictograms:** GHS hazard pictograms
3. **Hazard Statements:** H-codes with descriptions
4. **Precautionary Statements:** P-codes with descriptions
5. **Transport Info:** UN number, hazard class, packing group
6. **Footer:** Supplier info, emergency contact

---

## 🚀 Advanced Usage

### Custom Port

```bash
python -m uvicorn simple_app:app --host 127.0.0.1 --port 8001
```

### Run in Background

```bash
./run-simple.sh &
```

### View Logs

```bash
# The app logs to stdout
# Check terminal output for processing details
```

### API Access

The app provides REST API endpoints:

```bash
# Generate label
curl -X POST http://localhost:8000/api/generate-label \
  -F "files=@sds.pdf" \
  -F "mode=shipped_dot"

# Download label
curl -O http://localhost:8000/api/download-label/label_ProductName
```

---

## 📚 More Documentation

- **SIMPLE-START.md** - Quick reference guide
- **README.md** - Full project documentation
- **DEPLOYMENT.md** - Cloud deployment (if needed later)

---

## ✨ Features

✅ **No Cloud Required** - Runs entirely on your machine
✅ **AI-Powered** - Gemini 1.5 Pro extraction
✅ **Professional Labels** - Industry-standard formats
✅ **DOT/OSHA Compliant** - Meets regulatory requirements
✅ **Easy to Use** - Beautiful drag-and-drop interface
✅ **Fast** - Results in 30-60 seconds
✅ **Private** - Your data never leaves your computer (except Gemini API call)

---

## 🎉 You're Ready!

Just run:

```bash
./run-simple.sh
```

And open **http://localhost:8000** in your browser!

---

**Questions?** Check SIMPLE-START.md or README.md for detailed documentation.

**Version:** 1.0.0
**No cloud deployment required!**
