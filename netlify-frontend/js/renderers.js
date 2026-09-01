import {
    API_URL,
    CANVA_TEMPLATE_NAME,
    CANVA_TEMPLATE_URL,
    apiUrl,
    containerTypeLabel,
    escapeHtml,
    formatPageCount,
    formatPreviewPageLabel,
    ghsPictogramLabel
} from './utils.js';
import { createDotAnalysisSummary, createResultViewModel } from './view-model.js';

const CORRECTION_FIELDS = [
    { path: 'product.emergency_phone', label: 'Emergency Phone', source: data => data?.extracted?.product?.emergency_phone },
    { path: 'ghs.signal_word', label: 'Signal Word', source: data => data?.extracted?.ghs?.signal_word },
    { path: 'transport.un_number', label: 'UN/NA Number', source: data => data?.extracted?.transport?.un_number },
    { path: 'transport.proper_shipping_name', label: 'Proper Shipping Name', source: data => data?.extracted?.transport?.proper_shipping_name },
    { path: 'transport.hazard_class', label: 'Hazard Class', source: data => data?.extracted?.transport?.hazard_class },
    { path: 'transport.packing_group', label: 'Packing Group', source: data => data?.extracted?.transport?.packing_group },
    { path: 'nfpa.health', label: 'NFPA Health', source: data => data?.extracted?.nfpa?.health },
    { path: 'nfpa.flammability', label: 'NFPA Flammability', source: data => data?.extracted?.nfpa?.flammability },
    { path: 'nfpa.instability', label: 'NFPA Instability', source: data => data?.extracted?.nfpa?.instability },
    { path: 'nfpa.special', label: 'NFPA Special', source: data => data?.extracted?.nfpa?.special }
];

export function renderInitialPreview() {
    return `
        <div class="empty-preview">
            <p class="step-kicker">Preview</p>
            <h2>Preview will appear after SDS/TDS analysis.</h2>
            <p>Generate a label to see the product label page, DOT sticker sheet when required, and export actions.</p>
        </div>
    `;
}

export function renderProcessingPreview(stageLabel = 'Analyzing uploaded documents') {
    return `
        <div class="status-card review">
            <strong>Generating label</strong>
            <p>${escapeHtml(stageLabel)}</p>
        </div>
        <div class="empty-preview">
            <p class="step-kicker">In progress</p>
            <h2>Building preview and PDF outputs.</h2>
            <p>The app is extracting SDS/TDS text, checking DOT/GHS fields, and rendering the label artifacts.</p>
        </div>
    `;
}

export function renderErrorPanel(errorMessage) {
    return `
        <div class="status-card error">
            <strong>Error</strong>
            <p>${escapeHtml(errorMessage)}</p>
        </div>
    `;
}

export function renderAnalysisResult(data) {
    return `
        <div class="status-card success">
            <strong>SDS/TDS analysis complete</strong>
            <p>Review the extracted fields below, add the required shipment details, then generate the label preview.</p>
        </div>
        ${renderDotAnalysisStatus(data)}
        ${renderExtractedInformation(data)}
    `;
}

export function renderDotAnalysisStatus(data = {}) {
    const summary = createDotAnalysisSummary(data);
    return `
        <div class="status-card ${escapeHtml(summary.tone)}">
            <strong>${escapeHtml(summary.title)}</strong>
            <p>${escapeHtml(summary.detail)}</p>
            ${summary.fields.length ? `<p><strong>Parsed fields:</strong> ${escapeHtml(summary.fields.join(' | '))}</p>` : ''}
            ${summary.missingFields.length ? `<p><strong>Needs review:</strong> ${escapeHtml(summary.missingFields.join(', '))}</p>` : ''}
            ${summary.evidence ? `<p class="field-help"><strong>Source:</strong> ${escapeHtml(summary.evidence)}</p>` : ''}
        </div>
    `;
}

