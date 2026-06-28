import json

from app.openai_client import OpenAIClient
from app.canva_export import build_canva_export


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
        "product": {"name": "ClearEdge Normalized"},
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
    assert extracted.ghs.pictograms == ["GHS02"]
    assert extracted.ghs.hazard_statements[0].code == "H225"
    assert extracted.ghs.precautionary_statements[0].text == "Keep away from heat."
    assert extracted.ghs.supplemental_statements == ["For industrial use only."]
    assert extracted.transport.packing_group == "II"
    assert extracted.transport.limited_quantity == "No"
    assert extracted.transport.special_provisions == "IB2 | T4"


def test_canva_export_formats_scalar_special_provisions():
    exported = build_canva_export(
        {
            "product": {"name": "ClearEdge Canva"},
            "ghs": {},
            "transport": {"special_provisions": "IB2 | T4"},
            "nfpa": {},
            "shipment": {},
        },
        {"product_name": "ClearEdge Canva", "mode": "shipped_dot", "size": "drum"},
    )

    assert exported["special_provisions"] == "IB2 | T4"
