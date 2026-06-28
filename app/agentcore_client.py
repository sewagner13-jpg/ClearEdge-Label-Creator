"""Amazon Bedrock AgentCore client for second-pass label extraction review."""

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import settings
from .schema import GHS_PICTOGRAM_OPTIONS
from .validator import ComplianceValidator

logger = logging.getLogger(__name__)


class AgentCoreFieldReview(BaseModel):
    """AgentCore recommendation for one extracted field."""

    model_config = ConfigDict(extra="ignore")

    field_path: str
    recommended_value: Any = None
    status: str = "needs_review"
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    source_document: Optional[str] = None
    page: Optional[int] = None
    evidence: Optional[str] = None
    reason: Optional[str] = None


class AgentCoreInclusionDecision(BaseModel):
    """AgentCore decision about whether a label element should print."""

    model_config = ConfigDict(extra="ignore")

    field_path: str
    decision: str
    reason: Optional[str] = None


class AgentCoreCriticalIssue(BaseModel):
    """AgentCore issue that may require review or block download."""

    model_config = ConfigDict(extra="ignore")

    field_path: Optional[str] = None
    severity: str = "needs_review"
    message: str
    evidence: Optional[str] = None


class AgentCoreReview(BaseModel):
    """Strict normalized AgentCore review output."""

    model_config = ConfigDict(extra="ignore")

    status: str = "reviewed"
    field_reviews: List[AgentCoreFieldReview] = Field(default_factory=list)
    label_inclusion_decisions: List[AgentCoreInclusionDecision] = Field(default_factory=list)
    critical_issues: List[AgentCoreCriticalIssue] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    agentcore_trace_id: Optional[str] = None


def disabled_agentcore_review() -> dict:
    """Return the standard review payload when AgentCore is disabled."""
    return {
        "status": "disabled",
        "field_reviews": [],
        "label_inclusion_decisions": [],
        "critical_issues": [],
        "warnings": ["AgentCore review is disabled; OpenAI extraction and local validation were used."],
        "agentcore_trace_id": None,
    }


def unavailable_agentcore_review(message: str) -> dict:
    """Return the standard review payload when AgentCore cannot complete."""
    return {
        "status": "unavailable",
        "field_reviews": [],
        "label_inclusion_decisions": [],
        "critical_issues": [],
        "warnings": [message],
        "agentcore_trace_id": None,
    }


class AgentCoreClient:
    """Invoke an Amazon Bedrock AgentCore Runtime for label review."""

    REVIEW_PROMPT = (
        "Review the uploaded SDS/TDS extracted text and OpenAI extraction for a chemical label. "
        "Return only strict JSON matching the requested schema. Do not invent values. "
        "Every recommended value must include source evidence when available."
    )

    def __init__(self):
        if not settings.agentcore_runtime_arn:
            raise ValueError("AGENTCORE_RUNTIME_ARN is required when AgentCore is enabled")

        try:
            import boto3
            from botocore.config import Config
        except Exception as exc:
            raise RuntimeError("boto3 is required for AgentCore integration") from exc

        self.runtime_arn = settings.agentcore_runtime_arn
        self.qualifier = settings.agentcore_qualifier
        self.client = boto3.client(
            "bedrock-agentcore",
            region_name=settings.agentcore_region,
            config=Config(
                read_timeout=settings.agentcore_timeout_seconds,
                connect_timeout=10,
                retries={"max_attempts": 1},
            ),
        )

    def review_label_data(
        self,
        *,
        sds_text,
        tds_text,
        openai_extracted: dict,
        product_name: str,
        label_mode: str,
        shipment: dict,
    ) -> dict:
        """Ask AgentCore to review what should appear on the label."""
        payload = self._build_payload(
            sds_text=sds_text,
            tds_text=tds_text,
            openai_extracted=openai_extracted,
            product_name=product_name,
            label_mode=label_mode,
            shipment=shipment,
        )

        request = {
            "agentRuntimeArn": self.runtime_arn,
            "payload": json.dumps(payload).encode("utf-8"),
        }
        if self.qualifier:
            request["qualifier"] = self.qualifier

        response = self.client.invoke_agent_runtime(**request)
        raw_payload = self._read_response_payload(response.get("response") or response.get("payload"))
        review = self._parse_review_payload(raw_payload)

        if not review.agentcore_trace_id:
            review.agentcore_trace_id = (
                response.get("traceId")
                or response.get("requestId")
                or response.get("ResponseMetadata", {}).get("RequestId")
            )

        return review.model_dump(mode="json")

    def _build_payload(
        self,
        *,
        sds_text,
        tds_text,
        openai_extracted: dict,
        product_name: str,
        label_mode: str,
        shipment: dict,
    ) -> dict:
        """Build the AgentCore runtime payload."""
        return {
            "task": self.REVIEW_PROMPT,
            "expected_response_schema": {
                "field_reviews": [
                    {
                        "field_path": "string",
                        "recommended_value": "any|null",
                        "status": "found|missing|conflict|needs_review|agentcore_source_backed",
                        "confidence": "number 0-1",
                        "source_document": "SDS|TDS|null",
                        "page": "number|null",
                        "evidence": "short quote|null",
                        "reason": "string|null",
                    }
                ],
                "label_inclusion_decisions": [
                    {"field_path": "string", "decision": "print|do_not_print|needs_review", "reason": "string|null"}
                ],
                "critical_issues": [
                    {"field_path": "string|null", "severity": "blocking|needs_review|warning", "message": "string"}
                ],
                "agentcore_trace_id": "string|null",
            },
            "context": {
                "product_name": product_name,
                "label_mode": label_mode,
                "shipment": shipment,
                "approved_ghs_pictogram_map": GHS_PICTOGRAM_OPTIONS,
                "supported_dot_label_classes": sorted(ComplianceValidator.SUPPORTED_DOT_LABEL_CLASSES),
                "validation_rules_summary": [
                    "Do not invent SDS/TDS values.",
                    "Use missing when source evidence is absent.",
                    "Regulated shipped DOT labels require ID number, proper shipping name, hazard class, and supported DOT label asset.",
                    "N.O.S. proper shipping names require technical name detail in parentheses.",
                    "Explicit not-regulated transport statements should not force DOT fields.",
                ],
            },
            "documents": {
                "sds": self._document_pages(sds_text),
                "tds": self._document_pages(tds_text),
            },
            "openai_extracted": openai_extracted,
        }

    @staticmethod
    def _document_pages(extracted_text) -> list[dict]:
        """Convert ExtractedText into compact page dictionaries."""
        if not extracted_text:
            return []
        return [
            {"page": page.page, "text": page.text}
            for page in getattr(extracted_text, "pages", [])
        ]

    @staticmethod
    def _read_response_payload(payload) -> str:
        """Read runtime payload from common boto3 streaming response forms."""
        if payload is None:
            return ""
        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        if isinstance(payload, str):
            return payload
        if hasattr(payload, "read"):
            data = payload.read()
            return data.decode("utf-8") if isinstance(data, bytes) else str(data)
        return json.dumps(payload)

    @staticmethod
    def _parse_review_payload(raw_payload: str) -> AgentCoreReview:
        """Parse strict AgentCore JSON into the normalized review model."""
        try:
            parsed = json.loads(raw_payload or "{}")
            if "output" in parsed and isinstance(parsed["output"], str):
                parsed = json.loads(parsed["output"])
            return AgentCoreReview(**parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("AgentCore returned invalid review JSON: %s", exc)
            raise ValueError("AGENTCORE_INVALID_JSON") from exc
