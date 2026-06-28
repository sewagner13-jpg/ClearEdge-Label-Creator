"""Deterministic source-text fallback extraction for degraded AI availability."""

import re
from typing import Optional

from .schema import (
    Evidence,
    ExtractedData,
    ExtractedText,
    FieldConfidence,
    GHSClassification,
    HazardStatement,
    NFPA704Ratings,
    PrecautionaryStatement,
    ProductInfo,
    TransportClassification,
    normalize_ghs_pictogram,
)


class RuleBasedExtractor:
    """Extract only explicitly present fields from SDS/TDS text."""

    NOT_REGULATED_MARKERS = (
        "not regulated for dot transport",
        "not regulated as a dangerous good",
        "not dangerous goods",
        "not regulated for transport",
        "not restricted",
    )

    @classmethod
    def extract(
        cls,
        *,
        sds_text: Optional[ExtractedText],
        tds_text: Optional[ExtractedText],
        product_name: str,
        warning: str,
    ) -> ExtractedData:
        sources = cls._source_pages(sds_text, tds_text)
        text = "\n".join(page_text for _, _, page_text in sources)
        compact = cls._compact(text)

        data = ExtractedData(
            product=ProductInfo(name=product_name),
            ghs=GHSClassification(),
            transport=TransportClassification(),
            nfpa=NFPA704Ratings(),
            warnings=[warning, "Deterministic fallback extraction used only source-visible values."],
        )

        cls._extract_product_fields(data, sources, compact)
        cls._extract_ghs_fields(data, sources)
        cls._extract_transport_fields(data, sources, compact)
        cls._extract_nfpa_fields(data, sources)
        return data

    @staticmethod
    def _source_pages(sds_text: Optional[ExtractedText], tds_text: Optional[ExtractedText]) -> list[tuple[str, int, str]]:
        pages: list[tuple[str, int, str]] = []
        for document in (sds_text, tds_text):
            if not document:
                continue
            for page in document.pages:
                pages.append((document.doc, page.page, page.text or ""))
        return pages

    @staticmethod
    def _compact(value: str) -> str:
        return re.sub(r"\s+", "", value or "").lower()

    @classmethod
    def _extract_product_fields(cls, data: ExtractedData, sources, compact: str) -> None:
        cls._set_if_found(data, "product.supplier_name", "ClearEdge Solutions", "ClearEdgeSolutions", sources)
        cls._set_regex(data, "product.supplier_address", r"(14301\s*CR\s*Koon\s*Highway[^\n]+)", sources)
        cls._set_regex(data, "product.supplier_address", r"(1705\s*Gregory\s*Road[^\n]+)", sources)
        cls._set_regex(data, "product.supplier_phone", r"(704[-\s]*799[-\s]*5769)", sources)
        cls._set_regex(data, "product.emergency_phone", r"(CHEMTREC[:\s]*1?[-\s]*800[-\s]*424[-\s]*9300)", sources)
        cls._set_regex(data, "product.emergency_phone", r"(1[-\s]*800[-\s]*535[-\s]*5053)", sources)
        cls._set_regex(data, "product.revision_date", r"(?:Revised|Revision\s*Date)[:\s]*([0-9]{4}[-/][0-9]{2}[-/][0-9]{2})", sources)

        if "clearedgesolutions" in compact and not data.product.supplier_name:
            data.product.supplier_name = "ClearEdge Solutions"

    @classmethod
    def _extract_ghs_fields(cls, data: ExtractedData, sources) -> None:
        signal = cls._find_regex(r"\b(Danger|Warning)\b", sources, flags=re.IGNORECASE)
        if signal:
            value = signal["match"].title()
            if value in {"Danger", "Warning"}:
                data.ghs.signal_word = value
                cls._add_evidence(data, "ghs.signal_word", value, signal)

        pictograms = []
        pictogram_match = cls._find_regex(r"\b(GHS0[1-9](?:\s+GHS0[1-9])*)\b", sources, flags=re.IGNORECASE)
        if pictogram_match:
            for raw_code in pictogram_match["match"].split():
                code = normalize_ghs_pictogram(raw_code)
                if code not in pictograms:
                    pictograms.append(code)
            data.ghs.pictograms = pictograms
            cls._add_evidence(data, "ghs.pictograms", ", ".join(pictograms), pictogram_match)

        data.ghs.hazard_statements = [
            HazardStatement(code=code, text=text)
            for code, text in cls._statement_matches(r"(H[0-9]{3}[A-Z]?)\s*:\s*([^\n]+)", sources)
        ]
        data.ghs.precautionary_statements = [
            PrecautionaryStatement(code=code, text=text)
            for code, text in cls._statement_matches(r"(P[0-9]{3}(?:\+P[0-9]{3})*)\s*:\s*([^\n]+)", sources)
        ]

    @classmethod
    def _extract_transport_fields(cls, data: ExtractedData, sources, compact: str) -> None:
        if any(marker.replace(" ", "") in compact for marker in cls.NOT_REGULATED_MARKERS):
            data.transport.not_regulated = True
            match = cls._find_regex(r"(NOT\s+REGULATED[^\n]+|not\s+regulated[^\n]+)", sources, flags=re.IGNORECASE)
            if match:
                cls._add_evidence(data, "transport.not_regulated", "true", match)
            return

        cls._set_regex(data, "transport.un_number", r"\b(UN\s*[0-9]{4})\b", sources, transform=lambda value: value.replace(" ", "").upper())
        cls._set_regex(data, "transport.hazard_class", r"Hazard\s*Class\s*:?\s*([0-9](?:\.[0-9])?)", sources)
        cls._set_regex(data, "transport.packing_group", r"Packing\s*Group\s*:?\s*(I{1,3})\b", sources)

        shipping_name = cls._shipping_name_from_text(compact)
        if shipping_name:
            data.transport.proper_shipping_name = shipping_name
            match = cls._find_regex(r"(Flammable\s*liquids?[^\n]+)", sources, flags=re.IGNORECASE)
            if match:
                cls._add_evidence(data, "transport.proper_shipping_name", shipping_name, match)

        marine = cls._find_regex(r"Marine\s*Pollutant\s*:?\s*(yes|no)", sources, flags=re.IGNORECASE)
        if marine:
            data.transport.marine_pollutant = marine["match"].lower().endswith("yes")
            cls._add_evidence(data, "transport.marine_pollutant", str(data.transport.marine_pollutant), marine)

        limited = cls._find_regex(r"Limited\s*Quantity\s*:?\s*([^\n]+)", sources, flags=re.IGNORECASE)
        if limited:
            data.transport.limited_quantity = limited["match"].strip()
            cls._add_evidence(data, "transport.limited_quantity", data.transport.limited_quantity, limited)

    @classmethod
    def _extract_nfpa_fields(cls, data: ExtractedData, sources) -> None:
        for field_path, pattern in (
            ("nfpa.health", r"NFPA\s*(?:Health|Blue)\s*:?\s*([0-4])"),
            ("nfpa.flammability", r"NFPA\s*(?:Flammability|Red)\s*:?\s*([0-4])"),
            ("nfpa.instability", r"NFPA\s*(?:Instability|Reactivity|Yellow)\s*:?\s*([0-4])"),
        ):
            cls._set_regex(data, field_path, pattern, sources, transform=int)

    @staticmethod
    def _shipping_name_from_text(compact: str) -> Optional[str]:
        if "flammableliquids,n.o.s.(contains" in compact:
            contents = re.search(r"flammableliquids,n\.o\.s\.\(contains([a-z0-9,.-]+)\)", compact)
            suffix = f" (contains {contents.group(1)})" if contents else ""
            return f"Flammable liquids, n.o.s.{suffix}"
        if "flammableliquids,n.o.s." in compact:
            return "Flammable liquids, n.o.s."
        return None

    @classmethod
    def _statement_matches(cls, pattern: str, sources) -> list[tuple[str, str]]:
        matches: list[tuple[str, str]] = []
        seen = set()
        for doc, page, text in sources:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                code = match.group(1).upper()
                statement = cls._humanize_compacted_statement(match.group(2))
                key = (code, statement.lower())
                if statement and key not in seen:
                    matches.append((code, statement))
                    seen.add(key)
        return matches

    @staticmethod
    def _humanize_compacted_statement(value: str) -> str:
        text = " ".join(value.strip(" .").split())
        return text.rstrip(".") + "." if text else ""

    @classmethod
    def _set_if_found(cls, data: ExtractedData, field_path: str, value: str, needle: str, sources) -> None:
        for doc, page, text in sources:
            if needle.lower() in cls._compact(text):
                cls._set_field(data, field_path, value)
                cls._add_evidence(data, field_path, value, {"doc": doc, "page": page, "quote": needle})
                return

    @classmethod
    def _set_regex(cls, data: ExtractedData, field_path: str, pattern: str, sources, transform=None) -> None:
        match = cls._find_regex(pattern, sources)
        if not match:
            return
        value = match["match"].strip()
        if transform:
            value = transform(value)
        cls._set_field(data, field_path, value)
        cls._add_evidence(data, field_path, str(value), match)

    @staticmethod
    def _find_regex(pattern: str, sources, flags=0) -> Optional[dict]:
        for doc, page, text in sources:
            match = re.search(pattern, text, flags=flags)
            if match:
                return {
                    "doc": doc,
                    "page": page,
                    "match": match.group(1),
                    "quote": match.group(0),
                }
        return None

    @staticmethod
    def _set_field(data: ExtractedData, field_path: str, value) -> None:
        section, field = field_path.split(".", 1)
        setattr(getattr(data, section), field, value)

    @staticmethod
    def _add_evidence(data: ExtractedData, field_path: str, value: str, match: dict) -> None:
        data.evidence.append(Evidence(
            field_path=field_path,
            doc=match["doc"],
            section=None,
            page=match["page"],
            quote=str(match.get("quote") or value)[:240],
        ))
        data.confidence.append(FieldConfidence(field_path=field_path, confidence=0.75))
