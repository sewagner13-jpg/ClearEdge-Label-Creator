import base64
from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from app import label_pipeline
from app.dot_sticker_sheet import US_LETTER_HEIGHT_PT, US_LETTER_WIDTH_PT
from app.label_stub import LabelGenerator
from app.label_pipeline import LabelPipeline
from app.validator import ComplianceValidator
from app.schema import (
    ExtractedData,
    ExtractedText,
    ExtractedTextPage,
    GHSClassification,
    ProductInfo,
    ShipmentInfo,
    TransportClassification,
    ValidationResult,
)


class FakePDFExtractor:
    def extract_text(self, content: bytes, doc_type: str):
        return ExtractedText(
            doc=doc_type,
            method_used="text",
            pages=[ExtractedTextPage(page=1, text="Section 14 transport data")],
        )


class FakeOpenAIClient:
    def __init__(self, extracted: ExtractedData):
        self.extracted = extracted

    def extract_from_documents(self, sds_text, tds_text, product_name: str):
        self.extracted.product.name = product_name
        return self.extracted


class FailingOpenAIClient:
    def extract_from_documents(self, sds_text, tds_text, product_name: str):
        raise RuntimeError("quota exceeded")


class IncompleteNovAddOpenAIClient:
    def extract_from_documents(self, sds_text, tds_text, product_name: str):
        return ExtractedData(
            product=ProductInfo(name=product_name),
            ghs=GHSClassification(signal_word="Warning"),
            transport=TransportClassification(),
        )


class NovAddPDFExtractor:
    SDS_TEXT = """
    1. Identification
    Product name: Novadd D-5104E
    Manufacturer/Importer/Distributor Information
    Company Name

    : SynthEdge Advanced Materials Co.,Ltd.
    4F., No.8, Qinghua
    2nd St., Xinwu Dist.,
    Taoyuan City 327,
    Taiwan (R.O.C.)

    Telephone

    : +886-3-4971028

    Emergency telephone number:

    +886-3-4971028

    2. Hazard(s) identification
    Hazard Classification
    Health Hazards
    Acute toxicity (Oral)
    Serious Eye Damage/Eye Irritation
    Skin sensitizer
    Specific Target Organ Toxicity Repeated Exposure

    Category 4
    Category 1
    Category 1
    Category 2

    Label Elements
    Signal Word:

    Danger

    Hazard Statement:
    Harmful if swallowed.
    Causes serious eye damage.
    May cause an allergic skin reaction.
    May cause damage to organs through prolonged or repeated exposure.
    Harmful to aquatic life with long lasting effects.
    Precautionary
    Statements
    Prevention:

    Do not breathe dust/fume/gas/mist/vapors/spray. Wash face, hands and any
    exposed skin thoroughly after handling. Wear protective gloves/protective clothing/eye protection/face protection.

    Response:

    IF SWALLOWED: Call a POISON CENTER/doctor if you feel unwell. Rinse mouth.

    14. Transport information
    Domestic regulation
    49 CFR
    Not regulated as a dangerous good

    16.Other information, including date of preparation
    HMIS Hazard ID
    Health

    *

    2

    Flammability

    1

    Physical Hazards

    0
    """
    TDS_TEXT = """
    Technical Data Sheet
    MULTIFUNCTIONAL ADDITIVE NovAdd D-5104E
    NovAdd D-5104E is a multifunctional additive offering wetting, defoaming,
    and dispersing performance. It is a symmetric nonionic surfactant.

    APPLICATION AREAS
    Car OEM coatings
    ●
    General industrial coatings
    ●
    Printing Inks
    """

    def extract_text(self, content: bytes, doc_type: str):
        text = self.TDS_TEXT if doc_type == "TDS" else self.SDS_TEXT
        return ExtractedText(
            doc=doc_type,
            method_used="text",
            pages=[ExtractedTextPage(page=1, text=text)],
        )


class FakeValidator:
    def validate(self, extracted_data, mode: str):
        return ValidationResult(mode=mode, passed=bool(extracted_data.transport.un_number))


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
        return "<svg></svg>"

    def generate_pdf(self, svg_content: str):
        writer = PdfWriter()
        writer.add_blank_page(width=288, height=432)
        output = BytesIO()
        writer.write(output)
        return output.getvalue()


class FakeAgentCore:
    def __init__(self, review=None, error=None):
        self.review = review
        self.error = error

    def review_label_data(self, **kwargs):
        if self.error:
            raise self.error
        return self.review


def make_pipeline(tmp_path, extracted, agentcore_client=None):
    store = {}

    def save():
        pass

    return LabelPipeline(
        pdf_extractor=FakePDFExtractor(),
        openai_client=FakeOpenAIClient(extracted),
        validator=FakeValidator(),
        label_generator=FakeLabelGenerator(),
        agentcore_client=agentcore_client,
        labels_dir=tmp_path,
        metadata_store=store,
        save_metadata_store=save,
    ), store