export function renderPreviewRail(data) {
    const model = createResultViewModel(data);
    return `
        ${renderStatusCard(data)}
        ${renderActionLinks(data.label, data.download, { includeCanva: false })}
        ${renderLabelPreview(data)}
        ${!model.hasDotStickerPage ? renderDotStickerPreviewStatus(data.dot_stickers, model.pages) : ''}
    `;
}

export function renderResultPanel(data) {
    return `
        ${renderStatusCard(data)}
        ${renderValidationPanel(data.validation)}
        ${renderDotShippingReview(data.dot_shipping_review, data.dot_stickers)}
        ${renderSourceReview(data.source_review || data.agentcore_review)}
        ${renderBrandingSummary(data.branding)}
        ${renderExtractedInformation(data)}
        ${renderCorrectionPanel(data)}
        <section class="panel-card">
            <div class="panel-header">
                <div>
                    <h3>Exports</h3>
                    <p class="field-help">Download the app-generated PDF first. Canva handoff files are available for template work.</p>
                </div>
            </div>
            <div class="result-actions">
                ${renderActionLinks(data.label, data.download)}
            </div>
        </section>
    `;
}

function renderStatusCard(data) {
    const model = createResultViewModel(data);
    const labels = {
        ready: 'Ready to download',
        needs_review: 'Needs review',
        blocked: 'Review required',
        override_approved: 'Override approved'
    };
    const description = {
        ready: 'The generated PDF and available exports are ready for operator review.',
        needs_review: 'Review the notes below before printing or sending this label.',
        blocked: 'Review the missing or conflicting fields before printing.',
        override_approved: 'A manual approval was recorded for this label.'
    };

    return `
        <div class="status-card ${escapeHtml(model.statusTone)}">
            <strong>${escapeHtml(labels[data?.status] || 'Label generated')}</strong>
            <p>${escapeHtml(description[data?.status] || 'Review the preview, extracted fields, and exports before printing.')}</p>
        </div>
    `;
}

export function renderActionLinks(label = {}, download = {}, options = {}) {
    const downloadHref = label?.download_url ? apiUrl(label.download_url) : (label?.download_data_url || download?.data_url || apiUrl(download?.url));
    const downloadPageCount = download?.page_count || label?.page_count;
    const downloadPageText = formatPageCount(downloadPageCount);
    const dotStickerPdfUrl = label?.dot_sticker_pdf_url;
    const canvaCsvUrl = label?.canva_csv_url;
    const canvaJsonUrl = label?.canva_json_url;
    const canvaFieldMapUrl = `${API_URL}/api/v1/canva/template-fields`;
    const showCanvaHandoff = options.includeCanva !== false && Boolean(canvaCsvUrl || canvaJsonUrl);

    return `
        <div class="result-actions">
            ${downloadHref ? `
            <a href="${escapeHtml(downloadHref)}" download="clearedge-label.pdf" class="btn btn-primary">
                Download Full Label PDF${downloadPageText ? ` (${downloadPageText})` : ''}
            </a>
            ` : ''}
            ${dotStickerPdfUrl ? `
            <a href="${escapeHtml(apiUrl(dotStickerPdfUrl))}" download class="btn btn-secondary">
                Download DOT Stickers PDF
            </a>
            ` : ''}
        </div>
        ${showCanvaHandoff ? `
        <div class="panel-card">
            <h3>Canva handoff</h3>
            <p class="field-help">${escapeHtml(CANVA_TEMPLATE_NAME)} can use the generated CSV fields for Bulk Create. The app PDF remains the primary print output.</p>
            <div class="result-actions">
                ${CANVA_TEMPLATE_URL ? `
                <a href="${escapeHtml(CANVA_TEMPLATE_URL)}" target="_blank" rel="noopener" class="btn btn-secondary">
                    Open Canva Template
                </a>
                ` : ''}
                ${canvaCsvUrl ? `
                <a href="${escapeHtml(apiUrl(canvaCsvUrl))}" download class="btn btn-secondary">
                    Download Canva CSV
                </a>
                ` : ''}
                ${canvaJsonUrl ? `
                <a href="${escapeHtml(apiUrl(canvaJsonUrl))}" target="_blank" rel="noopener" class="btn btn-secondary">
                    View Canva JSON
                </a>
                ` : ''}
                <a href="${escapeHtml(canvaFieldMapUrl)}" target="_blank" rel="noopener" class="btn btn-ghost">
                    View Canva Field Map
                </a>
            </div>
        </div>
        ` : ''}
    `;
}

