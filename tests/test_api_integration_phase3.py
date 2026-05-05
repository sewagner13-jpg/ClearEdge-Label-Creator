from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.schema import (
    ExtractedData,
    ProductInfo,
    GHSClassification,
    TransportClassification,
    HazardStatement,
    PrecautionaryStatement,
    ValidationResult,
    ValidationError,
)


class FakePDFExtractor:
    def extract_text(self, content: bytes, doc_type: str):
        return type("Text", (), {"doc": doc_type, "pages": [1]})()


class FakeOpenAIClient:
    def extract_from_documents(self, sds_text, tds_text, product_name: str):
        return ExtractedData(
            product=ProductInfo(name=product_name, supplier_name="ClearEdge"),
            ghs=GHSClassification(
                signal_word="Warning",
                pictograms=["GHS07"],
                hazard_statements=[HazardStatement(code="H315", text="Causes skin irritation")],
                precautionary_statements=[PrecautionaryStatement(code="P280", text="Wear protective gloves")],
            ),
            transport=TransportClassification(),
        )


class FakeValidator:
    def __init__(self, passed: bool):
        self.passed = passed

    def validate(self, extracted_data, mode: str):
        return ValidationResult(
            mode=mode,
            passed=self.passed,
            errors=[] if self.passed else [ValidationError(field="ghs", message="blocked", severity="error")],
            warnings=[],
        )


class FakeLabelGenerator:
    def generate_svg(self, extracted_data, mode="shipped_dot", size="pail", template_id=None):
        return '<svg xmlns="http://www.w3.org/2000/svg"></svg>'

    def generate_pdf(self, svg_content: str):
        return b"%PDF-1.4 fake"


@asynccontextmanager
async def no_lifespan(app):
    yield


def setup_fakes(tmp_path: Path, passed: bool):
    main.app.router.lifespan_context = no_lifespan
    main.LABELS_DIR = tmp_path
    main.label_metadata_store = {}
    main.pdf_extractor = FakePDFExtractor()
    main.openai_client = FakeOpenAIClient()
    main.validator = FakeValidator(passed=passed)
    main.label_generator = FakeLabelGenerator()


def test_generate_blocked_then_override_then_download(tmp_path):
    setup_fakes(tmp_path, passed=False)

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {"product_name": "Test Product", "mode": "shipped_dot", "size": "pail"}

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)
        assert generate_res.status_code == 200
        payload = generate_res.json()
        label_id = payload["label_id"]
        assert payload["label"]["download_url"] is None

        blocked_download = client.get(f"/api/v1/labels/{label_id}/download")
        assert blocked_download.status_code == 403

        override_res = client.post(
            f"/api/v1/labels/{label_id}/override-approval",
            json={"approver": "QA Lead", "reason": "Business exception for controlled release"},
        )
        assert override_res.status_code == 200
        assert override_res.json()["status"] == "override_approved"

        allowed_download = client.get(f"/api/v1/labels/{label_id}/download")
        assert allowed_download.status_code == 200


def test_generate_approved_allows_download(tmp_path):
    setup_fakes(tmp_path, passed=True)

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {"product_name": "Approved Product", "mode": "shipped_dot", "size": "pail"}

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)
        assert generate_res.status_code == 200
        payload = generate_res.json()
        label_id = payload["label_id"]
        assert payload["label"]["download_url"]

        download_res = client.get(f"/api/v1/labels/{label_id}/download")
        assert download_res.status_code == 200
