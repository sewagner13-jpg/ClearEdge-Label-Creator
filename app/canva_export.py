"""Canva handoff helpers for generated label data."""

import json
from typing import List, Optional

from .schema import GHS_PICTOGRAM_OPTIONS, normalize_ghs_pictogram


def canva_urls(label_id: str, available: bool) -> dict:
    """Return Canva handoff URLs only when export is allowed."""
    if not available:
        return {"canva_csv_url": None, "canva_json_url": None}
    return {
        "canva_csv_url": f"/api/v1/labels/{label_id}/canva-export.csv",
        "canva_json_url": f"/api/v1/labels/{label_id}/canva-export.json",
    }


def clean_operator_field(value: Optional[str]) -> Optional[str]:
    """Normalize optional operator-entered shipment fields."""
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def parse_ghs_pictogram_selection(value: Optional[str]) -> List[str]:
    """Parse optional operator-selected GHS pictogram dropdown values."""
    cleaned = clean_operator_field(value)
    if not cleaned:
        return []

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = cleaned

    if isinstance(parsed, str):
        raw_values = [
            item.strip()
            for item in parsed.replace("|", ",").replace(";", ",").split(",")
            if item.strip()
        ]
    elif isinstance(parsed, list):
        raw_values = parsed
    else:
        raise ValueError("GHS pictograms must be a list or comma-separated string")

    deduped = []
    seen = set()
    for raw_value in raw_values:
        code = normalize_ghs_pictogram(str(raw_value))
        if code not in seen:
            deduped.append(code)
            seen.add(code)
    return deduped


def build_canva_export(extracted: dict, metadata: dict) -> dict:
    """Create a flat, Canva Bulk Create-friendly label data record."""
    product = extracted.get("product") or {}
    ghs = extracted.get("ghs") or {}
    transport = extracted.get("transport") or {}
    nfpa = extracted.get("nfpa") or {}
    shipment = extracted.get("shipment") or {}
    return {
        "product_name": metadata.get("product_name") or product.get("name") or "",
        "label_mode": metadata.get("mode") or "",
        "label_size": metadata.get("size") or "",
        "lot_number": shipment.get("lot_number") or "",
        "expiration_date": shipment.get("expiration_date") or "",
        "fill_amount": shipment.get("fill_amount") or "",
        "manufacture_date": shipment.get("manufacture_date") or "",
        "supplier_name": product.get("supplier_name") or "",
        "supplier_address": product.get("supplier_address") or "",
        "supplier_phone": product.get("supplier_phone") or "",
        "emergency_phone": product.get("emergency_phone") or "",
        "sds_revision_date": product.get("revision_date") or "",
        "signal_word": ghs.get("signal_word") or "",
        "ghs_pictograms": ", ".join(ghs.get("pictograms") or []),
        "ghs_pictogram_names": _ghs_pictogram_names(ghs.get("pictograms") or []),
        "hazard_statements": _format_statement_list(ghs.get("hazard_statements") or []),
        "precautionary_statements": _format_statement_list(ghs.get("precautionary_statements") or []),
        "supplemental_statements": " | ".join(ghs.get("supplemental_statements") or []),
        "un_number": transport.get("un_number") or "",
        "transport_not_regulated": str(bool(transport.get("not_regulated"))),
        "proper_shipping_name": transport.get("proper_shipping_name") or "",
        "hazard_class": transport.get("hazard_class") or "",
        "dot_hazard_label": dot_hazard_label_name(transport.get("hazard_class")),
        "packing_group": transport.get("packing_group") or "",
        "marine_pollutant": _optional_value(transport.get("marine_pollutant")),
        "limited_quantity": _optional_value(transport.get("limited_quantity")),
        "special_provisions": " | ".join(transport.get("special_provisions") or []),
        "erg_guide_number": transport.get("erg_guide_number") or "",
        "nfpa_health": str(nfpa.get("health", 0)),
        "nfpa_flammability": str(nfpa.get("flammability", 0)),
        "nfpa_instability": str(nfpa.get("instability", 0)),
        "nfpa_special": nfpa.get("special") or "",
        "validation_status": metadata.get("status") or "",
        "override_approved": str(bool(metadata.get("override_approved"))),
        "override_approver": metadata.get("override_approver") or "",
        "override_reason": metadata.get("override_reason") or "",
    }


def dot_hazard_label_name(hazard_class: Optional[str]) -> str:
    """Return supported DOT hazard label name for Canva handoff."""
    if not hazard_class:
        return ""
    clean = str(hazard_class).strip().lower()
    if "not regulated" in clean or "not applicable" in clean:
        return ""
    if clean.startswith("class "):
        clean = clean[6:]
    if "3" in clean:
        return "FLAMMABLE LIQUID"
    if "8" in clean:
        return "CORROSIVE"
    if "9" in clean:
        return "CLASS 9"
    return "Review required"


def _optional_value(value) -> str:
    """Return a CSV-safe blank for missing optional values."""
    return "" if value is None else str(value)


def _format_statement_list(items: list) -> str:
    """Flatten GHS statement objects for Canva Bulk Create cells."""
    formatted = []
    for item in items or []:
        code = (item.get("code") or "").strip()
        text = (item.get("text") or "").strip()
        if code and text:
            formatted.append(f"{code}: {text}")
        elif text:
            formatted.append(text)
        elif code:
            formatted.append(code)
    return " | ".join(formatted)


def _ghs_pictogram_names(codes: list) -> str:
    """Return display names for GHS pictogram codes."""
    return ", ".join(GHS_PICTOGRAM_OPTIONS.get(code, code) for code in codes or [])
