from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread
import time
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright
import pytest
import uvicorn

from app import main
from app.label_stub import LabelGenerator
from app.logo_library import LogoLibrary
from app.salesperson_library import SalespersonLibrary
from app.schema import (
    ExtractedData,
    ExtractedText,
    ExtractedTextPage,
    Evidence,
    GHSClassification,
    ProductInfo,
    TransportClassification,
    ValidationResult,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class BrowserTestPDFExtractor:
    def extract_text(self, content: bytes, doc_type: str):
        return ExtractedText(
            doc=doc_type,
            method_used="text",
            pages=[ExtractedTextPage(page=1, text="")],
        )


class BrowserTestOpenAIClient:
    def extract_from_documents(self, sds_text, tds_text, product_name: str):
        return ExtractedData(
            product=ProductInfo(
                name=product_name,
                product_uses=["Resins of Coating & Ink"],
            ),
            ghs=GHSClassification(signal_word="Warning", pictograms=["GHS07"]),
            transport=TransportClassification(
                not_regulated=True,
                proper_shipping_name="Not applicable",
            ),
            evidence=[Evidence(
                field_path="transport.not_regulated",
                doc="SDS",
                section="Section 14",
                page=7,
                quote="Not regulated as a dangerous good for transport.",
            )],
        )


class BrowserTestValidator:
    def validate(self, extracted_data, mode: str):
        return ValidationResult(mode=mode, passed=True, errors=[], warnings=[])


@asynccontextmanager
async def no_lifespan(app):
    yield


@pytest.fixture
def local_label_server(tmp_path, monkeypatch):
    labels_dir = tmp_path / "labels"
    logos_dir = tmp_path / "logos"
    salespeople_dir = tmp_path / "salespeople"
    labels_dir.mkdir()

    monkeypatch.setattr(main.app.router, "lifespan_context", no_lifespan)
    monkeypatch.setattr(main, "LABELS_DIR", labels_dir)
    monkeypatch.setattr(main, "LOGOS_DIR", logos_dir)
    monkeypatch.setattr(main, "SALESPEOPLE_DIR", salespeople_dir)
    monkeypatch.setattr(main, "label_metadata_store", {})
    monkeypatch.setattr(main, "pdf_extractor", BrowserTestPDFExtractor())
    monkeypatch.setattr(main, "openai_client", BrowserTestOpenAIClient())
    monkeypatch.setattr(main, "validator", BrowserTestValidator())
    monkeypatch.setattr(main, "web_retriever", object())
    monkeypatch.setattr(main, "label_generator", LabelGenerator())
    monkeypatch.setattr(main, "logo_library", LogoLibrary(logos_dir))
    monkeypatch.setattr(main, "salesperson_library", SalespersonLibrary(salespeople_dir))

    config = uvicorn.Config(
        main.app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    thread = Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with urlopen("http://127.0.0.1:8000/api/v1/health", timeout=1) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(0.1)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        pytest.fail("Local label server did not become healthy")

    yield "http://127.0.0.1:8000"

    server.should_exit = True
    thread.join(timeout=10)
    assert not thread.is_alive(), "Local label server did not stop"


@pytest.mark.browser
@pytest.mark.integration
def test_browser_generates_preview_and_pdf_for_xml_sensitive_label_text(local_label_server):
    artifact_dir = REPO_ROOT / "test_output" / "browser"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(local_label_server, wait_until="networkidle")

        page.locator("#fileInput").set_input_files(
            {
                "name": "coating-and-ink-sds.pdf",
                "mimeType": "application/pdf",
                "buffer": b"%PDF-1.4 browser regression fixture",
            }
        )
        page.locator("#productName").fill("Coating & Ink Resin")
        page.locator("#fillAmount").fill("500 lb")

        generate_button = page.locator("#generateBtn")
        expect(generate_button).to_be_enabled()
        generate_button.click()

        result = page.locator("#result")
        expect(result.get_by_text("Ready to download", exact=True)).to_be_visible(timeout=20_000)
        expect(page.locator(".label-preview-card").first).to_be_visible()
        expect(result.get_by_text("Error", exact=True)).to_have_count(0)

        download_link = result.get_by_role("link", name="Download Full Label PDF (1 page)")
        expect(download_link).to_be_visible()
        with page.expect_download() as download_info:
            download_link.click()
        download_path = artifact_dir / "T0001-coating-and-ink-label.pdf"
        download_info.value.save_as(download_path)
        assert download_path.read_bytes().startswith(b"%PDF")

        page.screenshot(
            path=artifact_dir / "T0001-label-preview.png",
            full_page=True,
        )
        browser.close()


@pytest.mark.browser
@pytest.mark.integration
def test_browser_explains_missing_weight_and_section_14_parse(local_label_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(local_label_server, wait_until="networkidle")

        page.locator("#fileInput").set_input_files({
            "name": "edgemer-e618-sds.pdf",
            "mimeType": "application/pdf",
            "buffer": b"%PDF-1.4 browser DOT analysis fixture",
        })
        page.locator("#productName").fill("SilaRes CE 618")

        generate_button = page.locator("#generateBtn")
        expect(generate_button).to_be_enabled()
        expect(page.locator("#generateHelp")).to_contain_text("Net Weight / Fill Amount")
        generate_button.click()
        expect(page.locator("#fillAmount")).to_be_focused()
        expect(page.locator("#result").get_by_text("Generating label", exact=True)).to_have_count(0)

        page.locator("#analyzeSdsBtn").click()
        expect(page.locator("#dotParseStatus")).to_contain_text(
            "Section 14 parsed: Not regulated for DOT transport",
            timeout=20_000,
        )
        expect(page.locator("#dotParseStatus")).to_contain_text(
            "SDS, Section 14, page 7: Not regulated as a dangerous good for transport."
        )
        expect(page.locator("#result")).to_contain_text(
            "Section 14 parsed: Not regulated for DOT transport"
        )
        browser.close()
