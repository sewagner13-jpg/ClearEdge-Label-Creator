from app.rule_based_extractor import RuleBasedExtractor
from app.schema import ExtractedText, ExtractedTextPage


def _text(body: str, doc: str = "SDS") -> ExtractedText:
    return ExtractedText(
        doc=doc,
        method_used="text",
        pages=[ExtractedTextPage(page=1, text=body)],
    )


def test_rule_based_extractor_captures_source_visible_dot_fields():
    extracted = RuleBasedExtractor.extract(
        sds_text=_text(
            """
            Danger
            GHS02 GHS07
            H225: Highly flammable liquid and vapor.
            P210: Keep away from heat.
            Proper Shipping Name:
            Flammable liquids, n.o.s. (contains solvent)
            UN1993
            Hazard Class: 3
            Packing Group: II
            ClearEdge Solutions
            14301 CR Koon Highway, Newberry, SC 29108
            704-799-5769
            24-HR EMERGENCY: CHEMTREC: 1-800-424-9300
            Revised: 2026-05-07
            """
        ),
        tds_text=None,
        product_name="Fallback Product",
        warning="AI failed",
    )

    assert extracted.product.name == "Fallback Product"
    assert extracted.product.supplier_name == "ClearEdge Solutions"
    assert extracted.product.emergency_phone.startswith("CHEMTREC")
    assert extracted.ghs.signal_word == "Danger"
    assert extracted.ghs.pictograms == ["GHS02", "GHS07"]
    assert extracted.ghs.hazard_statements[0].code == "H225"
    assert extracted.transport.un_number == "UN1993"
    assert extracted.transport.proper_shipping_name.startswith("Flammable liquids")
    assert extracted.transport.hazard_class == "3"
    assert extracted.transport.packing_group == "II"
    assert any(item.field_path == "transport.un_number" for item in extracted.evidence)


def test_rule_based_extractor_captures_not_regulated_transport_state():
    extracted = RuleBasedExtractor.extract(
        sds_text=_text("DOT TRANSPORT INFORMATION\nNOT REGULATED FOR DOT TRANSPORT"),
        tds_text=None,
        product_name="Not Regulated Product",
        warning="AI failed",
    )

    assert extracted.transport.not_regulated is True
    assert extracted.transport.un_number is None


def test_rule_based_extractor_captures_compact_product_uses_from_tds():
    extracted = RuleBasedExtractor.extract(
        sds_text=None,
        tds_text=_text(
            """
            Recommended Uses:
            Waterproofing membranes
            Adhesive modifier
            Sealant additive
            Decorative paragraph that should not be captured forever
            """,
            doc="TDS",
        ),
        product_name="TDS Use Product",
        warning="AI failed",
    )

    assert extracted.product.product_uses == [
        "Waterproofing membranes",
        "Adhesive modifier",
        "Sealant additive",
    ]
    assert any(item.field_path == "product.product_uses" and item.doc == "TDS" for item in extracted.evidence)


def test_rule_based_extractor_captures_subsidiary_hazard_classes_from_section_14():
    extracted = RuleBasedExtractor.extract(
        sds_text=_text(
            """
            Section 14 Transport Information
            UN Number: UN2924
            Proper Shipping Name: FLAMMABLE LIQUID, CORROSIVE, N.O.S. (solvent, acid)
            Hazard Class: 3
            Subsidiary Risk: 8
            Packing Group: II
            """
        ),
        tds_text=None,
        product_name="Subsidiary Risk Product",
        warning="AI failed",
    )

    assert extracted.transport.hazard_class == "3"
    assert extracted.transport.subsidiary_hazard_classes == ["8"]
    assert any(item.field_path == "transport.subsidiary_hazard_classes" for item in extracted.evidence)


