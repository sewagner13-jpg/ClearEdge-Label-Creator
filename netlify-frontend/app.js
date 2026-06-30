// API endpoint. For production, set window.CLEAREDGE_API_URL in config.js
// or replace the fallback URL after Railway generates the backend domain.
const API_URL = window.CLEAREDGE_API_URL || (
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:8000'
        : 'https://clearedgelabelcreator-production.up.railway.app'
);
const CANVA_TEMPLATE_NAME = window.CLEAREDGE_CANVA_TEMPLATE_NAME || 'ClearEdge Product Label Template';
const CANVA_TEMPLATE_URL = window.CLEAREDGE_CANVA_TEMPLATE_URL || '';

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const generateBtn = document.getElementById('generateBtn');
const loading = document.getElementById('loading');
const result = document.getElementById('result');
const labelMode = document.getElementById('labelMode');
const labelSize = document.getElementById('labelSize');
const labelOrientation = document.getElementById('labelOrientation');
const productName = document.getElementById('productName');
const lotNumber = document.getElementById('lotNumber');
const expirationDate = document.getElementById('expirationDate');
const manufactureDate = document.getElementById('manufactureDate');
const fillAmount = document.getElementById('fillAmount');
const containerTypeHint = document.getElementById('containerTypeHint');
const labelBrand = document.getElementById('labelBrand');
const brandLogo = document.getElementById('brandLogo');
const savedLogoSelect = document.getElementById('savedLogoSelect');
const refreshLogosBtn = document.getElementById('refreshLogosBtn');
const savedLogoPreview = document.getElementById('savedLogoPreview');
const savedLogoImage = document.getElementById('savedLogoImage');
const savedLogoMeta = document.getElementById('savedLogoMeta');
const saveBrandLogo = document.getElementById('saveBrandLogo');
const brandLogoName = document.getElementById('brandLogoName');
const customBrandFields = document.getElementById('customBrandFields');
const suggestedLogoPanel = document.getElementById('suggestedLogoPanel');
const suggestedLogoImage = document.getElementById('suggestedLogoImage');
const suggestedLogoMeta = document.getElementById('suggestedLogoMeta');
const supplierName = document.getElementById('supplierName');
const supplierAddress = document.getElementById('supplierAddress');
const supplierPhone = document.getElementById('supplierPhone');
const transportStatus = document.getElementById('transportStatus');
const unNumber = document.getElementById('unNumber');
const properShippingName = document.getElementById('properShippingName');
const hazardClass = document.getElementById('hazardClass');
const packingGroup = document.getElementById('packingGroup');
const marinePollutant = document.getElementById('marinePollutant');
const limitedQuantity = document.getElementById('limitedQuantity');
const emergencyPhone = document.getElementById('emergencyPhone');
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
let savedLogos = [];
const KG_TO_LB = 2.2046226218;

function updateBrandFields() {
    const isCustom = labelBrand.value === 'custom';
    customBrandFields.style.display = isCustom ? 'block' : 'none';
    if (!isCustom) {
        clearSuggestedLogo();
        clearSavedLogoPreview();
    } else {
        loadLogoLibrary();
    }
}

labelBrand.addEventListener('change', updateBrandFields);

