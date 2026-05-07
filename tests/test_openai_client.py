import json

from app.openai_client import OpenAIClient


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
