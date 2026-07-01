import base64
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import main
from app.dot_sticker_sheet import US_LETTER_HEIGHT_PT, US_LETTER_WIDTH_PT
from app.label_stub import LabelGenerator
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


class FakePDFExtractorWithSuggestedLogo(FakePDFExtractor):
    def extract_suggested_logo(self, content: bytes, doc_type: str, source_filename: str | None = None):
        return {
            "source_document": doc_type,
            "source_file": source_filename,
            "page": 1,
            "name": "vendor-logo.png",
            "width": 420,
            "height": 90,
            "media_type": "image/png",
            "data_uri": "data:image/png;base64,c3VnZ2VzdGVkLWxvZ28=",
            "confidence": 0.84,
        }


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


class FakeSupplierOpenAIClient(FakeOpenAIClient):
    def extract_from_documents(self, sds_text, tds_text, product_name: str):
        extracted = super().extract_from_documents(sds_text, tds_text, product_name)
        extracted.product.supplier_name = "Vendor Chemical Co."
        extracted.product.supplier_address = "500 Vendor Drive, Akron, OH 44301"
        extracted.product.supplier_phone = "330-555-0199"
        return extracted


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


class FakeCorrectionValidator:
    def validate(self, extracted_data, mode: str):
        passed = bool(extracted_data.transport.un_number)
        return ValidationResult(
            mode=mode,
            passed=passed,
            errors=[] if passed else [ValidationError(field="transport.un_number", message="missing", severity="error")],
            warnings=[],
        )


class FakeRequiredDotValidator:
    def validate(self, extracted_data, mode: str):
        required = {
            "transport.un_number": extracted_data.transport.un_number,
            "transport.proper_shipping_name": extracted_data.transport.proper_shipping_name,
            "transport.hazard_class": extracted_data.transport.hazard_class,
            "transport.packing_group": extracted_data.transport.packing_group,
            "product.emergency_phone": extracted_data.product.emergency_phone,
        }
        errors = [
            ValidationError(field=field, message="missing", severity="error")
            for field, value in required.items()
            if not value
        ]
        return ValidationResult(mode=mode, passed=not errors, errors=errors, warnings=[])


class FakeLabelGenerator:
    def __init__(self):
        self.last_branding = None
        self.last_orientation = None

    def generate_svg(
        self,
        extracted_data,
        mode="shipped_dot",
        size="pail",
        template_id=None,
        branding=None,
        orientation="vertical",
    ):
        self.last_branding = branding
        self.last_orientation = orientation
        return '<svg xmlns="http://www.w3.org/2000/svg"></svg>'

    def generate_pdf(self, svg_content: str):
        return b"%PDF-1.4 fake"


@asynccontextmanager
async def no_lifespan(app):
    yield


def setup_fakes(tmp_path: Path, passed: bool):
    main.app.router.lifespan_context = no_lifespan
    main.LABELS_DIR = tmp_path
    main.LOGOS_DIR = tmp_path / "logos"
    main.logo_library = None
    main.label_metadata_store = {}
    main.pdf_extractor = FakePDFExtractor()
    main.openai_client = FakeOpenAIClient()
    main.validator = FakeValidator(passed=passed)
    main.label_generator = FakeLabelGenerator()
    main.agentcore_client = None


def test_generate_blocked_then_override_then_download(tmp_path):
    setup_fakes(tmp_path, passed=False)

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {"product_name": "Test Product", "mode": "shipped_dot", "size": "pail"}

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)
        assert generate_res.status_code == 200
        payload = generate_res.json()
        label_id = payload["label_id"]
        assert payload["status"] == "needs_review"
        assert payload["label"]["download_url"] == f"/api/v1/labels/{label_id}/download"
        assert payload["download"]["available"] is True
        assert payload["download"]["data_url"].startswith("data:application/pdf;base64,")
        assert payload["label"]["download_data_url"].startswith("data:application/pdf;base64,")
        assert payload["preview"]["available"] is True
        assert payload["preview"]["inline_svg"].lstrip().startswith("<svg")
        assert payload["label"]["preview_url"].endswith(f"/{label_id}/preview.svg")

        preview = client.get(payload["label"]["preview_url"])
        assert preview.status_code == 200
        assert "image/svg+xml" in preview.headers["content-type"]
        assert "attachment" not in preview.headers.get("content-disposition", "").lower()
        assert b"<svg" in preview.content

        blocked_download = client.get(f"/api/v1/labels/{label_id}/download")
        assert blocked_download.status_code == 200

        override_res = client.post(
            f"/api/v1/labels/{label_id}/override-approval",
            json={"approver": "QA Lead", "reason": "Business exception for controlled release"},
        )
        assert override_res.status_code == 200
        assert override_res.json()["status"] == "override_approved"

        allowed_download = client.get(f"/api/v1/labels/{label_id}/download")
        assert allowed_download.status_code == 200


