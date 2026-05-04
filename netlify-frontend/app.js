// API endpoint - will be set via environment variable
const API_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'  // Local development
    : 'https://clearedge-label-creator-production.up.railway.app';  // Production

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const generateBtn = document.getElementById('generateBtn');
const loading = document.getElementById('loading');
const result = document.getElementById('result');
const labelMode = document.getElementById('labelMode');
const labelSize = document.getElementById('labelSize');
const productName = document.getElementById('productName');

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

    // Validate product name
    const prodName = productName.value.trim();
    if (!prodName) {
        alert('Please enter your product name');
        productName.focus();
        return;
    }

    const formData = new FormData();
    selectedFiles.forEach(file => {
        formData.append('files', file);
    });
    formData.append('product_name', prodName);
    formData.append('mode', labelMode.value);
    formData.append('size', labelSize.value);

    generateBtn.disabled = true;
    loading.classList.add('show');
    result.classList.remove('show');
    result.innerHTML = '';

    try {
        const response = await fetch(`${API_URL}/api/v1/labels/generate`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || `HTTP ${response.status}: ${response.statusText}`);
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
                ${data.label?.download_url ? `
                <a href="${API_URL}${data.label.download_url}" download style="text-decoration: none;">
                    <button class="btn">📥 Download Label PDF</button>
                </a>
                ` : `
                <div class="error-message">
                    <strong>Download blocked:</strong> Validation failed. Fix required compliance issues first.
                </div>
                <div style="margin-top: 12px; display: grid; gap: 8px; max-width: 500px;">
                    <input id="overrideApprover" placeholder="Approver name" style="padding:8px; border:1px solid #ccc; border-radius:4px;" />
                    <textarea id="overrideReason" placeholder="Override reason (required)" rows="3" style="padding:8px; border:1px solid #ccc; border-radius:4px;"></textarea>
                    <button class="btn" id="overrideBtn" style="max-width: 260px;">Approve Override & Enable Download</button>
                </div>
                `}
            </div>
        `;

        const overrideBtn = document.getElementById('overrideBtn');
        if (overrideBtn) {
            overrideBtn.addEventListener('click', async () => {
                const approver = document.getElementById('overrideApprover')?.value?.trim();
                const reason = document.getElementById('overrideReason')?.value?.trim();

                if (!approver || !reason) {
                    alert('Approver and reason are required for override approval.');
                    return;
                }

                try {
                    const overrideResponse = await fetch(`${API_URL}/api/v1/labels/${data.label_id}/override-approval`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ approver, reason })
                    });

                    if (!overrideResponse.ok) {
                        const err = await overrideResponse.text();
                        throw new Error(err || 'Override request failed');
                    }

                    const overrideData = await overrideResponse.json();
                    if (overrideData.download_url) {
                        window.location.href = `${API_URL}${overrideData.download_url}`;
                    }
                } catch (overrideError) {
                    alert(`Override failed: ${overrideError.message}`);
                }
            });
        }

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