def make_pipeline_with_openai(tmp_path, openai_client, agentcore_client=None):
    store = {}

    def save():
        pass

    return LabelPipeline(
        pdf_extractor=FakePDFExtractor(),
        openai_client=openai_client,
        validator=FakeValidator(),
        label_generator=FakeLabelGenerator(),
        agentcore_client=agentcore_client,
        labels_dir=tmp_path,
        metadata_store=store,
        save_metadata_store=save,
    ), store


def base_extracted(un_number=None):
    return ExtractedData(
        product=ProductInfo(name="Test Product"),
        ghs=GHSClassification(),
        transport=TransportClassification(
            un_number=un_number,
            proper_shipping_name="Paint related material",
            hazard_class="3",
            packing_group="II",
        ),
    )


def test_safe_exception_detail_redacts_openai_keys():
    detail = LabelPipeline._safe_exception_detail(Exception("bad key sk-test_SECRET123 in request"))

    assert "sk-test_SECRET123" not in detail
    assert "sk-***" in detail


@pytest.mark.asyncio
async def test_agentcore_disabled_review_degrades_to_openai_only(tmp_path, monkeypatch):
    monkeypatch.setattr(label_pipeline.settings, "agentcore_enabled", False)
    pipeline, _store = make_pipeline(tmp_path, base_extracted(un_number="UN1263"))

    result = await pipeline.generate_label_from_uploads(
        files=[_upload("test_sds.pdf")],
        product_name="AgentCore Disabled",
        mode="shipped_dot",
        size="pail",
    )

    assert result["status"] == "ready"
    assert result["agentcore_review"]["status"] == "disabled"
    assert result["download"]["available"] is True


@pytest.mark.asyncio
async def test_pipeline_response_includes_dot_shipping_review_for_separate_stickers(tmp_path, monkeypatch):
    monkeypatch.setattr(label_pipeline.settings, "agentcore_enabled", False)
    extracted = base_extracted(un_number="UN1263")
    extracted.shipment = ShipmentInfo(fill_amount="441 lb", container_type="drum")
    pipeline, _store = make_pipeline(tmp_path, extracted)
    pipeline.label_generator = LabelGenerator()

    result = await pipeline.generate_label_from_uploads(
        files=[_upload("test_sds.pdf")],
        product_name="Sticker Review Product",
        mode="shipped_dot",
        size="drum",
        fill_amount="441 lb",
    )

    assert result["status"] == "ready"
    assert result["download"]["available"] is True
    assert result["dot_shipping_review"]["separate_dot_sticker_required"] is True
    assert any(
        action["code"] == "APPLY_SEPARATE_DOT_HAZARD_LABEL"
        for action in result["dot_shipping_review"]["required_actions"]
    )
    pdf_bytes = base64.b64decode(result["download"]["data_url"].split(",", 1)[1])
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) == 2
    assert float(reader.pages[1].mediabox.width) == US_LETTER_WIDTH_PT
    assert float(reader.pages[1].mediabox.height) == US_LETTER_HEIGHT_PT


@pytest.mark.asyncio
async def test_openai_failure_uses_deterministic_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(label_pipeline.settings, "agentcore_enabled", False)
    pipeline, _store = make_pipeline_with_openai(tmp_path, FailingOpenAIClient())

    result = await pipeline.generate_label_from_uploads(
        files=[_upload("test_sds.pdf")],
        product_name="Fallback Product",
        mode="shipped_dot",
        size="pail",
    )

    assert result["status"] == "blocked"
    assert result["success"] is True
    assert any("AI_EXTRACTION_FAILED" in warning for warning in result["extracted"]["warnings"])


@pytest.mark.asyncio
async def test_pipeline_reconciles_incomplete_openai_with_novadd_source_facts(tmp_path, monkeypatch):
    monkeypatch.setattr(label_pipeline.settings, "agentcore_enabled", False)
    store = {}

    pipeline = LabelPipeline(
        pdf_extractor=NovAddPDFExtractor(),
        openai_client=IncompleteNovAddOpenAIClient(),
        validator=ComplianceValidator(),
        label_generator=LabelGenerator(),
        labels_dir=tmp_path,
        metadata_store=store,
        save_metadata_store=lambda: None,
    )

    result = await pipeline.generate_label_from_uploads(
        files=[_upload("novadd-sds.pdf"), _upload("novadd-tds.pdf")],
        product_name="NovAdd D-5104E",
        mode="shipped_dot",
        size="drum",
        label_brand="custom",
    )

    assert result["status"] == "ready"
    assert result["preview"]["page_count"] == 1
    assert result["download"]["page_count"] == 1
    assert result["dot_stickers"]["available"] is False
    assert result["dot_shipping_review"]["status"] == "not_regulated"
    extracted = result["extracted"]
    assert extracted["ghs"]["signal_word"] == "Danger"
    assert extracted["ghs"]["pictograms"] == ["GHS05", "GHS07", "GHS08"]
    assert "Harmful if swallowed." in {
        statement["text"] for statement in extracted["ghs"]["hazard_statements"]
    }
    assert any(
        "Do not breathe dust/fume/gas/mist/vapors/spray" in statement["text"]
        for statement in extracted["ghs"]["precautionary_statements"]
    )
    assert extracted["product"]["supplier_name"] == "SynthEdge Advanced Materials Co.,Ltd."
    assert extracted["product"]["emergency_phone"] == "+886-3-4971028"
    assert extracted["product"]["product_uses"][:2] == [
        "Wetting, defoaming, and dispersing additive",
        "Car OEM coatings",
    ]
    assert extracted["nfpa"]["health"] == 2
    assert extracted["nfpa"]["flammability"] == 1
    assert extracted["nfpa"]["instability"] == 0
    assert any("conflicted with source SDS signal word" in warning for warning in extracted["warnings"])
    assert "id=\"pictogram-GHS05\"" in result["preview"]["inline_svg"]
    assert "id=\"pictogram-GHS07\"" in result["preview"]["inline_svg"]
    assert "id=\"pictogram-GHS08\"" in result["preview"]["inline_svg"]
    assert "Harmful if swallowed." in result["preview"]["inline_svg"]


