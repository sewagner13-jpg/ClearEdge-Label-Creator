import pytest

from app import label_pipeline
from app.label_pipeline import LabelPipeline
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
        return b"%PDF-1.4 fake"


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
    assert result["download"]["available"] is False
    assert any(error["field"] == "agentcore.transport.un_number" for error in result["errors"])


@pytest.mark.asyncio
async def test_agentcore_blocking_issue_blocks_download(tmp_path, monkeypatch):
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

    assert result["status"] == "blocked"
    assert result["download"]["available"] is False
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
