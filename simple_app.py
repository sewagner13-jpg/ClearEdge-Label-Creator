"""
Simple local label creator - no cloud deployment needed.
Upload PDFs, AI extracts data, generate professional labels.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import tempfile
import os
from pathlib import Path

from .pdf_extract import PDFExtractor
from .gemini_client import GeminiClient
from .schema import ExtractedData
from .label_stub import LabelGenerator
from .config import settings

app = FastAPI(
    title="CLEAR EDGE Label Creator",
    description="AI-powered chemical product label generator",
    version="1.0.0"
)

# Enable CORS for local access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
pdf_extractor = PDFExtractor()
gemini_client = GeminiClient()
label_generator = LabelGenerator()

# Temp directory for generated labels
LABELS_DIR = Path(tempfile.gettempdir()) / "clearedge_labels"
LABELS_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the main web interface."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CLEAR EDGE Label Creator</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }

            .container {
                max-width: 1200px;
                margin: 0 auto;
            }

            .header {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }

            h1 {
                color: #5A2D82;
                font-size: 2.5em;
                margin-bottom: 10px;
            }

            .subtitle {
                color: #666;
                font-size: 1.1em;
            }

            .card {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }

            .upload-area {
                border: 3px dashed #5A2D82;
                border-radius: 10px;
                padding: 40px;
                text-align: center;
                background: #f8f9fa;
                margin-bottom: 20px;
                cursor: pointer;
                transition: all 0.3s;
            }

            .upload-area:hover {
                background: #e9ecef;
                border-color: #764ba2;
            }

            .upload-area.dragover {
                background: #dee2e6;
                border-color: #764ba2;
            }

            .file-input {
                display: none;
            }

            .upload-icon {
                font-size: 3em;
                color: #5A2D82;
                margin-bottom: 10px;
            }

            .btn {
                background: #5A2D82;
                color: white;
                border: none;
                padding: 15px 30px;
                font-size: 1.1em;
                border-radius: 5px;
                cursor: pointer;
                transition: all 0.3s;
                font-weight: 600;
            }

            .btn:hover {
                background: #764ba2;
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }

            .btn:disabled {
                background: #ccc;
                cursor: not-allowed;
                transform: none;
            }

            .file-list {
                margin-top: 20px;
            }

            .file-item {
                background: #f8f9fa;
                padding: 10px 15px;
                margin: 10px 0;
                border-radius: 5px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .file-name {
                font-weight: 500;
                color: #333;
            }

            .file-size {
                color: #666;
                font-size: 0.9em;
            }

            .loading {
                display: none;
                text-align: center;
                padding: 20px;
            }

            .loading.show {
                display: block;
            }

            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #5A2D82;
                border-radius: 50%;
                width: 50px;
                height: 50px;
                animation: spin 1s linear infinite;
                margin: 0 auto 15px;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .result {
                display: none;
                margin-top: 20px;
            }

            .result.show {
                display: block;
            }

            .preview {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 5px;
                margin: 15px 0;
            }

            .field-group {
                margin: 15px 0;
            }

            .field-label {
                font-weight: 600;
                color: #333;
                margin-bottom: 5px;
            }

            .field-value {
                color: #666;
                padding: 10px;
                background: white;
                border-radius: 5px;
                border: 1px solid #ddd;
            }

            .pictograms {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }

            .pictogram {
                background: #5A2D82;
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 0.9em;
            }

            .success-message {
                background: #d4edda;
                color: #155724;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
                border: 1px solid #c3e6cb;
            }

            .error-message {
                background: #f8d7da;
                color: #721c24;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
                border: 1px solid #f5c6cb;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏷️ CLEAR EDGE Label Creator</h1>
                <p class="subtitle">AI-Powered DOT/OSHA Compliant Chemical Product Labels</p>
            </div>

            <div class="card">
                <h2>Upload SDS/TDS Documents</h2>
                <p style="color: #666; margin: 10px 0 20px 0;">
                    Upload your Safety Data Sheet (SDS) and/or Technical Data Sheet (TDS) as PDF files.
                    Our AI will automatically extract all required information.
                </p>

                <div class="upload-area" id="uploadArea">
                    <div class="upload-icon">📄</div>
                    <h3>Drop PDF files here or click to browse</h3>
                    <p style="color: #666; margin-top: 10px;">Supports SDS and TDS documents</p>
                    <input type="file" id="fileInput" class="file-input" accept=".pdf" multiple>
                </div>

                <div class="file-list" id="fileList"></div>

                <div style="margin-top: 20px;">
                    <label style="font-weight: 600; margin-bottom: 10px; display: block;">Label Mode:</label>
                    <select id="labelMode" style="padding: 10px; border-radius: 5px; border: 1px solid #ddd; width: 100%; max-width: 300px;">
                        <option value="shipped_dot">Shipped/DOT (Transport)</option>
                        <option value="workplace">Workplace Container</option>
                    </select>
                </div>

                <button id="generateBtn" class="btn" style="margin-top: 20px;" disabled>Generate Label</button>

                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p><strong>Processing PDFs with AI...</strong></p>
                    <p style="color: #666;">This may take 30-60 seconds</p>
                </div>

                <div class="result" id="result"></div>
            </div>
        </div>

        <script>
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            const fileList = document.getElementById('fileList');
            const generateBtn = document.getElementById('generateBtn');
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');
            const labelMode = document.getElementById('labelMode');

            let selectedFiles = [];

            // Click to upload
            uploadArea.addEventListener('click', () => fileInput.click());

            // Drag and drop
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });

            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                handleFiles(e.dataTransfer.files);
            });

            fileInput.addEventListener('change', (e) => {
                handleFiles(e.target.files);
            });

            function handleFiles(files) {
                selectedFiles = Array.from(files).filter(f => f.type === 'application/pdf');

                if (selectedFiles.length === 0) {
                    alert('Please select PDF files only');
                    return;
                }

                displayFiles();
                generateBtn.disabled = false;
            }

            function displayFiles() {
                fileList.innerHTML = selectedFiles.map((file, index) => `
                    <div class="file-item">
                        <div>
                            <div class="file-name">📄 ${file.name}</div>
                            <div class="file-size">${(file.size / 1024 / 1024).toFixed(2)} MB</div>
                        </div>
                        <button onclick="removeFile(${index})" style="background: #dc3545; color: white; border: none; padding: 5px 15px; border-radius: 3px; cursor: pointer;">Remove</button>
                    </div>
                `).join('');
            }

            function removeFile(index) {
                selectedFiles.splice(index, 1);
                displayFiles();
                generateBtn.disabled = selectedFiles.length === 0;
            }

            generateBtn.addEventListener('click', async () => {
                if (selectedFiles.length === 0) return;

                const formData = new FormData();
                selectedFiles.forEach(file => {
                    formData.append('files', file);
                });
                formData.append('mode', labelMode.value);

                generateBtn.disabled = true;
                loading.classList.add('show');
                result.classList.remove('show');
                result.innerHTML = '';

                try {
                    const response = await fetch('/api/generate-label', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        throw new Error(await response.text());
                    }

                    const data = await response.json();

                    loading.classList.remove('show');
                    result.classList.add('show');

                    result.innerHTML = `
                        <div class="success-message">
                            <strong>✓ Label Generated Successfully!</strong>
                        </div>

                        <h3>Extracted Information</h3>
                        <div class="preview">
                            <div class="field-group">
                                <div class="field-label">Product Name</div>
                                <div class="field-value">${data.extracted.product.name}</div>
                            </div>

                            ${data.extracted.ghs.signal_word ? `
                            <div class="field-group">
                                <div class="field-label">Signal Word</div>
                                <div class="field-value" style="color: ${data.extracted.ghs.signal_word === 'Danger' ? '#dc3545' : '#ffc107'}; font-weight: bold; font-size: 1.2em;">
                                    ${data.extracted.ghs.signal_word}
                                </div>
                            </div>
                            ` : ''}

                            ${data.extracted.ghs.pictograms && data.extracted.ghs.pictograms.length > 0 ? `
                            <div class="field-group">
                                <div class="field-label">GHS Pictograms</div>
                                <div class="pictograms">
                                    ${data.extracted.ghs.pictograms.map(p => `<span class="pictogram">${p}</span>`).join('')}
                                </div>
                            </div>
                            ` : ''}

                            ${data.extracted.transport.un_number ? `
                            <div class="field-group">
                                <div class="field-label">UN Number</div>
                                <div class="field-value">UN ${data.extracted.transport.un_number}</div>
                            </div>
                            ` : ''}

                            ${data.extracted.ghs.hazard_statements && data.extracted.ghs.hazard_statements.length > 0 ? `
                            <div class="field-group">
                                <div class="field-label">Hazard Statements (${data.extracted.ghs.hazard_statements.length})</div>
                                <div class="field-value">
                                    ${data.extracted.ghs.hazard_statements.slice(0, 3).map(h =>
                                        `${h.code ? h.code + ': ' : ''}${h.text}`
                                    ).join('<br>')}
                                    ${data.extracted.ghs.hazard_statements.length > 3 ? '<br>...' : ''}
                                </div>
                            </div>
                            ` : ''}
                        </div>

                        <div style="margin-top: 20px;">
                            <a href="/api/download-label/${data.label_id}" download style="text-decoration: none;">
                                <button class="btn">📥 Download Label PDF</button>
                            </a>
                        </div>
                    `;

                } catch (error) {
                    loading.classList.remove('show');
                    result.classList.add('show');
                    result.innerHTML = `
                        <div class="error-message">
                            <strong>Error:</strong> ${error.message}
                        </div>
                    `;
                } finally {
                    generateBtn.disabled = false;
                }
            });
        </script>
    </body>
    </html>
    """


