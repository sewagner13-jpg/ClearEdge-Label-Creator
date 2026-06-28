from app.rule_based_extractor import RuleBasedExtractor
from app.schema import ExtractedText, ExtractedTextPage


def _text(body: str) -> ExtractedText:
    return ExtractedText(
        doc="SDS",
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