export function renderLabelPreview(data) {
    const model = createResultViewModel(data);
    if (!model.pages.length) return '';

    const pageFrames = model.pages.map((page, index) => {
        const pageNumber = page.page_number || index + 1;
        const pageLabel = formatPreviewPageLabel(page.label || `Preview page ${pageNumber}`);
        const pageUrl = page.url ? apiUrl(page.url) : '';
        const frameSource = pageUrl
            ? `data="${escapeHtml(pageUrl)}"`
            : `srcdoc="${escapeHtml(page.inline_svg || '')}"`;
        const previewSurface = pageUrl
            ? `<object class="label-preview-object" type="${escapeHtml(page.media_type || 'image/svg+xml')}" ${frameSource}>
                    <a href="${escapeHtml(pageUrl)}" target="_blank" rel="noopener">Open preview page</a>
               </object>`
            : `<iframe class="label-preview-frame" title="Generated label preview page ${escapeHtml(pageNumber)}" ${frameSource}></iframe>`;

        return `
            <section class="label-preview-page label-preview-card">
                <div class="label-preview-page-heading">
                    <span>Page ${escapeHtml(pageNumber)} - ${escapeHtml(pageLabel)}</span>
                    ${pageUrl ? `<a href="${escapeHtml(pageUrl)}" target="_blank" rel="noopener">Open larger preview</a>` : ''}
                </div>
                ${previewSurface}
            </section>
        `;
    }).join('');

    return `
        <section class="label-preview-panel">
            <div class="label-preview-heading">
                <h3>Label Preview${formatPageCount(model.pageCount) ? ` (${formatPageCount(model.pageCount)})` : ''}</h3>
            </div>
            <div class="label-preview-grid">
                ${pageFrames}
            </div>
        </section>
    `;
}

export function renderDotStickerPreviewStatus(dotStickers = {}, pages = []) {
    const hasStickerPreview = pages.some(page => String(page?.label || '').toLowerCase().includes('dot sticker'));
    if (hasStickerPreview) return '';

    const reason = dotStickers.reason || 'DOT sticker sheet not generated - review DOT shipping data.';
    const isNoStickerRequired = reason.startsWith('No DOT sticker page required');
    const title = isNoStickerRequired ? 'No DOT sticker page required' : 'DOT sticker sheet not generated';
    return `
        <div class="dot-sticker-status-card">
            <strong>${escapeHtml(title)}</strong>
            <p>${escapeHtml(reason)}</p>
        </div>
    `;
}

export function renderValidationPanel(validation = {}) {
    const errors = validation?.errors || [];
    const warnings = validation?.warnings || [];
    if (errors.length === 0 && warnings.length === 0) {
        return '';
    }

    return `
        <section class="panel-card">
            <h3>Review before downloading or printing</h3>
            ${renderIssueGroup('Review items', errors)}
            ${renderIssueGroup('Warnings', warnings)}
        </section>
    `;
}

export function renderDotShippingReview(review = {}, dotStickers = {}) {
    if (!review || !review.applicable) return '';
    const blockers = review.blockers || [];
    const warnings = review.warnings || [];
    const actions = review.required_actions || [];

    return `
        <section class="panel-card">
            <h3>DOT Shipping Review</h3>
            <div class="field-grid">
                ${renderReadOnlyField('Status', review.status || 'unknown')}
                ${renderReadOnlyField('Package', containerTypeLabel(review.container_type) || review.container_type || 'Unknown')}
                ${renderReadOnlyField('Category', review.package_category || 'Unknown')}
            </div>
            ${review.separate_dot_sticker_required ? `
            <div class="status-card review">
                <strong>DOT sticker sheet required:</strong>
                <p>The label PDF download includes the DOT-compliant sticker sheet after the product label.</p>
                ${dotStickers?.available ? `
                <p><strong>A separate DOT sticker PDF is also available.</strong></p>
                ` : dotStickers?.reason ? `
                <p>${escapeHtml(dotStickers.reason)}</p>
                ` : ''}
            </div>
            ` : ''}
            ${renderIssueGroup('DOT review items', blockers)}
            ${renderIssueGroup('Required outside-label actions', actions)}
            ${renderIssueGroup('DOT review notes', warnings)}
        </section>
    `;
}