def test_rule_based_extractor_derives_ce_flex_pictograms_from_source_hazards():
    extracted = RuleBasedExtractor.extract(
        sds_text=_text(
            """
            Section 2: Hazard(s) Identification
            Classification:
            Skin Irritation: Category 2
            Eye Irritation: Category 2A
            Skin Sensitization: Category 1
            Reproductive Toxicity: Category 2
            Aspiration Hazard: Category 1
            Chronic Aquatic Toxicity: Category 2
            GHS Label Elements, including precautionary statements:
            Signal Word: DANGER
            Hazard Statement(s):
            H304: May be fatal if swallowed and enters airways.
            H315: Causes skin irritation.
            H317: May cause an allergic skin reaction.
            H319: Causes serious eye irritation.
            H361: Suspected of damaging fertility or the unborn child.
            H411: Toxic to aquatic life with long-lasting effects.
            Precautionary Statement(s):
            Avoid breathing dust/fume/gas/mist/vapors/spray.
            """
        ),
        tds_text=None,
        product_name="CE Flex Mod",
    )

    assert extracted.ghs.signal_word == "Danger"
    assert extracted.ghs.pictograms == ["GHS07", "GHS08", "GHS09"]


def test_rule_based_extractor_does_not_invent_environment_for_category_3_aquatic():
    extracted = RuleBasedExtractor.extract(
        sds_text=_text(
            """
            Hazard Classification
            Skin Irritation Category 2
            Chronic hazards to the aquatic Category 3 environment
            Label Elements
            Signal Word: Warning
            Hazard Statement:
            H315: Causes skin irritation.
            H412: Harmful to aquatic life with long lasting effects.
            Precautionary
            """
        ),
        tds_text=None,
        product_name="Aquatic Category 3 Product",
    )

    assert extracted.ghs.pictograms == ["GHS07"]


def test_rule_based_extractor_captures_transport_class_and_pg_from_section_14_shorthand():
    extracted = RuleBasedExtractor.extract(
        sds_text=_text(
            """
            Section 14: Transport Information
            DOT (Domestic Ground): Not regulated in non-bulk containers (<= 119 gallons).
            IMDG/IATA (Ocean/Air): UN 3082, Environmentally hazardous substance,
            liquid, n.o.s. (Epoxy Resin),
            Class 9, PG III.
            """
        ),
        tds_text=None,
        product_name="CE Flex Mod",
    )

    assert extracted.transport.un_number == "UN3082"
    assert extracted.transport.hazard_class == "9"
    assert extracted.transport.packing_group == "III"


def test_rule_based_extractor_parses_supplier_and_dot_table_variants():
    extracted = RuleBasedExtractor.extract(
        sds_text=_text(
            """
            SECTION 1: Identification
            Supplier:
            RUDOLF GmbH
            Altvaterstrasse 58-64
            D-82538 Geretsried
            Phone: +49-(0)8171-53-0
            Emergency phone: +49-8171-53-222

            14. Transport information
            UN-Number
            DOT NA1993

            UN proper shipping name
            DOT COMBUSTIBLE LIQUID, N.O.S (2-methoxy-1-methylethyl acetate)

            Transport hazard class(es)
            DOT
            Class 3 Combustible liquids
            Label 3

            Packing group
            DOT III
            """
        ),
        tds_text=_text(
            """
            Technical Data Sheet
            Uses / Application:
            Wetting and foam control for waterborne coatings and printing inks.
            """,
            doc="TDS",
        ),
        product_name="Rucolac B-542",
    )

    assert extracted.product.supplier_name == "RUDOLF GmbH"
    assert "D-82538 Geretsried" in extracted.product.supplier_address
    assert extracted.product.supplier_phone == "+49-(0)8171-53-0"
    assert extracted.product.emergency_phone == "+49-8171-53-222"
    assert extracted.product.product_uses == [
        "Wetting and foam control for waterborne coatings and printing inks"
    ]
    assert extracted.transport.un_number == "NA1993"
    assert extracted.transport.proper_shipping_name == (
        "COMBUSTIBLE LIQUID, N.O.S (2-methoxy-1-methylethyl acetate)"
    )
    assert extracted.transport.hazard_class == "3"
    assert extracted.transport.packing_group == "III"


