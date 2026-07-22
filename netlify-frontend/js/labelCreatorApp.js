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
    renderAnalysisResult,
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
        savedSalespeople: [],
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
        updateSalespersonPanel();
        updateGenerateState();
        elements.previewRailContent.innerHTML = renderInitialPreview();
        loadLogoLibrary();
        loadSalespeople();
    }

    function bindElements() {
        [
            'uploadArea', 'fileInput', 'fileList', 'analyzeSdsBtn', 'analyzeHelp',
            'generateBtn', 'generateHelp', 'loading',
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
            'selectedGhsPictograms', 'fillAmountLabel', 'salespersonPanel', 'salespersonSelect',
            'refreshSalespeopleBtn', 'salespersonName', 'salespersonEmail', 'salespersonPhone',
            'saveSalespersonBtn', 'salespersonMessage'
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
        elements.fillAmount.addEventListener('input', () => {
            updateContainerTypeHint();
            updateGenerateState();
        });
        elements.productName.addEventListener('input', updateGenerateState);
        elements.labelSize.addEventListener('change', () => {
            updateContainerTypeHint();
            updateSalespersonPanel();
            updateGenerateState();
        });
        elements.refreshSalespeopleBtn.addEventListener('click', loadSalespeople);
        elements.salespersonSelect.addEventListener('change', applySelectedSalesperson);
        elements.saveSalespersonBtn.addEventListener('click', saveSalesperson);

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

        elements.analyzeSdsBtn.addEventListener('click', analyzeDocuments);
        elements.generateBtn.addEventListener('click', requestGenerationStart);
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
        const hasRequiredWeight = isSampleLabel() || normalizedText(elements.fillAmount.value).length > 0;
        elements.analyzeSdsBtn.disabled = !hasFiles;
        elements.generateBtn.disabled = !(hasFiles && hasProduct && hasRequiredWeight);
        if (!hasFiles) {
            elements.analyzeHelp.textContent = 'Upload SDS/TDS PDFs to unlock analysis.';
        } else {
            elements.analyzeHelp.textContent = 'PDFs are ready. Analyze now; product name and weight can be completed afterward.';
        }
        elements.generateHelp.textContent = hasFiles && hasProduct && hasRequiredWeight
            ? 'Ready to analyze the documents and render a label preview.'
            : 'Upload PDFs, enter a product name, and enter weight for non-sample labels.';
    }

    function updateContainerTypeHint() {
        if (isSampleLabel()) {
            elements.fillAmountLabel.textContent = 'Net Weight / Fill Amount (optional for samples)';
            elements.fillAmount.required = false;
            elements.containerTypeHint.textContent = 'Sample 4x6 labels can be generated without weight. Enter net weight only if you want it printed.';
            return;
        }
        elements.fillAmountLabel.textContent = 'Net Weight / Fill Amount (required)';
        elements.fillAmount.required = true;
        const containerType = inferContainerTypeFromFillAmount(elements.fillAmount.value);
        elements.containerTypeHint.textContent = containerType
            ? `Inferred container: ${containerTypeLabel(containerType)}`
            : 'Pail <= 55 lb, drum > 60 lb, tote > 2000 lb.';
    }

    function isSampleLabel() {
        return elements.labelSize.value === 'sample_4x6';
    }

    function updateSalespersonPanel() {
        elements.salespersonPanel.hidden = !isSampleLabel();
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

    async function loadSalespeople() {
        if (!elements.salespersonSelect) return;
        try {
            const response = await fetch(`${API_URL}/api/v1/salespeople`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const payload = await response.json();
            state.savedSalespeople = Array.isArray(payload.salespeople) ? payload.salespeople : [];
            const current = elements.salespersonSelect.value;
            elements.salespersonSelect.innerHTML = `
                <option value="">No sales contact selected</option>
                ${state.savedSalespeople.map(person => `
                    <option value="${escapeHtml(person.salesperson_id)}">${escapeHtml(person.name)}</option>
                `).join('')}
            `;
            if (state.savedSalespeople.some(person => person.salesperson_id === current)) {
                elements.salespersonSelect.value = current;
            }
            elements.salespersonMessage.textContent = state.savedSalespeople.length
                ? 'Choose a saved sales contact for the sample label.'
                : 'No saved sales contacts yet. Add one below.';
        } catch {
            elements.salespersonSelect.innerHTML = '<option value="">Sales contact library unavailable</option>';
            elements.salespersonMessage.textContent = 'Sales contact library unavailable.';
        }
    }

    async function saveSalesperson() {
        const payload = {
            name: normalizedText(elements.salespersonName.value),
            email: normalizedText(elements.salespersonEmail.value),
            phone: normalizedText(elements.salespersonPhone.value)
        };
        if (!payload.name || (!payload.email && !payload.phone)) {
            elements.salespersonMessage.textContent = 'Enter a name and at least one contact method.';
            return;
        }
        elements.salespersonMessage.textContent = 'Saving sales contact...';
        try {
            const response = await fetch(`${API_URL}/api/v1/salespeople`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || `HTTP ${response.status}`);
            }
            const created = await response.json();
            await loadSalespeople();
            elements.salespersonSelect.value = created.salesperson_id;
            applySelectedSalesperson();
            elements.salespersonMessage.textContent = 'Sales contact saved and selected.';
        } catch (error) {
            elements.salespersonMessage.textContent = formatFetchError(error);
        }
    }

    function selectedSalesperson() {
        return state.savedSalespeople.find(person => person.salesperson_id === elements.salespersonSelect.value) || null;
    }

    function manualSalespersonPayload() {
        return {
            name: normalizedText(elements.salespersonName.value),
            email: normalizedText(elements.salespersonEmail.value),
            phone: normalizedText(elements.salespersonPhone.value)
        };
    }

    function applySelectedSalesperson() {
        const selected = selectedSalesperson();
        if (!selected) return;
        elements.salespersonName.value = selected.name || '';
        elements.salespersonEmail.value = selected.email || '';
        elements.salespersonPhone.value = selected.phone || '';
        elements.salespersonMessage.textContent = 'Saved sales contact loaded. Edit the fields to override for this label.';
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
        if (isSampleLabel()) {
            const selected = selectedSalesperson();
            const manual = manualSalespersonPayload();
            const manualDiffersFromSelected = !selected
                || manual.name !== (selected.name || '')
                || manual.email !== (selected.email || '')
                || manual.phone !== (selected.phone || '');

            if (manual.name && manualDiffersFromSelected) {
                formData.append('salesperson_name', manual.name);
                formData.append('salesperson_email', manual.email);
                formData.append('salesperson_phone', manual.phone);
            } else if (elements.salespersonSelect.value) {
                formData.append('salesperson_id', elements.salespersonSelect.value);
            } else if (manual.name) {
                formData.append('salesperson_name', manual.name);
                formData.append('salesperson_email', manual.email);
                formData.append('salesperson_phone', manual.phone);
            }
        }

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

    function buildAnalysisFormData() {
        const formData = new FormData();
        state.selectedFiles.forEach(file => formData.append('files', file));
        const productName = normalizedText(elements.productName.value);
        if (productName) formData.append('product_name', productName);
        return formData;
    }

    function setBooleanSelect(input, value) {
        if (value === true) input.value = 'yes';
        if (value === false) input.value = 'no';
    }

    function applyAnalysisToForm(data) {
        const extracted = data?.extracted || {};
        const product = extracted.product || {};
        const ghs = extracted.ghs || {};
        const transport = extracted.transport || {};

        setIfBlank(elements.productName, product.name);
        setIfBlank(elements.supplierName, product.supplier_name);
        setIfBlank(elements.supplierAddress, product.supplier_address);
        setIfBlank(elements.supplierPhone, product.supplier_phone);
        setIfBlank(elements.emergencyPhone, product.emergency_phone);
        setIfBlank(elements.unNumber, transport.un_number);
        setIfBlank(elements.properShippingName, transport.proper_shipping_name);
        setIfBlank(elements.hazardClass, transport.hazard_class);
        setIfBlank(elements.subsidiaryHazardClasses, (transport.subsidiary_hazard_classes || []).join(', '));
        if (!elements.packingGroup.value && transport.packing_group) {
            elements.packingGroup.value = transport.packing_group;
        }
        if (transport.not_regulated === true) {
            elements.transportStatus.value = 'not_regulated';
        } else if (transport.not_regulated === false) {
            elements.transportStatus.value = 'regulated';
        }
        setBooleanSelect(elements.marinePollutant, transport.marine_pollutant);
        setBooleanSelect(elements.hazardousSubstance, transport.hazardous_substance);
        setBooleanSelect(elements.hazardousWaste, transport.hazardous_waste);
        setIfBlank(elements.limitedQuantity, transport.limited_quantity);

        state.selectedGhsPictograms = Array.from(new Set(ghs.pictograms || []));
        renderSelectedGhsPictograms();
        applyCustomBrandSuggestions({
            extracted,
            branding: {
                suggested_logo: data?.suggested_logo,
                logo_source: data?.suggested_logo ? 'suggested' : 'none'
            }
        });
        updateGenerateState();
    }

    async function analyzeDocuments() {
        if (!state.selectedFiles.length) return;
        setProcessing(true);
        try {
            const response = await fetch(`${API_URL}/api/v1/documents/analyze`, {
                method: 'POST',
                body: buildAnalysisFormData()
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || `HTTP ${response.status}: ${response.statusText}`);
            }
            const data = await response.json();
            applyAnalysisToForm(data);
            elements.result.innerHTML = renderAnalysisResult(data);
            elements.previewRailContent.innerHTML = renderAnalysisResult(data);
            elements.analyzeHelp.textContent = 'Analysis complete. Review the extracted fields and enter shipment details before generating.';
            scrollToStep('stepSetup');
        } catch (error) {
            const message = formatFetchError(error);
            elements.result.innerHTML = renderErrorPanel(message);
            elements.previewRailContent.innerHTML = renderErrorPanel(message);
        } finally {
            setProcessing(false);
        }
    }

    function requestGenerationStart() {
        if (!state.selectedFiles.length) {
            elements.analyzeHelp.textContent = 'Upload at least one SDS or TDS PDF before starting analysis.';
            scrollToStep('stepUpload');
            return;
        }

        if (normalizedText(elements.productName.value).length < 2) {
            elements.analyzeHelp.textContent = 'Enter the label product name in Step 2, then click Analyze SDS/TDS.';
            elements.generateHelp.textContent = 'Product name is required before SDS/TDS analysis can start.';
            scrollToStep('stepSetup');
            elements.productName.focus({ preventScroll: true });
            return;
        }

        if (!isSampleLabel() && !normalizedText(elements.fillAmount.value)) {
            const message = 'MISSING_FILL_AMOUNT: Enter the net weight before generating pail, drum, or tote labels.';
            elements.analyzeHelp.textContent = message;
            elements.generateHelp.textContent = message;
            scrollToStep('stepSetup');
            elements.fillAmount.focus({ preventScroll: true });
            return;
        }

        generateLabel();
    }

    async function generateLabel() {
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
        elements.analyzeSdsBtn.disabled = isProcessing || !state.selectedFiles.length;
        elements.generateBtn.disabled = isProcessing || !(
            state.selectedFiles.length
            && normalizedText(elements.productName.value).length >= 2
            && (isSampleLabel() || normalizedText(elements.fillAmount.value))
        );
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
