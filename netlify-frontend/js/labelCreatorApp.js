import {
    API_URL,
    apiUrl,
    escapeHtml,
    formatBytes,
    formatFetchError,
    ghsPictogramLabel,
    inferContainerTypeFromFillAmount,
    containerTypeLabel,
    normalizedText,
    safeImageDataUri
} from './utils.js';
import {
    renderErrorPanel,
    renderInitialPreview,
    renderPreviewRail,
    renderProcessingPreview,
    renderResultPanel
} from './renderers.js';

const PROCESSING_STAGES = [
    'Uploading documents',
    'Extracting SDS/TDS text',
    'Analyzing GHS and DOT fields',
    'Rendering preview and PDFs'
];

export function createLabelCreatorApp() {
    const elements = {};
    const state = {
        selectedFiles: [],
        selectedGhsPictograms: [],
        savedLogos: [],
        currentResult: null,
        progressTimer: null,
        progressIndex: 0
    };

    function init() {
        bindElements();
        bindEvents();
        renderSelectedGhsPictograms();
        updateBrandFields();
        updateContainerTypeHint();
        updateGenerateState();
        elements.previewRailContent.innerHTML = renderInitialPreview();
        loadLogoLibrary();
    }

    function bindElements() {
        [
            'uploadArea', 'fileInput', 'fileList', 'generateBtn', 'generateHelp', 'loading',
            'progressStageList', 'result', 'previewRailContent', 'labelMode', 'labelSize',
            'labelOrientation', 'productName', 'clearedgeBrandNote', 'lotNumber', 'expirationDate', 'manufactureDate',
            'fillAmount', 'containerTypeHint', 'labelBrand', 'brandLogo', 'savedLogoSelect',
            'refreshLogosBtn', 'savedLogoPreview', 'savedLogoImage', 'savedLogoMeta',
            'saveBrandLogo', 'brandLogoName', 'showClearedgeMark', 'customBrandFields',
            'suggestedLogoPanel', 'suggestedLogoImage', 'suggestedLogoMeta', 'supplierName',
            'supplierAddress', 'supplierPhone', 'transportStatus', 'unNumber',
            'properShippingName', 'hazardClass', 'subsidiaryHazardClasses', 'packingGroup',
            'marinePollutant', 'hazardousSubstance', 'hazardousWaste', 'limitedQuantity',
            'emergencyPhone', 'ghsPictogramSelect', 'addGhsPictogram', 'clearGhsPictograms',
            'selectedGhsPictograms'
        ].forEach(id => {
            elements[id] = document.getElementById(id);
        });
    }

    function bindEvents() {
        document.querySelectorAll('[data-scroll-target]').forEach(button => {
            button.addEventListener('click', () => scrollToStep(button.dataset.scrollTarget));
        });

        elements.labelBrand.addEventListener('change', updateBrandFields);
        elements.savedLogoSelect.addEventListener('change', renderSavedLogoPreview);
        elements.refreshLogosBtn.addEventListener('click', loadLogoLibrary);
        elements.brandLogo.addEventListener('change', handleBrandLogoSelection);
        elements.fillAmount.addEventListener('input', updateContainerTypeHint);
        elements.productName.addEventListener('input', updateGenerateState);

        elements.uploadArea.addEventListener('click', () => elements.fileInput.click());
        elements.uploadArea.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                elements.fileInput.click();
            }
        });
        elements.uploadArea.addEventListener('dragover', event => {
            event.preventDefault();
            elements.uploadArea.classList.add('dragover');
        });
        elements.uploadArea.addEventListener('dragleave', () => {
            elements.uploadArea.classList.remove('dragover');
        });
        elements.uploadArea.addEventListener('drop', event => {
            event.preventDefault();
            elements.uploadArea.classList.remove('dragover');
            handleFiles(event.dataTransfer.files);
        });
        elements.fileInput.addEventListener('change', event => handleFiles(event.target.files));
        elements.fileList.addEventListener('click', event => {
            const button = event.target.closest('[data-remove-file]');
            if (!button) return;
            removeFile(Number(button.dataset.removeFile));
        });

        elements.addGhsPictogram.addEventListener('click', addSelectedGhsPictogram);
        elements.clearGhsPictograms.addEventListener('click', clearSelectedGhsPictograms);
        elements.selectedGhsPictograms.addEventListener('click', event => {
            const button = event.target.closest('[data-ghs-remove]');
            if (!button) return;
            state.selectedGhsPictograms = state.selectedGhsPictograms.filter(code => code !== button.dataset.ghsRemove);
            renderSelectedGhsPictograms();
        });

        elements.generateBtn.addEventListener('click', generateLabel);
        elements.result.addEventListener('submit', handleCorrectionSubmit);
    }

    function scrollToStep(targetId) {
        document.querySelectorAll('.step-link').forEach(button => {
            button.classList.toggle('is-active', button.dataset.scrollTarget === targetId);
        });
        document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function updateBrandFields() {
        const isCustom = elements.labelBrand.value === 'custom';
        elements.customBrandFields.hidden = !isCustom;
        elements.clearedgeBrandNote.hidden = isCustom;
        if (isCustom) {
            loadLogoLibrary();
        } else {
            clearSuggestedLogo();
            clearSavedLogoPreview();
        }
    }

    function handleBrandLogoSelection() {
        const file = elements.brandLogo.files?.[0];
        if (file && !elements.brandLogoName.value.trim()) {
            elements.brandLogoName.value = file.name.replace(/\.[^.]+$/, '');
        }
    }

    function handleFiles(files) {
        state.selectedFiles = Array.from(files || []).filter(file => file.name.toLowerCase().endsWith('.pdf'));
        displayFiles();
        updateGenerateState();
    }

    function displayFiles() {
        if (!state.selectedFiles.length) {
            elements.fileList.innerHTML = '';
            return;
        }

        elements.fileList.innerHTML = state.selectedFiles.map((file, index) => `
            <div class="file-item">
                <div>
                    <div class="file-name">${escapeHtml(file.name)}</div>
                    <div class="file-size">${escapeHtml(formatBytes(file.size))}</div>
                </div>
                <button type="button" class="btn btn-ghost" data-remove-file="${index}">Remove</button>
            </div>
        `).join('');
    }

    function removeFile(index) {
        state.selectedFiles.splice(index, 1);
        displayFiles();
        updateGenerateState();
    }

    function updateGenerateState() {
        const hasFiles = state.selectedFiles.length > 0;
        const hasProduct = normalizedText(elements.productName.value).length >= 2;
        elements.generateBtn.disabled = !(hasFiles && hasProduct);
        elements.generateHelp.textContent = hasFiles && hasProduct
            ? 'Ready to analyze the documents and render a label preview.'
            : 'Upload at least one PDF and enter a product name to generate a label.';
    }

    function updateContainerTypeHint() {
        const containerType = inferContainerTypeFromFillAmount(elements.fillAmount.value);
        elements.containerTypeHint.textContent = containerType
            ? `Inferred container: ${containerTypeLabel(containerType)}`
            : 'Pail <= 55 lb, drum > 60 lb, tote > 2000 lb.';
    }

    function addSelectedGhsPictogram() {
        const code = elements.ghsPictogramSelect.value;
        if (!code || state.selectedGhsPictograms.includes(code)) return;
        state.selectedGhsPictograms.push(code);
        renderSelectedGhsPictograms();
    }

    function clearSelectedGhsPictograms() {
        state.selectedGhsPictograms = [];
        renderSelectedGhsPictograms();
    }

    function renderSelectedGhsPictograms() {
        if (!state.selectedGhsPictograms.length) {
            elements.selectedGhsPictograms.textContent = 'Auto from SDS';
            return;
        }
        elements.selectedGhsPictograms.innerHTML = state.selectedGhsPictograms.map(code => `
            <span class="pictogram-chip">
                ${escapeHtml(ghsPictogramLabel(code))}
                <button type="button" class="chip-remove" data-ghs-remove="${escapeHtml(code)}" aria-label="Remove ${escapeHtml(ghsPictogramLabel(code))}">x</button>
            </span>
        `).join('');
    }

    async function loadLogoLibrary() {
        if (!elements.savedLogoSelect) return;
        try {
            const response = await fetch(`${API_URL}/api/v1/logos`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const payload = await response.json();
            state.savedLogos = Array.isArray(payload.logos) ? payload.logos : [];
            const current = elements.savedLogoSelect.value;
            elements.savedLogoSelect.innerHTML = `
                <option value="">No saved logo selected</option>
                ${state.savedLogos.map(logo => `
                    <option value="${escapeHtml(logo.logo_id)}">${escapeHtml(logo.name)}</option>
                `).join('')}
            `;
            if (state.savedLogos.some(logo => logo.logo_id === current)) {
                elements.savedLogoSelect.value = current;
            }
            renderSavedLogoPreview();
        } catch {
            elements.savedLogoSelect.innerHTML = '<option value="">Logo library unavailable</option>';
            clearSavedLogoPreview();
        }
    }

    function renderSavedLogoPreview() {
        const logo = state.savedLogos.find(item => item.logo_id === elements.savedLogoSelect.value);
        if (!logo) {
            clearSavedLogoPreview();
            return;
        }
        elements.savedLogoImage.src = apiUrl(logo.image_url);
        elements.savedLogoMeta.textContent = [logo.name, logo.filename].filter(Boolean).join(' | ');
        elements.savedLogoPreview.hidden = false;
    }

    function clearSavedLogoPreview() {
        elements.savedLogoPreview.hidden = true;
        elements.savedLogoImage.removeAttribute('src');
        elements.savedLogoMeta.textContent = '';
    }

    function applyCustomBrandSuggestions(data) {
        const product = data?.extracted?.product || {};
        if (elements.labelBrand.value !== 'custom') return;
        setIfBlank(elements.supplierName, product.supplier_name);
        setIfBlank(elements.supplierAddress, product.supplier_address);
        setIfBlank(elements.supplierPhone, product.supplier_phone);
        setIfBlank(elements.emergencyPhone, product.emergency_phone);
        renderSuggestedLogo(data?.branding);
    }

    function setIfBlank(input, value) {
        if (input && !input.value.trim() && value) {
            input.value = value;
        }
    }

    function renderSuggestedLogo(branding) {
        const suggestion = branding?.suggested_logo;
        const dataUri = safeImageDataUri(suggestion?.data_uri);
        if (!suggestion || !dataUri) {
            clearSuggestedLogo();
            return;
        }
        elements.suggestedLogoImage.src = dataUri;
        const source = suggestion.source_file || suggestion.source_document || 'uploaded document';
        const dimensions = suggestion.width && suggestion.height ? `${suggestion.width} x ${suggestion.height}` : '';
        const usage = branding?.logo_source === 'suggested'
            ? 'Using suggested logo on this label.'
            : 'Suggested logo detected; uploaded logo was used instead.';
        elements.suggestedLogoMeta.textContent = [usage, source, dimensions].filter(Boolean).join(' | ');
        elements.suggestedLogoPanel.hidden = false;
    }

    function clearSuggestedLogo() {
        elements.suggestedLogoPanel.hidden = true;
        elements.suggestedLogoImage.removeAttribute('src');
        elements.suggestedLogoMeta.textContent = '';
    }

    function buildFormData() {
        const formData = new FormData();
        state.selectedFiles.forEach(file => formData.append('files', file));
        formData.append('product_name', normalizedText(elements.productName.value));
        formData.append('mode', elements.labelMode.value);
        formData.append('size', elements.labelSize.value);
        formData.append('orientation', elements.labelOrientation.value);
        formData.append('lot_number', normalizedText(elements.lotNumber.value));
        formData.append('expiration_date', normalizedText(elements.expirationDate.value));
        formData.append('manufacture_date', normalizedText(elements.manufactureDate.value));
        formData.append('fill_amount', normalizedText(elements.fillAmount.value));
        formData.append('label_brand', elements.labelBrand.value);

        if (elements.labelBrand.value === 'custom') {
            const logoFile = elements.brandLogo.files?.[0];
            if (logoFile) {
                formData.append('brand_logo', logoFile);
                formData.append('save_brand_logo', elements.saveBrandLogo.checked ? 'true' : 'false');
                formData.append('brand_logo_name', normalizedText(elements.brandLogoName.value));
            } else if (elements.savedLogoSelect.value) {
                formData.append('brand_logo_id', elements.savedLogoSelect.value);
            }
            formData.append('show_clearedge_mark', elements.showClearedgeMark.checked ? 'true' : 'false');
            formData.append('supplier_name', normalizedText(elements.supplierName.value));
            formData.append('supplier_address', normalizedText(elements.supplierAddress.value));
            formData.append('supplier_phone', normalizedText(elements.supplierPhone.value));
        }

        formData.append('transport_status', elements.transportStatus.value);
        formData.append('un_number', normalizedText(elements.unNumber.value));
        formData.append('proper_shipping_name', normalizedText(elements.properShippingName.value));
        formData.append('hazard_class', normalizedText(elements.hazardClass.value));
        formData.append('subsidiary_hazard_classes', normalizedText(elements.subsidiaryHazardClasses.value));
        formData.append('packing_group', elements.packingGroup.value);
        formData.append('marine_pollutant', elements.marinePollutant.value);
        formData.append('hazardous_substance', elements.hazardousSubstance.value);
        formData.append('hazardous_waste', elements.hazardousWaste.value);
        formData.append('limited_quantity', normalizedText(elements.limitedQuantity.value));
        formData.append('emergency_phone', normalizedText(elements.emergencyPhone.value));
        if (state.selectedGhsPictograms.length > 0) {
            formData.append('ghs_pictograms', JSON.stringify(state.selectedGhsPictograms));
        }
        return formData;
    }

    async function generateLabel() {
        if (elements.generateBtn.disabled) return;
        setProcessing(true);

        try {
            const response = await fetch(`${API_URL}/api/v1/labels/generate`, {
                method: 'POST',
                body: buildFormData()
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
            renderGenerationResult(data);
        } catch (error) {
            const message = formatFetchError(error);
            elements.result.innerHTML = renderErrorPanel(message);
            elements.previewRailContent.innerHTML = renderErrorPanel(message);
        } finally {
            setProcessing(false);
        }
    }

    function renderGenerationResult(data) {
        state.currentResult = data;
        elements.result.innerHTML = renderResultPanel(data);
        elements.previewRailContent.innerHTML = renderPreviewRail(data);
        elements.result.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function setProcessing(isProcessing) {
        clearInterval(state.progressTimer);
        state.progressTimer = null;
        state.progressIndex = 0;
        elements.generateBtn.disabled = isProcessing || !(state.selectedFiles.length && normalizedText(elements.productName.value).length >= 2);
        elements.loading.hidden = !isProcessing;
        if (!isProcessing) {
            updateGenerateState();
            return;
        }
        updateProgressStage();
        elements.previewRailContent.innerHTML = renderProcessingPreview(PROCESSING_STAGES[0]);
        state.progressTimer = setInterval(() => {
            state.progressIndex = Math.min(state.progressIndex + 1, PROCESSING_STAGES.length - 1);
            updateProgressStage();
            elements.previewRailContent.innerHTML = renderProcessingPreview(PROCESSING_STAGES[state.progressIndex]);
        }, 3500);
    }

    function updateProgressStage() {
        elements.progressStageList.innerHTML = PROCESSING_STAGES.map((stage, index) => `
            <li class="${index === state.progressIndex ? 'is-active' : ''}">${escapeHtml(stage)}</li>
        `).join('');
    }

    async function handleCorrectionSubmit(event) {
        if (event.target?.id !== 'correctionForm') return;
        event.preventDefault();
        const form = event.target;
        const message = form.querySelector('#correctionMessage');
        const fields = {};
        form.querySelectorAll('[data-correction-field]').forEach(input => {
            const value = normalizedText(input.value);
            if (value) fields[input.dataset.correctionField] = value;
        });

        const updatedBy = normalizedText(form.querySelector('#correctionUpdatedBy')?.value);
        const reason = normalizedText(form.querySelector('#correctionReason')?.value);
        if (!updatedBy || reason.length < 10 || Object.keys(fields).length === 0) {
            message.textContent = 'Enter updated by, a reason of at least 10 characters, and at least one corrected field.';
            return;
        }

        message.textContent = 'Applying corrections...';
        try {
            const labelId = form.dataset.labelId;
            const response = await fetch(`${API_URL}/api/v1/labels/${encodeURIComponent(labelId)}/corrections`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    updated_by: updatedBy,
                    reason,
                    fields
                })
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || `HTTP ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();
            renderGenerationResult(data);
        } catch (error) {
            message.textContent = formatFetchError(error);
        }
    }

    return { init };
}