def test_rule_based_extractor_captures_novadd_plain_hazard_sections_and_tds_uses():
    sds = """
    1. Identification
    Product name: Novadd D-5104E
    Manufacturer/Importer/Distributor Information
    Company Name : SynthEdge Advanced Materials Co.,Ltd.
    4F., No.8, Qinghua
    2nd St., Xinwu Dist.,
    Taoyuan City 327,
    Taiwan (R.O.C.)

    Telephone : +886-3-4971028

    Emergency telephone number: +886-3-4971028

    2. Hazard(s) identification
    Hazard Classification
    Health Hazards
    Acute toxicity (Oral) Category 4
    Serious Eye Damage/Eye Irritation Category 1
    Skin sensitizer Category 1
    Specific Target Organ Toxicity - Category 2
    Repeated Exposure
    Environmental Hazards
    Acute hazards to the aquatic Category 3
    environment
    Chronic hazards to the aquatic Category 3
    environment

    Label Elements
    Hazard Symbol:

    Signal Word:

    Danger

    Hazard Statement:
    Harmful if swallowed.
    Causes serious eye damage.
    May cause an allergic skin reaction.
    May cause damage to organs through prolonged or repeated exposure.
    Harmful to aquatic life with long lasting effects.
    Precautionary
    Statements
    Prevention:

    Do not breathe dust/fume/gas/mist/vapors/spray. Wash face, hands and any
    exposed skin thoroughly after handling. Do not eat, drink or smoke when
    using this product. Wear protective gloves/protective clothing/eye protection/face protection.

    Response:

    IF SWALLOWED: Call a POISON CENTER/doctor if you feel unwell. Rinse mouth.

    14. Transport information
    Domestic regulation
    49 CFR
    Not regulated as a dangerous good
    Remarks
    : Not dangerous according to transport regulations., FOR USA ONLY.

    16.Other information, including date of preparation
    HMIS Hazard ID
    Health * 2
    Flammability 1
    Physical Hazards 0
    """
    tds = """
    Technical Data Sheet
    MULTIFUNCTIONAL ADDITIVE NovAdd D-5104E
    CHEMICAL DESCRIPTION: tetramethyldecynediol, gemini surfactant
    NovAdd D-5104E is a multifunctional additive offering wetting, defoaming,
    and dispersing performance. It is a symmetric nonionic surfactant.

    APPLICATION AREAS
    Car OEM coatings
    ●
    General industrial coatings
    ●
    Printing Inks
    ●
    Architectural paints

    The additive is recommended for producing stable universal pigment concentrates.
    """

    extracted = RuleBasedExtractor.extract(
        sds_text=_text(sds),
        tds_text=_text(tds, doc="TDS"),
        product_name="NovAdd D-5104E",
        warning=None,
    )

    assert extracted.product.supplier_name == "SynthEdge Advanced Materials Co.,Ltd."
    assert "Taoyuan City 327" in extracted.product.supplier_address
    assert extracted.product.supplier_phone == "+886-3-4971028"
    assert extracted.product.emergency_phone == "+886-3-4971028"
    assert extracted.product.product_uses == [
        "Wetting, defoaming, and dispersing additive",
        "Car OEM coatings",
        "General industrial coatings",
    ]
    assert extracted.ghs.signal_word == "Danger"
    assert extracted.ghs.pictograms == ["GHS05", "GHS07", "GHS08"]
    assert [statement.text for statement in extracted.ghs.hazard_statements] == [
        "Harmful if swallowed.",
        "Causes serious eye damage.",
        "May cause an allergic skin reaction.",
        "May cause damage to organs through prolonged or repeated exposure.",
        "Harmful to aquatic life with long lasting effects.",
    ]
    assert any(
        "Do not breathe dust/fume/gas/mist/vapors/spray" in statement.text
        for statement in extracted.ghs.precautionary_statements
    )
    assert any(
        "IF SWALLOWED" in statement.text
        for statement in extracted.ghs.precautionary_statements
    )
    assert extracted.transport.not_regulated is True
    assert extracted.nfpa.health == 2
    assert extracted.nfpa.flammability == 1
    assert extracted.nfpa.instability == 0
    assert any("HMIS" in warning for warning in extracted.warnings)
