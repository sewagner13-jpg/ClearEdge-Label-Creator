from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_frontend_config_targets_local_backend_for_file_and_localhost_opens():
    config_js = (REPO_ROOT / "netlify-frontend" / "config.js").read_text()

    assert "window.location.protocol === 'file:'" in config_js
    assert "localhost:8000" in config_js
    assert "clearedgelabelcreator-production.up.railway.app" in config_js


def test_frontend_formats_failed_fetch_for_local_file_opens():
    app_js = (REPO_ROOT / "netlify-frontend" / "app.js").read_text()
    utils_js = (REPO_ROOT / "netlify-frontend" / "js" / "utils.js").read_text()

    assert "formatFetchError" in app_js
    assert "function formatFetchError" in utils_js
    assert "You are opening this page as a local file" in utils_js
    assert "Open the app from http://localhost:8000" in utils_js


def test_frontend_shell_uses_guided_workflow_and_preview_rail():
    index_html = (REPO_ROOT / "netlify-frontend" / "index.html").read_text()

    assert 'class="workflow-stepper"' in index_html
    assert 'id="stepUpload"' in index_html
    assert 'id="stepSetup"' in index_html
    assert 'id="stepCompliance"' in index_html
    assert 'id="stepExport"' in index_html
    assert 'id="previewRail"' in index_html
    assert 'id="previewRailContent"' in index_html
    assert "Preview will appear after SDS/TDS analysis" in index_html
    assert 'type="module" src="app.js"' in index_html
    assert 'style="' not in index_html


def test_frontend_upload_step_exposes_direct_sds_analysis_action():
    index_html = (REPO_ROOT / "netlify-frontend" / "index.html").read_text()
    controller_js = (REPO_ROOT / "netlify-frontend" / "js" / "labelCreatorApp.js").read_text()

    assert 'id="analyzeSdsBtn"' in index_html
    assert "Analyze SDS/TDS" in index_html
    assert 'id="analyzeHelp"' in index_html
    assert "analyzeSdsBtn" in controller_js
    assert "analyzeHelp" in controller_js
    assert "analyzeDocuments" in controller_js
    assert "elements.analyzeSdsBtn.addEventListener('click', analyzeDocuments)" in controller_js
    assert "elements.analyzeSdsBtn.disabled = !hasFiles" in controller_js
    assert "/api/v1/documents/analyze" in controller_js


def test_frontend_entrypoint_is_modular_static_javascript():
    app_js = (REPO_ROOT / "netlify-frontend" / "app.js").read_text()
    js_dir = REPO_ROOT / "netlify-frontend" / "js"

    expected_modules = {
        "labelCreatorApp.js",
        "utils.js",
        "renderers.js",
        "view-model.js",
    }

    assert "import { createLabelCreatorApp } from './js/labelCreatorApp.js';" in app_js
    for module_name in expected_modules:
        assert (js_dir / module_name).exists(), f"missing frontend module {module_name}"


def test_frontend_custom_branding_exposes_clearedge_process_mark_toggle():
    index_html = (REPO_ROOT / "netlify-frontend" / "index.html").read_text()
    controller_js = (REPO_ROOT / "netlify-frontend" / "js" / "labelCreatorApp.js").read_text()

    assert 'id="showClearedgeMark"' in index_html
    assert "Show ClearEdge logo mark" in index_html
    assert "clearedgeBrandNote" in controller_js
    assert "showClearedgeMark" in controller_js
    assert "show_clearedge_mark" in controller_js
    assert "showClearedgeMark.checked ? 'true' : 'false'" in controller_js


def test_frontend_renders_dot_shipping_review_panel():
    renderers_js = (REPO_ROOT / "netlify-frontend" / "js" / "renderers.js").read_text()

    assert "function renderDotShippingReview" in renderers_js
    assert "dot_shipping_review" in renderers_js


def test_frontend_identifies_openai_source_review_without_agentcore_copy():
    renderers_js = (REPO_ROOT / "netlify-frontend" / "js" / "renderers.js").read_text()

    assert "OpenAI source review" in renderers_js
    assert "AgentCore status" not in renderers_js
    assert "DOT sticker sheet required" in renderers_js
    assert "includes the DOT-compliant sticker sheet after the product label" in renderers_js


