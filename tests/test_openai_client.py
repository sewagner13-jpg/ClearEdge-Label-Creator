import json
from types import SimpleNamespace

from app.openai_client import OpenAIClient
from app.canva_export import build_canva_export, canva_template_manifest
from app.schema import ExtractedText, ExtractedTextPage
from app.source_review import OpenAISourceReview


def test_parse_response_defaults_missing_nfpa_values_to_zero():
    client = OpenAIClient.__new__(OpenAIClient)
    response = {
        "product": {"name": "ClearEdge Default NFPA"},
        "ghs": {},
        "transport": {},
        "evidence": [],
        "confidence": [],
        "warnings": [],
    }

    extracted = client._parse_response(json.dumps(response), "ClearEdge Default NFPA")

    assert extracted.nfpa.health == 0
    assert extracted.nfpa.flammability == 0
    assert extracted.nfpa.instability == 0
    assert any("defaulted missing values to 0" in warning for warning in extracted.warnings)


def test_parse_response_accepts_explicit_nfpa_values():
    client = OpenAIClient.__new__(OpenAIClient)
    response = {
        "product": {"name": "ClearEdge Rated NFPA"},
        "ghs": {},
        "transport": {},
        "nfpa": {
            "health": 2,
            "flammability": 3,
            "reactivity": 1,
            "special": "ox",
        },
        "evidence": [],
        "confidence": [],
        "warnings": [],
    }

    extracted = client._parse_response(json.dumps(response), "ClearEdge Rated NFPA")

    assert extracted.nfpa.health == 2
    assert extracted.nfpa.flammability == 3
    assert extracted.nfpa.instability == 1
    assert extracted.nfpa.special == "OX"


def test_parse_response_normalizes_common_ai_shape_drift():
    client = OpenAIClient.__new__(OpenAIClient)
    response = {
        "product": {
            "name": "ClearEdge Normalized",
            "product_uses": "Waterproofing membranes; adhesive modifier; sealant additive",
        },
        "ghs": {
            "signal_word": "DANGER",
            "pictograms": ["flame"],
            "hazard_statements": ["H225: Highly flammable liquid and vapor."],
            "precautionary_statements": ["Keep away from heat."],
            "supplemental_statements": "For industrial use only.",
        },
        "transport": {
            "packing_group": "PG II",
            "limited_quantity": False,
            "special_provisions": ["IB2", "T4"],
        },
        "evidence": [],
        "confidence": [],
        "warnings": [],
    }

    extracted = client._parse_response(json.dumps(response), "ClearEdge Normalized")

    assert extracted.ghs.signal_word == "Danger"
    assert extracted.product.product_uses == [
        "Waterproofing membranes",
        "Adhesive modifier",
        "Sealant additive",
    ]
    assert extracted.ghs.pictograms == ["GHS02"]
    assert extracted.ghs.hazard_statements[0].code == "H225"
    assert extracted.ghs.precautionary_statements[0].text == "Keep away from heat."
    assert extracted.ghs.supplemental_statements == ["For industrial use only."]
    assert extracted.transport.packing_group == "II"
    assert extracted.transport.limited_quantity == "No"
    assert extracted.transport.special_provisions == "IB2 | T4"


def test_parse_response_clips_overlong_evidence_quotes():
    client = OpenAIClient.__new__(OpenAIClient)
    response = {
        "product": {"name": "ClearEdge Evidence Clip"},
        "ghs": {},
        "transport": {},
        "evidence": [
            {
                "field_path": "ghs.precautionary_statements",
                "doc": "SDS",
                "section": "2",
                "page": 2,
                "quote": "Prevention: " + ("Wear protective gloves. " * 30),
            }
        ],
        "confidence": [],
        "warnings": [],
    }

    extracted = client._parse_response(json.dumps(response), "ClearEdge Evidence Clip")

    assert len(extracted.evidence[0].quote) == 240


