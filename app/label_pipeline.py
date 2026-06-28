"""Label generation pipeline orchestration."""

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
from .schema import Evidence, ExtractedData, FieldConfidence, ValidationError, ValidationResult

logger = logging.getLogger(__name__)


MAX_PDFS_PER_REQUEST = 4
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_UPLOAD_BYTES = 50 * 1024 * 1024
AGENTCORE_PROMOTION_CONFIDENCE = 0.85

ALLOWED_PDF_CONTENT_TYPES = {
    "application/pdf",
    "application/octet-stream",
    "",
    None,
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
        labels_dir: Path,
        metadata_store: dict,
        save_metadata_store,
    ):
        self.pdf_extractor = pdf_extractor
        self.openai_client = openai_client
        self.validator = validator
        self.label_generator = label_generator
        self.agentcore_client = agentcore_client
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
        lot_number: Optional[str] = None,
        expiration_date: Optional[str] = None,
        fill_amount: Optional[str] = None,
        manufacture_date: Optional[str] = None,
        ghs_pictograms: Optional[str] = None,
    ) -> dict:
        """Run the label generation workflow."""
        cleaned_product_name = self._validate_product_name(product_name)
        if self.openai_client is None:
            raise LabelPipelineError(503, "OPENAI_API_KEY is not configured")

        sds_text, tds_text = await self._extract_uploaded_documents(files)

        extracted_data = self.openai_client.extract_from_documents(sds_text, tds_text, cleaned_product_name)
        extracted_data.product.name = cleaned_product_name
        self._apply_operator_fields(
            extracted_data,
            lot_number=lot_number,
            expiration_date=expiration_date,
            fill_amount=fill_amount,
            manufacture_date=manufacture_date,
            ghs_pictograms=ghs_pictograms,
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
        label_path = self._render_pdf(label_id, extracted_data, mode, size)
        status = self._label_status(validation_result, agentcore_needs_review, agentcore_review)

        metadata = self._build_metadata(
            label_id=label_id,
            product_name=cleaned_product_name,
            mode=mode,
            size=size,
            extracted_data=extracted_data,
            validation_result=validation_result,
            status=status,
            agentcore_review=agentcore_review,
        )
        metadata["artifact_path"] = str(label_path)
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
        self._render_pdf(label_id, extracted_data, metadata["mode"], metadata["size"])

        metadata.update(
            self._build_metadata(
                label_id=label_id,
                product_name=metadata["product_name"],
                mode=metadata["mode"],
                size=metadata["size"],
                extracted_data=extracted_data,
                validation_result=validation_result,
                status=status,
                agentcore_review=metadata.get("agentcore_review") or disabled_agentcore_review(),
            )
        )
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

        if not sds_text and not tds_text:
            raise LabelPipelineError(400, "PDF_TEXT_EXTRACTION_FAILED: No valid PDF files provided")

        return sds_text, tds_text

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

    def _apply_operator_fields(
        self,
        extracted_data: ExtractedData,
        *,
        lot_number: Optional[str],
        expiration_date: Optional[str],
        fill_amount: Optional[str],
        manufacture_date: Optional[str],
        ghs_pictograms: Optional[str],
    ) -> None:
        extracted_data.shipment.lot_number = clean_operator_field(lot_number)
        extracted_data.shipment.expiration_date = clean_operator_field(expiration_date)
        extracted_data.shipment.fill_amount = clean_operator_field(fill_amount)
        extracted_data.shipment.manufacture_date = clean_operator_field(manufacture_date)

        operator_pictograms = parse_ghs_pictogram_selection(ghs_pictograms)
        if operator_pictograms:
            extracted_data.ghs.pictograms = operator_pictograms
            extracted_data.warnings.append(
                "GHS pictograms were selected by operator dropdown and override the SDS auto-pick."
            )

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

    def _render_pdf(self, label_id: str, extracted_data: ExtractedData, mode: str, size: str) -> Path:
        template_id = f"clearedge_{size}_v1"
        svg_content = self.label_generator.generate_svg(
            extracted_data,
            mode=mode,
            size=size,
            template_id=template_id,
        )
        self.labels_dir.mkdir(parents=True, exist_ok=True)
        pdf_content = self.label_generator.generate_pdf(svg_content)
        label_path = self.labels_dir / f"{label_id}.pdf"
        label_path.write_bytes(pdf_content)
        return label_path

    def _build_metadata(
        self,
        *,
        label_id: str,
        product_name: str,
        mode: str,
        size: str,
        extracted_data: ExtractedData,
        validation_result: ValidationResult,
        status: str,
        agentcore_review: dict,
    ) -> dict:
        download_url = f"/api/v1/labels/{label_id}/download" if status == "ready" else None
        canva_export_urls = canva_urls(label_id, status == "ready")
        extracted_payload = extracted_data.model_dump(mode="json")
        download_reason = None
        if not download_url:
            download_reason = (
                "AgentCore review requires operator review before download."
                if status == "needs_review"
                else "Validation failed. Fix required compliance issues first."
            )

        metadata = {
            "label_id": label_id,
            "product_name": product_name,
            "mode": mode,
            "size": size,
            "created_at": datetime.utcnow().isoformat(),
            "validation_passed": validation_result.passed and status == "ready",
            "warnings": [w.model_dump() for w in validation_result.warnings],
            "errors": [e.model_dump() for e in validation_result.errors],
            "download_url": download_url,
            **canva_export_urls,
            "download": {
                "available": bool(download_url),
                "url": download_url,
                "reason": download_reason,
            },
            "status": status,
            "override_approved": False,
            "override_reason": None,
            "override_approver": None,
            "override_timestamp": None,
            "extracted": extracted_payload,
            "agentcore_review": agentcore_review,
        }
        metadata["canva_export"] = build_canva_export(extracted_payload, metadata)
        return metadata

    @staticmethod
    def _label_status(validation_result: ValidationResult, agentcore_needs_review: bool, review: dict) -> str:
        if validation_result.errors:
            agentcore_conflict_fields = {
                f"agentcore.{field_review.get('field_path') or 'review'}"
                for field_review in review.get("field_reviews") or []
                if str(field_review.get("status") or "").lower() == "conflict"
            }
            only_agentcore_conflicts = (
                bool(agentcore_conflict_fields)
                and all(error.field in agentcore_conflict_fields for error in validation_result.errors)
            )
            return "needs_review" if only_agentcore_conflicts else "blocked"
        if agentcore_needs_review:
            return "needs_review"
        return "ready" if validation_result.passed else "blocked"

    @staticmethod
    def _response_payload(metadata: dict) -> dict:
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
                "download_url": metadata["download_url"],
                "canva_csv_url": metadata["canva_csv_url"],
                "canva_json_url": metadata["canva_json_url"],
            },
            "download": metadata["download"],
            "agentcore_review": metadata.get("agentcore_review"),
            "warnings": metadata["warnings"],
            "errors": metadata["errors"],
            "audit": {
                "created_at": metadata["created_at"],
                "phase": "agentcore_review" if metadata.get("agentcore_review", {}).get("status") == "reviewed" else "phase_1",
            },
            "success": True,
        }

    @staticmethod
    def _new_label_id(product_name: str) -> str:
        safe_product_name = re.sub(r"[^a-zA-Z0-9_-]", "", product_name[:50])
        return f"label_{safe_product_name}_{uuid.uuid4().hex[:8]}"

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
