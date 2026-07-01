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
from .dot_shipping import build_dot_shipping_review, is_not_regulated_for_transport

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
    SUPPORTED_DOT_LABEL_CLASSES = {"3", "8", "9"}

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
        shipping_review = build_dot_shipping_review(data, "shipped_dot")
        for blocker in shipping_review.get("blockers") or []:
            errors.append(ValidationError(
                field=blocker.get("field") or "transport",
                message=blocker.get("message") or "DOT shipping review requires correction",
                severity="error",
            ))
        for warning in shipping_review.get("warnings") or []:
            warnings.append(ValidationError(
                field=warning.get("field") or "transport",
                message=warning.get("message") or "DOT shipping review warning",
                severity="warning",
            ))
        for action in shipping_review.get("required_actions") or []:
            warnings.append(ValidationError(
                field=action.get("field") or "transport",
                message=action.get("message") or "DOT shipping action is required outside this product label",
                severity="warning",
            ))

        if is_not_regulated_for_transport(data):
            if not data.product.emergency_phone:
                warnings.append(ValidationError(
                    field="product.emergency_phone",
                    message="Emergency phone number recommended for shipping labels",
                    severity="warning"
                ))
            return

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
        elif self._shipping_name_needs_technical_name(data.transport.proper_shipping_name):
            errors.append(ValidationError(
                field="transport.proper_shipping_name",
                message=(
                    "Proper shipping names using n.o.s. must include the SDS-listed "
                    "technical name in parentheses before the label can be downloaded"
                ),
                severity="error"
            ))

        if not data.transport.hazard_class:
            errors.append(ValidationError(
                field="transport.hazard_class",
                message="Hazard class is required for DOT compliance",
                severity="error"
            ))
        else:
            normalized_hazard_class = self._normalize_hazard_class(data.transport.hazard_class)
            if not normalized_hazard_class:
                errors.append(ValidationError(
                    field="transport.hazard_class",
                    message="Hazard class could not be recognized for DOT label selection",
                    severity="error"
                ))
            elif normalized_hazard_class not in self.SUPPORTED_DOT_LABEL_CLASSES:
                errors.append(ValidationError(
                    field="transport.hazard_class",
                    message=(
                        f"DOT hazard label asset is not available for hazard class "
                        f"{data.transport.hazard_class}. Add the required DOT label asset "
                        "before downloading this shipped label."
                    ),
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

    @staticmethod
    def _normalize_hazard_class(hazard_class: str | None) -> str | None:
        """Normalize DOT hazard class wording for supported-label checks."""
        if not hazard_class:
            return None
        clean = str(hazard_class).strip().lower()
        if "not regulated" in clean or "not applicable" in clean:
            return None
        if clean.startswith("class "):
            clean = clean[6:]
        for candidate in ("6.1", "5.1", "5.2", "2.1", "2.2", "2.3", "4.1", "4.2", "4.3"):
            if candidate in clean:
                return candidate
        for char in clean:
            if char.isdigit():
                return char
        return None

    @staticmethod
    def _shipping_name_needs_technical_name(proper_shipping_name: str | None) -> bool:
        """Return true when an n.o.s. shipping name is missing parenthetical detail."""
        if not proper_shipping_name:
            return False
        clean = str(proper_shipping_name).lower()
        has_nos = "n.o.s" in clean or " n.o.s." in clean
        has_parenthetical_detail = "(" in str(proper_shipping_name) and ")" in str(proper_shipping_name)
        return has_nos and not has_parenthetical_detail

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
        hazard_class = self._normalize_hazard_class(data.transport.hazard_class)
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
