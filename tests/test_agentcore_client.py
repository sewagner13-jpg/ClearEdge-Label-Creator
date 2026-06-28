import pytest

from app.agentcore_client import AgentCoreClient


def test_agentcore_review_parser_accepts_strict_json():
    review = AgentCoreClient._parse_review_payload(
        """
        {
          "status": "reviewed",
          "field_reviews": [
            {
              "field_path": "transport.un_number",
              "recommended_value": "UN1993",
              "status": "found",
              "confidence": 0.91,
              "source_document": "SDS",
              "page": 6,
              "evidence": "UN1993"
            }
          ],
          "label_inclusion_decisions": [
            {"field_path": "transport.un_number", "decision": "print"}
          ],
          "critical_issues": [],
          "agentcore_trace_id": "trace-123"
        }
        """
    )

    assert review.status == "reviewed"
    assert review.agentcore_trace_id == "trace-123"
    assert review.field_reviews[0].recommended_value == "UN1993"


def test_agentcore_review_parser_rejects_invalid_json():
    with pytest.raises(ValueError, match="AGENTCORE_INVALID_JSON"):
        AgentCoreClient._parse_review_payload("{not json")