@pytest.mark.asyncio
async def test_agentcore_promotes_missing_source_backed_value(tmp_path, monkeypatch):
    monkeypatch.setattr(label_pipeline.settings, "agentcore_enabled", True)
    review = {
        "status": "reviewed",
        "field_reviews": [
            {
                "field_path": "transport.un_number",
                "recommended_value": "UN1263",
                "status": "found",
                "confidence": 0.91,
                "source_document": "SDS",
                "page": 1,
                "evidence": "UN number: UN1263",
            }
        ],
        "label_inclusion_decisions": [],
        "critical_issues": [],
        "warnings": [],
    }
    pipeline, _store = make_pipeline(tmp_path, base_extracted(), FakeAgentCore(review=review))

    result = await pipeline.generate_label_from_uploads(
        files=[_upload("test_sds.pdf")],
        product_name="Recovered Product",
        mode="shipped_dot",
        size="pail",
    )

    assert result["status"] == "ready"
    assert result["extracted"]["transport"]["un_number"] == "UN1263"
    assert result["agentcore_review"]["status"] == "reviewed"
    assert result["download"]["available"] is True


@pytest.mark.asyncio
async def test_agentcore_conflict_forces_needs_review(tmp_path, monkeypatch):
    monkeypatch.setattr(label_pipeline.settings, "agentcore_enabled", True)
    review = {
        "status": "reviewed",
        "field_reviews": [
            {
                "field_path": "transport.un_number",
                "recommended_value": "UN1993",
                "status": "conflict",
                "confidence": 0.93,
                "source_document": "SDS",
                "page": 1,
                "evidence": "UN number: UN1993",
            }
        ],
        "label_inclusion_decisions": [],
        "critical_issues": [],
        "warnings": [],
    }
    pipeline, _store = make_pipeline(tmp_path, base_extracted(un_number="UN1263"), FakeAgentCore(review=review))

    result = await pipeline.generate_label_from_uploads(
        files=[_upload("test_sds.pdf")],
        product_name="Conflict Product",
        mode="shipped_dot",
        size="pail",
    )

    assert result["status"] == "needs_review"
    assert result["download"]["available"] is True
    assert any(error["field"] == "agentcore.transport.un_number" for error in result["errors"])


@pytest.mark.asyncio
async def test_agentcore_blocking_issue_marks_needs_review_without_blocking_download(tmp_path, monkeypatch):
    monkeypatch.setattr(label_pipeline.settings, "agentcore_enabled", True)
    review = {
        "status": "reviewed",
        "field_reviews": [],
        "label_inclusion_decisions": [],
        "critical_issues": [
            {
                "field_path": "transport.proper_shipping_name",
                "severity": "blocking",
                "message": "Proper shipping name evidence is unresolved.",
            }
        ],
        "warnings": [],
    }
    pipeline, _store = make_pipeline(tmp_path, base_extracted(un_number="UN1263"), FakeAgentCore(review=review))

    result = await pipeline.generate_label_from_uploads(
        files=[_upload("test_sds.pdf")],
        product_name="Blocked Product",
        mode="shipped_dot",
        size="pail",
    )

    assert result["status"] == "needs_review"
    assert result["download"]["available"] is True
    assert any(error["field"] == "agentcore.transport.proper_shipping_name" for error in result["errors"])


@pytest.mark.asyncio
async def test_agentcore_failure_continues_with_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(label_pipeline.settings, "agentcore_enabled", True)
    pipeline, _store = make_pipeline(
        tmp_path,
        base_extracted(un_number="UN1263"),
        FakeAgentCore(error=TimeoutError("timed out")),
    )

    result = await pipeline.generate_label_from_uploads(
        files=[_upload("test_sds.pdf")],
        product_name="Timeout Product",
        mode="shipped_dot",
        size="pail",
    )

    assert result["status"] == "ready"
    assert result["agentcore_review"]["status"] == "unavailable"
    assert "timed out" in result["agentcore_review"]["warnings"][0]


class _upload:
    def __init__(self, filename, content=b"%PDF-1.4 test", content_type="application/pdf"):
        self.filename = filename
        self.content = content
        self.content_type = content_type

    async def read(self):
        return self.content
