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

function statusToTone(status) {
    if (status === 'ready' || status === 'override_approved') return 'ready';
    if (status === 'needs_review') return 'review';
    if (status === 'blocked' || status === 'failed') return 'blocked';
    return 'neutral';
}
