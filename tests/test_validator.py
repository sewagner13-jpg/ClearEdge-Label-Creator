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
    HazardStatement,
    ShipmentInfo,
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
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="UN1090",
                proper_shipping_name="Acetone",
                hazard_class="3"
            )
        )

        result = validator.validate(data, mode="shipped_dot")
        assert result.passed is True

    def test_shipped_dot_requires_container_type_for_regulated_package(self, validator):
        """Regulated shipped labels must know the package type before being ready."""
        data = ExtractedData(
            product=ProductInfo(name="Acetone"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="UN1090",
                proper_shipping_name="Acetone",
                hazard_class="3",
                packing_group="II",
            )
        )

        result = validator.validate(data, mode="shipped_dot")

        assert result.passed is False
        assert any(error.field == "shipment.container_type" for error in result.errors)

    def test_shipped_dot_warns_to_apply_separate_dot_sticker_when_regulated(self, validator):
        """The product label can pass while instructing operators to apply DOT stickers separately."""
        data = ExtractedData(
            product=ProductInfo(name="Acetone"),
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="UN1090",
                proper_shipping_name="Acetone",
                hazard_class="3",
                packing_group="II",
            )
        )

        result = validator.validate(data, mode="shipped_dot")

        assert result.passed is True
        assert any(
            warning.field == "transport.dot_hazard_label"
            and "separate DOT hazard label sticker" in warning.message
            for warning in result.warnings
        )

    def test_combustible_liquid_non_bulk_requires_exception_facts(self, validator):
        """Combustible-liquid exception review needs haz substance/waste/marine facts."""
        data = ExtractedData(
            product=ProductInfo(name="Combustible Blend"),
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="NA1993",
                proper_shipping_name="COMBUSTIBLE LIQUID, N.O.S. (glycol ether)",
                hazard_class="3",
                packing_group="III",
            )
        )

        result = validator.validate(data, mode="shipped_dot")

        assert result.passed is False
        assert any(error.field == "transport.combustible_liquid_exception" for error in result.errors)

    def test_combustible_liquid_non_bulk_passes_when_exception_facts_are_known(self, validator):
        """Known non-bulk combustible exception facts should not block the label."""
        data = ExtractedData(
            product=ProductInfo(name="Combustible Blend"),
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="NA1993",
                proper_shipping_name="COMBUSTIBLE LIQUID, N.O.S. (glycol ether)",
                hazard_class="3",
                packing_group="III",
                marine_pollutant=False,
                hazardous_substance=False,
                hazardous_waste=False,
            )
        )

        result = validator.validate(data, mode="shipped_dot")

        assert result.passed is True
        assert any(
            warning.field == "transport.combustible_liquid_exception"
            and "may qualify" in warning.message
            for warning in result.warnings
        )

    def test_shipped_dot_blocks_unsupported_dot_hazard_label_asset(self, validator):
        """Shipped DOT labels must have a supported DOT hazard label asset."""
        data = ExtractedData(
            product=ProductInfo(name="Toxic Liquid"),
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="UN2810",
                proper_shipping_name="Toxic liquid, organic, n.o.s. (aniline)",
                hazard_class="6.1",
                packing_group="II",
            )
        )

        result = validator.validate(data, mode="shipped_dot")

        assert result.passed is False
        assert any(
            error.field == "transport.hazard_class"
            and "DOT hazard label asset is not available" in error.message
            for error in result.errors
        )

    def test_shipped_dot_blocks_nos_shipping_name_without_technical_name(self, validator):
        """N.O.S. shipping names need parenthetical technical detail before download."""
        data = ExtractedData(
            product=ProductInfo(name="Flammable Blend"),
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="UN1993",
                proper_shipping_name="Flammable liquids, n.o.s.",
                hazard_class="3",
                packing_group="II",
            )
        )

        result = validator.validate(data, mode="shipped_dot")

        assert result.passed is False
        assert any(
            error.field == "transport.proper_shipping_name"
            and "technical name" in error.message
            for error in result.errors
        )

    def test_shipped_dot_accepts_supported_hazard_label_asset_with_class_wording(self, validator):
        """Supported DOT hazard classes can be extracted as words like 'Class 8'."""
        data = ExtractedData(
            product=ProductInfo(name="Corrosive Liquid"),
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="UN1760",
                proper_shipping_name="Corrosive liquid, n.o.s. (sodium hydroxide)",
                hazard_class="Class 8",
                packing_group="II",
            )
        )

        result = validator.validate(data, mode="shipped_dot")

        assert result.passed is True

    def test_shipped_dot_supported_subsidiary_hazard_class_is_required_sticker_not_blocker(self, validator):
        """Supported subsidiary hazard classes should become additional sticker metadata."""
        data = ExtractedData(
            product=ProductInfo(name="Flammable Corrosive Liquid"),
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="UN2924",
                proper_shipping_name="Flammable liquid, corrosive, n.o.s. (solvent, acid)",
                hazard_class="3",
                subsidiary_hazard_classes=["8"],
                packing_group="II",
            )
        )

        result = validator.validate(data, mode="shipped_dot")

        assert result.passed is True
        assert not any(error.field == "transport.subsidiary_hazard_classes" for error in result.errors)

    def test_shipped_dot_blocks_unsupported_subsidiary_hazard_label_asset(self, validator):
        """Subsidiary hazard stickers must also use approved DOT assets."""
        data = ExtractedData(
            product=ProductInfo(name="Flammable Toxic Liquid"),
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
            ghs=GHSClassification(),
            transport=TransportClassification(
                un_number="UN1992",
                proper_shipping_name="Flammable liquid, toxic, n.o.s. (solvent, aniline)",
                hazard_class="3",
                subsidiary_hazard_classes=["6.1"],
                packing_group="II",
            )
        )

        result = validator.validate(data, mode="shipped_dot")

        assert result.passed is False
        assert any(
            error.field == "transport.subsidiary_hazard_classes"
            and "DOT hazard label asset is not available" in error.message
            for error in result.errors
        )

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
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
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
            shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
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
