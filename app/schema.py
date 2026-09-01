"""
Pydantic v2 schemas for strict data validation.
All schemas enforce compliance with SDS/TDS structure and DOT/OSHA requirements.
"""

from datetime import datetime
from typing import List, Optional, Literal
from pydantic import AliasChoices, BaseModel, Field, field_validator, ConfigDict


GHS_PICTOGRAM_OPTIONS = {
    "GHS01": "Exploding Bomb",
    "GHS02": "Flame",
    "GHS03": "Flame Over Circle",
    "GHS04": "Gas Cylinder",
    "GHS05": "Corrosive",
    "GHS06": "Skull and Crossbones",
    "GHS07": "Exclamation Point",
    "GHS08": "Health Hazard",
    "GHS09": "Environment",
}

GHS_PICTOGRAM_ALIASES = {
    "exploding bomb": "GHS01",
    "bomb": "GHS01",
    "flame": "GHS02",
    "flammable": "GHS02",
    "flame over circle": "GHS03",
    "oxidizer": "GHS03",
    "oxidizing": "GHS03",
    "gas cylinder": "GHS04",
    "gas under pressure": "GHS04",
    "gases under pressure": "GHS04",
    "corrosive": "GHS05",
    "corrosion": "GHS05",
    "skull and crossbones": "GHS06",
    "skull": "GHS06",
    "exclamation point": "GHS07",
    "exclamation": "GHS07",
    "irritant": "GHS07",
    "health hazard": "GHS08",
    "environment": "GHS09",
    "environmental": "GHS09",
    "aquatic toxicity": "GHS09",
}


def _normalize_pictogram_key(value: str) -> str:
    return " ".join(value.replace("_", " ").replace("-", " ").split()).lower()


def normalize_ghs_pictogram(value: str) -> str:
    """Map operator/UI words or GHS codes to exact GHS pictogram codes."""
    code = str(value).strip().upper()
    if code in GHS_PICTOGRAM_OPTIONS:
        return code

    normalized = _normalize_pictogram_key(str(value))
    mapped = GHS_PICTOGRAM_ALIASES.get(normalized)
    if mapped:
        return mapped

    for candidate_code, name in GHS_PICTOGRAM_OPTIONS.items():
        if normalized == _normalize_pictogram_key(name):
            return candidate_code

    raise ValueError(f"Invalid GHS pictogram: {value}")


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

    @field_validator("signal_word", mode="before")
    @classmethod
    def normalize_signal_word(cls, v) -> Optional[str]:
        """Normalize extractor output into the exact GHS signal word values."""
        if v is None:
            return None

        value = str(v).strip()
        if not value or value.lower() in {"none", "null", "n/a", "na", "not applicable"}:
            return None

        normalized = value.lower()
        if normalized == "danger":
            return "Danger"
        if normalized == "warning":
            return "Warning"
        return value

    @field_validator("pictograms", mode="before")
    @classmethod
    def validate_pictograms(cls, v) -> List[str]:
        """Normalize UI words and GHS codes into stable, deduped GHS codes."""
        if v is None:
            return []
        if isinstance(v, str):
            values = [
                item.strip()
                for item in v.replace("|", ",").replace(";", ",").split(",")
                if item.strip()
            ]
        else:
            values = list(v)

        deduped = []
        seen = set()
        for raw_code in values:
            code = normalize_ghs_pictogram(raw_code)
            if code not in seen:
                deduped.append(code)
                seen.add(code)
        return deduped


