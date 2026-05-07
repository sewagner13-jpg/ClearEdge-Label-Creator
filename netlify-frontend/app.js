// API endpoint. For production, set window.CLEAREDGE_API_URL in config.js
// or replace the fallback URL after Railway generates the backend domain.
const API_URL = window.CLEAREDGE_API_URL || (
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:8000'
        : 'https://clearedge-label-creator-production.up.railway.app'
);

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const generateBtn = document.getElementById('generateBtn');
const loading = document.getElementById('loading');
const result = document.getElementById('result');
const labelMode = document.getElementById('labelMode');
const labelSize = document.getElementById('labelSize');
const productName = document.getElementById('productName');
const lotNumber = document.getElementById('lotNumber');
const expirationDate = document.getElementById('expirationDate');
const fillAmount = document.getElementById('fillAmount');
const ghsPictogramSelect = document.getElementById('ghsPictogramSelect');
const addGhsPictogram = document.getElementById('addGhsPictogram');
const clearGhsPictograms = document.getElementById('clearGhsPictograms');
const selectedGhsPictogramsEl = document.getElementById('selectedGhsPictograms');

const GHS_PICTOGRAM_OPTIONS = {
    GHS01: 'Exploding Bomb',
    GHS02: 'Flame',
    GHS03: 'Flame Over Circle',
    GHS04: 'Gas Cylinder',
    GHS05: 'Corrosive',
    GHS06: 'Skull and Crossbones',
    GHS07: 'Exclamation Point',
    GHS08: 'Health Hazard',
    GHS09: 'Environment'
};

let selectedFiles = [];
let selectedGhsPictograms = [];

function ghsPictogramLabel(code) {
    return GHS_PICTOGRAM_OPTIONS[code] || code;
}

function renderSelectedGhsPictograms() {
    if (selectedGhsPictograms.length === 0) {
        selectedGhsPictogramsEl.textContent = 'Auto from SDS';
        return;
    }

    selectedGhsPictogramsEl.innerHTML = selectedGhsPictograms.map(code => `
        <span style="display:inline-flex; align-items:center; gap:6px; padding:6px 8px; margin:0 6px 6px 0; border:1px solid #1B006E; border-radius:4px; color:#1B006E; background:#F0E9FF;">
            ${ghsPictogramLabel(code)}
            <button type="button" data-ghs-remove="${code}" style="border:none; background:transparent; color:#1B006E; cursor:pointer; font-weight:700;">x</button>
        </span>
    `).join('');
}

addGhsPictogram.addEventListener('click', () => {
    const code = ghsPictogramSelect.value;
    if (!code) return;
    if (!selectedGhsPictograms.includes(code)) {
        selectedGhsPictograms.push(code);
        renderSelectedGhsPictograms();
    }
});

clearGhsPictograms.addEventListener('click', () => {
    selectedGhsPictograms = [];
    ghsPictogramSelect.value = '';
    renderSelectedGhsPictograms();
});

selectedGhsPictogramsEl.addEventListener('click', (event) => {
    const code = event.target?.dataset?.ghsRemove;
    if (!code) return;
    selectedGhsPictograms = selectedGhsPictograms.filter(item => item !== code);
    renderSelectedGhsPictograms();
});

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

function renderActionLinks(label) {
    const downloadUrl = label?.download_url;
    const canvaCsvUrl = label?.canva_csv_url;
    const canvaJsonUrl = label?.canva_json_url;

    return `
        ${downloadUrl ? `
        <a href="${API_URL}${downloadUrl}" download style="text-decoration: none;">
            <button class="btn">📥 Download Label PDF</button>
        </a>
        ` : ''}
        ${canvaCsvUrl || canvaJsonUrl ? `
        <div style="margin-top: 14px;">
            <h3>Canva Handoff</h3>
            <p style="margin: 6px 0 12px; color: #555;">
                Use the CSV for Canva Bulk Create, or the JSON for manual template entry/review.
            </p>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                ${canvaCsvUrl ? `
                <a href="${API_URL}${canvaCsvUrl}" download style="text-decoration: none;">
                    <button class="btn" type="button">Download Canva CSV</button>
                </a>
                ` : ''}
                ${canvaJsonUrl ? `
                <a href="${API_URL}${canvaJsonUrl}" target="_blank" rel="noopener" style="text-decoration: none;">
                    <button class="btn" type="button">View Canva JSON</button>
                </a>
                ` : ''}
            </div>
        </div>
        ` : ''}
    `;
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
    formData.append('lot_number', lotNumber.value.trim());
    formData.append('expiration_date', expirationDate.value.trim());
    formData.append('fill_amount', fillAmount.value.trim());
    if (selectedGhsPictograms.length > 0) {
        formData.append('ghs_pictograms', JSON.stringify(selectedGhsPictograms));
    }

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
                        ${data.extracted.ghs.pictograms.map(p => `<span class="pictogram">${ghsPictogramLabel(p)}</span>`).join('')}
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

            <div id="actionPanel" style="margin-top: 20px;">
                ${data.label?.download_url ? `
                ${renderActionLinks(data.label)}
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
                    const actionPanel = document.getElementById('actionPanel');
                    if (actionPanel) {
                        actionPanel.innerHTML = `
                            <div class="success-message">
                                <strong>Override approved.</strong> Label PDF and Canva handoff files are now available.
                            </div>
                            ${renderActionLinks(overrideData)}
                        `;
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