def test_logo_library_upload_list_and_generate_reuses_saved_logo(tmp_path):
    setup_fakes(tmp_path, passed=True)
    fake_generator = FakeLabelGenerator()
    main.label_generator = fake_generator

    with TestClient(main.app) as client:
        upload = client.post(
            "/api/v1/logos",
            files={"logo": ("rudolf-logo.png", b"fake-png", "image/png")},
            data={"name": "Rudolf"},
        )
        assert upload.status_code == 200
        logo = upload.json()
        assert logo["name"] == "Rudolf"
        assert logo["logo_id"]
        assert logo["image_url"].endswith(f"/api/v1/logos/{logo['logo_id']}/image")

        listing = client.get("/api/v1/logos")
        assert listing.status_code == 200
        assert [item["logo_id"] for item in listing.json()["logos"]] == [logo["logo_id"]]

        image = client.get(logo["image_url"])
        assert image.status_code == 200
        assert image.content == b"fake-png"
        assert image.headers["content-type"] == "image/png"

        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {
            "product_name": "Customer Label",
            "mode": "workplace",
            "size": "pail",
            "label_brand": "custom",
            "brand_logo_id": logo["logo_id"],
        }
        generated = client.post("/api/v1/labels/generate", files=files, data=data)

        assert generated.status_code == 200
        payload = generated.json()
        assert payload["branding"]["logo_source"] == "library"
        assert payload["branding"]["logo_id"] == logo["logo_id"]
        assert payload["branding"]["logo_name"] == "Rudolf"
        assert fake_generator.last_branding["logo_data_uri"] == "data:image/png;base64,ZmFrZS1wbmc="


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


def test_corrections_endpoint_reruns_validation_and_enables_download(tmp_path):
    setup_fakes(tmp_path, passed=False)
    main.validator = FakeCorrectionValidator()

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {"product_name": "Corrected Product", "mode": "shipped_dot", "size": "pail"}

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)
        assert generate_res.status_code == 200
        payload = generate_res.json()
        label_id = payload["label_id"]
        assert payload["status"] == "needs_review"
        assert payload["download"]["available"] is True

        correction_res = client.patch(
            f"/api/v1/labels/{label_id}/corrections",
            json={
                "updated_by": "QA Lead",
                "reason": "Confirmed ID number against source SDS",
                "fields": {"transport.un_number": "UN1263"},
            },
        )

        assert correction_res.status_code == 200
        corrected = correction_res.json()
        assert corrected["status"] == "ready"
        assert corrected["download"]["available"] is True
        assert corrected["extracted"]["transport"]["un_number"] == "UN1263"


