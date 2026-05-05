"""
Tests for audit trail system.
"""

import pytest
from datetime import datetime

from app.audit import AuditLogger
from app.schema import (
    ExtractionMeta,
    LabelBuildReport
)


class TestAuditLogger:
    """Test audit logging functionality."""

    def test_compute_sha256(self):
        """Test SHA-256 hash computation."""
        data = b"test data"
        hash1 = AuditLogger.compute_sha256(data)
        hash2 = AuditLogger.compute_sha256(data)

        # Same data should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 is 64 hex characters

        # Different data should produce different hash
        hash3 = AuditLogger.compute_sha256(b"different data")
        assert hash1 != hash3

    def test_create_extraction_meta(self):
        """Test extraction metadata creation."""
        meta = AuditLogger.create_extraction_meta(
            product_name="Test Product",
            ai_model="gpt-4o",
            sds_source_id="file123",
            sds_bytes=b"test sds data",
            duration_seconds=45.2
        )

        assert isinstance(meta, ExtractionMeta)
        assert meta.product_name == "Test Product"
        assert meta.ai_model == "gpt-4o"
        assert meta.sds_source_id == "file123"
        assert meta.sds_sha256 is not None
        assert len(meta.sds_sha256) == 64
        assert meta.extraction_duration_seconds == 45.2

    def test_create_extraction_meta_with_urls(self):
        """Test extraction metadata with source URLs."""
        meta = AuditLogger.create_extraction_meta(
            product_name="Web Product",
            ai_model="gpt-4o",
            source_urls=["https://example.com/sds.pdf"]
        )

        assert meta.source_urls == ["https://example.com/sds.pdf"]

    def test_create_label_report(self):
        """Test label build report creation."""
        report = AuditLogger.create_label_report(
            product_name="Test Product",
            mode="shipped_dot",
            template_used="default",
            validation_passed=True,
            svg_file_id="svg123",
            pdf_file_id="pdf456",
            approver_name="John Doe",
            approval_date="2024-01-15"
        )

        assert isinstance(report, LabelBuildReport)
        assert report.product_name == "Test Product"
        assert report.mode == "shipped_dot"
        assert report.validation_passed is True
        assert report.svg_file_id == "svg123"
        assert report.pdf_file_id == "pdf456"
        assert report.approver_name == "John Doe"

    def test_timestamps_are_set(self):
        """Test that timestamps are automatically set."""
        meta = AuditLogger.create_extraction_meta(
            product_name="Test",
            ai_model="test-model"
        )

        assert isinstance(meta.extraction_timestamp, datetime)

        report = AuditLogger.create_label_report(
            product_name="Test",
            mode="workplace",
            template_used="default",
            validation_passed=True
        )

        assert isinstance(report.generated_timestamp, datetime)
