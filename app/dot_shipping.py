"""DOT highway shipping review helpers.

This module does not replace hazmat training or carrier review. It keeps the
app honest about what the generated product label can and cannot prove.
"""

from __future__ import annotations

from typing import Optional

from .dot_sticker_sheet import dot_label_name_for_class, normalize_dot_hazard_class
from .schema import ExtractedData


NOT_REGULATED_MARKERS = (
    "not regulated",
    "not restricted",
    "not dangerous goods",
    "not classified as dangerous",
    "not classified as a dangerous good",
    "not hazardous for transport",
    "not subject to dot",
    "non-regulated",
    "non regulated",
)

NON_BULK_CONTAINERS = {"pail", "drum"}
BULK_CONTAINERS = {"tote"}


def build_dot_shipping_review(data: ExtractedData, mode: str) -> dict:
    """Return operator-facing DOT highway package review metadata."""
    if mode != "shipped_dot":
        return {
            "applicable": False,
            "status": "not_applicable",
            "container_type": data.shipment.container_type,
            "package_category": None,
            "dot_exception_status": "not_applicable",
            "separate_dot_sticker_required": False,
            "required_stickers": [],
            "blockers": [],
            "warnings": [],
            "required_actions": [],
        }

    container_type = data.shipment.container_type
    package_category = package_category_for_container(container_type)
    not_regulated = is_not_regulated_for_transport(data)
    combustible_liquid = is_combustible_liquid(data)

    blockers = []
    warnings = []
    required_actions = []
    dot_exception_status = "not_regulated" if not_regulated else "regulated"

    if not_regulated:
        return {
            "applicable": True,
            "status": "not_regulated",
            "container_type": container_type,
            "package_category": package_category,
            "dot_exception_status": dot_exception_status,
            "separate_dot_sticker_required": False,
            "required_stickers": [],
            "blockers": [],
            "warnings": [],
            "required_actions": [],
        }

    if package_category == "unknown":
        blockers.append({
            "code": "CONFIRM_CONTAINER_TYPE",
            "field": "shipment.container_type",
            "message": (
                "Fill amount or container type is required so the app can decide "
                "whether this is a pail, drum, or tote before calling the shipped label ready."
            ),
        })

    if combustible_liquid and package_category == "non_bulk":
        unknown_exception_facts = [
            field
            for field, value in (
                ("transport.marine_pollutant", data.transport.marine_pollutant),
                ("transport.hazardous_substance", data.transport.hazardous_substance),
                ("transport.hazardous_waste", data.transport.hazardous_waste),
            )
            if value is None
        ]
        if unknown_exception_facts:
            dot_exception_status = "needs_review"
            blockers.append({
                "code": "CONFIRM_COMBUSTIBLE_LIQUID_EXCEPTION",
                "field": "transport.combustible_liquid_exception",
                "message": (
                    "This appears to be a non-bulk combustible liquid. Confirm whether it is a "
                    "marine pollutant, hazardous substance, or hazardous waste before deciding "
                    "whether the domestic highway combustible-liquid exception applies."
                ),
                "missing_fields": unknown_exception_facts,
            })
        elif not (
            data.transport.marine_pollutant
            or data.transport.hazardous_substance
            or data.transport.hazardous_waste
        ):
            dot_exception_status = "combustible_liquid_non_bulk_exception_possible"
            warnings.append({
                "code": "COMBUSTIBLE_LIQUID_NON_BULK_EXCEPTION_POSSIBLE",
                "field": "transport.combustible_liquid_exception",
                "message": (
                    "This non-bulk combustible liquid may qualify for the domestic highway "
                    "combustible-liquid exception. The sticker sheet is generated because a DOT "
                    "hazard class is shown; confirm the final exterior marking decision before shipment."
                ),
            })

    regulated_for_label_actions = (
        not blockers
        and dot_exception_status != "not_regulated"
    )
    regulated_for_sticker_generation = dot_exception_status != "not_regulated"

    required_stickers = []
    if regulated_for_sticker_generation and data.transport.hazard_class:
        required_stickers.extend(_required_dot_stickers(data))
        required_actions.append({
            "code": "APPLY_SEPARATE_DOT_HAZARD_LABEL",
            "field": "transport.dot_hazard_label",
            "message": (
                "Apply separate DOT hazard label sticker(s) for hazard class "
                f"{_format_hazard_classes(required_stickers) or data.transport.hazard_class} on the package."
            ),
        })

    if regulated_for_label_actions and package_category == "bulk":
        required_actions.append({
            "code": "BULK_PACKAGE_MARKING_REVIEW",
            "field": "shipment.container_type",
            "message": (
                "Tote/bulk packaging needs DOT ID-number marking/placard review. "
                "The product label alone is not the complete exterior DOT marking set."
            ),
        })

    if regulated_for_label_actions and data.transport.marine_pollutant is True:
        required_actions.append({
            "code": "MARINE_POLLUTANT_MARK_REVIEW",
            "field": "transport.marine_pollutant",
            "message": "Marine pollutant marking may be required; confirm against the shipment mode and SDS.",
        })

    if regulated_for_label_actions and _truthy_limited_quantity(data.transport.limited_quantity):
        required_actions.append({
            "code": "LIMITED_QUANTITY_MARK_REVIEW",
            "field": "transport.limited_quantity",
            "message": "Limited quantity marking/exception status must be confirmed before shipment.",
        })

    if regulated_for_label_actions and data.transport.special_provisions:
        required_actions.append({
            "code": "SPECIAL_PROVISIONS_REVIEW",
            "field": "transport.special_provisions",
            "message": "DOT special provisions are listed; review them before releasing the shipment.",
        })

    status = "blocked" if blockers else "ready"
    if status == "ready" and required_actions:
        status = "ready_with_external_markings"
    elif status == "ready" and dot_exception_status == "combustible_liquid_non_bulk_exception_possible":
        status = "exception_possible"

    return {
        "applicable": True,
        "status": status,
        "container_type": container_type,
        "package_category": package_category,
        "dot_exception_status": dot_exception_status,
        "separate_dot_sticker_required": bool(required_stickers),
        "required_stickers": required_stickers,
        "blockers": blockers,
        "warnings": warnings,
        "required_actions": required_actions,
    }


