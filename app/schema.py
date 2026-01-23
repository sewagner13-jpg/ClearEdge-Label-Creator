"""
Pydantic v2 schemas for strict data validation.
All schemas enforce compliance with SDS/TDS structure and DOT/OSHA requirements.
"""

from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class HazardStatement(BaseModel):
    """GHS hazard statement with optional H-code."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: Optional[str] = Field(None, description="H-code (e.g., H225, H315)")
    text: str = Field(..., min_length=1, description="Full hazard statement text")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == "":
            return None
        return v


class PrecautionaryStatement(BaseModel):
    """GHS precautionary statement with optional P-code."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: Optional[str] = Field(None, description="P-code (e.g., P210, P280)")
    text: str = Field(..., min_length=1, description="Full precautionary statement text")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == "":
            return None
        return v


class GHSClassification(BaseModel):
    """GHS hazard classification and communication elements."""
    model_config = ConfigDict(extra="forbid")

    signal_word: Optional[Literal["Danger", "Warning"]] = Field(
        None,
        description="GHS signal word"
    )
    pictograms: List[str] = Field(
        default_factory=list,
        description="GHS pictogram codes (GHS01-GHS09)"
    )
    hazard_statements: List[HazardStatement] = Field(default_factory=list)
    precautionary_statements: List[PrecautionaryStatement] = Field(default_factory=list)
    supplemental_statements: Optional[List[str]] = Field(
        None,
        description="Additional non-GHS hazard information"
    )

    @field_validator("pictograms")
    @classmethod
    def validate_pictograms(cls, v: List[str]) -> List[str]:
        """Ensure pictogram codes are valid GHS codes."""
        valid_codes = {f"GHS{i:02d}" for i in range(1, 10)}
        for code in v:
            if code not in valid_codes:
                raise ValueError(f"Invalid GHS pictogram code: {code}")
        return list(set(v))  # Remove duplicates


class TransportClassification(BaseModel):
    """DOT/IATA/IMDG transport classification (SDS Section 14)."""
    model_config = ConfigDict(extra="forbid")

    un_number: Optional[str] = Field(
        None,
        description="UN identification number (e.g., UN1090)"
    )
    proper_shipping_name: Optional[str] = Field(
        None,
        description="DOT proper shipping name"
    )
    hazard_class: Optional[str] = Field(
        None,
        description="Primary hazard class (e.g., 3, 6.1, 8)"
    )
    packing_group: Optional[Literal["I", "II", "III"]] = Field(
        None,
        description="Packing group"
    )
    marine_pollutant: Optional[bool] = Field(
        None,
        description="Marine pollutant status"
    )
    limited_quantity: Optional[str] = Field(
        None,
        description="Limited quantity threshold"
    )
    special_provisions: Optional[str] = Field(
        None,
        description="Special provisions codes"
    )
    erg_guide_number: Optional[str] = Field(
        None,
        description="Emergency Response Guidebook number"
    )


class ProductInfo(BaseModel):
    """Core product identification and supplier information."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, description="Product name")
    supplier_name: Optional[str] = Field(None, description="Manufacturer/supplier name")
    supplier_address: Optional[str] = Field(None, description="Supplier address")
    supplier_phone: Optional[str] = Field(None, description="Supplier phone number")
    emergency_phone: Optional[str] = Field(None, description="24-hour emergency phone")
    revision_date: Optional[str] = Field(
        None,
        description="SDS revision date (ISO format preferred)"
    )


class Evidence(BaseModel):
    """Source evidence for extracted field with provenance."""
    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(
        ...,
        description="JSON path to the field (e.g., 'product.name', 'ghs.signal_word')"
    )
    doc: Literal["SDS", "TDS"] = Field(..., description="Source document type")
    section: Optional[str] = Field(None, description="Section name or number")
    page: Optional[int] = Field(None, ge=1, description="Page number")
    quote: str = Field(
        ...,
        max_length=240,
        description="Verbatim quote from source document"
    )


class FieldConfidence(BaseModel):
    """Confidence scores for extracted fields."""
    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(..., description="JSON path to field")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")


class ExtractedData(BaseModel):
    """Complete extracted data from SDS/TDS with evidence and confidence."""
    model_config = ConfigDict(extra="forbid")

    product: ProductInfo
    ghs: GHSClassification
    transport: TransportClassification
    evidence: List[Evidence] = Field(default_factory=list)
    confidence: List[FieldConfidence] = Field(default_factory=list)
    warnings: List[str] = Field(
        default_factory=list,
        description="Extraction warnings (missing data, ambiguities)"
    )


class ExtractedTextPage(BaseModel):
    """Extracted text for a single page."""
    model_config = ConfigDict(extra="forbid")

    page: int = Field(..., ge=1)
    text: str


class ExtractedText(BaseModel):
    """Complete extracted text from PDF document."""
    model_config = ConfigDict(extra="forbid")

    doc: Literal["SDS", "TDS"]
    method_used: Literal["text", "ocr", "mixed"]
    pages: List[ExtractedTextPage]


class ValidationError(BaseModel):
    """Compliance validation error."""
    model_config = ConfigDict(extra="forbid")

    field: str
    message: str
    severity: Literal["error", "warning"]


class ValidationResult(BaseModel):
    """Complete validation result for compliance check."""
    model_config = ConfigDict(extra="forbid")

    mode: Literal["workplace", "shipped_dot"]
    passed: bool
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExtractionMeta(BaseModel):
    """Metadata for extraction run with audit trail."""
    model_config = ConfigDict(extra="forbid")

    product_name: str
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    gemini_model: str
    sds_file_id: Optional[str] = Field(None, description="Drive file ID")
    sds_sha256: Optional[str] = Field(None, description="SHA-256 hash")
    tds_file_id: Optional[str] = Field(None, description="Drive file ID")
    tds_sha256: Optional[str] = Field(None, description="SHA-256 hash")
    source_urls: Optional[List[str]] = Field(None, description="URLs if web-retrieved")
    extraction_duration_seconds: Optional[float] = None


class LabelBuildReport(BaseModel):
    """Audit report for label generation."""
    model_config = ConfigDict(extra="forbid")

    product_name: str
    mode: Literal["workplace", "shipped_dot"]
    generated_timestamp: datetime = Field(default_factory=datetime.utcnow)
    template_used: str
    svg_file_id: Optional[str] = None
    pdf_file_id: Optional[str] = None
    validation_passed: bool
    approver_name: Optional[str] = Field(None, description="Name of person who approved")
    approval_date: Optional[str] = Field(None, description="Date of approval")
    notes: Optional[str] = None


class ProductManifest(BaseModel):
    """Single source of truth for a product (product.json)."""
    model_config = ConfigDict(extra="forbid")

    product_name: str
    drive_folder_id: str
    latest_extraction_date: Optional[str] = None
    latest_label_date: Optional[str] = None
    sds_files: List[dict] = Field(default_factory=list)  # [{id, name, sha256, uploaded}]
    tds_files: List[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