@app.post("/api/generate-label")
async def generate_label(
    files: List[UploadFile] = File(...),
    mode: str = Form("shipped_dot")
):
    """Generate label from uploaded PDFs."""
    try:
        # Save uploaded files temporarily
        temp_files = []
        sds_text = None
        tds_text = None
        product_name = "Unknown Product"

        for file in files:
            if not file.filename.endswith('.pdf'):
                continue

            content = await file.read()
            temp_path = LABELS_DIR / file.filename
            temp_path.write_bytes(content)
            temp_files.append(temp_path)

            # Extract text
            doc_type = "SDS" if "sds" in file.filename.lower() else "TDS"
            extracted = pdf_extractor.extract_text(content, doc_type)

            if doc_type == "SDS":
                sds_text = extracted
            else:
                tds_text = extracted

        if not sds_text and not tds_text:
            raise HTTPException(status_code=400, detail="No valid PDF files provided")

        # Extract with Gemini
        extracted_data = gemini_client.extract_from_documents(sds_text, tds_text, product_name)

        # Generate label
        svg_content = label_generator.generate_svg(extracted_data, mode)
        pdf_content = label_generator.generate_pdf(svg_content)

        # Save label
        label_id = f"label_{extracted_data.product.name.replace(' ', '_')}"
        label_path = LABELS_DIR / f"{label_id}.pdf"
        label_path.write_bytes(pdf_content)

        # Cleanup temp files
        for temp_file in temp_files:
            temp_file.unlink(missing_ok=True)

        return {
            "success": True,
            "label_id": label_id,
            "extracted": extracted_data.model_dump(mode='json')
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download-label/{label_id}")
async def download_label(label_id: str):
    """Download generated label PDF."""
    label_path = LABELS_DIR / f"{label_id}.pdf"

    if not label_path.exists():
        raise HTTPException(status_code=404, detail="Label not found")

    return FileResponse(
        label_path,
        media_type="application/pdf",
        filename=f"{label_id}.pdf"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
