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


class FakeGeminiClient:
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


class FakeValidatorBlocked:
    def validate(self, extracted_data, mode: str):
        return ValidationResult(
            mode=mode,
            passed=False,
            errors=[ValidationError(field="ghs", message="blocked", severity="error")],
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


def setup_fakes(tmp_path: Path):
    main.app.router.lifespan_context = no_lifespan
    main.LABELS_DIR = tmp_path
    main.label_metadata_store = {}
    main.drive_client = object()
    main.pdf_extractor = FakePDFExtractor()
    main.gemini_client = FakeGeminiClient()
    main.validator = FakeValidatorBlocked()
    main.web_retriever = object()
    main.label_generator = FakeLabelGenerator()


def test_operator_journey_blocked_to_override_to_download(tmp_path):
    setup_fakes(tmp_path)

    with TestClient(main.app) as client:
        # 1) Readiness
        readiness = client.get("/api/v1/readiness")
        assert readiness.status_code == 200
        assert "checks" in readiness.json()

        # 2) Generate blocked label
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {"product_name": "Journey Product", "mode": "shipped_dot", "size": "pail"}
        generate = client.post("/api/v1/labels/generate", files=files, data=data)
        assert generate.status_code == 200
        payload = generate.json()
        label_id = payload["label_id"]
        assert payload["label"]["download_url"] is None

        # 3) Metadata reflects blocked status
        meta1 = client.get(f"/api/v1/labels/{label_id}")
        assert meta1.status_code == 200
        assert meta1.json()["status"] == "blocked"

        # 4) Blocked download
        blocked_download = client.get(f"/api/v1/labels/{label_id}/download")
        assert blocked_download.status_code == 403

        # 5) Override approval
        override = client.post(
            f"/api/v1/labels/{label_id}/override-approval",
            json={"approver": "QA Lead", "reason": "Controlled customer release with EHS approval"},
        )
        assert override.status_code == 200
        assert override.json()["status"] == "override_approved"

        # 6) Metadata reflects override state
        meta2 = client.get(f"/api/v1/labels/{label_id}")
        assert meta2.status_code == 200
        assert meta2.json()["status"] == "override_approved"

        # 7) Download now allowed
        allowed_download = client.get(f"/api/v1/labels/{label_id}/download")
        assert allowed_download.status_code == 200


class FakeValidatorApproved:
    def validate(self, extracted_data, mode: str):
        return ValidationResult(
            mode=mode,
            passed=True,
            errors=[],
            warnings=[],
        )


def setup_fakes_approved(tmp_path: Path):
    main.app.router.lifespan_context = no_lifespan
    main.LABELS_DIR = tmp_path
    main.label_metadata_store = {}
    main.drive_client = object()
    main.pdf_extractor = FakePDFExtractor()
    main.gemini_client = FakeGeminiClient()
    main.validator = FakeValidatorApproved()
    main.web_retriever = object()
    main.label_generator = FakeLabelGenerator()


def test_operator_journey_first_pass_approved(tmp_path):
    setup_fakes_approved(tmp_path)

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {"product_name": "Approved Journey", "mode": "shipped_dot", "size": "pail"}

        generate = client.post("/api/v1/labels/generate", files=files, data=data)
        assert generate.status_code == 200
        payload = generate.json()
        label_id = payload["label_id"]
        assert payload["label"]["download_url"] is not None

        meta = client.get(f"/api/v1/labels/{label_id}")
        assert meta.status_code == 200
        meta_payload = meta.json()
        assert meta_payload["status"] == "approved"
        assert meta_payload["override_approved"] is False
        assert meta_payload["download_url"].endswith(f"/{label_id}/download")

        download = client.get(f"/api/v1/labels/{label_id}/download")
        assert download.status_code == 200
