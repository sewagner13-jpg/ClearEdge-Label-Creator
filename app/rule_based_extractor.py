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

    GHS_PICTOGRAM_ORDER = (
        "GHS01",
        "GHS02",
        "GHS03",
        "GHS04",
        "GHS05",
        "GHS06",
        "GHS07",
        "GHS08",
        "GHS09",
    )

    H_CODE_PICTOGRAMS = {
        "H200": ("GHS01",),
        "H201": ("GHS01",),
        "H202": ("GHS01",),
        "H203": ("GHS01",),
        "H204": ("GHS01",),
        "H205": ("GHS01",),
        "H220": ("GHS02",),
        "H221": ("GHS02",),
        "H222": ("GHS02",),
        "H223": ("GHS02",),
        "H224": ("GHS02",),
        "H225": ("GHS02",),
        "H226": ("GHS02",),
        "H240": ("GHS01", "GHS02"),
        "H241": ("GHS01", "GHS02"),
        "H242": ("GHS02",),
        "H270": ("GHS03",),
        "H280": ("GHS04",),
        "H281": ("GHS04",),
        "H290": ("GHS05",),
        "H300": ("GHS06",),
        "H301": ("GHS06",),
        "H302": ("GHS07",),
        "H304": ("GHS08",),
        "H310": ("GHS06",),
        "H311": ("GHS06",),
        "H312": ("GHS07",),
        "H314": ("GHS05",),
        "H315": ("GHS07",),
        "H317": ("GHS07",),
        "H318": ("GHS05",),
        "H319": ("GHS07",),
        "H330": ("GHS06",),
        "H331": ("GHS06",),
        "H332": ("GHS07",),
        "H334": ("GHS08",),
        "H335": ("GHS07",),
        "H336": ("GHS07",),
        "H340": ("GHS08",),
        "H341": ("GHS08",),
        "H350": ("GHS08",),
        "H351": ("GHS08",),
        "H360": ("GHS08",),
        "H361": ("GHS08",),
        "H370": ("GHS08",),
        "H371": ("GHS08",),
        "H372": ("GHS08",),
        "H373": ("GHS08",),
        "H400": ("GHS09",),
        "H410": ("GHS09",),
        "H411": ("GHS09",),
    }

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
        warning: Optional[str] = None,
    ) -> ExtractedData:
        sources = cls._source_pages(sds_text, tds_text)
        text = "\n".join(page_text for _, _, page_text in sources)
        compact = cls._compact(text)
        warnings = []
        if warning:
            warnings.extend([warning, "Deterministic fallback extraction used only source-visible values."])

        data = ExtractedData(
            product=ProductInfo(name=product_name),
            ghs=GHSClassification(),
            transport=TransportClassification(),
            nfpa=NFPA704Ratings(),
            warnings=warnings,
        )

        cls._extract_product_fields(data, sources, compact)
        detected_pictograms = list(
            getattr(sds_text, "detected_ghs_pictograms", None) or []
        )
        cls._extract_ghs_fields(data, sources, detected_pictograms)
        cls._extract_transport_fields(data, sources, compact)
        cls._extract_nfpa_fields(data, sources)
        return data

    @staticmethod
    def _source_pages(sds_text: Optional[ExtractedText], tds_text: Optional[ExtractedText]) -> list[tuple[str, int, str]]:
        pages: list[tuple[str, int, str]] = []
        for document in (sds_text, tds_text):
            if not document:
                continue
            raw_pages = getattr(document, "pages", None) or []
            if isinstance(raw_pages, dict):
                iterator = raw_pages.items()
            else:
                iterator = enumerate(raw_pages, start=1)
            for index, page in iterator:
                if isinstance(page, dict):
                    page_number = int(page.get("page") or index or 1)
                    page_text = page.get("text") or ""
                else:
                    page_number = int(getattr(page, "page", index) or 1)
                    page_text = getattr(page, "text", "") or ""
                pages.append((document.doc, page_number, page_text))
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

        cls._extract_section_1_supplier_fields(data, sources)

        product_uses = cls._extract_product_uses(sources)
        if product_uses:
            data.product.product_uses = product_uses
            match = next((item for item in sources if item[0] == "TDS"), sources[0] if sources else None)
            if match:
                doc, page, _ = match
                cls._add_evidence(
                    data,
                    "product.product_uses",
                    "; ".join(product_uses),
                    {"doc": doc, "page": page, "quote": "; ".join(product_uses)},
                )

    @classmethod
    def _extract_ghs_fields(cls, data: ExtractedData, sources, detected_pictograms=None) -> None:
        signal = cls._find_regex(r"\b(Danger|Warning)\b", sources, flags=re.IGNORECASE)
        if signal:
            value = signal["match"].title()
            if value in {"Danger", "Warning"}:
                data.ghs.signal_word = value
                cls._add_evidence(data, "ghs.signal_word", value, signal)

        detected_pictograms = list(detected_pictograms or [])
        pictograms = [item.code for item in detected_pictograms]
        pictogram_match = cls._find_regex(r"\b(GHS0[1-9](?:\s+GHS0[1-9])*)\b", sources, flags=re.IGNORECASE)
        if pictogram_match and not detected_pictograms:
            for raw_code in pictogram_match["match"].split():
                code = normalize_ghs_pictogram(raw_code)
                cls._append_unique(pictograms, code)

        hazard_statements = [
            HazardStatement(code=code, text=text)
            for code, text in cls._statement_matches(r"(H[0-9]{3}[A-Z]?)\s*:\s*([^\n]+)", sources)
        ]
        for statement in cls._plain_section_statements(
            sources,
            start_pattern=r"^\s*Hazard\s+Statement\s*:?\s*$",
            stop_patterns=(
                r"^\s*Precautionary\b",
                r"^\s*Other\s+Hazards?\b",
                r"^\s*3\.",
                r"^\s*Section\s+3\b",
            ),
        ):
            key = statement.lower()
            if key not in {item.text.lower() for item in hazard_statements}:
                hazard_statements.append(HazardStatement(code=None, text=statement))
        data.ghs.hazard_statements = hazard_statements

        if not detected_pictograms:
            for derived_code in cls._derive_pictograms_from_classifications(sources):
                cls._append_unique(pictograms, derived_code)
            for derived_code in cls._derive_pictograms_from_hazard_statements(hazard_statements):
                cls._append_unique(pictograms, derived_code)
        if pictograms:
            data.ghs.pictograms = cls._sort_pictograms(pictograms)
            if detected_pictograms:
                pages = sorted({item.page for item in detected_pictograms})
                confidence = min(item.confidence for item in detected_pictograms)
                data.evidence.append(
                    Evidence(
                        field_path="ghs.pictograms",
                        doc="SDS",
                        section="2",
                        page=pages[0],
                        quote=(
                            "Embedded SDS pictogram images matched approved assets: "
                            + ", ".join(data.ghs.pictograms)
                        ),
                    )
                )
                data.confidence.append(
                    FieldConfidence(field_path="ghs.pictograms", confidence=confidence)
                )
            elif pictogram_match:
                cls._add_evidence(data, "ghs.pictograms", ", ".join(data.ghs.pictograms), pictogram_match)
            else:
                match = (
                    cls._find_regex(
                        r"((?:Hazard\s+Classification|Classification\s*:)[\s\S]{0,1400}?(?:Label\s+Elements|Signal\s+Word|Hazard\s+Statement))",
                        sources,
                        flags=re.IGNORECASE,
                    )
                    or cls._find_regex(r"((?:Hazard\s+Statement|Hazard\s+Statement\(s\))[\s\S]{0,1200})", sources, flags=re.IGNORECASE)
                )
                if match:
                    cls._add_evidence(data, "ghs.pictograms", ", ".join(data.ghs.pictograms), match)

        precautionary_statements = [
            PrecautionaryStatement(code=code, text=text)
            for code, text in cls._statement_matches(r"(P[0-9]{3}(?:\+P[0-9]{3})*)\s*:\s*([^\n]+)", sources)
        ]
        for statement in cls._plain_section_statements(
            sources,
            start_pattern=r"^\s*Precautionary\b",
            stop_patterns=(
                r"^\s*3\.",
                r"^\s*Section\s+3\b",
                r"^\s*14\.",
                r"^\s*Section\s+14\b",
                r"^\s*Transport\s+information\b",
                r"^\s*HMIS\s+Hazard\s+ID\b",
            ),
            skip_patterns=(
                r"^\s*Statements?\s*$",
                r"^\s*(Prevention|Response|Storage|Disposal|General)\s*:?\s*$",
            ),
        ):
            key = statement.lower()
            if key not in {item.text.lower() for item in precautionary_statements}:
                precautionary_statements.append(PrecautionaryStatement(code=None, text=statement))
        data.ghs.precautionary_statements = precautionary_statements

    @classmethod
    def _extract_transport_fields(cls, data: ExtractedData, sources, compact: str) -> None:
        if any(marker.replace(" ", "") in compact for marker in cls.NOT_REGULATED_MARKERS):
            data.transport.not_regulated = True
            match = cls._find_regex(r"(NOT\s+REGULATED[^\n]+|not\s+regulated[^\n]+)", sources, flags=re.IGNORECASE)
            if match:
                cls._add_evidence(data, "transport.not_regulated", "true", match)
            return

        cls._set_regex(
            data,
            "transport.un_number",
            r"\b((?:UN|NA)\s*[0-9]{4})\b",
            sources,
            transform=lambda value: value.replace(" ", "").upper(),
        )
        cls._set_regex(data, "transport.hazard_class", r"Hazard\s*Class\s*:?\s*([0-9](?:\.[0-9])?)", sources)
        if not data.transport.hazard_class:
            cls._set_regex(data, "transport.hazard_class", r"\bClass\s*([0-9](?:\.[0-9])?)\b", sources)
        if not data.transport.hazard_class:
            cls._set_regex(data, "transport.hazard_class", r"\bClass\s*DOT\s*([0-9](?:\.[0-9])?)\b", sources, flags=re.IGNORECASE)
        subsidiary = cls._find_regex(
            r"Subsidiary\s*(?:Hazards?|Risks?|Class(?:es)?)\s*:?\s*([0-9.,;\s]+)",
            sources,
            flags=re.IGNORECASE,
        )
        if subsidiary:
            classes = cls._hazard_class_list(subsidiary["match"])
            if classes:
                data.transport.subsidiary_hazard_classes = classes
                cls._add_evidence(
                    data,
                    "transport.subsidiary_hazard_classes",
                    ", ".join(classes),
                    subsidiary,
                )
        cls._set_regex(data, "transport.packing_group", r"Packing\s*Group\s*:?\s*(I{1,3})\b", sources)
        if not data.transport.packing_group:
            cls._set_regex(data, "transport.packing_group", r"\bPG\s*(I{1,3})\b", sources)
        if not data.transport.packing_group:
            table_pg = cls._table_value_after_heading(sources, r"^Packing\s+group\b")
            if table_pg:
                pg_match = re.search(r"\b(I{1,3})\b", table_pg["value"], flags=re.IGNORECASE)
                if pg_match:
                    data.transport.packing_group = pg_match.group(1).upper()
                    cls._add_evidence(
                        data,
                        "transport.packing_group",
                        data.transport.packing_group,
                        table_pg["evidence"],
                    )

        shipping_name = cls._proper_shipping_name_from_table(sources)
        if not shipping_name:
            shipping_name = cls._shipping_name_from_text(compact)
        if shipping_name:
            data.transport.proper_shipping_name = shipping_name
            match = (
                cls._find_regex(r"((?:Flammable|Combustible)\s*liquids?[^\n]+)", sources, flags=re.IGNORECASE)
                or cls._find_regex(r"(COMBUSTIBLE\s+LIQUID[^\n]+)", sources, flags=re.IGNORECASE)
            )
            if match:
                cls._add_evidence(data, "transport.proper_shipping_name", shipping_name, match)

        marine = cls._find_regex(r"Marine\s*Pollutant\s*:?\s*(yes|no)", sources, flags=re.IGNORECASE)
        if marine:
            data.transport.marine_pollutant = marine["match"].lower().endswith("yes")
            cls._add_evidence(data, "transport.marine_pollutant", str(data.transport.marine_pollutant), marine)

        hazardous_substance = cls._find_regex(r"Hazardous\s*Substance\s*(?:\(RQ\))?\s*:?\s*(yes|no)", sources, flags=re.IGNORECASE)
        if hazardous_substance:
            data.transport.hazardous_substance = hazardous_substance["match"].lower().endswith("yes")
            cls._add_evidence(
                data,
                "transport.hazardous_substance",
                str(data.transport.hazardous_substance),
                hazardous_substance,
            )

        hazardous_waste = cls._find_regex(r"Hazardous\s*Waste\s*:?\s*(yes|no)", sources, flags=re.IGNORECASE)
        if hazardous_waste:
            data.transport.hazardous_waste = hazardous_waste["match"].lower().endswith("yes")
            cls._add_evidence(data, "transport.hazardous_waste", str(data.transport.hazardous_waste), hazardous_waste)

        limited = cls._find_regex(r"Limited\s*Quantity\s*:?\s*([^\n]+)", sources, flags=re.IGNORECASE)
        if limited:
            data.transport.limited_quantity = limited["match"].strip()
            cls._add_evidence(data, "transport.limited_quantity", data.transport.limited_quantity, limited)

    @classmethod
    def _extract_nfpa_fields(cls, data: ExtractedData, sources) -> None:
        found_nfpa = False
        for field_path, pattern in (
            ("nfpa.health", r"NFPA\s*(?:Health|Blue)\s*:?\s*([0-4])"),
            ("nfpa.flammability", r"NFPA\s*(?:Flammability|Red)\s*:?\s*([0-4])"),
            ("nfpa.instability", r"NFPA\s*(?:Instability|Reactivity|Yellow)\s*:?\s*([0-4])"),
        ):
            match = cls._find_regex(pattern, sources, flags=re.IGNORECASE)
            if match:
                found_nfpa = True
                cls._set_field(data, field_path, int(match["match"]))
                cls._add_evidence(data, field_path, match["match"], match)

        if found_nfpa:
            data.nfpa.source = "sds"
        else:
            cls._extract_hmis_as_nfpa_fields(data, sources)
        if data.nfpa.source == "clearedge_default":
            cls._append_unique(
                data.warnings,
                (
                    "NFPA 704 and HMIS ratings were not listed in the SDS/TDS; "
                    "0-0-0 is the ClearEdge default and is not a source-derived rating."
                ),
            )

    @staticmethod
    def _shipping_name_from_text(compact: str) -> Optional[str]:
        combustible = re.search(r"combustibleliquid,n\.o\.s\.?\(([^)]+)\)", compact)
        if combustible:
            return f"COMBUSTIBLE LIQUID, N.O.S ({combustible.group(1)})"
        if "combustibleliquid,n.o.s." in compact:
            return "COMBUSTIBLE LIQUID, N.O.S"
        if "flammableliquids,n.o.s.(contains" in compact:
            contents = re.search(r"flammableliquids,n\.o\.s\.\(contains([a-z0-9,.-]+)\)", compact)
            suffix = f" (contains {contents.group(1)})" if contents else ""
            return f"Flammable liquids, n.o.s.{suffix}"
        if "flammableliquids,n.o.s." in compact:
            return "Flammable liquids, n.o.s."
        return None

    @classmethod
    def _proper_shipping_name_from_table(cls, sources) -> Optional[str]:
        value = cls._table_value_after_heading(
            sources,
            r"^(?:UN\s+proper\s+shipping\s+name|Proper\s+Shipping\s+Name)\b",
        )
        if not value:
            return None
        clean = re.sub(r"^(?:DOT|49\s*CFR)\s+", "", value["value"], flags=re.IGNORECASE).strip(" :")
        return " ".join(clean.split()) or None

    @classmethod
    def _table_value_after_heading(cls, sources, heading_pattern: str) -> Optional[dict]:
        heading_re = re.compile(heading_pattern, flags=re.IGNORECASE)
        stop_re = re.compile(
            r"^(?:UN[-\s]?Number|Transport\s+hazard|Class\b|Label\b|Packing\s+group|Environmental\s+hazards|"
            r"Special\s+precautions|Transport/Additional|Section\s+\d+|\d+\.)",
            flags=re.IGNORECASE,
        )
        for doc, page, text in sources:
            lines = cls._meaningful_lines(text)
            for index, line in enumerate(lines):
                if not heading_re.match(line):
                    continue
                inline = cls._inline_label_value(line, heading_pattern)
                candidates = [inline] if inline else []
                candidates.extend(lines[index + 1:index + 5])
                for candidate in candidates:
                    clean = cls._clean_label_value(candidate)
                    if not clean or heading_re.match(clean):
                        continue
                    if clean.upper() in {"DOT", "ADR, IMDG, IATA", "49 CFR"}:
                        continue
                    if stop_re.match(clean):
                        break
                    return {
                        "value": clean,
                        "evidence": {"doc": doc, "page": page, "quote": clean},
                    }
        return None

    @staticmethod
    def _hazard_class_list(value: str) -> list[str]:
        classes = []
        seen = set()
        for match in re.finditer(r"\b[0-9](?:\.[0-9])?\b", value or ""):
            hazard_class = match.group(0)
            if hazard_class not in seen:
                classes.append(hazard_class)
                seen.add(hazard_class)
        return classes

    @classmethod
    def _extract_product_uses(cls, sources) -> list[str]:
        """Extract a few explicit product uses from TDS/application sections."""
        heading_pattern = re.compile(
            r"^\s*(?:recommended\s+uses?|uses?(?:\s*/\s*applications?)?|applications?|application\s+areas?|typical\s+applications?|product\s+description)\s*:?\s*$",
            flags=re.IGNORECASE,
        )
        uses = []
        for doc, _, text in sources:
            if doc != "TDS":
                continue
            offering = re.search(
                r"offering\s+(.{3,140}?)\s+performance",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if offering:
                phrase = " ".join(offering.group(1).replace("\n", " ").split())
                phrase = phrase.strip(" .;,")
                if phrase:
                    cls._append_unique(uses, f"{phrase.capitalize()} additive")

            lines = [line.strip(" \t-•●○") for line in text.splitlines()]
            for index, line in enumerate(lines):
                if not heading_pattern.match(line):
                    continue
                for candidate in lines[index + 1:index + 8]:
                    clean = " ".join(candidate.strip(" .;-•●○").split())
                    if not clean:
                        continue
                    if clean in {"●", "○", "•"}:
                        continue
                    if heading_pattern.match(clean) or re.match(r"^[A-Z][A-Za-z ]{2,30}:$", clean):
                        break
                    cls._append_unique(uses, clean)
                    if len(uses) >= 3:
                        return uses
                if uses:
                    return uses[:3]
        return []

    @classmethod
    def _extract_section_1_supplier_fields(cls, data: ExtractedData, sources) -> None:
        for doc, page, text in sources:
            if doc != "SDS":
                continue
            lines = cls._meaningful_lines(text)
            supplier_label_pattern = r"^(?:Company\s+Name|Supplier|Manufacturer/Supplier|Manufacturer\s*:)\b"
            company_index = cls._find_line_index(lines, supplier_label_pattern)
            if company_index is not None:
                inline_name = cls._inline_label_value(lines[company_index], supplier_label_pattern)
                name_index = company_index if inline_name else cls._next_value_line_index(lines, company_index + 1)
                if name_index is not None and not data.product.supplier_name:
                    name = inline_name or cls._clean_label_value(lines[name_index])
                    data.product.supplier_name = name
                    cls._add_evidence(data, "product.supplier_name", name, {"doc": doc, "page": page, "quote": name})

                    address_lines = []
                    for line in lines[name_index + 1:]:
                        if re.match(r"^(Telephone|Phone|Emergency\s+telephone|Emergency\s+phone)\b", line, flags=re.IGNORECASE):
                            break
                        clean = cls._clean_label_value(line)
                        if clean:
                            address_lines.append(clean)
                    if address_lines and not data.product.supplier_address:
                        address = ", ".join(address_lines)
                        data.product.supplier_address = address
                        cls._add_evidence(data, "product.supplier_address", address, {"doc": doc, "page": page, "quote": address})

            phone = cls._value_after_label(lines, r"^(?:Telephone|Phone)\b")
            if phone and not data.product.supplier_phone:
                data.product.supplier_phone = phone
                cls._add_evidence(data, "product.supplier_phone", phone, {"doc": doc, "page": page, "quote": phone})

            emergency = cls._value_after_label(lines, r"^Emergency\s+telephone\s+number\b|^Emergency\s+phone\b")
            if emergency and not data.product.emergency_phone:
                data.product.emergency_phone = emergency
                cls._add_evidence(data, "product.emergency_phone", emergency, {"doc": doc, "page": page, "quote": emergency})

    @classmethod
    def _derive_pictograms_from_classifications(cls, sources) -> list[str]:
        block = cls._classification_block(sources).lower()
        if not block:
            return []

        pictograms = []
        if cls._block_has_corrosion_category(block):
            cls._append_unique(pictograms, "GHS05")
        if (
            "skin sensitizer" in block
            or "skin sensitization" in block
            or "skin irritation" in block
            or "eye irritation" in block
            or ("acute toxicity" in block and "category 4" in block)
        ):
            cls._append_unique(pictograms, "GHS07")
        if (
            "specific target organ toxicity repeated exposure" in block
            or "stot repeated exposure" in block
            or ("specific target organ toxicity" in block and "repeated exposure" in block)
            or "reproductive toxicity" in block
            or "germ cell mutagenicity" in block
            or "carcinogenicity" in block
            or "aspiration hazard" in block
            or "respiratory sensitization" in block
        ):
            cls._append_unique(pictograms, "GHS08")
        if cls._block_has_aquatic_category_requiring_environment(block):
            cls._append_unique(pictograms, "GHS09")
        return pictograms

    @staticmethod
    def _block_has_corrosion_category(block: str) -> bool:
        category_one_patterns = (
            r"skin\s+corrosion(?:/irritation)?[^\n]{0,80}\bcategory\s+1(?:[abc])?\b",
            r"serious\s+eye\s+damage(?:/eye\s+irritation)?[^\n]{0,80}\bcategory\s+1\b",
            r"corrosive\s+to\s+metals?[^\n]{0,80}\bcategory\s+1\b",
        )
        return any(re.search(pattern, block, flags=re.IGNORECASE) for pattern in category_one_patterns)

    @classmethod
    def _classification_block(cls, sources) -> str:
        for _doc, _page, text in sources:
            match = re.search(
                r"Hazard\s+Classification(?P<block>[\s\S]{0,1400}?)(?:Label\s+Elements|Signal\s+Word|Hazard\s+Statement)",
                text,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group("block")
            match = re.search(
                r"\bClassification\s*:?(?P<block>[\s\S]{0,1400}?)(?:GHS\s+Label\s+Elements|Label\s+Elements|Signal\s+Word|Hazard\s+Statement)",
                text,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group("block")
        return ""

    @classmethod
    def _derive_pictograms_from_hazard_statements(cls, hazard_statements: list[HazardStatement]) -> list[str]:
        pictograms = []
        for statement in hazard_statements:
            for code in cls._h_codes_from_statement(statement):
                for pictogram in cls.H_CODE_PICTOGRAMS.get(code, ()):
                    cls._append_unique(pictograms, pictogram)
            text = statement.text.lower()
            if "serious eye damage" in text or "severe skin burns" in text:
                cls._append_unique(pictograms, "GHS05")
            if (
                "skin irritation" in text
                or "eye irritation" in text
                or "allergic skin reaction" in text
                or "harmful if swallowed" in text
                or "harmful if inhaled" in text
                or "drowsiness or dizziness" in text
            ):
                cls._append_unique(pictograms, "GHS07")
            if (
                "may be fatal if swallowed and enters airways" in text
                or "damaging fertility" in text
                or "damage to organs" in text
                or "may cause cancer" in text
            ):
                cls._append_unique(pictograms, "GHS08")
            if "toxic to aquatic life with long" in text or "very toxic to aquatic life" in text:
                cls._append_unique(pictograms, "GHS09")
        return pictograms

    @staticmethod
    def _block_has_aquatic_category_requiring_environment(block: str) -> bool:
        lines = [" ".join(line.split()) for line in block.splitlines() if line.strip()]
        candidates = []
        for index, line in enumerate(lines):
            candidates.append(line)
            if index + 1 < len(lines):
                candidates.append(f"{line} {lines[index + 1]}")

        for candidate in candidates:
            if re.search(
                r"\b(?:aquatic|environmental)\b.{0,90}\bcategory\s*(?:1|2|i|ii)\b",
                candidate,
                flags=re.IGNORECASE,
            ):
                return True
        return False

    @staticmethod
    def _h_codes_from_statement(statement: HazardStatement) -> list[str]:
        codes = []
        if statement.code:
            codes.extend(re.findall(r"H[0-9]{3}[A-Z]?", statement.code.upper()))
        codes.extend(re.findall(r"H[0-9]{3}[A-Z]?", statement.text.upper()))
        deduped = []
        for code in codes:
            if code not in deduped:
                deduped.append(code)
        return deduped

    @classmethod
    def _sort_pictograms(cls, pictograms: list[str]) -> list[str]:
        order = {code: index for index, code in enumerate(cls.GHS_PICTOGRAM_ORDER)}
        return sorted(pictograms, key=lambda code: order.get(code, len(order)))

    @classmethod
    def _plain_section_statements(
        cls,
        sources,
        *,
        start_pattern: str,
        stop_patterns: tuple[str, ...],
        skip_patterns: tuple[str, ...] = (),
    ) -> list[str]:
        statements = []
        seen = set()
        start_re = re.compile(start_pattern, flags=re.IGNORECASE)
        stop_res = [re.compile(pattern, flags=re.IGNORECASE) for pattern in stop_patterns]
        skip_res = [re.compile(pattern, flags=re.IGNORECASE) for pattern in skip_patterns]
        for _doc, _page, text in sources:
            lines = text.splitlines()
            collecting = False
            collected = []
            for line in lines:
                clean = line.strip()
                if not collecting and start_re.match(clean):
                    collecting = True
                    inline = re.sub(start_pattern, "", clean, flags=re.IGNORECASE).strip(" :")
                    if inline:
                        collected.append(inline)
                    continue
                if not collecting:
                    continue
                if any(stop_re.match(clean) for stop_re in stop_res):
                    break
                if any(skip_re.match(clean) for skip_re in skip_res):
                    continue
                if clean:
                    collected.append(clean)
            if not collected:
                continue
            for statement in cls._split_source_sentences(" ".join(collected)):
                key = statement.lower()
                if statement and key not in seen:
                    statements.append(statement)
                    seen.add(key)
        return statements

    @staticmethod
    def _split_source_sentences(text: str) -> list[str]:
        clean = " ".join(text.replace("•", " ").replace("●", " ").replace("○", " ").split())
        if not clean:
            return []
        return [
            statement.strip()
            for statement in re.split(r"(?<=\.)\s+(?=[A-Z])", clean)
            if statement.strip()
        ]

    @classmethod
    def _extract_hmis_as_nfpa_fields(cls, data: ExtractedData, sources) -> None:
        hmis_values = (
            ("nfpa.health", r"Health\s+(?:\*\s*)?([0-4])"),
            ("nfpa.flammability", r"Flammability\s+([0-4])"),
            ("nfpa.instability", r"Physical\s+Hazards?\s+([0-4])"),
        )
        found_any = False
        for field_path, pattern in hmis_values:
            match = cls._find_regex(pattern, sources, flags=re.IGNORECASE)
            if not match:
                continue
            found_any = True
            cls._set_field(data, field_path, int(match["match"]))
            cls._add_evidence(data, field_path, match["match"], match)
        if found_any:
            data.nfpa.source = "hmis"
            cls._append_unique(
                data.warnings,
                "NFPA 704 values were populated from SDS HMIS Hazard ID values because NFPA 704 values were not listed.",
            )

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

    @staticmethod
    def _meaningful_lines(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    @staticmethod
    def _find_line_index(lines: list[str], pattern: str) -> Optional[int]:
        for index, line in enumerate(lines):
            if re.match(pattern, line, flags=re.IGNORECASE):
                return index
        return None

    @classmethod
    def _next_value_line_index(cls, lines: list[str], start: int) -> Optional[int]:
        for index in range(start, len(lines)):
            clean = cls._clean_label_value(lines[index])
            if clean:
                return index
        return None

    @classmethod
    def _value_after_label(cls, lines: list[str], label_pattern: str) -> Optional[str]:
        label_re = re.compile(label_pattern, flags=re.IGNORECASE)
        for index, line in enumerate(lines):
            if not label_re.match(line):
                continue
            inline = cls._inline_label_value(line, label_pattern)
            if inline:
                return inline
            value_index = cls._next_value_line_index(lines, index + 1)
            if value_index is not None:
                return cls._clean_label_value(lines[value_index])
        return None

    @classmethod
    def _inline_label_value(cls, line: str, label_pattern: str) -> str:
        return cls._clean_label_value(re.sub(label_pattern, "", line, flags=re.IGNORECASE))

    @staticmethod
    def _clean_label_value(value: str) -> str:
        return " ".join(value.strip(" :").split())

    @staticmethod
    def _append_unique(values: list, value) -> None:
        key = str(value).strip().lower()
        if not key:
            return
        if key not in {str(item).strip().lower() for item in values}:
            values.append(value)

    @classmethod
    def _set_if_found(cls, data: ExtractedData, field_path: str, value: str, needle: str, sources) -> None:
        for doc, page, text in sources:
            if needle.lower() in cls._compact(text):
                cls._set_field(data, field_path, value)
                cls._add_evidence(data, field_path, value, {"doc": doc, "page": page, "quote": needle})
                return

    @classmethod
    def _set_regex(cls, data: ExtractedData, field_path: str, pattern: str, sources, transform=None, flags=0) -> None:
        match = cls._find_regex(pattern, sources, flags=flags)
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