function ghsPictogramLabel(code) {
    return GHS_PICTOGRAM_OPTIONS[code] || code;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatFetchError(error) {
    const message = String(error?.message || error || 'Unknown error');
    if (/failed to fetch|networkerror|load failed/i.test(message)) {
        if (window.location.protocol === 'file:') {
            return (
                'Failed to connect to the label backend. You are opening this page as a local file. ' +
                'Start the backend with ./run-local.sh, then Open the app from http://localhost:8000 instead of the file path.'
            );
        }

        return (
            `Failed to connect to the label backend at ${API_URL}. ` +
            'Check that the backend is running and reachable, then try again.'
        );
    }

    return message;
}

function safeImageDataUri(value) {
    const dataUri = String(value || '');
    return /^data:image\/(png|jpeg|jpg|webp|svg\+xml);base64,[A-Za-z0-9+/=]+$/i.test(dataUri)
        ? dataUri
        : '';
}

function apiUrl(path) {
    const value = String(path || '');
    if (!value) return '';
    if (/^https?:\/\//i.test(value)) return value;
    return `${API_URL}${value}`;
}

function clearSuggestedLogo() {
    suggestedLogoPanel.style.display = 'none';
    suggestedLogoImage.removeAttribute('src');
    suggestedLogoMeta.textContent = '';
}

function clearSavedLogoPreview() {
    savedLogoPreview.style.display = 'none';
    savedLogoImage.removeAttribute('src');
    savedLogoMeta.textContent = '';
}

function renderSavedLogoPreview() {
    const logo = savedLogos.find(item => item.logo_id === savedLogoSelect.value);
    if (!logo) {
        clearSavedLogoPreview();
        return;
    }

    savedLogoImage.src = apiUrl(logo.image_url);
    savedLogoMeta.textContent = [logo.name, logo.filename].filter(Boolean).join(' | ');
    savedLogoPreview.style.display = 'block';
}

async function loadLogoLibrary() {
    if (!savedLogoSelect || labelBrand.value !== 'custom') return;

    try {
        const response = await fetch(`${API_URL}/api/v1/logos`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        savedLogos = Array.isArray(payload.logos) ? payload.logos : [];
        const current = savedLogoSelect.value;
        savedLogoSelect.innerHTML = `
            <option value="">No saved logo selected</option>
            ${savedLogos.map(logo => `
                <option value="${escapeHtml(logo.logo_id)}">${escapeHtml(logo.name)}</option>
            `).join('')}
        `;
        if (savedLogos.some(logo => logo.logo_id === current)) {
            savedLogoSelect.value = current;
        }
        renderSavedLogoPreview();
    } catch (error) {
        savedLogos = [];
        savedLogoSelect.innerHTML = '<option value="">Logo library unavailable</option>';
        clearSavedLogoPreview();
    }
}

savedLogoSelect.addEventListener('change', renderSavedLogoPreview);
refreshLogosBtn.addEventListener('click', loadLogoLibrary);
brandLogo.addEventListener('change', () => {
    const file = brandLogo.files?.[0];
    if (!file) return;
    savedLogoSelect.value = '';
    clearSavedLogoPreview();
    if (!brandLogoName.value.trim()) {
        brandLogoName.value = file.name.replace(/\.[^.]+$/, '');
    }
});

function setIfBlank(input, value) {
    if (input && !input.value.trim() && value) {
        input.value = value;
    }
}

function applyCustomBrandSuggestions(data) {
    if (labelBrand.value !== 'custom') {
        clearSuggestedLogo();
        return;
    }

    setIfBlank(supplierName, data?.extracted?.product?.supplier_name);
    setIfBlank(supplierAddress, data?.extracted?.product?.supplier_address);
    setIfBlank(supplierPhone, data?.extracted?.product?.supplier_phone);
    renderSuggestedLogo(data?.branding);
}

function renderSuggestedLogo(branding) {
    const suggestion = branding?.suggested_logo;
    const dataUri = safeImageDataUri(suggestion?.data_uri);
    if (!dataUri) {
        clearSuggestedLogo();
        return;
    }

    const source = suggestion.source_file || suggestion.source_document || 'uploaded document';
    const dimensions = suggestion.width && suggestion.height ? `${suggestion.width} x ${suggestion.height}` : '';
    const usage = branding?.logo_source === 'suggested'
        ? 'Using suggested logo on this label.'
        : 'Suggested logo detected; uploaded logo was used instead.';

    suggestedLogoImage.src = dataUri;
    suggestedLogoMeta.textContent = [usage, source, dimensions].filter(Boolean).join(' | ');
    suggestedLogoPanel.style.display = 'block';
}

function renderBrandingSummary(branding) {
    if (!branding || branding.mode !== 'custom') return '';
    const sourceLabels = {
        suggested: 'Suggested logo from SDS/TDS',
        uploaded: 'Uploaded logo',
        library: 'Saved logo library',
        none: 'No logo selected'
    };
    const sourceLabel = sourceLabels[branding.logo_source] || branding.logo_source || 'Not set';
    return `
        <div style="margin-top: 14px; padding: 12px; border: 1px solid #C8BEDD; border-radius: 6px; background: #FBFAFE;">
            <strong>Custom brand source:</strong> ${escapeHtml(sourceLabel)}
            ${branding.logo_name ? `<div style="margin-top:4px; color:#555;">Logo: ${escapeHtml(branding.logo_name)}</div>` : ''}
            ${branding.saved_logo?.name ? `<div style="margin-top:4px; color:#555;">Saved to library as ${escapeHtml(branding.saved_logo.name)}</div>` : ''}
            ${branding.suggested_logo?.source_file ? `<div style="margin-top:4px; color:#555;">Suggested from ${escapeHtml(branding.suggested_logo.source_file)}</div>` : ''}
        </div>
    `;
}

function renderLabelPreview(data) {
    const previewUrl = data?.preview?.url || data?.label?.preview_url;
    if (!previewUrl) return '';

    return `
        <div class="label-preview-panel">
            <div class="label-preview-heading">
                <h3>Label Preview</h3>
                <a href="${apiUrl(previewUrl)}" target="_blank" rel="noopener">Open larger preview</a>
            </div>
            <iframe class="label-preview-frame" title="Generated label preview" src="${apiUrl(previewUrl)}"></iframe>
        </div>
    `;
}

function statusLabel(status) {
    const labels = {
        ready: 'Ready to download',
        needs_review: 'Needs review',
        blocked: 'Blocked',
        override_approved: 'Override approved'
    };
    return labels[status] || 'Label generated';
}

function containerTypeLabel(containerType) {
    const labels = {
        pail: 'Pail',
        drum: 'Drum',
        tote: 'Tote'
    };
    return labels[containerType] || '';
}

function inferContainerTypeFromFillAmount(value) {
    const cleaned = String(value || '').trim();
    const match = cleaned.match(/(\d+(?:,\d{3})*(?:\.\d+)?)/);
    if (!match) return '';

    const amount = Number(match[1].replace(/,/g, ''));
    if (!Number.isFinite(amount)) return '';

    const normalized = cleaned.toLowerCase().replace(/\./g, '');
    const pounds = /\b(kg|kgs|kilogram|kilograms)\b/.test(normalized)
        ? amount * KG_TO_LB
        : amount;

    if (pounds > 2000) return 'tote';
    if (pounds > 60) return 'drum';
    if (pounds <= 55) return 'pail';
    return '';
}

function updateContainerTypeHint() {
    const containerType = inferContainerTypeFromFillAmount(fillAmount.value);
    if (!containerType) {
        containerTypeHint.textContent = 'Container will be inferred when the weight is clear.';
        return;
    }

    labelSize.value = containerType;
    containerTypeHint.textContent = `Inferred container: ${containerTypeLabel(containerType)}.`;
}

fillAmount.addEventListener('input', updateContainerTypeHint);
updateContainerTypeHint();
updateBrandFields();

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
    clearSuggestedLogo();
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
    const canvaFieldMapUrl = `${API_URL}/api/v1/canva/template-fields`;

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
                ${escapeHtml(CANVA_TEMPLATE_NAME)} uses the generated CSV fields for Bulk Create.
            </p>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                ${CANVA_TEMPLATE_URL ? `
                <a href="${escapeHtml(CANVA_TEMPLATE_URL)}" target="_blank" rel="noopener" style="text-decoration: none;">
                    <button class="btn" type="button">Open Canva Template</button>
                </a>
                ` : ''}
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
                <a href="${canvaFieldMapUrl}" target="_blank" rel="noopener" style="text-decoration: none;">
                    <button class="btn" type="button">View Canva Field Map</button>
                </a>
            </div>
        </div>
        ` : ''}
    `;
}

function renderValidationPanel(validation) {
    const errors = validation?.errors || [];
    const warnings = validation?.warnings || [];
    if (errors.length === 0 && warnings.length === 0) {
        return '';
    }

    const renderIssue = issue => `
        <li style="margin-bottom: 6px;">
            <strong>${issue.field || 'validation'}:</strong> ${issue.message || JSON.stringify(issue)}
        </li>
    `;

    return `
        <div style="margin-top: 14px; padding: 14px; border: 1px solid #ddd; border-radius: 6px; background: #fff;">
            ${errors.length ? `
            <div style="margin-bottom: 12px;">
                <strong>Blocking compliance issues</strong>
                <ul style="margin: 8px 0 0 18px; padding: 0;">
                    ${errors.map(renderIssue).join('')}
                </ul>
            </div>
            ` : ''}
            ${warnings.length ? `
            <div>
                <strong>Warnings</strong>
                <ul style="margin: 8px 0 0 18px; padding: 0;">
                    ${warnings.map(renderIssue).join('')}
                </ul>
            </div>
            ` : ''}
        </div>
    `;
}

function renderAgentCoreReview(review) {
    if (!review) return '';

    const fieldReviews = review.field_reviews || [];
    const criticalIssues = review.critical_issues || [];
    const warnings = review.warnings || [];
    const hasContent = review.status || fieldReviews.length || criticalIssues.length || warnings.length;
    if (!hasContent) return '';

    const renderFieldReview = item => `
        <li style="margin-bottom: 8px;">
            <strong>${escapeHtml(item.field_path || 'field')}:</strong>
            ${escapeHtml(item.status || 'reviewed')}
            ${item.recommended_value !== undefined && item.recommended_value !== null ? ` - ${escapeHtml(item.recommended_value)}` : ''}
            ${item.confidence !== undefined ? ` (${Math.round(Number(item.confidence || 0) * 100)}%)` : ''}
            ${item.evidence ? `<div style="margin-top:4px; color:#555;">"${escapeHtml(item.evidence)}"</div>` : ''}
            ${item.reason ? `<div style="margin-top:4px; color:#555;">${escapeHtml(item.reason)}</div>` : ''}
        </li>
    `;

    const renderIssue = issue => `
        <li style="margin-bottom: 8px;">
            <strong>${escapeHtml(issue.field_path || 'review')}:</strong>
            ${escapeHtml(issue.message || 'Review required')}
            ${issue.evidence ? `<div style="margin-top:4px; color:#555;">"${escapeHtml(issue.evidence)}"</div>` : ''}
        </li>
    `;

    return `
        <div style="margin-top: 14px; padding: 14px; border: 1px solid #C8BEDD; border-radius: 6px; background: #FBFAFE;">
            <h3 style="margin-top:0;">Review what goes on the label</h3>
            <div style="margin-bottom: 10px; color:#555;">
                AgentCore status: <strong>${escapeHtml(review.status || 'unknown')}</strong>
            </div>
            ${criticalIssues.length ? `
            <div style="margin-bottom: 12px;">
                <strong>Critical review issues</strong>
                <ul style="margin: 8px 0 0 18px; padding: 0;">${criticalIssues.map(renderIssue).join('')}</ul>
            </div>
            ` : ''}
            ${fieldReviews.length ? `
            <div style="margin-bottom: 12px;">
                <strong>Field review</strong>
                <ul style="margin: 8px 0 0 18px; padding: 0;">${fieldReviews.slice(0, 8).map(renderFieldReview).join('')}</ul>
            </div>
            ` : ''}
            ${warnings.length ? `
            <div style="color:#555;">${warnings.map(escapeHtml).join('<br>')}</div>
            ` : ''}
        </div>
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
    formData.append('orientation', labelOrientation.value);
    formData.append('lot_number', lotNumber.value.trim());
    formData.append('expiration_date', expirationDate.value.trim());
    formData.append('manufacture_date', manufactureDate.value.trim());
    formData.append('fill_amount', fillAmount.value.trim());
    formData.append('label_brand', labelBrand.value);
    if (labelBrand.value === 'custom') {
        const logoFile = brandLogo.files?.[0];
        if (logoFile) {
            formData.append('brand_logo', logoFile);
            formData.append('save_brand_logo', saveBrandLogo.checked ? 'true' : 'false');
            formData.append('brand_logo_name', brandLogoName.value.trim());
        } else if (savedLogoSelect.value) {
            formData.append('brand_logo_id', savedLogoSelect.value);
        }
        formData.append('supplier_name', supplierName.value.trim());
        formData.append('supplier_address', supplierAddress.value.trim());
        formData.append('supplier_phone', supplierPhone.value.trim());
    }
    formData.append('transport_status', transportStatus.value);
    formData.append('un_number', unNumber.value.trim());
    formData.append('proper_shipping_name', properShippingName.value.trim());
    formData.append('hazard_class', hazardClass.value.trim());
    formData.append('packing_group', packingGroup.value);
    formData.append('marine_pollutant', marinePollutant.value);
    formData.append('limited_quantity', limitedQuantity.value.trim());
    formData.append('emergency_phone', emergencyPhone.value.trim());
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
        applyCustomBrandSuggestions(data);
        if (data?.branding?.saved_logo) {
            loadLogoLibrary();
        }

        loading.classList.remove('show');
        result.classList.add('show');

        result.innerHTML = `
            <div class="success-message">
                <strong>${statusLabel(data.status)}</strong>
            </div>

            ${renderLabelPreview(data)}

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
                    <div class="field-value">${escapeHtml(data.extracted.transport.un_number)}</div>
                </div>
                ` : ''}

                ${data.extracted.transport.proper_shipping_name ? `
                <div class="field-group">
                    <div class="field-label">Proper Shipping Name</div>
                    <div class="field-value">${escapeHtml(data.extracted.transport.proper_shipping_name)}</div>
                </div>
                ` : ''}

                ${data.extracted.transport.hazard_class ? `
                <div class="field-group">
                    <div class="field-label">Hazard Class</div>
                    <div class="field-value">${escapeHtml(data.extracted.transport.hazard_class)}</div>
                </div>
                ` : ''}

                ${data.extracted.transport.packing_group ? `
                <div class="field-group">
                    <div class="field-label">Packing Group</div>
                    <div class="field-value">${escapeHtml(data.extracted.transport.packing_group)}</div>
                </div>
                ` : ''}

                ${data.label?.orientation ? `
                <div class="field-group">
                    <div class="field-label">Orientation</div>
                    <div class="field-value">${escapeHtml(containerTypeLabel(data.label.orientation) || data.label.orientation)}</div>
                </div>
                ` : ''}

                ${data.label?.container_type ? `
                <div class="field-group">
                    <div class="field-label">Inferred Container</div>
                    <div class="field-value">${escapeHtml(containerTypeLabel(data.label.container_type) || data.label.container_type)}</div>
                </div>
                ` : ''}

                ${data.extracted.product.emergency_phone ? `
                <div class="field-group">
                    <div class="field-label">Emergency Phone</div>
                    <div class="field-value">${escapeHtml(data.extracted.product.emergency_phone)}</div>
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

            ${renderBrandingSummary(data.branding)}

            ${renderAgentCoreReview(data.agentcore_review)}

            <div id="actionPanel" style="margin-top: 20px;">
                ${data.label?.download_url ? `
                ${renderActionLinks(data.label)}
                ` : `
                <div class="error-message">
                    <strong>Download blocked:</strong> ${escapeHtml(data.download?.reason || 'Validation failed. Fix required compliance issues first.')}
                </div>
                ${renderValidationPanel(data.validation)}
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
                <strong>Error:</strong> ${escapeHtml(formatFetchError(error))}
            </div>
        `;
    } finally {
        generateBtn.disabled = false;
    }
});