def package_category_for_container(container_type: Optional[str]) -> str:
    """Classify the selected container into broad DOT package categories."""
    normalized = (container_type or "").strip().lower()
    if normalized in NON_BULK_CONTAINERS:
        return "non_bulk"
    if normalized in BULK_CONTAINERS:
        return "bulk"
    return "unknown"


def is_not_regulated_for_transport(data: ExtractedData) -> bool:
    """Return true when Section 14 or operator input proves transport is not regulated."""
    transport = data.transport
    if transport.not_regulated is True:
        return True

    fields = (
        transport.proper_shipping_name,
        transport.hazard_class,
        transport.un_number,
        transport.special_provisions,
    )
    joined = " ".join(str(field).lower() for field in fields if field)
    return any(marker in joined for marker in NOT_REGULATED_MARKERS)


def is_combustible_liquid(data: ExtractedData) -> bool:
    """Return true for Section 14 combustible liquid descriptions."""
    transport = data.transport
    values = " ".join(
        str(value).lower()
        for value in (
            transport.proper_shipping_name,
            transport.hazard_class,
            transport.special_provisions,
        )
        if value
    )
    return "combustible liquid" in values


def _required_dot_stickers(data: ExtractedData) -> list[dict]:
    stickers = []
    seen = set()

    def add_sticker(raw_class: str | None, source: str) -> None:
        normalized = normalize_dot_hazard_class(raw_class)
        if not normalized:
            return
        key = (normalized, source)
        if key in seen:
            return
        seen.add(key)
        stickers.append({
            "hazard_class": normalized,
            "label_name": dot_label_name_for_class(normalized) or f"Class {normalized}",
            "asset_key": normalized,
            "source": source,
            "quantity": 1,
        })

    add_sticker(data.transport.hazard_class, "primary")
    for subsidiary_class in data.transport.subsidiary_hazard_classes:
        add_sticker(subsidiary_class, "subsidiary")
    return stickers


def _format_hazard_classes(stickers: list[dict]) -> str:
    if not stickers:
        return ""
    return ", ".join(
        f"{sticker.get('hazard_class')} ({sticker.get('source')})"
        for sticker in stickers
        if sticker.get("hazard_class")
    )


def _truthy_limited_quantity(value: Optional[str]) -> bool:
    if value is None:
        return False
    cleaned = str(value).strip().lower()
    return bool(cleaned) and cleaned not in {
        "no",
        "none",
        "not applicable",
        "n/a",
        "na",
        "not listed",
        "void",
    }