def test_generate_applies_operator_dot_fields_before_validation(tmp_path):
    setup_fakes(tmp_path, passed=False)
    main.validator = FakeRequiredDotValidator()
    main.label_generator = LabelGenerator()

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {
            "product_name": "Highway Shipped Product",
            "mode": "shipped_dot",
            "size": "drum",
            "transport_status": "regulated",
            "un_number": "1993",
            "proper_shipping_name": "Flammable liquids, n.o.s. (solvent blend)",
            "hazard_class": "3",
            "packing_group": "II",
            "marine_pollutant": "no",
            "limited_quantity": "No",
            "emergency_phone": "800-424-9300",
        }

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)

        assert generate_res.status_code == 200
        payload = generate_res.json()
        assert payload["status"] == "ready"
        assert payload["download"]["available"] is True
        assert payload["extracted"]["transport"]["un_number"] == "1993"
        assert payload["extracted"]["transport"]["proper_shipping_name"] == "Flammable liquids, n.o.s. (solvent blend)"
        assert payload["extracted"]["transport"]["hazard_class"] == "3"
        assert payload["extracted"]["transport"]["packing_group"] == "II"
        assert payload["extracted"]["transport"]["marine_pollutant"] is False
        assert payload["extracted"]["transport"]["limited_quantity"] == "No"
        assert payload["extracted"]["product"]["emergency_phone"] == "800-424-9300"
        assert payload["extracted"]["product"]["supplier_name"] == "ClearEdge Solutions"
        assert payload["extracted"]["product"]["supplier_address"] == "14301 CR Koon Highway, Newberry, SC 29108"
        assert payload["extracted"]["product"]["supplier_phone"] == "704-799-5769"


def test_generate_regulated_dot_label_exposes_separate_sticker_pdf_when_download_is_allowed(tmp_path):
    setup_fakes(tmp_path, passed=True)
    main.label_generator = LabelGenerator()

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {
            "product_name": "Sticker Product",
            "mode": "shipped_dot",
            "size": "drum",
            "fill_amount": "441 lb",
            "transport_status": "regulated",
            "un_number": "UN2924",
            "proper_shipping_name": "Flammable liquid, corrosive, n.o.s. (solvent, acid)",
            "hazard_class": "3",
            "subsidiary_hazard_classes": "8",
            "packing_group": "II",
        }

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)

        assert generate_res.status_code == 200
        payload = generate_res.json()
        label_id = payload["label_id"]
        assert payload["label"]["dot_sticker_pdf_url"] == f"/api/v1/labels/{label_id}/dot-stickers.pdf"
        assert payload["dot_stickers"]["available"] is True
        assert "artifact_path" not in payload["dot_stickers"]
        assert payload["dot_stickers"]["sticker_size_mm"] == 100
        assert [item["hazard_class"] for item in payload["dot_stickers"]["stickers"]] == ["3", "8"]
        assert payload["preview"]["page_count"] == 2
        assert payload["download"]["page_count"] == 2
        assert [page["page_number"] for page in payload["preview"]["pages"]] == [1, 2]
        assert payload["preview"]["pages"][0]["label"] == "Product label"
        assert payload["preview"]["pages"][0]["url"] == f"/api/v1/labels/{label_id}/preview.svg"
        assert "<svg" in payload["preview"]["pages"][0]["inline_svg"]
        assert payload["preview"]["pages"][1]["label"] == "DOT sticker sheet"
        assert payload["preview"]["pages"][1]["url"] == (
            f"/api/v1/labels/{label_id}/dot-stickers/preview-page-1.svg"
        )
        assert payload["dot_stickers"]["preview_pages"] == [{
            "page_number": 2,
            "label": "DOT sticker sheet",
            "media_type": "image/svg+xml",
            "url": f"/api/v1/labels/{label_id}/dot-stickers/preview-page-1.svg",
        }]

        sticker_preview = client.get(payload["preview"]["pages"][1]["url"])
        assert sticker_preview.status_code == 200
        assert "image/svg+xml" in sticker_preview.headers["content-type"]
        assert 'fill="#D71920"' in sticker_preview.text

        sticker_res = client.get(payload["label"]["dot_sticker_pdf_url"])
        assert sticker_res.status_code == 200
        assert sticker_res.headers["content-type"] == "application/pdf"
        assert sticker_res.content.startswith(b"%PDF")

        label_res = client.get(payload["label"]["download_url"])
        assert label_res.status_code == 200
        label_pdf = PdfReader(BytesIO(label_res.content))
        assert len(label_pdf.pages) == 2
        assert float(label_pdf.pages[0].mediabox.width) == 648
        assert float(label_pdf.pages[0].mediabox.height) == 864
        assert float(label_pdf.pages[1].mediabox.width) == US_LETTER_WIDTH_PT
        assert float(label_pdf.pages[1].mediabox.height) == US_LETTER_HEIGHT_PT

        inline_pdf = PdfReader(BytesIO(base64.b64decode(payload["download"]["data_url"].split(",", 1)[1])))
        assert len(inline_pdf.pages) == 2


