# 🚀 Simple Label Creator - Quick Start

**No cloud setup needed!** Just run it on your Mac and create labels.

## ✨ What This Does

1. **Upload SDS/TDS PDFs** from your computer
2. **AI extracts** all the hazard information automatically (Gemini)
3. **Generates professional label** (DOW/BASF/Evonik style)
4. **Download PDF** - ready to print

---

## 🎯 One-Command Start

Open Terminal and run:

```bash
cd ClearEdge-Label-Creator
./run-simple.sh
```

That's it! It will:
- Install everything needed
- Start the label creator
- Open at: **http://localhost:8000**

---

## 📋 First Time Setup (2 minutes)

### Step 1: Install Prerequisites

**Make sure you have:**
- Python 3.11+ (`python3 --version`)
- Tesseract OCR (for reading scanned PDFs)

**Install Tesseract:**

```bash
# Mac
brew install tesseract poppler

# Ubuntu/Linux
sudo apt-get install tesseract-ocr poppler-utils
```

### Step 2: Get Your Gemini API Key

1. Go to https://aistudio.google.com/app/apikey
2. Click "Get API Key"
3. Copy the key

The startup script already has your key configured! (AIzaSyBs9RRCTZYT99JgLpP3I7raixF3yJJwvO0)

---

## 🎮 How to Use

### 1. Start the App

```bash
./run-simple.sh
```

### 2. Open Your Browser

Go to: **http://localhost:8000**

### 3. Upload PDFs

- Drag and drop your SDS/TDS PDFs
- Or click to browse

### 4. Generate Label

- Click "Generate Label"
- Wait 30-60 seconds for AI processing
- Download your professional PDF label!

---

## 📊 What You'll See

**Beautiful Web Interface with:**
- Drag & drop PDF upload
- Real-time processing status
- Preview of extracted data
- One-click PDF download

**Professional Labels with:**
- Product name
- Signal word (Danger/Warning)
- GHS pictograms
- Hazard statements
- Precautionary statements
- UN number & DOT shipping info
- Emergency contact

---

## 🎨 Label Modes

**Shipped/DOT Mode** (for transport)
- Full DOT compliance
- UN number prominent
- Hazard class diamond
- Packing group

**Workplace Mode** (for containers)
- Full GHS pictograms
- All hazard statements
- QR code for SDS
- Supplier info

---

## 🛑 Stopping the App

Press **Ctrl+C** in the terminal

---

## 🔧 Troubleshooting

### "Port 8000 already in use"

Stop the other app or use a different port:
```bash
python -m uvicorn simple_app:app --port 8001
```

### "Tesseract not found"

Install it:
```bash
brew install tesseract  # Mac
```

### "Gemini API error"

Check your API key in `.env` file

---

## 💡 Tips

- **Better extraction**: Use clear, searchable PDFs (not scanned images)
- **Multiple products**: Upload multiple PDFs at once
- **Save labels**: PDFs are saved in your system's temp folder

---

## 📁 Where Are Files Saved?

Generated labels are temporarily saved in:
- Mac: `/tmp/clearedge_labels/`
- Linux: `/tmp/clearedge_labels/`

Download them before closing the app!

---

## 🎉 That's It!

**Simple. Local. No cloud complexity.**

Just:
1. Run `./run-simple.sh`
2. Upload PDFs
3. Download labels

Need help? Check the main [README.md](README.md) for full documentation.

---

**Version:** 1.0.0 Simple Mode
**No cloud deployment required!**
