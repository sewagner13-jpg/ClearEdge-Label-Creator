"""Request and response models for the public label API."""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class LabelMode(str, Enum):
    """Label mode options."""

    SHIPPED_DOT = "shipped_dot"
    WORKPLACE = "workplace"


class LabelSize(str, Enum):
    """Label size options."""

    PAIL = "pail"
    DRUM = "drum"
    TOTE = "tote"


class LabelOrientation(str, Enum):
    """Printed label orientation options."""

    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


class ValidationSummary(BaseModel):
    """Validation summary payload."""

    passed: bool
    warnings: List[dict]
    errors: List[dict]


class LabelPayload(BaseModel):
    """Label artifact payload."""

    mode: str
    size: str
    orientation: str = "vertical"
    container_type: Optional[str] = None
    preview_url: Optional[str] = None
    download_url: Optional[str] = None
    download_data_url: Optional[str] = None
    dot_sticker_pdf_url: Optional[str] = None
    canva_csv_url: Optional[str] = None
    canva_json_url: Optional[str] = None


class PreviewPayload(BaseModel):
    """Inline label preview availability payload."""

    available: bool
    url: Optional[str] = None
    media_type: Optional[str] = None
    inline_svg: Optional[str] = None
    pages: Optional[List[dict]] = None
    page_count: Optional[int] = None


class DownloadPayload(BaseModel):
    """Explicit download availability payload."""

    available: bool
    url: Optional[str] = None
    reason: Optional[str] = None
    data_url: Optional[str] = None
    page_count: Optional[int] = None


class AuditPayload(BaseModel):
    """Audit metadata payload."""

    created_at: str
    phase: str


class OverrideApprovalRequest(BaseModel):
    """Manual override request for compliance-blocked exports."""

    approver: str = Field(..., min_length=2, max_length=100)
    reason: str = Field(..., min_length=10, max_length=500)


class CorrectionRequest(BaseModel):
    """Manual field correction request."""

    updated_by: str = Field(..., min_length=2, max_length=100)
    reason: str = Field(..., min_length=10, max_length=500)
    fields: Dict[str, object] = Field(..., min_length=1)


class GenerateLabelResponse(BaseModel):
    """Unified label generation response."""

    label_id: str
    status: str
    extracted: dict
    validation: ValidationSummary
    label: LabelPayload
    preview: Optional[PreviewPayload] = None
    download: Optional[DownloadPayload] = None
    dot_shipping_review: Optional[dict] = None
    dot_stickers: Optional[dict] = None
    agentcore_review: Optional[dict] = None
    branding: Optional[dict] = None
    warnings: List[dict]
    errors: List[dict]
    audit: AuditPayload
    success: bool