def test_openai_client_runs_responses_api_second_pass_with_strict_schema():
    class FakeResponses:
        def __init__(self):
            self.kwargs = None

        def parse(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                id="resp_review_123",
                output_parsed=OpenAISourceReview(),
            )

    responses = FakeResponses()
    client = OpenAIClient.__new__(OpenAIClient)
    client.client = SimpleNamespace(responses=responses)
    client.review_model_name = "gpt-test-review"
    sds_text = ExtractedText(
        doc="SDS",
        method_used="text",
        pages=[ExtractedTextPage(page=2, text="Signal word: Warning")],
    )

    review = client.review_label_data(
        sds_text=sds_text,
        tds_text=None,
        openai_extracted={"ghs": {"signal_word": "Warning"}},
        deterministic_extracted={"ghs": {"signal_word": "Warning"}},
        product_name="Reviewed Product",
        label_mode="workplace",
        shipment={},
    )

    assert responses.kwargs["model"] == "gpt-test-review"
    assert responses.kwargs["text_format"] is OpenAISourceReview
    assert responses.kwargs["store"] is False
    request_payload = json.loads(responses.kwargs["input"][1]["content"])
    assert request_payload["documents"]["sds"] == [
        {"page": 2, "text": "Signal word: Warning"}
    ]
    assert request_payload["primary_openai_extraction"]["ghs"]["signal_word"] == "Warning"
    assert review["provider"] == "openai"
    assert review["openai_response_id"] == "resp_review_123"


def test_canva_export_formats_scalar_special_provisions():
    exported = build_canva_export(
        {
            "product": {
                "name": "ClearEdge Canva",
                "product_uses": ["Waterproofing membranes", "Adhesive modifier", "Sealant additive"],
            },
            "ghs": {},
            "transport": {"special_provisions": "IB2 | T4"},
            "nfpa": {},
            "shipment": {},
        },
        {"product_name": "ClearEdge Canva", "mode": "shipped_dot", "size": "drum"},
    )

    assert exported["special_provisions"] == "IB2 | T4"


def test_canva_export_includes_template_ready_display_fields():
    exported = build_canva_export(
        {
            "product": {
                "name": "ClearEdge Canva",
                "product_uses": ["Waterproofing membranes", "Adhesive modifier", "Sealant additive"],
            },
            "ghs": {
                "signal_word": "Warning",
                "pictograms": ["GHS05", "GHS07"],
            },
            "transport": {
                "un_number": "UN1760",
                "proper_shipping_name": "Corrosive liquid, n.o.s.",
                "hazard_class": "8",
                "packing_group": "III",
            },
            "nfpa": {"health": 2, "flammability": 1, "instability": 0},
            "shipment": {
                "lot_number": "LOT-100",
                "expiration_date": "2027-05-07",
                "fill_amount": "441 lb",
                "manufacture_date": "2026-05-07",
            },
        },
        {
            "label_id": "label_ClearEdgeCanva_abc123",
            "product_name": "ClearEdge Canva",
            "mode": "shipped_dot",
            "size": "drum",
            "status": "ready",
        },
    )

    assert exported["label_id"] == "label_ClearEdgeCanva_abc123"
    assert exported["product_name_display"] == "ClearEdge Canva"
    assert exported["product_uses"] == "Waterproofing membranes | Adhesive modifier | Sealant additive"
    assert exported["product_uses_display"] == "Waterproofing membranes | Adhesive modifier"
    assert exported["lot_number_display"] == "LOT-100"
    assert exported["expiration_date_display"] == "2027-05-07"
    assert exported["fill_amount_display"] == "441 lb"
    assert exported["manufacture_date"] == "2026-05-07"
    assert exported["signal_word_display"] == "WARNING"
    assert exported["ghs_pictogram_1_code"] == "GHS05"
    assert exported["ghs_pictogram_1_name"] == "Corrosive"
    assert exported["ghs_pictogram_2_code"] == "GHS07"
    assert exported["ghs_pictogram_2_name"] == "Exclamation Point"
    assert exported["transport_summary"] == "UN1760 | Corrosive liquid, n.o.s. | Class 8 | PG III"
    assert exported["nfpa_704_summary"] == "Health 2 | Flammability 1 | Instability 0"


def test_canva_template_manifest_has_required_bulk_create_fields():
    manifest = canva_template_manifest()
    field_names = {field["name"] for field in manifest["fields"]}

    assert manifest["template_name"] == "ClearEdge Product Label Template"
    assert "product_name" in field_names
    assert "lot_number_display" in field_names
    assert "ghs_pictogram_1_code" in field_names
    assert "nfpa_704_summary" in field_names
