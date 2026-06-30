(() => {
    const productionApiUrl = 'https://clearedgelabelcreator-production.up.railway.app';
    const isLocalHost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const isLocalFile = window.location.protocol === 'file:';

    window.CLEAREDGE_API_URL = (isLocalHost || isLocalFile)
        ? 'http://localhost:8000'
        : productionApiUrl;
    window.CLEAREDGE_CANVA_TEMPLATE_NAME = 'ClearEdge Product Label Template';
    window.CLEAREDGE_CANVA_TEMPLATE_URL = '';
})();
