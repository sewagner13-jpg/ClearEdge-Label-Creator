"""
Compliance validation engine for DOT/OSHA/GHS requirements.
Validates extracted data against mode-specific rules.
"""

import logging
from typing import List

from .schema import (
    ExtractedData,
    ValidationResult,
    ValidationError
)

logger = logging.getLogger(__name__)


class ComplianceValidator:
    """Validates extracted data for compliance with DOT/OSHA/GHS requirements."""

    # GHS pictograms that overlap with DOT hazard classes
    DOT_GHS_OVERLAP = {
        "3": ["GHS02"],  # Flammable liquid -> Flammable
        "2.1": ["GHS02"],  # Flammable gas -> Flammable
        "5.1": ["GHS03"],  # Oxidizer -> Oxidizing
        "6.1": ["GHS06"],  # Toxic -> Acute toxicity
        "8": ["GHS05"],  # Corrosive -> Corrosive
    }

    def validate(
        self,
        data: ExtractedData,
        mode: str = "shipped_dot"
    ) -> ValidationResult:
        """
        Validate extracted data for compliance.

        Args:
            data: Extracted product data
            mode: "shipped_dot" or "workplace"

        Returns:
            ValidationResult with errors and warnings
        """
        errors: List[ValidationError] = []
        warnings: List[ValidationError] = []

        # Common validations
        if not data.product.name:
            errors.append(ValidationError(
                field="product.name",
                message="Product name is required",
                severity="error"
            ))

        is_valid_mode = mode in {"shipped_dot", "workplace"}
        normalized_mode = mode if is_valid_mode else "shipped_dot"

        if not is_valid_mode:
            errors.append(ValidationError(
                field="mode",
                message=f"Invalid validation mode: {mode}",
                severity="error"
            ))

        # Mode-specific validations
        if normalized_mode == "shipped_dot":
            self._validate_shipping(data, errors, warnings)
        elif normalized_mode == "workplace":
            self._validate_workplace(data, errors, warnings)
        # Check for DOT/GHS pictogram overlap
        if normalized_mode == "shipped_dot" and data.transport.hazard_class:
            self._check_pictogram_overlap(data, warnings)

        passed = len(errors) == 0

        return ValidationResult(
            mode=normalized_mode,
            passed=passed,
            errors=errors,
            warnings=warnings
        )

    def _validate_shipping(
        self,
        data: ExtractedData,
        errors: List[ValidationError],
        warnings: List[ValidationError]
    ):
        """Validate for shipped DOT compliance."""
        # Critical DOT fields
        if not data.transport.un_number:
            errors.append(ValidationError(
                field="transport.un_number",
                message="UN number is required for shipped products",
                severity="error"
            ))

        if not data.transport.proper_shipping_name:
            errors.append(ValidationError(
                field="transport.proper_shipping_name",
                message="Proper shipping name is required for DOT compliance",
                severity="error"
            ))

        if not data.transport.hazard_class:
            errors.append(ValidationError(
                field="transport.hazard_class",
                message="Hazard class is required for DOT compliance",
                severity="error"
            ))

        # Packing group warning (required for most but not all)
        if not data.transport.packing_group:
            warnings.append(ValidationError(
                field="transport.packing_group",
                message="Packing group is missing (may be required depending on hazard class)",
                severity="warning"
            ))

        # Emergency contact
        if not data.product.emergency_phone:
            warnings.append(ValidationError(
                field="product.emergency_phone",
                message="Emergency phone number recommended for shipping labels",
                severity="warning"
            ))

    def _validate_workplace(
        self,
        data: ExtractedData,
        errors: List[ValidationError],
        warnings: List[ValidationError]
    ):
        """Validate for workplace label compliance."""
        # GHS requirements
        if data.ghs.hazard_statements and not data.ghs.signal_word:
            warnings.append(ValidationError(
                field="ghs.signal_word",
                message="Signal word recommended when hazard statements are present",
                severity="warning"
            ))

        if data.ghs.signal_word and not data.ghs.pictograms:
            warnings.append(ValidationError(
                field="ghs.pictograms",
                message="GHS pictograms recommended when signal word is present",
                severity="warning"
            ))

        # Supplier information
        if not data.product.supplier_name:
            warnings.append(ValidationError(
                field="product.supplier_name",
                message="Supplier name recommended for workplace labels",
                severity="warning"
            ))

    def _check_pictogram_overlap(
        self,
        data: ExtractedData,
        warnings: List[ValidationError]
    ):
        """Check for DOT/GHS pictogram overlap and warn user."""
        hazard_class = data.transport.hazard_class
        if not hazard_class:
            return

        # Check if this hazard class overlaps with GHS pictograms
        overlapping_ghs = self.DOT_GHS_OVERLAP.get(hazard_class, [])
        if not overlapping_ghs:
            return

        # Check if any overlapping pictograms are present
        present_overlap = [
            p for p in data.ghs.pictograms
            if p in overlapping_ghs
        ]

        if present_overlap:
            warnings.append(ValidationError(
                field="ghs.pictograms",
                message=(
                    f"DOT hazard class {hazard_class} overlaps with GHS pictograms "
                    f"{', '.join(present_overlap)}. Consider removing GHS pictograms "
                    "to avoid confusion on shipping labels."
                ),
                severity="warning"
            ))

    def validate_pictogram_code(self, code: str) -> bool:
        """Check if pictogram code is valid."""
        try:
            num = int(code.replace("GHS", ""))
            return 1 <= num <= 9
        except (ValueError, AttributeError):
            return False
