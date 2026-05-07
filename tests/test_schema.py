"""
Tests for Pydantic schema validation and enforcement.
"""

import pytest
from pydantic import ValidationError

from app.schema import (
    GHS_PICTOGRAM_OPTIONS,
    HazardStatement,
    PrecautionaryStatement,
    GHSClassification,
    TransportClassification,
    NFPA704Ratings,
    ProductInfo,
    ShipmentInfo,
    ExtractedData,
    Evidence,
    ValidationResult,
    ValidationError as SchemaValidationError
)


class TestHazardStatement:
    """Test HazardStatement schema."""

    def test_valid_statement_with_code(self):
        stmt = HazardStatement(code="H225", text="Highly flammable liquid and vapor")
        assert stmt.code == "H225"
        assert stmt.text == "Highly flammable liquid and vapor"

    def test_valid_statement_without_code(self):
        stmt = HazardStatement(code=None, text="May cause drowsiness")
        assert stmt.code is None
        assert stmt.text == "May cause drowsiness"

    def test_empty_code_becomes_none(self):
        stmt = HazardStatement(code="", text="Some text")
        assert stmt.code is None

    def test_invalid_empty_text(self):
        with pytest.raises(ValidationError):
            HazardStatement(code="H225", text="")


class TestGHSClassification:
    """Test GHS classification schema."""

    def test_valid_ghs_data(self):
        ghs = GHSClassification(
            signal_word="Danger",
            pictograms=["GHS02", "GHS07"],
            hazard_statements=[
                HazardStatement(code="H225", text="Highly flammable liquid")
            ]
        )
        assert ghs.signal_word == "Danger"
        assert len(ghs.pictograms) == 2

    def test_invalid_pictogram_code(self):
        with pytest.raises(ValidationError):
            GHSClassification(pictograms=["GHS99"])

    def test_duplicate_pictograms_removed(self):
        ghs = GHSClassification(pictograms=["GHS02", "GHS02", "GHS07"])
        assert len(ghs.pictograms) == 2
        assert ghs.pictograms == ["GHS02", "GHS07"]

    def test_pictogram_dropdown_names_map_to_codes(self):
        ghs = GHSClassification(
            pictograms=["Corrosive", "Exclamation Point", "Corrosive"]
        )
        assert ghs.pictograms == ["GHS05", "GHS07"]

    def test_pictogram_option_table_has_all_codes(self):
        assert GHS_PICTOGRAM_OPTIONS == {
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

    def test_invalid_signal_word(self):
        with pytest.raises(ValidationError):
            GHSClassification(signal_word="Caution")  # Must be Danger or Warning


class TestTransportClassification:
    """Test transport classification schema."""

    def test_valid_transport_data(self):
        transport = TransportClassification(
            un_number="UN1090",
            proper_shipping_name="Acetone",
            hazard_class="3",
            packing_group="II"
        )
        assert transport.un_number == "UN1090"
        assert transport.packing_group == "II"

    def test_invalid_packing_group(self):
        with pytest.raises(ValidationError):
            TransportClassification(packing_group="IV")

    def test_all_optional_fields_none(self):
        transport = TransportClassification()
        assert transport.un_number is None
        assert transport.hazard_class is None


class TestNFPA704Ratings:
    """Test NFPA 704 rating schema."""

    def test_defaults_missing_ratings_to_zero(self):
        nfpa = NFPA704Ratings()
        assert nfpa.health == 0
        assert nfpa.flammability == 0
        assert nfpa.instability == 0
        assert nfpa.special is None

    def test_valid_nfpa_ratings(self):
        nfpa = NFPA704Ratings(health=2, flammability=3, instability=1, special="ox")
        assert nfpa.health == 2
        assert nfpa.flammability == 3
        assert nfpa.instability == 1
        assert nfpa.special == "OX"

    def test_reactivity_alias_maps_to_instability(self):
        nfpa = NFPA704Ratings(health=1, flammability=2, reactivity=3)
        assert nfpa.instability == 3

    def test_invalid_rating_above_four(self):
        with pytest.raises(ValidationError):
            NFPA704Ratings(health=5)


class TestShipmentInfo:
    """Test operator-provided shipment field schema."""

    def test_optional_shipment_fields(self):
        shipment = ShipmentInfo(fill_amount="441 lb")
        assert shipment.fill_amount == "441 lb"
        assert shipment.lot_number is None
        assert shipment.expiration_date is None


class TestExtractedData:
    """Test complete extracted data schema."""

    def test_valid_complete_data(self):
        data = ExtractedData(
            product=ProductInfo(
                name="Test Product",
                supplier_name="Test Supplier"
            ),
            ghs=GHSClassification(
                signal_word="Warning",
                pictograms=["GHS07"]
            ),
            transport=TransportClassification(
                un_number="UN1234"
            ),
            evidence=[
                Evidence(
                    field_path="product.name",
                    doc="SDS",
                    section="Section 1",
                    page=1,
                    quote="Product Name: Test Product"
                )
            ]
        )

        assert data.product.name == "Test Product"
        assert len(data.evidence) == 1

    def test_evidence_quote_max_length(self):
        """Evidence quotes must be ≤240 chars."""
        with pytest.raises(ValidationError):
            Evidence(
                field_path="test",
                doc="SDS",
                quote="x" * 241  # Too long
            )


class TestValidationResult:
    """Test validation result schema."""

    def test_validation_passed(self):
        result = ValidationResult(
            mode="shipped_dot",
            passed=True,
            errors=[],
            warnings=[]
        )
        assert result.passed is True
        assert len(result.errors) == 0

    def test_validation_with_errors(self):
        result = ValidationResult(
            mode="workplace",
            passed=False,
            errors=[
                SchemaValidationError(
                    field="product.name",
                    message="Required field missing",
                    severity="error"
                )
            ]
        )
        assert result.passed is False
        assert len(result.errors) == 1
        assert result.errors[0].severity == "error"
