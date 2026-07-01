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

    assert "function formatFetchError" in app_js
    assert "You are opening this page as a local file" in app_js
    assert "Open the app from http://localhost:8000" in app_js


def test_frontend_custom_branding_exposes_clearedge_process_mark_toggle():
    index_html = (REPO_ROOT / "netlify-frontend" / "index.html").read_text()
    app_js = (REPO_ROOT / "netlify-frontend" / "app.js").read_text()

    assert 'id="showClearedgeMark"' in index_html
    assert "Show ClearEdge logo mark" in index_html
    assert "const showClearedgeMark" in app_js
    assert "show_clearedge_mark" in app_js
    assert "showClearedgeMark.checked ? 'true' : 'false'" in app_js


def test_frontend_renders_dot_shipping_review_panel():
    app_js = (REPO_ROOT / "netlify-frontend" / "app.js").read_text()

    assert "function renderDotShippingReview" in app_js
    assert "dot_shipping_review" in app_js
    assert "DOT sticker sheet required" in app_js
    assert "includes the DOT-compliant sticker sheet after the product label" in app_js


def test_frontend_handles_dot_sticker_pdf_download_contract():
    index_html = (REPO_ROOT / "netlify-frontend" / "index.html").read_text()
    app_js = (REPO_ROOT / "netlify-frontend" / "app.js").read_text()

    assert 'id="subsidiaryHazardClasses"' in index_html
    assert "Subsidiary Hazard Classes" in index_html
    assert "const subsidiaryHazardClasses" in app_js
    assert "subsidiary_hazard_classes" in app_js
    assert "dot_sticker_pdf_url" in app_js
    assert "Download DOT Stickers PDF" in app_js
    assert "A separate DOT sticker PDF is also available" in app_js


def test_frontend_shows_review_notes_without_blocked_download_copy():
    app_js = (REPO_ROOT / "netlify-frontend" / "app.js").read_text()

    assert "Download blocked" not in app_js
    assert "Approve Override & Enable Download" not in app_js
    assert "Review before downloading or printing" in app_js


def test_frontend_renders_inline_preview_and_download_data_url_first():
    app_js = (REPO_ROOT / "netlify-frontend" / "app.js").read_text()

    assert "preview?.pages" in app_js
    assert "label-preview-page" in app_js
    assert "preview?.inline_svg" in app_js
    assert "srcdoc=" in app_js
    assert "download_data_url" in app_js
    assert "data_url" in app_js


def test_backend_root_serves_local_frontend():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "CLEAR EDGE Label Creator" in response.text
