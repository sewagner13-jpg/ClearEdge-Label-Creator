"""Label generation pipeline orchestration."""

import base64
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile

from .agentcore_client import disabled_agentcore_review, unavailable_agentcore_review
from .api_models import CorrectionRequest
from .canva_export import (
    build_canva_export,
    canva_urls,
    clean_operator_field,
    parse_ghs_pictogram_selection,
)
from .config import settings
from .dot_shipping import build_dot_shipping_review
from .dot_sticker_sheet import (
    DOT_STICKER_SIZE_MM,
    DotStickerSheetRenderer,
    DotStickerSheetUnavailable,
)
from .rule_based_extractor import RuleBasedExtractor
from .schema import Evidence, ExtractedData, FieldConfidence, ValidationError, ValidationResult

logger = logging.getLogger(__name__)


MAX_PDFS_PER_REQUEST = 4
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_LOGO_FILE_SIZE_BYTES = 2 * 1024 * 1024
AGENTCORE_PROMOTION_CONFIDENCE = 0.85
KG_TO_LB = 2.2046226218

ALLOWED_PDF_CONTENT_TYPES = {
    "application/pdf",
    "application/octet-stream",
    "",
    None,
}

ALLOWED_LOGO_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/svg+xml": "svg",
    "image/webp": "webp",
}
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "svg", "webp"}

OFFICIAL_CLEAREDGE_SUPPLIER = {
    "supplier_name": "ClearEdge Solutions",
    "supplier_address": "14301 CR Koon Highway, Newberry, SC 29108",
    "supplier_phone": "704-799-5769",
}

CRITICAL_AGENTCORE_FIELDS = {
    "product.supplier_name",
    "product.emergency_phone",
    "ghs.signal_word",
    "ghs.pictograms",
    "ghs.hazard_statements",
    "ghs.precautionary_statements",
    "transport.un_number",
    "transport.proper_shipping_name",
    "transport.hazard_class",
    "transport.packing_group",
    "transport.marine_pollutant",
    "transport.limited_quantity",
    "nfpa.health",
    "nfpa.flammability",
    "nfpa.instability",
    "nfpa.special",
}

PROMOTABLE_AGENTCORE_FIELDS = {
    "product.supplier_name",
    "product.emergency_phone",
    "ghs.signal_word",
    "ghs.pictograms",
    "transport.un_number",
    "transport.proper_shipping_name",
    "transport.hazard_class",
    "transport.packing_group",
    "transport.marine_pollutant",
    "transport.limited_quantity",
    "nfpa.health",
    "nfpa.flammability",
    "nfpa.instability",
    "nfpa.special",
}


def infer_container_type_from_fill_amount(fill_amount: Optional[str]) -> Optional[str]:
    """Infer pail, drum, or tote from net weight using ClearEdge thresholds."""
    cleaned = clean_operator_field(fill_amount)
    if not cleaned:
        return None

    match = re.search(r"(?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)", cleaned)
    if not match:
        return None

    try:
        amount = float(match.group("amount").replace(",", ""))
    except ValueError:
        return None

    normalized = cleaned.lower().replace(".", "")
    pounds = amount * KG_TO_LB if re.search(r"\b(kg|kgs|kilogram|kilograms)\b", normalized) else amount

    if pounds > 2000:
        return "tote"
    if pounds > 60:
        return "drum"
    if pounds <= 55:
        return "pail"
    return None


