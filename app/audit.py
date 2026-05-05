"""
Audit trail system for tracking all operations.
Maintains comprehensive records of extractions, validations, and label generation.
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from .schema import (
    ExtractionMeta,
    ExtractedData,
    ValidationResult,
    LabelBuildReport
)

logger = logging.getLogger(__name__)


class AuditLogger:
    """Comprehensive audit trail for all pipeline operations."""

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """Compute SHA-256 hash of data."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def create_extraction_meta(
        product_name: str,
        ai_model: str,
        sds_source_id: Optional[str] = None,
        sds_bytes: Optional[bytes] = None,
        tds_source_id: Optional[str] = None,
        tds_bytes: Optional[bytes] = None,
        source_urls: Optional[list] = None,
        duration_seconds: Optional[float] = None
    ) -> ExtractionMeta:
        """Create extraction metadata record."""
        return ExtractionMeta(
            product_name=product_name,
            extraction_timestamp=datetime.utcnow(),
            ai_model=ai_model,
            sds_source_id=sds_source_id,
            sds_sha256=AuditLogger.compute_sha256(sds_bytes) if sds_bytes else None,
            tds_source_id=tds_source_id,
            tds_sha256=AuditLogger.compute_sha256(tds_bytes) if tds_bytes else None,
            source_urls=source_urls,
            extraction_duration_seconds=duration_seconds
        )

    @staticmethod
    def create_label_report(
        product_name: str,
        mode: str,
        template_used: str,
        validation_passed: bool,
        svg_file_id: Optional[str] = None,
        pdf_file_id: Optional[str] = None,
        approver_name: Optional[str] = None,
        approval_date: Optional[str] = None,
        notes: Optional[str] = None
    ) -> LabelBuildReport:
        """Create label build report."""
        return LabelBuildReport(
            product_name=product_name,
            mode=mode,
            generated_timestamp=datetime.utcnow(),
            template_used=template_used,
            svg_file_id=svg_file_id,
            pdf_file_id=pdf_file_id,
            validation_passed=validation_passed,
            approver_name=approver_name,
            approval_date=approval_date,
            notes=notes
        )

    @staticmethod
    def save_audit_trail(
        storage_client,
        product_folder_id: str,
        date_folder: str,
        extraction_meta: ExtractionMeta,
        extracted_data: ExtractedData,
        validation_result: ValidationResult
    ) -> Dict[str, str]:
        """
        Save complete audit trail to the configured storage backend.

        Returns:
            Dictionary of saved artifact IDs
        """
        from datetime import datetime

        # Find or create Extracted/{date} folder
        extracted_folder_id = storage_client.find_subfolder(product_folder_id, "Extracted")
        if not extracted_folder_id:
            raise ValueError("Extracted folder not found")

        dated_folder_id = storage_client.create_dated_folder(extracted_folder_id, date_folder)

        file_ids = {}

        # Save extraction metadata
        meta_id = storage_client.upload_json(
            extraction_meta.model_dump(mode='json'),
            "extraction_meta.json",
            dated_folder_id
        )
        file_ids["extraction_meta"] = meta_id
        logger.info(f"Saved extraction_meta.json: {meta_id}")

        # Save extracted fields
        fields_id = storage_client.upload_json(
            {
                "product": extracted_data.product.model_dump(mode='json'),
                "ghs": extracted_data.ghs.model_dump(mode='json'),
                "transport": extracted_data.transport.model_dump(mode='json')
            },
            "extracted_fields.json",
            dated_folder_id
        )
        file_ids["extracted_fields"] = fields_id
        logger.info(f"Saved extracted_fields.json: {fields_id}")

        # Save evidence
        evidence_id = storage_client.upload_json(
            [e.model_dump(mode='json') for e in extracted_data.evidence],
            "evidence.json",
            dated_folder_id
        )
        file_ids["evidence"] = evidence_id
        logger.info(f"Saved evidence.json: {evidence_id}")

        # Save validation result
        validation_id = storage_client.upload_json(
            validation_result.model_dump(mode='json'),
            "validation.json",
            dated_folder_id
        )
        file_ids["validation"] = validation_id
        logger.info(f"Saved validation.json: {validation_id}")

        return file_ids

    @staticmethod
    def save_label_audit(
        storage_client,
        product_folder_id: str,
        date_folder: str,
        label_report: LabelBuildReport
    ) -> str:
        """Save label build report to the configured storage backend."""
        # Find or create Labels/{date} folder
        labels_folder_id = storage_client.find_subfolder(product_folder_id, "Labels")
        if not labels_folder_id:
            raise ValueError("Labels folder not found")

        dated_folder_id = storage_client.create_dated_folder(labels_folder_id, date_folder)

        # Save report
        report_id = storage_client.upload_json(
            label_report.model_dump(mode='json'),
            "label_build_report.json",
            dated_folder_id
        )
        logger.info(f"Saved label_build_report.json: {report_id}")

        return report_id