def test_not_regulated_dot_label_explains_no_sticker_page(tmp_path):
    setup_fakes(tmp_path, passed=True)

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {
            "product_name": "Not Regulated Product",
            "mode": "shipped_dot",
            "size": "drum",
            "fill_amount": "441 lb",
            "transport_status": "not_regulated",
        }

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)

        assert generate_res.status_code == 200
        payload = generate_res.json()
        assert payload["preview"]["page_count"] == 1
        assert payload["download"]["page_count"] == 1
        assert len(payload["preview"]["pages"]) == 1
        assert payload["dot_stickers"]["available"] is False
        assert payload["dot_stickers"]["preview_pages"] == []
        assert payload["dot_stickers"]["reason"] == "No DOT sticker page required: product is not regulated for transport."


def test_regulated_dot_label_without_hazard_class_explains_missing_sticker_page(tmp_path):
    setup_fakes(tmp_path, passed=True)

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {
            "product_name": "Missing Hazard Class Product",
            "mode": "shipped_dot",
            "size": "drum",
            "fill_amount": "441 lb",
            "transport_status": "regulated",
            "un_number": "UN1993",
            "proper_shipping_name": "Flammable liquid, n.o.s. (solvent)",
            "packing_group": "II",
        }

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)

        assert generate_res.status_code == 200
        payload = generate_res.json()
        assert payload["preview"]["page_count"] == 1
        assert payload["download"]["page_count"] == 1
        assert payload["dot_stickers"]["available"] is False
        assert payload["dot_stickers"]["preview_pages"] == []
        assert payload["dot_stickers"]["reason"] == (
            "DOT sticker sheet not generated - enter hazard class."
        )


def test_unsupported_dot_label_class_explains_missing_sticker_asset(tmp_path):
    setup_fakes(tmp_path, passed=True)

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {
            "product_name": "Unsupported Sticker Product",
            "mode": "shipped_dot",
            "size": "drum",
            "fill_amount": "441 lb",
            "transport_status": "regulated",
            "un_number": "UN2810",
            "proper_shipping_name": "Toxic liquid, organic, n.o.s.",
            "hazard_class": "6.1",
            "packing_group": "II",
        }

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)

        assert generate_res.status_code == 200
        payload = generate_res.json()
        assert payload["preview"]["page_count"] == 1
        assert payload["download"]["page_count"] == 1
        assert payload["dot_stickers"]["available"] is False
        assert payload["dot_stickers"]["preview_pages"] == []
        assert payload["dot_stickers"]["reason"] == (
            "DOT sticker sheet not generated - approved DOT sticker asset is missing for hazard class 6.1."
        )


def test_blocked_dot_label_keeps_sticker_pdf_download_blocked_until_override(tmp_path):
    setup_fakes(tmp_path, passed=False)
    main.label_generator = LabelGenerator()

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {
            "product_name": "Blocked Sticker Product",
            "mode": "shipped_dot",
            "size": "drum",
            "fill_amount": "441 lb",
            "transport_status": "regulated",
            "un_number": "UN1993",
            "proper_shipping_name": "Flammable liquid, n.o.s. (solvent)",
            "hazard_class": "3",
            "packing_group": "II",
        }

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)
        assert generate_res.status_code == 200
        payload = generate_res.json()
        label_id = payload["label_id"]

        assert payload["label"]["dot_sticker_pdf_url"] == f"/api/v1/labels/{label_id}/dot-stickers.pdf"
        assert payload["dot_stickers"]["available"] is True
        sticker_download = client.get(f"/api/v1/labels/{label_id}/dot-stickers.pdf")
        assert sticker_download.status_code == 200

        override_res = client.post(
            f"/api/v1/labels/{label_id}/override-approval",
            json={"approver": "QA Lead", "reason": "Reviewed SDS and approved shipping sticker release"},
        )
        assert override_res.status_code == 200
        assert override_res.json()["dot_sticker_pdf_url"] == f"/api/v1/labels/{label_id}/dot-stickers.pdf"

        allowed_stickers = client.get(f"/api/v1/labels/{label_id}/dot-stickers.pdf")
        assert allowed_stickers.status_code == 200
        assert allowed_stickers.headers["content-type"] == "application/pdf"