export function renderSourceReview(review = {}) {
    if (!review) return '';
    const fieldReviews = review.field_reviews || [];
    const criticalIssues = review.critical_issues || [];
    const warnings = review.warnings || [];
    const hasContent = review.status || fieldReviews.length || criticalIssues.length || warnings.length;
    if (!hasContent) return '';

    return `
        <section class="panel-card">
            <h3>OpenAI source review</h3>
            <p class="field-help">Review status: <strong>${escapeHtml(review.status || 'unknown')}</strong></p>
            ${renderIssueGroup('Critical review issues', criticalIssues)}
            ${fieldReviews.length ? `
            <div>
                <strong>Field review</strong>
                <ul class="review-list">
                    ${fieldReviews.slice(0, 8).map(item => `
                    <li>
                        <strong>${escapeHtml(item.field_path || 'field')}:</strong>
                        ${escapeHtml(item.status || 'reviewed')}
                        ${item.recommended_value !== undefined && item.recommended_value !== null ? ` - ${escapeHtml(item.recommended_value)}` : ''}
                        ${item.confidence !== undefined ? ` (${Math.round(Number(item.confidence || 0) * 100)}%)` : ''}
                        ${item.evidence ? `<div class="field-help">"${escapeHtml(item.evidence)}"</div>` : ''}
                        ${item.reason ? `<div class="field-help">${escapeHtml(item.reason)}</div>` : ''}
                    </li>
                    `).join('')}
                </ul>
            </div>
            ` : ''}
            ${warnings.length ? `<p class="field-help">${warnings.map(escapeHtml).join('<br>')}</p>` : ''}
        </section>
    `;
}

export function renderBrandingSummary(branding = {}) {
    if (!branding) return '';
    const sourceLabels = {
        clearedge: 'Official ClearEdge brand',
        suggested: 'Suggested logo from SDS/TDS',
        uploaded: 'Uploaded logo',
        library: 'Saved logo library',
        none: 'No logo selected'
    };
    const sourceLabel = sourceLabels[branding.logo_source] || branding.logo_source || 'Not set';
    return `
        <section class="panel-card">
            <h3>Branding</h3>
            <div class="field-grid">
                ${renderReadOnlyField('Brand mode', branding.mode || 'clearedge')}
                ${renderReadOnlyField('Logo source', sourceLabel)}
                ${branding.logo_name ? renderReadOnlyField('Logo', branding.logo_name) : ''}
                ${branding.saved_logo?.name ? renderReadOnlyField('Saved as', branding.saved_logo.name) : ''}
                ${branding.suggested_logo?.source_file ? renderReadOnlyField('Suggested from', branding.suggested_logo.source_file) : ''}
            </div>
        </section>
    `;
}

