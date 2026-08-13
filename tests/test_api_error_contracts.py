from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from app import main


class FakePDFExtractor:
    def extract_text(self, content: bytes, doc_type: str):
        return type("Text", (), {"doc": doc_type, "pages": [1]})()


class FakeOpenAIClient:
    def extract_from_documents(self, sds_text, tds_text, product_name: str):
        raise AssertionError("Should not be called in error-path tests")


class FakeValidator:
    def validate(self, extracted_data, mode: str):
        raise AssertionError("Should not be called in error-path tests")


class FakeLabelGenerator:
    def generate_svg(
        self,
        extracted_data,
        mode="shipped_dot",
        size="pail",
        template_id=None,
        branding=None,
        orientation="vertical",
    ):
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
    main.pdf_extractor = FakePDFExtractor()
    main.openai_client = FakeOpenAIClient()
    main.validator = FakeValidator()
    main.label_generator = FakeLabelGenerator()


def test_generate_rejects_non_pdf_upload(tmp_path):
    setup_fakes(tmp_path)
    with TestClient(main.app) as client:
        files = {"files": ("notes.txt", b"not a pdf", "text/plain")}
        data = {"product_name": "Test Product", "mode": "shipped_dot", "size": "pail"}
        response = client.post("/api/v1/labels/generate", files=files, data=data)
        assert response.status_code == 400
        assert "UNSUPPORTED_FILE_TYPE" in response.text


def test_generate_rejects_oversized_product_name(tmp_path):
    setup_fakes(tmp_path)
    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {"product_name": "X" * 101, "mode": "shipped_dot", "size": "pail"}
        response = client.post("/api/v1/labels/generate", files=files, data=data)
        assert response.status_code == 400
        assert "Product name too long" in response.text


def test_override_requires_reason_and_approver(tmp_path):
    setup_fakes(tmp_path)
    with TestClient(main.app) as client:
        label_id = "label_missing_fields"
        main.label_metadata_store[label_id] = {
            "label_id": label_id,
            "validation_passed": False,
            "override_approved": False,
        }
        response = client.post(f"/api/v1/labels/{label_id}/override-approval", json={})
        assert response.status_code == 422


def test_download_rejects_invalid_label_id(tmp_path):
    setup_fakes(tmp_path)
    with TestClient(main.app) as client:
        response = client.get("/api/v1/labels/label*bad/download")
        assert response.status_code == 400
        assert "Invalid label ID" in response.text


def test_download_rejects_orphan_pdf_without_metadata(tmp_path):
    setup_fakes(tmp_path)
    label_id = "label_orphan"
    (tmp_path / f"{label_id}.pdf").write_bytes(b"%PDF-1.4 orphan")

    with TestClient(main.app) as client:
        response = client.get(f"/api/v1/labels/{label_id}/download")
        assert response.status_code == 404
        assert "Label not found" in response.text


def test_canva_template_fields_endpoint_returns_manifest(tmp_path):
    setup_fakes(tmp_path)

    with TestClient(main.app) as client:
        response = client.get("/api/v1/canva/template-fields")
        assert response.status_code == 200
        payload = response.json()
        field_names = {field["name"] for field in payload["fields"]}
        assert payload["template_name"] == "ClearEdge Product Label Template"
        assert "product_name" in field_names
        assert "ghs_pictogram_1_code" in field_names
