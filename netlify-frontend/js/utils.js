export const API_URL = window.CLEAREDGE_API_URL || (
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:8000'
        : 'https://clearedgelabelcreator-production.up.railway.app'
);

export const CANVA_TEMPLATE_NAME = window.CLEAREDGE_CANVA_TEMPLATE_NAME || 'ClearEdge Product Label Template';
export const CANVA_TEMPLATE_URL = window.CLEAREDGE_CANVA_TEMPLATE_URL || '';
export const KG_TO_LB = 2.2046226218;

export const GHS_PICTOGRAM_OPTIONS = {
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

export function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value === null || value === undefined ? '' : String(value);
    return div.innerHTML;
}

export function formatFetchError(error) {
    const message = String(error?.message || error || 'Unknown error');
    if (/failed to fetch|networkerror|load failed/i.test(message)) {
        if (window.location.protocol === 'file:') {
            return (
                `Failed to connect to the label backend at ${API_URL}. ` +
                'You are opening this page as a local file. Open the app from http://localhost:8000 after running ./run-local.sh, or use the deployed Netlify URL.'
            );
        }
        return (
            `Failed to connect to the label backend at ${API_URL}. ` +
            'Confirm the backend is running and that the frontend is allowed by CORS.'
        );
    }
    return message;
}

export function safeImageDataUri(value) {
    const dataUri = String(value || '');
    if (/^data:image\/(png|jpeg|jpg|svg\+xml|webp);base64,[a-zA-Z0-9+/=]+$/i.test(dataUri)) {
        return dataUri;
    }
    return '';
}

export function apiUrl(path) {
    const value = String(path || '');
    if (!value) return '';
    if (/^https?:\/\//i.test(value) || value.startsWith('data:')) return value;
    return `${API_URL}${value.startsWith('/') ? value : `/${value}`}`;
}

export function formatPageCount(pageCount) {
    const count = Number(pageCount || 0);
    if (!count) return '';
    return `${count} ${count === 1 ? 'page' : 'pages'}`;
}

export function formatPreviewPageLabel(label) {
    const value = String(label || '').trim();
    const knownLabels = {
        'Product label': 'Product Label',
        'DOT sticker sheet': 'DOT Sticker Sheet'
    };
    return knownLabels[value] || value || 'Preview Page';
}

export function ghsPictogramLabel(code) {
    return GHS_PICTOGRAM_OPTIONS[code] || code;
}

export function containerTypeLabel(containerType) {
    const labels = {
        pail: 'Pail',
        drum: 'Drum',
        tote: 'Tote',
        vertical: 'Vertical',
        horizontal: 'Horizontal'
    };
    return labels[containerType] || containerType || '';
}

export function inferContainerTypeFromFillAmount(value) {
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

export function normalizedText(value) {
    return String(value || '').trim();
}

export function formatBytes(size) {
    const bytes = Number(size || 0);
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${bytes} B`;
}