class LabelPipelineError(Exception):
    """HTTP-compatible pipeline error."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class LabelPipeline:
    """Generate, review, validate, render, and persist labels."""

    def __init__(
        self,
        *,
        pdf_extractor,
        openai_client,
        validator,
        label_generator,
        agentcore_client=None,
        logo_library=None,
        labels_dir: Path,
        metadata_store: dict,
        save_metadata_store,
    ):
        self.pdf_extractor = pdf_extractor
        self.openai_client = openai_client
        self.validator = validator
        self.label_generator = label_generator
        self.agentcore_client = agentcore_client
        self.logo_library = logo_library
        self.labels_dir = labels_dir
        self.metadata_store = metadata_store
        self.save_metadata_store = save_metadata_store

    async def generate_label_from_uploads(
        self,
        *,
        files: List[UploadFile],
        product_name: str,
        mode: str,
        size: str,
        orientation: str = "vertical",
        lot_number: Optional[str] = None,
        expiration_date: Optional[str] = None,
        fill_amount: Optional[str] = None,
        manufacture_date: Optional[str] = None,
        ghs_pictograms: Optional[str] = None,
        label_brand: Optional[str] = None,
        show_clearedge_mark: bool = True,
        brand_logo: Optional[UploadFile] = None,
        brand_logo_id: Optional[str] = None,
        save_brand_logo: bool = False,
        brand_logo_name: Optional[str] = None,
        supplier_name: Optional[str] = None,
        supplier_address: Optional[str] = None,
        supplier_phone: Optional[str] = None,
        emergency_phone: Optional[str] = None,
        transport_status: Optional[str] = None,
        un_number: Optional[str] = None,
        proper_shipping_name: Optional[str] = None,
        hazard_class: Optional[str] = None,
        packing_group: Optional[str] = None,
        marine_pollutant: Optional[str] = None,
        hazardous_substance: Optional[str] = None,
        hazardous_waste: Optional[str] = None,
        limited_quantity: Optional[str] = None,
        subsidiary_hazard_classes: Optional[str] = None,
    ) -> dict:
        """Run the label generation workflow."""
        cleaned_product_name = self._validate_product_name(product_name)
        orientation = self._normalize_orientation(orientation)
        if self.openai_client is None:
            raise LabelPipelineError(503, "OPENAI_API_KEY is not configured")

        branding = await self._build_branding(
            label_brand=label_brand,
            show_clearedge_mark=show_clearedge_mark,
            brand_logo=brand_logo,
            brand_logo_id=brand_logo_id,
            save_brand_logo=save_brand_logo,
            brand_logo_name=brand_logo_name,
        )

        sds_text, tds_text, suggested_logo = await self._extract_uploaded_documents(files)

        try:
            extracted_data = self.openai_client.extract_from_documents(sds_text, tds_text, cleaned_product_name)
        except ValueError as exc:
            extracted_data = RuleBasedExtractor.extract(
                sds_text=sds_text,
                tds_text=tds_text,
                product_name=cleaned_product_name,
                warning=f"AI_EXTRACTION_FAILED: {self._safe_exception_detail(exc)}",
            )
        except Exception as exc:
            logger.error("AI extraction failed: %s", exc, exc_info=True)
            extracted_data = RuleBasedExtractor.extract(
                sds_text=sds_text,
                tds_text=tds_text,
                product_name=cleaned_product_name,
                warning=f"AI_EXTRACTION_FAILED: {exc.__class__.__name__}: {self._safe_exception_detail(exc)}",
            )
        extracted_data.product.name = cleaned_product_name
        branding = self._apply_suggested_logo_to_branding(branding, suggested_logo)
        self._apply_operator_fields(
            extracted_data,
            lot_number=lot_number,
            expiration_date=expiration_date,
            fill_amount=fill_amount,
            manufacture_date=manufacture_date,
            ghs_pictograms=ghs_pictograms,
            branding=branding,
            supplier_name=supplier_name,
            supplier_address=supplier_address,
            supplier_phone=supplier_phone,
            emergency_phone=emergency_phone,
            transport_status=transport_status,
            un_number=un_number,
            proper_shipping_name=proper_shipping_name,
            hazard_class=hazard_class,
            packing_group=packing_group,
            marine_pollutant=marine_pollutant,
            hazardous_substance=hazardous_substance,
            hazardous_waste=hazardous_waste,
            limited_quantity=limited_quantity,
            subsidiary_hazard_classes=subsidiary_hazard_classes,
        )

        agentcore_review = self._run_agentcore_review(
            sds_text=sds_text,
            tds_text=tds_text,
            extracted_data=extracted_data,
            product_name=cleaned_product_name,
            mode=mode,
        )
        agentcore_needs_review = self._reconcile_agentcore_review(extracted_data, agentcore_review)

        validation_result = self.validator.validate(extracted_data, mode)
        self._apply_agentcore_issues_to_validation(validation_result, agentcore_review, agentcore_needs_review)

        label_id = self._new_label_id(cleaned_product_name)
        label_path = self._render_pdf(
            label_id,
            extracted_data,
            mode,
            size,
            orientation=orientation,
            branding=branding,
        )
        status = self._label_status(validation_result, agentcore_needs_review, agentcore_review)
        dot_shipping_review = build_dot_shipping_review(extracted_data, mode)
        dot_sticker_path = self._render_dot_sticker_pdf(label_id, dot_shipping_review)

        metadata = self._build_metadata(
            label_id=label_id,
            product_name=cleaned_product_name,
            mode=mode,
            size=size,
            orientation=orientation,
            extracted_data=extracted_data,
            validation_result=validation_result,
            status=status,
            agentcore_review=agentcore_review,
            branding=branding,
            dot_shipping_review=dot_shipping_review,
            dot_sticker_path=dot_sticker_path,
        )
        metadata["artifact_path"] = str(label_path)
        metadata["preview_artifact_path"] = str(label_path.with_suffix(".svg"))
        self.metadata_store[label_id] = metadata
        self.save_metadata_store()

        return self._response_payload(metadata)

    def apply_corrections(self, label_id: str, request: CorrectionRequest) -> dict:
        """Apply operator corrections, rerun validation, and rerender the label."""
        metadata = self.metadata_store.get(label_id)
        if not metadata:
            raise LabelPipelineError(404, "Label not found")
        if not metadata.get("extracted"):
            raise LabelPipelineError(409, "Label extraction payload is not available for correction")

        extracted_data = ExtractedData(**metadata["extracted"])
        for field_path, value in request.fields.items():
            self._set_field_value(extracted_data, field_path, value)

        extracted_data.warnings.append(
            f"Operator corrections applied by {request.updated_by.strip()}: {request.reason.strip()}"
        )

        validation_result = self.validator.validate(extracted_data, metadata["mode"])
        status = "ready" if validation_result.passed else "blocked"
        label_path = self._render_pdf(
            label_id,
            extracted_data,
            metadata["mode"],
            metadata["size"],
            orientation=metadata.get("orientation") or "vertical",
            branding=metadata.get("branding"),
        )
        dot_shipping_review = build_dot_shipping_review(extracted_data, metadata["mode"])
        dot_sticker_path = self._render_dot_sticker_pdf(label_id, dot_shipping_review)

        metadata.update(
            self._build_metadata(
                label_id=label_id,
                product_name=metadata["product_name"],
                mode=metadata["mode"],
                size=metadata["size"],
                orientation=metadata.get("orientation") or "vertical",
                extracted_data=extracted_data,
                validation_result=validation_result,
                status=status,
                agentcore_review=metadata.get("agentcore_review") or disabled_agentcore_review(),
                branding=metadata.get("branding"),
                dot_shipping_review=dot_shipping_review,
                dot_sticker_path=dot_sticker_path,
            )
        )
        metadata["artifact_path"] = str(label_path)
        metadata["preview_artifact_path"] = str(label_path.with_suffix(".svg"))
        metadata.setdefault("correction_history", []).append({
            "updated_by": request.updated_by.strip(),
            "reason": request.reason.strip(),
            "fields": request.fields,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.metadata_store[label_id] = metadata
        self.save_metadata_store()
        return self._response_payload(metadata)

    @staticmethod
    def _validate_product_name(product_name: str) -> str:
        cleaned = product_name.strip()
        if not cleaned or len(cleaned) < 2:
            raise LabelPipelineError(400, "Product name is required")
        if len(cleaned) > 100:
            raise LabelPipelineError(400, "Product name too long (max 100 chars)")
        return cleaned

    async def _extract_uploaded_documents(self, files: List[UploadFile]):
        if len(files) > MAX_PDFS_PER_REQUEST:
            raise LabelPipelineError(400, f"TOO_MANY_FILES: Upload no more than {MAX_PDFS_PER_REQUEST} PDFs")

        total_size = 0
        sds_text = None
        tds_text = None
        suggested_logo = None

        for upload in files:
            self._validate_upload_file(upload)
            content = await upload.read()
            total_size += len(content)
            if len(content) > MAX_FILE_SIZE_BYTES:
                raise LabelPipelineError(400, "FILE_TOO_LARGE: Each PDF must be 20 MB or smaller")
            if total_size > MAX_TOTAL_UPLOAD_BYTES:
                raise LabelPipelineError(400, "FILE_TOO_LARGE: Total upload must be 50 MB or smaller")

            doc_type = self._classify_document(upload.filename or "")
            try:
                extracted = self.pdf_extractor.extract_text(content, doc_type)
            except Exception as exc:
                raise LabelPipelineError(400, f"PDF_TEXT_EXTRACTION_FAILED: {exc}") from exc

            if doc_type == "SDS" and sds_text is None:
                sds_text = extracted
            elif doc_type == "TDS" and tds_text is None:
                tds_text = extracted
            elif sds_text is None:
                sds_text = extracted
            else:
                tds_text = extracted

            detected_logo = self._extract_suggested_logo(content, doc_type, upload.filename)
            if detected_logo and (
                not suggested_logo
                or detected_logo.get("confidence", 0) > suggested_logo.get("confidence", 0)
            ):
                suggested_logo = detected_logo

        if not sds_text and not tds_text:
            raise LabelPipelineError(400, "PDF_TEXT_EXTRACTION_FAILED: No valid PDF files provided")

        return sds_text, tds_text, suggested_logo

    @staticmethod
    def _validate_upload_file(upload: UploadFile) -> None:
        filename = upload.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise LabelPipelineError(400, "UNSUPPORTED_FILE_TYPE: Only PDF files are supported")
        if upload.content_type not in ALLOWED_PDF_CONTENT_TYPES:
            raise LabelPipelineError(400, "UNSUPPORTED_FILE_TYPE: Only PDF files are supported")

    @staticmethod
    def _classify_document(filename: str) -> str:
        lower = filename.lower()
        if "tds" in lower:
            return "TDS"
        return "SDS"

    def _extract_suggested_logo(self, content: bytes, doc_type: str, filename: Optional[str]) -> Optional[dict]:
        extractor = getattr(self.pdf_extractor, "extract_suggested_logo", None)
        if not callable(extractor):
            return None

        try:
            return extractor(content, doc_type, source_filename=filename)
        except TypeError:
            return extractor(content, doc_type)
        except Exception as exc:
            logger.info("Suggested logo extraction failed for %s: %s", filename, exc)
            return None

    def _apply_operator_fields(
        self,
        extracted_data: ExtractedData,
        *,
        lot_number: Optional[str],
        expiration_date: Optional[str],
        fill_amount: Optional[str],
        manufacture_date: Optional[str],
        ghs_pictograms: Optional[str],
        branding: dict,
        supplier_name: Optional[str],
        supplier_address: Optional[str],
        supplier_phone: Optional[str],
        emergency_phone: Optional[str],
        transport_status: Optional[str],
        un_number: Optional[str],
        proper_shipping_name: Optional[str],
        hazard_class: Optional[str],
        packing_group: Optional[str],
        marine_pollutant: Optional[str],
        hazardous_substance: Optional[str],
        hazardous_waste: Optional[str],
        limited_quantity: Optional[str],
        subsidiary_hazard_classes: Optional[str],
    ) -> None:
        extracted_data.shipment.lot_number = clean_operator_field(lot_number)
        extracted_data.shipment.expiration_date = clean_operator_field(expiration_date)
        extracted_data.shipment.fill_amount = clean_operator_field(fill_amount)
        extracted_data.shipment.manufacture_date = clean_operator_field(manufacture_date)
        extracted_data.shipment.container_type = infer_container_type_from_fill_amount(
            extracted_data.shipment.fill_amount
        )

        self._apply_branding_fields(
            extracted_data,
            branding=branding,
            supplier_name=supplier_name,
            supplier_address=supplier_address,
            supplier_phone=supplier_phone,
            emergency_phone=emergency_phone,
        )
        self._apply_transport_fields(
            extracted_data,
            transport_status=transport_status,
            un_number=un_number,
            proper_shipping_name=proper_shipping_name,
            hazard_class=hazard_class,
            packing_group=packing_group,
            marine_pollutant=marine_pollutant,
            hazardous_substance=hazardous_substance,
            hazardous_waste=hazardous_waste,
            limited_quantity=limited_quantity,
            subsidiary_hazard_classes=subsidiary_hazard_classes,
        )

        operator_pictograms = parse_ghs_pictogram_selection(ghs_pictograms)
        if operator_pictograms:
            extracted_data.ghs.pictograms = operator_pictograms
            extracted_data.warnings.append(
                "GHS pictograms were selected by operator dropdown and override the SDS auto-pick."
            )

    async def _build_branding(
        self,
        *,
        label_brand: Optional[str],
        show_clearedge_mark: bool = True,
        brand_logo: Optional[UploadFile] = None,
        brand_logo_id: Optional[str] = None,
        save_brand_logo: bool = False,
        brand_logo_name: Optional[str] = None,
    ) -> dict:
        mode = self._normalize_label_brand(label_brand)
        if brand_logo and mode == "clearedge" and label_brand is None:
            mode = "custom"

        logo_data_uri = None
        logo_filename = None
        logo_id = None
        logo_name = None
        logo_source = "clearedge" if mode == "clearedge" else "none"
        saved_logo = None
        if mode == "custom" and brand_logo is not None:
            logo_upload = await self._read_brand_logo_upload(brand_logo)
            logo_data_uri = logo_upload["data_uri"]
            logo_filename = logo_upload["filename"]
            logo_source = "uploaded"
            if save_brand_logo:
                if self.logo_library is None:
                    raise LabelPipelineError(500, "LOGO_LIBRARY_UNAVAILABLE: Saved logo library is not initialized")
                try:
                    saved_logo = self.logo_library.save_logo(
                        name=brand_logo_name or logo_upload["filename"],
                        filename=logo_upload["filename"],
                        content_type=logo_upload["content_type"],
                        content=logo_upload["content"],
                    )
                except ValueError as exc:
                    raise LabelPipelineError(400, str(exc)) from exc
                logo_id = saved_logo["logo_id"]
                logo_name = saved_logo["name"]
        elif mode == "custom" and clean_operator_field(brand_logo_id):
            if self.logo_library is None:
                raise LabelPipelineError(500, "LOGO_LIBRARY_UNAVAILABLE: Saved logo library is not initialized")
            try:
                saved = self.logo_library.get_logo(clean_operator_field(brand_logo_id))
                logo_data_uri = self.logo_library.logo_data_uri(saved["logo_id"])
            except ValueError as exc:
                raise LabelPipelineError(400, str(exc)) from exc
            logo_filename = saved.get("filename")
            logo_id = saved["logo_id"]
            logo_name = saved["name"]
            logo_source = "library"

        return {
            "mode": mode,
            "logo_data_uri": logo_data_uri,
            "logo_filename": logo_filename,
            "logo_source": logo_source,
            "logo_id": logo_id,
            "logo_name": logo_name,
            "show_clearedge_mark": bool(show_clearedge_mark) if mode == "custom" else False,
            "saved_logo": saved_logo,
            "suggested_logo": None,
        }

    @staticmethod
    def _apply_suggested_logo_to_branding(branding: dict, suggested_logo: Optional[dict]) -> dict:
        resolved = dict(branding)
        if resolved.get("mode") != "custom":
            resolved["suggested_logo"] = None
            resolved["logo_source"] = "clearedge"
            return resolved

        resolved["suggested_logo"] = suggested_logo
        if suggested_logo and not resolved.get("logo_data_uri"):
            resolved["logo_data_uri"] = suggested_logo.get("data_uri")
            resolved["logo_filename"] = suggested_logo.get("source_file") or suggested_logo.get("name")
            resolved["logo_source"] = "suggested"
        elif resolved.get("logo_data_uri"):
            resolved["logo_source"] = resolved.get("logo_source") or "uploaded"
        else:
            resolved["logo_source"] = "none"
        return resolved

    @staticmethod
    def _normalize_label_brand(value: Optional[str]) -> str:
        cleaned = (clean_operator_field(value) or "clearedge").lower()
        if cleaned in {"clearedge", "clear edge", "ce"}:
            return "clearedge"
        if cleaned in {"custom", "customer", "other", "vendor", "supplier", "private_label"}:
            return "custom"
        raise LabelPipelineError(400, "INVALID_LABEL_BRAND: Use clearedge or custom")

    @staticmethod
    async def _read_brand_logo_data_uri(brand_logo: UploadFile) -> str:
        return (await LabelPipeline._read_brand_logo_upload(brand_logo))["data_uri"]

    @staticmethod
    async def _read_brand_logo_upload(brand_logo: UploadFile) -> dict:
        filename = brand_logo.filename or ""
        content_type = brand_logo.content_type or ""
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if content_type not in ALLOWED_LOGO_CONTENT_TYPES or suffix not in ALLOWED_LOGO_EXTENSIONS:
            raise LabelPipelineError(400, "UNSUPPORTED_LOGO_FILE_TYPE: Upload a PNG, JPG, SVG, or WebP logo image")

        content = await brand_logo.read()
        if len(content) > MAX_LOGO_FILE_SIZE_BYTES:
            raise LabelPipelineError(400, "LOGO_FILE_TOO_LARGE: Logo image must be 2 MB or smaller")
        if not content:
            raise LabelPipelineError(400, "EMPTY_LOGO_FILE: Uploaded logo file is empty")

        encoded = base64.b64encode(content).decode("ascii")
        return {
            "filename": filename,
            "content_type": content_type,
            "suffix": suffix,
            "content": content,
            "data_uri": f"data:{content_type};base64,{encoded}",
        }

    @staticmethod
    def _apply_branding_fields(
        extracted_data: ExtractedData,
        *,
        branding: dict,
        supplier_name: Optional[str],
        supplier_address: Optional[str],
        supplier_phone: Optional[str],
        emergency_phone: Optional[str],
    ) -> None:
        if branding.get("mode") == "custom":
            extracted_data.product.supplier_name = (
                clean_operator_field(supplier_name) or extracted_data.product.supplier_name
            )
            extracted_data.product.supplier_address = (
                clean_operator_field(supplier_address) or extracted_data.product.supplier_address
            )
            extracted_data.product.supplier_phone = (
                clean_operator_field(supplier_phone) or extracted_data.product.supplier_phone
            )
        else:
            extracted_data.product.supplier_name = OFFICIAL_CLEAREDGE_SUPPLIER["supplier_name"]
            extracted_data.product.supplier_address = OFFICIAL_CLEAREDGE_SUPPLIER["supplier_address"]
            extracted_data.product.supplier_phone = OFFICIAL_CLEAREDGE_SUPPLIER["supplier_phone"]

        entered_emergency_phone = clean_operator_field(emergency_phone)
        if entered_emergency_phone:
            extracted_data.product.emergency_phone = entered_emergency_phone

    @classmethod
    def _apply_transport_fields(
        cls,
        extracted_data: ExtractedData,
        *,
        transport_status: Optional[str],
        un_number: Optional[str],
        proper_shipping_name: Optional[str],
        hazard_class: Optional[str],
        packing_group: Optional[str],
        marine_pollutant: Optional[str],
        hazardous_substance: Optional[str],
        hazardous_waste: Optional[str],
        limited_quantity: Optional[str],
        subsidiary_hazard_classes: Optional[str],
    ) -> None:
        status = cls._normalize_transport_status(transport_status)
        if status == "regulated":
            extracted_data.transport.not_regulated = False
        elif status == "not_regulated":
            extracted_data.transport.not_regulated = True

        entered_un_number = clean_operator_field(un_number)
        entered_shipping_name = clean_operator_field(proper_shipping_name)
        entered_hazard_class = clean_operator_field(hazard_class)
        entered_packing_group = cls._normalize_packing_group(packing_group)
        entered_marine_pollutant = cls._parse_optional_bool(marine_pollutant, "marine_pollutant")
        entered_hazardous_substance = cls._parse_optional_bool(hazardous_substance, "hazardous_substance")
        entered_hazardous_waste = cls._parse_optional_bool(hazardous_waste, "hazardous_waste")
        entered_limited_quantity = clean_operator_field(limited_quantity)
        entered_subsidiary_classes = cls._normalize_hazard_class_list(subsidiary_hazard_classes)

        applied = False
        if entered_un_number:
            extracted_data.transport.un_number = entered_un_number
            applied = True
        if entered_shipping_name:
            extracted_data.transport.proper_shipping_name = entered_shipping_name
            applied = True
        if entered_hazard_class:
            extracted_data.transport.hazard_class = entered_hazard_class
            applied = True
        if entered_packing_group:
            extracted_data.transport.packing_group = entered_packing_group
            applied = True
        if entered_marine_pollutant is not None:
            extracted_data.transport.marine_pollutant = entered_marine_pollutant
            applied = True
        if entered_hazardous_substance is not None:
            extracted_data.transport.hazardous_substance = entered_hazardous_substance
            applied = True
        if entered_hazardous_waste is not None:
            extracted_data.transport.hazardous_waste = entered_hazardous_waste
            applied = True
        if entered_limited_quantity:
            extracted_data.transport.limited_quantity = entered_limited_quantity
            applied = True
        if entered_subsidiary_classes:
            extracted_data.transport.subsidiary_hazard_classes = entered_subsidiary_classes
            applied = True
        if status != "auto":
            applied = True

        if applied:
            extracted_data.warnings.append("Operator-entered DOT/shipping fields were applied before validation.")

    @staticmethod
    def _normalize_transport_status(value: Optional[str]) -> str:
        cleaned = (clean_operator_field(value) or "auto").lower().replace("-", "_").replace(" ", "_")
        if cleaned in {"", "auto", "from_sds", "sds"}:
            return "auto"
        if cleaned in {"regulated", "dot_regulated", "hazmat", "hazardous"}:
            return "regulated"
        if cleaned in {"not_regulated", "not_dot_regulated", "not_hazmat", "not_restricted"}:
            return "not_regulated"
        raise LabelPipelineError(400, "INVALID_TRANSPORT_STATUS: Use auto, regulated, or not_regulated")

    @staticmethod
    def _normalize_packing_group(value: Optional[str]) -> Optional[str]:
        cleaned = clean_operator_field(value)
        if not cleaned:
            return None

        normalized = cleaned.upper().replace("PACKING GROUP", "").replace("PG", "").strip()
        normalized = normalized.replace(" ", "")
        mapping = {
            "1": "I",
            "I": "I",
            "2": "II",
            "II": "II",
            "3": "III",
            "III": "III",
        }
        packing_group = mapping.get(normalized)
        if not packing_group:
            raise LabelPipelineError(400, "INVALID_PACKING_GROUP: Use I, II, III, 1, 2, or 3")
        return packing_group

    @staticmethod
    def _parse_optional_bool(value: Optional[str], field_name: str) -> Optional[bool]:
        cleaned = clean_operator_field(value)
        if not cleaned:
            return None

        normalized = cleaned.lower()
        if normalized in {"auto", "unknown", "not listed"}:
            return None
        if normalized in {"true", "yes", "y", "1"}:
            return True
        if normalized in {"false", "no", "n", "0"}:
            return False
        raise LabelPipelineError(400, f"INVALID_BOOLEAN_FIELD: {field_name} must be yes, no, or auto")

    @staticmethod
    def _normalize_hazard_class_list(value: Optional[str]) -> list[str]:
        cleaned = clean_operator_field(value)
        if not cleaned:
            return []

        classes = []
        seen = set()
        for item in re.split(r"[,;|]", cleaned):
            normalized = " ".join(item.strip().split())
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in {"none", "n/a", "na", "not applicable", "not listed", "void"}:
                continue
            if lowered.startswith("class "):
                normalized = normalized[6:].strip()
            if normalized not in seen:
                classes.append(normalized)
                seen.add(normalized)
        return classes

    @staticmethod
    def _normalize_orientation(value: Optional[str]) -> str:
        cleaned = (clean_operator_field(value) or "vertical").lower().replace("-", "_").replace(" ", "_")
        if cleaned in {"vertical", "portrait"}:
            return "vertical"
        if cleaned in {"horizontal", "landscape"}:
            return "horizontal"
        raise LabelPipelineError(400, "INVALID_ORIENTATION: Use vertical or horizontal")

    def _run_agentcore_review(
        self,
        *,
        sds_text,
        tds_text,
        extracted_data: ExtractedData,
        product_name: str,
        mode: str,
    ) -> dict:
        if not settings.agentcore_enabled:
            return disabled_agentcore_review()
        if self.agentcore_client is None:
            return unavailable_agentcore_review(
                "AgentCore is enabled but no runtime client is configured; OpenAI extraction was used without AgentCore review."
            )

        try:
            return self.agentcore_client.review_label_data(
                sds_text=sds_text,
                tds_text=tds_text,
                openai_extracted=extracted_data.model_dump(mode="json"),
                product_name=product_name,
                label_mode=mode,
                shipment=extracted_data.shipment.model_dump(mode="json"),
            )
        except Exception as exc:
            logger.warning("AgentCore review failed: %s", exc)
            return unavailable_agentcore_review(
                f"AgentCore review failed or timed out: {exc}. OpenAI extraction and local validation were used."
            )

    def _reconcile_agentcore_review(self, extracted_data: ExtractedData, review: dict) -> bool:
        needs_review = False
        for field_review in review.get("field_reviews") or []:
            field_path = field_review.get("field_path")
            if not field_path or field_path not in CRITICAL_AGENTCORE_FIELDS:
                continue

            recommended = field_review.get("recommended_value")
            current = self._get_field_value(extracted_data, field_path)
            confidence = float(field_review.get("confidence") or 0)
            status = str(field_review.get("status") or "").lower()
            has_source = bool(field_review.get("evidence")) and field_review.get("source_document") in {"SDS", "TDS"}

            if self._is_missing(current) and not self._is_missing(recommended):
                if confidence >= AGENTCORE_PROMOTION_CONFIDENCE and has_source and status in {"found", "source_backed", "agentcore_source_backed"}:
                    if field_path in PROMOTABLE_AGENTCORE_FIELDS:
                        self._set_field_value(extracted_data, field_path, recommended)
                        self._add_agentcore_evidence(extracted_data, field_review)
                        extracted_data.warnings.append(f"AgentCore source-backed value applied for {field_path}.")
                    else:
                        needs_review = True
                continue

            if (
                not self._is_missing(current)
                and not self._is_missing(recommended)
                and self._normalized_value(current) != self._normalized_value(recommended)
                and (status == "conflict" or confidence >= AGENTCORE_PROMOTION_CONFIDENCE)
            ):
                field_review["status"] = "conflict"
                field_review.setdefault(
                    "reason",
                    f"OpenAI value '{current}' conflicts with AgentCore recommendation '{recommended}'.",
                )
                needs_review = True

        for issue in review.get("critical_issues") or []:
            if str(issue.get("severity") or "").lower() in {"blocking", "error", "needs_review"}:
                needs_review = True

        return needs_review

    @staticmethod
    def _apply_agentcore_issues_to_validation(
        validation_result: ValidationResult,
        review: dict,
        agentcore_needs_review: bool,
    ) -> None:
        if agentcore_needs_review:
            for field_review in review.get("field_reviews") or []:
                if str(field_review.get("status") or "").lower() == "conflict":
                    validation_result.errors.append(ValidationError(
                        field=f"agentcore.{field_review.get('field_path') or 'review'}",
                        message=field_review.get("reason") or "AgentCore found a source-backed conflict requiring review.",
                        severity="error",
                    ))

        for issue in review.get("critical_issues") or []:
            severity = str(issue.get("severity") or "").lower()
            target = validation_result.warnings if severity == "warning" else validation_result.errors
            target.append(ValidationError(
                field=f"agentcore.{issue.get('field_path') or 'review'}",
                message=issue.get("message") or "AgentCore review issue",
                severity="warning" if severity == "warning" else "error",
            ))

        if validation_result.errors:
            validation_result.passed = False

    def _render_pdf(
        self,
        label_id: str,
        extracted_data: ExtractedData,
        mode: str,
        size: str,
        *,
        orientation: str = "vertical",
        branding: Optional[dict] = None,
    ) -> Path:
        try:
            template_id = f"clearedge_{size}_v1"
            svg_content = self.label_generator.generate_svg(
                extracted_data,
                mode=mode,
                size=size,
                template_id=template_id,
                orientation=orientation,
                branding=branding,
            )
            self.labels_dir.mkdir(parents=True, exist_ok=True)
            pdf_content = self.label_generator.generate_pdf(svg_content)
            label_path = self.labels_dir / f"{label_id}.pdf"
            preview_path = self.labels_dir / f"{label_id}.svg"
            preview_path.write_text(svg_content)
            label_path.write_bytes(pdf_content)
            return label_path
        except Exception as exc:
            logger.error("Label rendering failed for %s: %s", label_id, exc, exc_info=True)
            raise LabelPipelineError(500, f"LABEL_RENDERING_FAILED: {exc}") from exc

    def _render_dot_sticker_pdf(self, label_id: str, dot_shipping_review: dict) -> Optional[Path]:
        """Render the separate DOT sticker sheet artifact when required."""
        if not dot_shipping_review.get("separate_dot_sticker_required"):
            return None

        required_stickers = dot_shipping_review.get("required_stickers") or []
        if not required_stickers:
            return None

        try:
            sticker_path = self.labels_dir / f"{label_id}-dot-stickers.pdf"
            return DotStickerSheetRenderer().write_pdf(required_stickers, sticker_path)
        except DotStickerSheetUnavailable as exc:
            logger.warning("DOT sticker sheet unavailable for %s: %s", label_id, exc)
            return None
        except Exception as exc:
            logger.error("DOT sticker rendering failed for %s: %s", label_id, exc, exc_info=True)
            raise LabelPipelineError(500, f"DOT_STICKER_RENDERING_FAILED: {exc}") from exc

    def _build_metadata(
        self,
        *,
        label_id: str,
        product_name: str,
        mode: str,
        size: str,
        orientation: str,
        extracted_data: ExtractedData,
        validation_result: ValidationResult,
        status: str,
        agentcore_review: dict,
        branding: Optional[dict] = None,
        dot_shipping_review: Optional[dict] = None,
        dot_sticker_path: Optional[Path] = None,
    ) -> dict:
        preview_url = f"/api/v1/labels/{label_id}/preview.svg"
        download_url = f"/api/v1/labels/{label_id}/download"
        canva_export_urls = canva_urls(label_id, True)
        extracted_payload = extracted_data.model_dump(mode="json")
        dot_shipping_review = dot_shipping_review or build_dot_shipping_review(extracted_data, mode)
        dot_stickers = self._dot_stickers_payload(
            label_id=label_id,
            status=status,
            dot_shipping_review=dot_shipping_review,
            dot_sticker_path=dot_sticker_path,
        )
        metadata = {
            "label_id": label_id,
            "product_name": product_name,
            "mode": mode,
            "size": size,
            "orientation": orientation,
            "container_type": extracted_payload.get("shipment", {}).get("container_type"),
            "created_at": datetime.utcnow().isoformat(),
            "validation_passed": validation_result.passed and status == "ready",
            "warnings": [w.model_dump() for w in validation_result.warnings],
            "errors": [e.model_dump() for e in validation_result.errors],
            "preview_url": preview_url,
            "download_url": download_url,
            **canva_export_urls,
            "preview": {
                "available": True,
                "url": preview_url,
                "media_type": "image/svg+xml",
            },
            "download": {
                "available": True,
                "url": download_url,
                "reason": None,
            },
            "status": status,
            "override_approved": False,
            "override_reason": None,
            "override_approver": None,
            "override_timestamp": None,
            "extracted": extracted_payload,
            "dot_shipping_review": dot_shipping_review,
            "dot_stickers": dot_stickers,
            "dot_sticker_artifact_path": str(dot_sticker_path) if dot_sticker_path else None,
            "agentcore_review": agentcore_review,
            "branding": branding or {"mode": "clearedge", "logo_data_uri": None, "logo_filename": None},
        }
        metadata["canva_export"] = build_canva_export(extracted_payload, metadata)
        return metadata

    @staticmethod
    def _label_status(validation_result: ValidationResult, agentcore_needs_review: bool, review: dict) -> str:
        if validation_result.errors:
            return "needs_review"
        if agentcore_needs_review:
            return "needs_review"
        return "ready" if validation_result.passed else "blocked"

    @staticmethod
    def _response_payload(metadata: dict) -> dict:
        inline_svg = LabelPipeline._read_preview_svg(metadata)
        download_data_url = LabelPipeline._read_pdf_data_url(metadata)
        preview_payload = {
            **metadata["preview"],
            "inline_svg": inline_svg,
        }
        download_payload = {
            **metadata["download"],
            "data_url": download_data_url,
        }
        return {
            "label_id": metadata["label_id"],
            "status": metadata["status"],
            "extracted": metadata["extracted"],
            "validation": {
                "passed": metadata["validation_passed"],
                "warnings": metadata["warnings"],
                "errors": metadata["errors"],
            },
            "label": {
                "mode": metadata["mode"],
                "size": metadata["size"],
                "orientation": metadata.get("orientation") or "vertical",
                "container_type": metadata.get("container_type"),
                "preview_url": metadata["preview_url"],
                "download_url": metadata["download_url"],
                "download_data_url": download_data_url,
                "dot_sticker_pdf_url": metadata.get("dot_stickers", {}).get("url"),
                "canva_csv_url": metadata["canva_csv_url"],
                "canva_json_url": metadata["canva_json_url"],
            },
            "preview": preview_payload,
            "download": download_payload,
            "dot_shipping_review": metadata.get("dot_shipping_review"),
            "dot_stickers": metadata.get("dot_stickers"),
            "agentcore_review": metadata.get("agentcore_review"),
            "branding": metadata.get("branding"),
            "warnings": metadata["warnings"],
            "errors": metadata["errors"],
            "audit": {
                "created_at": metadata["created_at"],
                "phase": "agentcore_review" if metadata.get("agentcore_review", {}).get("status") == "reviewed" else "phase_1",
            },
            "success": True,
        }

    @staticmethod
    def _read_preview_svg(metadata: dict) -> Optional[str]:
        preview_path = metadata.get("preview_artifact_path")
        if not preview_path and metadata.get("artifact_path"):
            preview_path = str(Path(metadata["artifact_path"]).with_suffix(".svg"))
        if not preview_path:
            return None
        try:
            path = Path(preview_path)
            if path.exists():
                return path.read_text()
        except OSError as exc:
            logger.warning("Could not inline preview SVG for %s: %s", metadata.get("label_id"), exc)
        return None

    @staticmethod
    def _read_pdf_data_url(metadata: dict) -> Optional[str]:
        artifact_path = metadata.get("artifact_path")
        if not artifact_path:
            return None
        try:
            path = Path(artifact_path)
            if path.exists():
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                return f"data:application/pdf;base64,{encoded}"
        except OSError as exc:
            logger.warning("Could not inline PDF download for %s: %s", metadata.get("label_id"), exc)
        return None

    @staticmethod
    def _new_label_id(product_name: str) -> str:
        safe_product_name = re.sub(r"[^a-zA-Z0-9_-]", "", product_name[:50])
        return f"label_{safe_product_name}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _dot_stickers_payload(
        *,
        label_id: str,
        status: str,
        dot_shipping_review: dict,
        dot_sticker_path: Optional[Path],
    ) -> dict:
        required_stickers = dot_shipping_review.get("required_stickers") or []
        sticker_artifact_exists = bool(dot_sticker_path and dot_sticker_path.exists())
        sticker_url = f"/api/v1/labels/{label_id}/dot-stickers.pdf" if sticker_artifact_exists else None

        if not dot_shipping_review.get("separate_dot_sticker_required"):
            reason = "No separate DOT sticker PDF is required for this label."
        elif not sticker_artifact_exists:
            reason = "DOT sticker PDF unavailable because an approved DOT sticker asset is missing."
        else:
            reason = None

        return {
            "available": bool(sticker_url),
            "url": sticker_url,
            "sticker_size_mm": DOT_STICKER_SIZE_MM,
            "sheet_size": "US Letter",
            "stickers": required_stickers,
            "reason": reason,
        }

    @staticmethod
    def _is_missing(value) -> bool:
        return value is None or value == "" or value == [] or value == {}

    @staticmethod
    def _normalized_value(value) -> str:
        if isinstance(value, list):
            return "|".join(str(item).strip().lower() for item in value)
        return " ".join(str(value).split()).lower()

    @staticmethod
    def _get_field_value(extracted_data: ExtractedData, field_path: str):
        current = extracted_data
        for part in field_path.split("."):
            current = getattr(current, part)
        return current

    @staticmethod
    def _set_field_value(extracted_data: ExtractedData, field_path: str, value) -> None:
        parts = field_path.split(".")
        if len(parts) != 2:
            raise LabelPipelineError(400, f"INVALID_CORRECTION_FIELD: {field_path}")

        section, field = parts
        target = getattr(extracted_data, section, None)
        if target is None or not hasattr(target, field):
            raise LabelPipelineError(400, f"INVALID_CORRECTION_FIELD: {field_path}")
        setattr(target, field, value)

    @staticmethod
    def _add_agentcore_evidence(extracted_data: ExtractedData, field_review: dict) -> None:
        evidence = field_review.get("evidence")
        source_document = field_review.get("source_document")
        if not evidence or source_document not in {"SDS", "TDS"}:
            return

        extracted_data.evidence.append(Evidence(
            field_path=field_review["field_path"],
            doc=source_document,
            section=None,
            page=field_review.get("page"),
            quote=str(evidence)[:240],
        ))
        extracted_data.confidence.append(FieldConfidence(
            field_path=field_review["field_path"],
            confidence=float(field_review.get("confidence") or 0),
        ))

    @staticmethod
    def _safe_exception_detail(exc: Exception) -> str:
        """Return a short external-service error message without secrets."""
        detail = str(exc) or "No error detail returned"
        detail = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-***", detail)
        return detail[:300]
