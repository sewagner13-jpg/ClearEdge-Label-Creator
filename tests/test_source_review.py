import pytest
from pydantic import ValidationError

from app.source_review import OpenAISourceReview, reviewed_source_payload


def test_source_review_accepts_strict_source_backed_field():
    review = OpenAISourceReview(
        field_reviews=[
            {
                "field_path": "transport.un_number",
                "recommended_value": "UN1993",
                "status": "found",
                "confidence": 0.91,
                "source_document": "SDS",
                "page": 6,
                "evidence": "UN1993",
            }
        ],
        label_inclusion_decisions=[
            {"field_path": "transport.un_number", "decision": "print"}
        ],
    )

    payload = reviewed_source_payload(review, "resp_123")

    assert payload["provider"] == "openai"
    assert payload["openai_response_id"] == "resp_123"
    assert payload["agentcore_trace_id"] == "resp_123"
    assert payload["field_reviews"][0]["recommended_value"] == "UN1993"


def test_source_review_rejects_unknown_status():
    with pytest.raises(ValidationError):
        OpenAISourceReview(
            field_reviews=[
                {
                    "field_path": "transport.un_number",
                    "recommended_value": "UN1993",
                    "status": "guessed",
                    "confidence": 0.91,
                    "source_document": "SDS",
                }
            ]
        )
