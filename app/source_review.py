"""Structured second-pass review models for source-backed label extraction."""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


ReviewValue = Optional[Union[str, bool, int, float, List[str]]]


class SourceFieldReview(BaseModel):
    """OpenAI recommendation for one extracted field."""

    model_config = ConfigDict(extra="forbid")

    field_path: str
    recommended_value: ReviewValue = None
    status: Literal["found", "missing", "conflict", "needs_review", "source_backed"]
    confidence: float = Field(ge=0.0, le=1.0)
    source_document: Optional[Literal["SDS", "TDS"]] = None
    page: Optional[int] = None
    evidence: Optional[str] = None
    reason: Optional[str] = None


class SourceInclusionDecision(BaseModel):
    """Decision about whether a reviewed label element should print."""

    model_config = ConfigDict(extra="forbid")

    field_path: str
    decision: Literal["print", "do_not_print", "needs_review"]
    reason: Optional[str] = None


class SourceCriticalIssue(BaseModel):
    """Source-review issue requiring operator attention."""

    model_config = ConfigDict(extra="forbid")

    field_path: Optional[str] = None
    severity: Literal["blocking", "needs_review", "warning"]
    message: str
    evidence: Optional[str] = None


class OpenAISourceReview(BaseModel):
    """Strict OpenAI Responses API output for a label source review."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["reviewed"] = "reviewed"
    field_reviews: List[SourceFieldReview] = Field(default_factory=list)
    label_inclusion_decisions: List[SourceInclusionDecision] = Field(default_factory=list)
    critical_issues: List[SourceCriticalIssue] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def disabled_source_review() -> dict:
    """Return a stable payload when the optional second pass is disabled."""
    return _base_review_payload(
        status="disabled",
        warnings=["OpenAI source review is disabled; primary OpenAI extraction and local validation were used."],
    )


def unavailable_source_review(message: str) -> dict:
    """Return a stable payload when the second pass cannot complete."""
    return _base_review_payload(status="unavailable", warnings=[message])


def reviewed_source_payload(review: OpenAISourceReview, response_id: Optional[str]) -> dict:
    """Add provider metadata and the legacy trace alias to a parsed review."""
    return {
        **review.model_dump(mode="json"),
        "provider": "openai",
        "review_type": "source_review",
        "openai_response_id": response_id,
        "agentcore_trace_id": response_id,
    }


def _base_review_payload(*, status: str, warnings: list[str]) -> dict:
    return {
        "status": status,
        "provider": "openai",
        "review_type": "source_review",
        "field_reviews": [],
        "label_inclusion_decisions": [],
        "critical_issues": [],
        "warnings": warnings,
        "openai_response_id": None,
        "agentcore_trace_id": None,
    }