def test_frontend_handles_dot_sticker_pdf_download_contract():
    index_html = (REPO_ROOT / "netlify-frontend" / "index.html").read_text()
    controller_js = (REPO_ROOT / "netlify-frontend" / "js" / "labelCreatorApp.js").read_text()
    renderers_js = (REPO_ROOT / "netlify-frontend" / "js" / "renderers.js").read_text()

    assert 'id="subsidiaryHazardClasses"' in index_html
    assert "Subsidiary Hazard Classes" in index_html
    assert "subsidiaryHazardClasses" in controller_js
    assert "subsidiary_hazard_classes" in controller_js
    assert "dot_sticker_pdf_url" in renderers_js
    assert "Download DOT Stickers PDF" in renderers_js
    assert "A separate DOT sticker PDF is also available" in renderers_js
    assert "DOT sticker sheet not generated" in renderers_js
    assert "No DOT sticker page required" in renderers_js


def test_frontend_exposes_sample_size_sales_contact_and_required_weight_contract():
    index_html = (REPO_ROOT / "netlify-frontend" / "index.html").read_text()
    controller_js = (REPO_ROOT / "netlify-frontend" / "js" / "labelCreatorApp.js").read_text()

    assert 'value="sample_4x6"' in index_html
    assert "Sample 4x6 thermal" in index_html
    assert 'id="salespersonPanel"' in index_html
    assert 'id="salespersonSelect"' in index_html
    assert 'id="salespersonName"' in index_html
    assert 'id="salespersonEmail"' in index_html
    assert 'id="salespersonPhone"' in index_html
    assert "loadSalespeople" in controller_js
    assert "salesperson_id" in controller_js
    assert "salesperson_name" in controller_js
    assert "applySelectedSalesperson" in controller_js
    assert "MISSING_FILL_AMOUNT" in controller_js
    assert "Sample 4x6 labels can be generated without weight" in controller_js


def test_frontend_shows_review_notes_without_blocked_download_copy():
    renderers_js = (REPO_ROOT / "netlify-frontend" / "js" / "renderers.js").read_text()

    assert "Download blocked" not in renderers_js
    assert "Approve Override & Enable Download" not in renderers_js
    assert "Review before downloading or printing" in renderers_js


def test_frontend_renders_inline_preview_and_download_data_url_first():
    renderers_js = (REPO_ROOT / "netlify-frontend" / "js" / "renderers.js").read_text()
    view_model_js = (REPO_ROOT / "netlify-frontend" / "js" / "view-model.js").read_text()

    assert "preview?.pages" in view_model_js
    assert "preview?.page_count" in view_model_js
    assert "label-preview-grid" in renderers_js
    assert "label-preview-card" in renderers_js
    assert "Page ${escapeHtml(pageNumber)} - ${escapeHtml(pageLabel)}" in renderers_js
    assert "label-preview-page" in renderers_js
    assert "const frameSource = pageUrl" in renderers_js
    assert "preview?.inline_svg" in view_model_js
    assert "srcdoc=" in renderers_js
    assert "download_data_url" in view_model_js
    assert "data_url" in view_model_js
    assert "const downloadHref = label?.download_url ?" in renderers_js
    assert "Download Full Label PDF" in renderers_js
    assert "formatPageCount" in renderers_js


def test_frontend_correction_ui_uses_existing_patch_endpoint():
    renderers_js = (REPO_ROOT / "netlify-frontend" / "js" / "renderers.js").read_text()
    controller_js = (REPO_ROOT / "netlify-frontend" / "js" / "labelCreatorApp.js").read_text()

    assert "Manual field corrections" in renderers_js
    assert "data-correction-field" in renderers_js
    assert "PATCH" in controller_js
    assert "/corrections" in controller_js
    assert "updated_by" in controller_js
    assert "reason" in controller_js


def test_backend_root_serves_local_frontend():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "CLEAR EDGE Label Creator" in response.text