class TransportClassification(BaseModel):
    """DOT/IATA/IMDG transport classification (SDS Section 14)."""
    model_config = ConfigDict(extra="forbid")

    not_regulated: Optional[bool] = Field(
        None,
        description="True when SDS Section 14 explicitly states the product is not regulated for transport"
    )
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
    subsidiary_hazard_classes: List[str] = Field(
        default_factory=list,
        description="Subsidiary hazard classes or risks from SDS Section 14, e.g. 8 or 6.1"
    )
    packing_group: Optional[Literal["I", "II", "III"]] = Field(
        None,
        description="Packing group"
    )
    marine_pollutant: Optional[bool] = Field(
        None,
        description="Marine pollutant status"
    )
    hazardous_substance: Optional[bool] = Field(
        None,
        description="True when SDS/DOT data identifies the material as a hazardous substance or RQ"
    )
    hazardous_waste: Optional[bool] = Field(
        None,
        description="True when SDS/DOT data identifies the material as a hazardous waste"
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

    @field_validator("subsidiary_hazard_classes", mode="before")
    @classmethod
    def normalize_subsidiary_hazard_classes(cls, v) -> List[str]:
        """Normalize scalar/list subsidiary hazard output into a deduped string list."""
        if v is None:
            return []
        if isinstance(v, str):
            values = [
                item.strip()
                for item in v.replace("|", ",").replace(";", ",").split(",")
                if item.strip()
            ]
        else:
            values = list(v)

        normalized = []
        seen = set()
        for item in values:
            clean = " ".join(str(item).strip().split())
            if not clean:
                continue
            lowered = clean.lower()
            if lowered in {"none", "null", "n/a", "na", "not applicable", "void", "not listed"}:
                continue
            if lowered.startswith("class "):
                clean = clean[6:].strip()
            if clean not in seen:
                normalized.append(clean)
                seen.add(clean)
        return normalized


class NFPA704Ratings(BaseModel):
    """NFPA 704 fire diamond ratings."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    health: int = Field(
        0,
        ge=0,
        le=4,
        description="Blue/left health hazard rating, 0=minimal through 4=severe"
    )
    flammability: int = Field(
        0,
        ge=0,
        le=4,
        description="Red/top flammability hazard rating, 0=minimal through 4=severe"
    )
    instability: int = Field(
        0,
        ge=0,
        le=4,
        validation_alias=AliasChoices("instability", "reactivity"),
        description="Yellow/right instability or reactivity rating, 0=minimal through 4=severe"
    )
    special: Optional[str] = Field(
        None,
        max_length=12,
        description="White/bottom special hazard code such as OX or W, if explicitly stated"
    )
    source: Literal["sds", "hmis", "operator", "clearedge_default"] = Field(
        "clearedge_default",
        description="Provenance for the NFPA values; defaults are not source-derived ratings",
    )

    @field_validator("special")
    @classmethod
    def normalize_special(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = " ".join(v.split()).upper()
        return normalized or None


class ProductInfo(BaseModel):
    """Core product identification and supplier information."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, description="Product name")
    product_uses: List[str] = Field(
        default_factory=list,
        description="Short source-backed product uses/applications from SDS/TDS, preferably TDS"
    )
    supplier_name: Optional[str] = Field(None, description="Manufacturer/supplier name")
    supplier_address: Optional[str] = Field(None, description="Supplier address")
    supplier_phone: Optional[str] = Field(None, description="Supplier phone number")
    emergency_phone: Optional[str] = Field(None, description="24-hour emergency phone")
    revision_date: Optional[str] = Field(
        None,
        description="SDS revision date (ISO format preferred)"
    )

    @field_validator("product_uses", mode="before")
    @classmethod
    def normalize_product_uses(cls, value) -> List[str]:
        """Keep product-use text compact enough for a label."""
        if value is None:
            return []
        if isinstance(value, str):
            raw_values = [
                item.strip()
                for item in value.replace("|", ";").replace(",", ";").split(";")
                if item.strip()
            ]
        else:
            raw_values = list(value)

        normalized = []
        seen = set()
        for raw_value in raw_values:
            clean = " ".join(str(raw_value or "").strip(" .;-").split())
            if not clean:
                continue
            clean = clean[0].upper() + clean[1:] if clean[:1].islower() else clean
            if len(clean) > 68:
                clipped = clean[:65].rsplit(" ", 1)[0].rstrip(" ,.;")
                clean = f"{clipped}..."
            key = clean.lower()
            if key in seen:
                continue
            normalized.append(clean)
            seen.add(key)
            if len(normalized) >= 3:
                break
        return normalized


class ShipmentInfo(BaseModel):
    """Operator-provided shipment and batch fields."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    lot_number: Optional[str] = Field(None, description="Batch or lot number for this shipment")
    expiration_date: Optional[str] = Field(None, description="Expiration date for this shipment")
    fill_amount: Optional[str] = Field(None, description="Net contents or fill amount for this container")
    manufacture_date: Optional[str] = Field(None, description="Manufacture date for this shipment")
    container_type: Optional[Literal["pail", "drum", "tote"]] = Field(
        None,
        description="Container inferred from net weight when possible"
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
    nfpa: NFPA704Ratings = Field(default_factory=NFPA704Ratings)
    shipment: ShipmentInfo = Field(default_factory=ShipmentInfo)
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


class DetectedGHSPictogram(BaseModel):
    """GHS pictogram detected from embedded SDS artwork."""
    model_config = ConfigDict(extra="forbid")

    code: str
    page: int = Field(..., ge=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return normalize_ghs_pictogram(value)


class ExtractedText(BaseModel):
    """Complete extracted text from PDF document."""
    model_config = ConfigDict(extra="forbid")

    doc: Literal["SDS", "TDS"]
    method_used: Literal["text", "ocr", "mixed"]
    pages: List[ExtractedTextPage]
    detected_ghs_pictograms: List[DetectedGHSPictogram] = Field(default_factory=list)


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
    ai_model: str
    sds_source_id: Optional[str] = Field(None, description="Source file ID")
    sds_sha256: Optional[str] = Field(None, description="SHA-256 hash")
    tds_source_id: Optional[str] = Field(None, description="Source file ID")
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
    storage_path: str
    latest_extraction_date: Optional[str] = None
    latest_label_date: Optional[str] = None
    sds_files: List[dict] = Field(default_factory=list)  # [{id, name, sha256, uploaded}]
    tds_files: List[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