def test_generate_accepts_orientation_and_infers_container_type_from_weight(tmp_path):
    setup_fakes(tmp_path, passed=True)
    fake_generator = FakeLabelGenerator()
    main.label_generator = fake_generator

    with TestClient(main.app) as client:
        files = {"files": ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {
            "product_name": "Orientation Product",
            "mode": "workplace",
            "size": "pail",
            "orientation": "horizontal",
            "fill_amount": "441 lb",
        }

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)

        assert generate_res.status_code == 200
        payload = generate_res.json()
        assert payload["label"]["orientation"] == "horizontal"
        assert payload["label"]["container_type"] == "drum"
        assert payload["extracted"]["shipment"]["container_type"] == "drum"
        assert fake_generator.last_orientation == "horizontal"


def test_generate_custom_brand_accepts_uploaded_logo_and_supplier_fields(tmp_path):
    setup_fakes(tmp_path, passed=True)
    fake_generator = FakeLabelGenerator()
    main.label_generator = fake_generator

    with TestClient(main.app) as client:
        files = [
            ("files", ("test_sds.pdf", b"%PDF-1.4 test", "application/pdf")),
            ("brand_logo", ("customer-logo.png", b"fake-png", "image/png")),
        ]
        data = {
            "product_name": "Customer Label",
            "mode": "workplace",
            "size": "pail",
            "label_brand": "custom",
            "show_clearedge_mark": "false",
            "supplier_name": "Customer Chemical Co.",
            "supplier_address": "200 Customer Lane, Charlotte, NC",
            "supplier_phone": "704-555-0199",
        }

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)

        assert generate_res.status_code == 200
        payload = generate_res.json()
        assert payload["status"] == "ready"
        assert payload["extracted"]["product"]["supplier_name"] == "Customer Chemical Co."
        assert payload["extracted"]["product"]["supplier_address"] == "200 Customer Lane, Charlotte, NC"
        assert payload["extracted"]["product"]["supplier_phone"] == "704-555-0199"
        assert fake_generator.last_branding["mode"] == "custom"
        assert fake_generator.last_branding["show_clearedge_mark"] is False
        assert payload["branding"]["show_clearedge_mark"] is False
        assert fake_generator.last_branding["logo_data_uri"].startswith("data:image/png;base64,")


def test_generate_custom_brand_uses_extracted_supplier_and_suggested_logo(tmp_path):
    setup_fakes(tmp_path, passed=True)
    fake_generator = FakeLabelGenerator()
    main.pdf_extractor = FakePDFExtractorWithSuggestedLogo()
    main.openai_client = FakeSupplierOpenAIClient()
    main.label_generator = fake_generator

    with TestClient(main.app) as client:
        files = {"files": ("vendor_sds.pdf", b"%PDF-1.4 test", "application/pdf")}
        data = {
            "product_name": "Private Label Product",
            "mode": "workplace",
            "size": "pail",
            "label_brand": "custom",
        }

        generate_res = client.post("/api/v1/labels/generate", files=files, data=data)

        assert generate_res.status_code == 200
        payload = generate_res.json()
        assert payload["status"] == "ready"
        assert payload["extracted"]["product"]["supplier_name"] == "Vendor Chemical Co."
        assert payload["extracted"]["product"]["supplier_address"] == "500 Vendor Drive, Akron, OH 44301"
        assert payload["extracted"]["product"]["supplier_phone"] == "330-555-0199"
        assert payload["branding"]["mode"] == "custom"
        assert payload["branding"]["logo_source"] == "suggested"
        assert payload["branding"]["suggested_logo"]["source_file"] == "vendor_sds.pdf"
        assert payload["branding"]["suggested_logo"]["data_uri"].startswith("data:image/png;base64,")
        assert fake_generator.last_branding["logo_data_uri"] == "data:image/png;base64,c3VnZ2VzdGVkLWxvZ28="
