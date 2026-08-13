export function createResultViewModel(data = {}) {
    const previewPages = Array.isArray(data?.preview?.pages) ? data.preview.pages : [];
    const fallbackPage = data?.preview?.inline_svg || data?.preview?.url || data?.label?.preview_url
        ? [{
            page_number: 1,
            label: 'Product label',
            inline_svg: data?.preview?.inline_svg,
            url: data?.preview?.url || data?.label?.preview_url,
            media_type: data?.preview?.media_type || 'image/svg+xml'
        }]
        : [];
    const pages = previewPages.length ? previewPages : fallbackPage;
    const renderablePages = pages.filter(page => page?.inline_svg || page?.url);
    const pageCount = Number(data?.preview?.page_count || renderablePages.length || 0);
    const hasDotStickerPage = renderablePages.some(page => String(page?.label || '').toLowerCase().includes('dot sticker'));
    const dotStickerReason = hasDotStickerPage
        ? ''
        : (data?.dot_stickers?.reason || 'DOT sticker sheet not generated - review DOT shipping data.');
    const label = data?.label || {};
    const download = data?.download || {};
    const downloadHref = label.download_url || label.download_data_url || download.url || download.data_url || '';
    const statusTone = statusToTone(data?.status);

    return {
        raw: data,
        labelId: data?.label_id || '',
        status: data?.status || 'generated',
        statusTone,
        pageCount,
        pages: renderablePages,
        hasDotStickerPage,
        dotStickerReason,
        actions: {
            downloadHref,
            downloadPageCount: download.page_count || label.page_count || pageCount,
            hasFullPdf: Boolean(downloadHref),
            dotStickerPdfUrl: label.dot_sticker_pdf_url || data?.dot_stickers?.url || '',
            hasDotStickerPdf: Boolean(label.dot_sticker_pdf_url || data?.dot_stickers?.url),
            canvaCsvUrl: label.canva_csv_url || '',
            canvaJsonUrl: label.canva_json_url || '',
            hasCanvaHandoff: Boolean(label.canva_csv_url || label.canva_json_url)
        }
    };
}

export function createGenerationRequirements({
    fileCount = 0,
    productName = '',
    fillAmount = '',
    sampleLabel = false
} = {}) {
    const requirements = [];
    if (Number(fileCount) < 1) {
        requirements.push({ field: 'files', label: 'SDS or TDS PDF' });
    }
    if (String(productName || '').trim().length < 2) {
        requirements.push({ field: 'productName', label: 'Product Name' });
    }
    if (!sampleLabel && !String(fillAmount || '').trim()) {
        requirements.push({ field: 'fillAmount', label: 'Net Weight / Fill Amount' });
    }
    return requirements;
}

export function createDotAnalysisSummary(data = {}) {
    const extracted = data?.extracted || {};
    const transport = extracted.transport || {};
    const evidence = (extracted.evidence || []).find(item =>
        String(item?.field_path || '').startsWith('transport.') && item?.quote
    );
    const evidenceText = evidence ? [
        evidence.doc,
        evidence.section,
        evidence.page ? `page ${evidence.page}` : ''
    ].filter(Boolean).join(', ') + `: ${evidence.quote}` : '';

    if (transport.not_regulated === true) {
        return {
            status: 'not_regulated',
            tone: 'ready',
            title: 'Section 14 parsed: Not regulated for DOT transport',
            detail: 'The uploaded SDS does not require UN/NA number, hazard class, or packing group for this transport state.',
            fields: [],
            missingFields: [],
            evidence: evidenceText
        };
    }

    if (transport.not_regulated === false) {
        const fieldDefinitions = [
            ['UN/NA', transport.un_number],
            ['Shipping name', transport.proper_shipping_name],
            ['Hazard class', transport.hazard_class],
            ['Packing group', transport.packing_group]
        ];
        const fields = fieldDefinitions
            .filter(([, value]) => value !== null && value !== undefined && String(value).trim())
            .map(([label, value]) => `${label}: ${value}`);
        const missingFields = fieldDefinitions
            .filter(([, value]) => value === null || value === undefined || !String(value).trim())
            .map(([label]) => label);
        return {
            status: 'regulated',
            tone: missingFields.length ? 'review' : 'ready',
            title: 'Section 14 parsed: DOT regulated',
            detail: 'Review the parsed highway-shipping fields before generating the label.',
            fields,
            missingFields,
            evidence: evidenceText
        };
    }

    return {
        status: 'undetermined',
        tone: 'blocked',
        title: 'Section 14 result needs review',
        detail: 'The SDS/TDS analysis did not find a reliable DOT regulated or not-regulated conclusion. Review Section 14 or enter the transport fields manually.',
        fields: [],
        missingFields: [],
        evidence: evidenceText
    };
}

function statusToTone(status) {
    if (status === 'ready' || status === 'override_approved') return 'ready';
    if (status === 'needs_review') return 'review';
    if (status === 'blocked' || status === 'failed') return 'blocked';
    return 'neutral';
}