export function renderExtractedInformation(data = {}) {
    const extracted = data.extracted || {};
    const product = extracted.product || {};
    const ghs = extracted.ghs || {};
    const transport = extracted.transport || {};
    const nfpa = extracted.nfpa || {};
    const shipment = extracted.shipment || {};
    const dotSummary = createDotAnalysisSummary(data);
    const uses = product.product_uses || [];
    const hazardStatements = ghs.hazard_statements || [];

    return `
        <section class="panel-card">
            <h3>Extracted Information</h3>
            <div class="field-grid">
                ${renderReadOnlyField('Product Name', product.name || data.product_name || '')}
                ${renderReadOnlyField('Signal Word', ghs.signal_word || '')}
                ${renderReadOnlyField('GHS Pictograms', (ghs.pictograms || []).map(ghsPictogramLabel).join(', '))}
                ${renderReadOnlyField('Product Uses', uses.slice(0, 3).join(' | '))}
                ${renderReadOnlyField('DOT Section 14 Result', dotSummary.title.replace('Section 14 parsed: ', '').replace('Section 14 result ', ''))}
                ${renderReadOnlyField('UN/NA Number', transport.un_number || '')}
                ${renderReadOnlyField('Proper Shipping Name', transport.proper_shipping_name || '')}
                ${renderReadOnlyField('Hazard Class', transport.hazard_class || '')}
                ${renderReadOnlyField('Packing Group', transport.packing_group || '')}
                ${renderReadOnlyField('Emergency Phone', product.emergency_phone || '')}
                ${renderReadOnlyField(
                    'NFPA 704',
                    `${nfpa.health ?? 0}-${nfpa.flammability ?? 0}-${nfpa.instability ?? 0}`
                    + (nfpa.source === 'clearedge_default' ? ' (ClearEdge default; SDS/HMIS not listed)' : '')
                )}
                ${renderReadOnlyField('Lot / Exp / Fill', [shipment.lot_number, shipment.expiration_date, shipment.fill_amount].filter(Boolean).join(' | '))}
                ${hazardStatements.length ? renderReadOnlyField(
                    `Hazard Statements (${hazardStatements.length})`,
                    hazardStatements.slice(0, 3).map(item => `${item.code ? `${item.code}: ` : ''}${item.text || ''}`).join(' | ')
                ) : ''}
            </div>
        </section>
    `;
}

export function renderCorrectionPanel(data = {}) {
    if (!data?.label_id) return '';
    const fields = CORRECTION_FIELDS.map(field => {
        const value = field.source(data);
        return `
            <div class="form-field">
                <label for="correction-${escapeHtml(field.path.replace('.', '-'))}">${escapeHtml(field.label)}</label>
                <input
                    id="correction-${escapeHtml(field.path.replace('.', '-'))}"
                    type="text"
                    data-correction-field="${escapeHtml(field.path)}"
                    value="${escapeHtml(value === null || value === undefined ? '' : value)}"
                >
            </div>
        `;
    }).join('');

    return `
        <section class="correction-panel">
            <h3>Manual field corrections</h3>
            <p class="field-help">Update fields after checking the SDS/TDS source. Corrections rerender the preview and PDF.</p>
            <form id="correctionForm" data-label-id="${escapeHtml(data.label_id)}">
                <div class="correction-grid">
                    ${fields}
                    <div class="form-field">
                        <label for="correctionUpdatedBy">Updated by</label>
                        <input id="correctionUpdatedBy" name="updated_by" type="text" placeholder="Operator initials or name" required>
                    </div>
                    <div class="form-field">
                        <label for="correctionReason">Reason</label>
                        <input id="correctionReason" name="reason" type="text" placeholder="Confirmed against SDS Section 14" required>
                    </div>
                </div>
                <div class="form-actions">
                    <button type="submit" class="btn btn-secondary">Apply corrections</button>
                    <p class="form-message" id="correctionMessage"></p>
                </div>
            </form>
        </section>
    `;
}

function renderIssueGroup(title, issues = []) {
    if (!issues.length) return '';
    return `
        <div>
            <strong>${escapeHtml(title)}</strong>
            <ul class="review-list">
                ${issues.map(issue => `
                    <li>
                        <strong>${escapeHtml(issue.code || issue.field || issue.field_path || 'review')}:</strong>
                        ${escapeHtml(issue.message || issue.reason || JSON.stringify(issue))}
                        ${issue.evidence ? `<div class="field-help">"${escapeHtml(issue.evidence)}"</div>` : ''}
                    </li>
                `).join('')}
            </ul>
        </div>
    `;
}

function renderReadOnlyField(label, value) {
    const display = value === null || value === undefined || value === '' ? 'Not listed' : String(value);
    return `
        <div class="field-group">
            <div class="field-label">${escapeHtml(label)}</div>
            <div class="field-value">${escapeHtml(display)}</div>
        </div>
    `;
}
