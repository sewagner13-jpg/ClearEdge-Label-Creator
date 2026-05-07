"""
Tests for compliance validation engine.
"""

import pytest

from app.validator import ComplianceValidator
from app.schema import (
    ExtractedData,
    ProductInfo,
    GHSClassification,
    TransportClassification,
    HazardStatement
)


class TestComplianceValidator:
    """Test validation rules."""

    @pytest.fixture
    def validator(self):
        return ComplianceValidator()

    @pytest.fixture
    def minimal_product_data(self):
        return ExtractedData(
            product=ProductInfo(name="Test Product"),
            ghs=GHSClassification(),
            transport=TransportClassification()
        )

    def test_shipped_dot_requires_un_number(self, validator, minimal_product_data):
        """Shipped DOT mode requires UN number."""
        result = validator.validate(minimal_product_data, mode="shipped_dot")

        assert not result.passed
        error_fields = [e.field for e in result.errors]
        assert "transport.un_number" in error_fields

    def test_shipped_dot_requires_shipping_name(self, validator, minimal_product_data):
        """Shipped DOT mode requires proper shipping name."""
        result = validator.validate(minimal_product_data, mode="shipped_dot")

        error_fields = [e.field for e in result.errors]
        assert "transport.proper_shipping_name" in error_fields

    def test_shipped_dot_requires_hazard_class(self, validator, minimal_product_data):
        """Shipped DOT mode requires hazard class."""
        result = validator.validate(minimal_product_data, mode="shipped_dot")

        error_fields = [e.field for e in result.errors]
        assert "transport.hazard_class" in error_fields

    def test_shipped_dot_valid_data(self, validator):
        """Valid shipped DOT data passes validation."""
        data = ExtractedData(
            product=ProductInfo(name="Acetone"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="UN1090",
                proper_shipping_name="Acetone",
                hazard_class="3"
            )
        )

        result = validator.validate(data, mode="shipped_dot")
        assert result.passed is True

    def test_shipped_dot_not_regulated_transport_passes_without_dot_fields(self, validator):
        """Products explicitly not regulated for transport should not require UN/DOT fields."""
        data = ExtractedData(
            product=ProductInfo(name="ClearEdge PSA 336"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                not_regulated=True,
                proper_shipping_name="Not regulated for DOT transport"
            )
        )

        result = validator.validate(data, mode="shipped_dot")
        assert result.passed is True
        error_fields = [e.field for e in result.errors]
        assert "transport.un_number" not in error_fields
        assert "transport.proper_shipping_name" not in error_fields
        assert "transport.hazard_class" not in error_fields

    def test_shipped_dot_not_dangerous_goods_phrase_passes_without_dot_fields(self, validator):
        """Section 14 wording can prove the transport state even without the boolean flag."""
        data = ExtractedData(
            product=ProductInfo(name="ClearEdge Product"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                proper_shipping_name="Not dangerous goods"
            )
        )

        result = validator.validate(data, mode="shipped_dot")
        assert result.passed is True

    def test_missing_packing_group_warning(self, validator):
        """Missing packing group generates warning."""
        data = ExtractedData(
            product=ProductInfo(name="Test"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="UN1090",
                proper_shipping_name="Acetone",
                hazard_class="3"
                # No packing_group
            )
        )

        result = validator.validate(data, mode="shipped_dot")
        warning_fields = [w.field for w in result.warnings]
        assert "transport.packing_group" in warning_fields

    def test_workplace_mode_minimal(self, validator, minimal_product_data):
        """Workplace mode is more lenient."""
        result = validator.validate(minimal_product_data, mode="workplace")

        # Should pass with just product name
        assert result.passed is True

    def test_pictogram_overlap_warning(self, validator):
        """DOT/GHS pictogram overlap generates warning."""
        data = ExtractedData(
            product=ProductInfo(name="Flammable Liquid"),
            ghs=GHSClassification(
                signal_word="Danger",
                pictograms=["GHS02"]  # Flammable - overlaps with class 3
            ),
            transport=TransportClassification(
                un_number="UN1090",
                proper_shipping_name="Acetone",
                hazard_class="3"  # Flammable liquid
            )
        )

        result = validator.validate(data, mode="shipped_dot")

        # Should have warning about pictogram overlap
        warning_messages = [w.message for w in result.warnings]
        overlap_warnings = [m for m in warning_messages if "overlap" in m.lower()]
        assert len(overlap_warnings) > 0

    def test_invalid_mode(self, validator, minimal_product_data):
        """Invalid mode generates error."""
        result = validator.validate(minimal_product_data, mode="invalid_mode")

        assert not result.passed
        error_messages = [e.message for e in result.errors]
        assert any("Invalid validation mode" in m for m in error_messages)

    def test_validate_pictogram_code(self, validator):
        """Test pictogram code validation."""
        assert validator.validate_pictogram_code("GHS01") is True
        assert validator.validate_pictogram_code("GHS09") is True
        assert validator.validate_pictogram_code("GHS10") is False
        assert validator.validate_pictogram_code("INVALID") is False
