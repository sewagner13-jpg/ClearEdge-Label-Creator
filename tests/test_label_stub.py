from pathlib import Path
import base64
from io import BytesIO
import re

from pypdf import PdfReader

from app.label_stub import LabelGenerator
from app.schema import (
    ExtractedData,
    GHSClassification,
    HazardStatement,
    NFPA704Ratings,
    PrecautionaryStatement,
    ProductInfo,
    ShipmentInfo,
    TransportClassification,
)


def test_template_registry_has_phase2_templates():
    generator = LabelGenerator()
    assert "clearedge_pail_v1" in generator.templates
    assert "clearedge_drum_v1" in generator.templates


def test_get_template_config_by_size_and_id():
    generator = LabelGenerator()
    by_size = generator.get_template_config(None, "drum")
    by_id = generator.get_template_config("clearedge_pail_v1", "drum")

    assert by_size["size"] == "drum"
    assert by_id["size"] == "pail"


def test_horizontal_orientation_uses_same_template_dimensions_rotated():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge Orientation Test"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    vertical_svg = generator.generate_svg(data, mode="workplace", size="pail", orientation="vertical")
    horizontal_svg = generator.generate_svg(data, mode="workplace", size="pail", orientation="horizontal")

    assert '<svg width="612pt" height="792pt"' in vertical_svg
    assert '<svg width="792pt" height="612pt"' in horizontal_svg


def test_generated_pdf_uses_full_requested_label_page_size():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge PDF Size Test"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    pail_svg = generator.generate_svg(data, mode="workplace", size="pail", orientation="vertical")
    pail_pdf = generator.generate_pdf(pail_svg)
    pail_page = PdfReader(BytesIO(pail_pdf)).pages[0]
    assert float(pail_page.mediabox.width) == 612
    assert float(pail_page.mediabox.height) == 792

    drum_svg = generator.generate_svg(data, mode="workplace", size="drum", orientation="horizontal")
    drum_pdf = generator.generate_pdf(drum_svg)
    drum_page = PdfReader(BytesIO(drum_pdf)).pages[0]
    assert float(drum_page.mediabox.width) == 864
    assert float(drum_page.mediabox.height) == 648


def test_standard_label_escapes_xml_sensitive_dynamic_text_before_pdf_rendering():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(
            name="Coating & Ink Resin",
            product_uses=["Resins of Coating & Ink"],
            emergency_phone="Support <24 hours>",
        ),
        ghs=GHSClassification(signal_word="Warning", pictograms=["GHS07"]),
        transport=TransportClassification(not_regulated=True),
    )

    svg = generator.generate_svg(
        data,
        mode="shipped_dot",
        size="drum",
        orientation="horizontal",
    )
    pdf = generator.generate_pdf(svg)

    assert "Coating &amp; Ink Resin" in svg
    assert "Resins of Coating &amp; Ink" in svg
    assert "Support &lt;24 hours&gt;" in svg
    assert pdf.startswith(b"%PDF")


def test_sample_4x6_label_renders_compact_sales_contact_and_thermal_page_size():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(
            name="Rucolac B-542",
            product_uses=["Wetting and foam control for waterborne coatings"],
        ),
        ghs=GHSClassification(signal_word="Warning", pictograms=["GHS07"]),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(
        data,
        mode="workplace",
        size="sample_4x6",
        orientation="vertical",
        branding={
            "mode": "clearedge",
            "salesperson": {
                "name": "Sean Wagner",
                "email": "sean@clear-edge.net",
                "phone": "704-799-5769",
            },
        },
    )
    pdf = generator.generate_pdf(svg)
    page = PdfReader(BytesIO(pdf)).pages[0]

    assert '<svg width="432pt" height="288pt"' in svg
    assert float(page.mediabox.width) == 432
    assert float(page.mediabox.height) == 288
    assert "Rucolac B-542" in svg
    assert "PRODUCT USE:" in svg
    assert "Wetting and foam control" in svg
    assert "SALES CONTACT" in svg
    assert "Sean Wagner" in svg
    assert "sean@clear-edge.net" in svg
    assert "704-799-5769" in svg
    assert 'id="pictogram-GHS07"' in svg
    assert "HAZARD STATEMENTS" not in svg
    assert "PRECAUTIONARY STATEMENTS" not in svg


def test_sample_4x6_product_name_fits_right_header_space():
    heading = LabelGenerator._format_sample_product_heading("NovAdd D-5104E")

    assert heading["lines"] == ["NovAdd D-5104E"]
    assert heading["font_size"] <= 29
    assert heading["font_size"] >= 20
    for line in heading["lines"]:
        assert LabelGenerator._estimated_text_width_units(line) * heading["font_size"] <= 205

    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="NovAdd D-5104E"),
        ghs=GHSClassification(signal_word="Danger", pictograms=["GHS05", "GHS07", "GHS08"]),
        transport=TransportClassification(),
    )
    svg = generator.generate_svg(data, mode="workplace", size="sample_4x6")

    assert "NovAdd D-5104E" in svg
    assert f'font-size="{heading["font_size"]}"' in svg


def test_sample_4x6_long_product_name_wraps_within_header_frame():
    heading = LabelGenerator._format_sample_product_heading("Rucosan B-WB Sample No Biocide")

    assert heading["font_size"] >= 20
    assert len(heading["lines"]) == 2
    assert " ".join(heading["lines"]).replace("...", "").strip().startswith("Rucosan B-WB Sample")
    for line in heading["lines"]:
        assert LabelGenerator._estimated_text_width_units(line) * heading["font_size"] <= 205


def test_sample_4x6_single_line_fields_are_fitted_to_frame():
    generator = LabelGenerator()
    long_use = "Water repellent for manufacturing aqueous impregnations or exterior industrial coatings"
    long_contact = "B-WB Returned Product Test With Wide Words | very-long-salesperson-email@clear-edge.net | 704-799-5769"
    data = ExtractedData(
        product=ProductInfo(
            name="Rucosan B-WB Sample No Biocide",
            product_uses=[long_use],
        ),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(
        data,
        mode="workplace",
        size="sample_4x6",
        branding={
            "mode": "clearedge",
            "salesperson": {
                "name": "B-WB Returned Product Test With Wide Words",
                "email": "very-long-salesperson-email@clear-edge.net",
                "phone": "704-799-5769",
            },
        },
    )

    assert long_use not in svg
    assert long_contact not in svg
    assert "Water repellent for manufacturing" in svg
    assert "..." in svg


def test_header_shipment_fields_do_not_overlap_long_product_name():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Needs Review Smoke Product"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
        shipment=ShipmentInfo(
            lot_number="SMOKE-REVIEW",
            expiration_date="2027-07-01",
            fill_amount="441 lb",
        ),
    )

    svg = generator.generate_svg(data, mode="shipped_dot", size="pail", orientation="vertical")

    assert 'x="262" y="108" font-size="10.5"' in svg
    assert 'x="400" y="108" font-size="10.5"' in svg
    assert 'x="508" y="108" font-size="10.5"' in svg
    assert "SMOKE-REVIEW" in svg
    assert "2027-07-01" in svg
    assert "441 lb" in svg


def test_fit_text_truncates_deterministically():
    text = "This is a very long product name that should be truncated"
    fitted = LabelGenerator._fit_text(text, 20)
    assert fitted.endswith("...")
    assert len(fitted) <= 20


def test_template_brand_tokens_present():
    generator = LabelGenerator()
    cfg = generator.get_template_config("clearedge_pail_v1", "pail")
    assert cfg["brand"]["header_color"].startswith("#")
    assert cfg["brand"]["accent_color"].startswith("#")
    assert cfg["brand"]["text_color"].startswith("#")


def test_wrap_lines_and_format_statements_clips_deterministically():
    generator = LabelGenerator()
    long_text = "This precautionary statement should wrap cleanly and clip at predictable boundaries for stable print output"
    wrapped = generator._wrap_lines(long_text, line_width=30, max_lines=2)
    assert len(wrapped) <= 2
    assert wrapped[-1].endswith("...")

    class Statement:
        def __init__(self, code, text):
            self.code = code
            self.text = text

    statements = [Statement("P101", long_text)]
    formatted = generator._format_statements(statements, line_width=30, max_items=1)
    assert formatted[0]["code"] == "P101"
    assert formatted[0]["text"].endswith("...")


def test_label_uses_brand_purple_for_previous_red_accents():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(
            name="ClearEdge Purple Test",
            emergency_phone="800-555-1212",
        ),
        ghs=GHSClassification(
            signal_word="Danger",
            pictograms=["GHS02"],
            hazard_statements=[HazardStatement(code="H225", text="Highly flammable liquid and vapor")],
        ),
        transport=TransportClassification(
            un_number="UN1993",
            proper_shipping_name="Flammable liquids, n.o.s.",
            hazard_class="3",
            packing_group="II",
        ),
    )

    svg = generator.generate_svg(data, mode="shipped_dot", size="pail")

    assert "#DC143C" not in svg
    assert "#E74C3C" not in svg
    assert "#FFE5E5" not in svg
    assert svg.count("#110251") >= 6
    assert 'id="pictogram-GHS02"' in svg
    assert "data:image/png;base64" in svg


def test_label_theme_uses_clearedge_royal_purple_and_approved_ghs_asset():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge Purple Test"),
        ghs=GHSClassification(signal_word="Warning", pictograms=["GHS07"]),
        transport=TransportClassification(),
        nfpa=NFPA704Ratings(health=1, flammability=2, instability=0),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail")

    assert "#110251" in svg
    assert "#1B006E" not in svg
    assert 'id="pictogram-GHS07"' in svg
    assert "data:image/png;base64" in svg
    assert 'id="nfpa-704"' not in svg


def test_signal_word_replaces_ghs_heading_and_strip_stays_blank():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge Signal Test"),
        ghs=GHSClassification(signal_word="Danger", pictograms=["GHS02"]),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail")

    assert "GHS PICTOGRAMS" not in svg
    assert 'id="signal-strip"' in svg
    assert 'id="signal-word-heading"' in svg
    assert 'font-size="21"' in svg
    assert "Danger" in svg
    assert 'fill="white" text-anchor="middle"' not in svg


def test_product_uses_render_as_compact_clipped_label_block():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(
            name="ClearEdge Uses Test",
            product_uses=[
                "Waterproofing membranes",
                "Adhesive modifier",
                "Sealant additive",
                "This extra application should be clipped out of the label block",
            ],
        ),
        ghs=GHSClassification(signal_word="Warning", pictograms=["GHS07"]),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail")

    assert 'id="product-uses"' in svg
    assert "PRODUCT USES:" in svg
    assert "Waterproofing membranes" in svg
    assert "Adhesive modifier" in svg
    assert "This extra application" not in svg
    uses_rect = re.search(r'id="product-uses"[\s\S]*?<rect x="10" y="(?P<y>\d+)" width="(?P<width>\d+)" height="(?P<height>\d+)"', svg)
    assert uses_rect
    assert int(uses_rect.group("height")) <= 42


def test_product_name_uses_logo_purple():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="CE Flex Mod"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="drum")

    assert 'font-weight="bold" fill="#110251"' in svg
    assert 'text-anchor="middle"' in svg
    assert "CE Flex Mod" in svg


def test_clearedge_label_forces_official_supplier_and_exact_logo_asset():
    generator = LabelGenerator()
    logo_path = Path(__file__).resolve().parents[1] / "High Res Logo.png"
    expected_logo_data_uri = f"data:image/png;base64,{base64.b64encode(logo_path.read_bytes()).decode('ascii')}"
    data = ExtractedData(
        product=ProductInfo(
            name="ClearEdge Private Label",
            supplier_name="Outside Chemical Company",
            supplier_address="100 Vendor Road, Elsewhere, TX",
            supplier_phone="555-0100",
        ),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail", branding={"mode": "clearedge"})

    assert generator.logo_data_uri == expected_logo_data_uri
    assert 'id="brand-logo"' in svg
    assert expected_logo_data_uri in svg
    assert 'preserveAspectRatio="xMinYMid meet"' in svg
    assert "ClearEdge Solutions" in svg
    assert "14301 CR Koon Highway, Newberry, SC 29108" in svg
    assert "704-799-5769" in svg
    assert "Outside Chemical Company" not in svg
    assert "100 Vendor Road" not in svg


def test_custom_label_uses_custom_logo_and_supplier_identity():
    generator = LabelGenerator()
    custom_logo = "data:image/png;base64,Y3VzdG9tLWxvZ28="
    data = ExtractedData(
        product=ProductInfo(
            name="Customer Blend",
            supplier_name="Customer Chemical Co.",
            supplier_address="200 Customer Lane, Charlotte, NC",
            supplier_phone="704-555-0199",
        ),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(
        data,
        mode="workplace",
        size="pail",
        branding={"mode": "custom", "logo_data_uri": custom_logo},
    )

    assert custom_logo in svg
    logo_match = re.search(r'id="brand-logo" x="20" y="(?P<y>\d+)" width="(?P<width>\d+)" height="(?P<height>\d+)"', svg)
    assert logo_match
    assert int(logo_match.group("y")) <= 24
    assert int(logo_match.group("width")) >= 190
    assert int(logo_match.group("height")) >= 86
    assert "Customer Chemical Co." in svg
    assert "200 Customer Lane, Charlotte, NC" in svg
    assert "704-555-0199" in svg
    assert "ClearEdge Solutions" not in svg


def test_custom_label_can_include_clearedge_process_mark_without_replacing_customer_logo():
    generator = LabelGenerator()
    custom_logo = "data:image/png;base64,Y3VzdG9tLWxvZ28="
    data = ExtractedData(
        product=ProductInfo(
            name="Customer Blend",
            supplier_name="Customer Chemical Co.",
            supplier_address="200 Customer Lane, Charlotte, NC",
            supplier_phone="704-555-0199",
        ),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(
        data,
        mode="workplace",
        size="pail",
        branding={
            "mode": "custom",
            "logo_data_uri": custom_logo,
            "show_clearedge_mark": True,
        },
    )

    assert custom_logo in svg
    assert 'id="clearedge-process-mark"' in svg
    assert "Processed by ClearEdge" not in svg
    logo_match = re.search(
        r'id="clearedge-process-logo" x="(?P<x>\d+)" y="(?P<y>\d+)" '
        r'width="(?P<width>\d+)" height="(?P<height>\d+)"',
        svg,
    )
    assert logo_match
    assert int(logo_match.group("width")) >= 140
    assert int(logo_match.group("height")) >= 24
    assert "Customer Chemical Co." in svg


def test_custom_label_can_disable_clearedge_process_mark():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Customer Blend", supplier_name="Customer Chemical Co."),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(
        data,
        mode="workplace",
        size="pail",
        branding={
            "mode": "custom",
            "logo_data_uri": "data:image/png;base64,Y3VzdG9tLWxvZ28=",
            "show_clearedge_mark": False,
        },
    )

    assert 'id="clearedge-process-mark"' not in svg
    assert "Processed by ClearEdge" not in svg


def test_clearedge_label_does_not_duplicate_process_mark():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge Owned Label"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(
        data,
        mode="workplace",
        size="pail",
        branding={"mode": "clearedge", "show_clearedge_mark": True},
    )

    assert 'id="clearedge-process-mark"' not in svg
    assert "Processed by ClearEdge" not in svg


def test_shipment_lot_and_expiration_have_header_spacing():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Customer Blend", supplier_name="Customer Chemical Co."),
        shipment=ShipmentInfo(
            lot_number="LOT-1234567890",
            expiration_date="2027-12-31",
            fill_amount="441 lb",
        ),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(
        data,
        mode="workplace",
        size="drum",
        orientation="horizontal",
        branding={
            "mode": "custom",
            "logo_data_uri": "data:image/png;base64,Y3VzdG9tLWxvZ28=",
        },
    )

    lot_value_match = re.search(
        r'<text x="(?P<x>\d+)" y="108" font-size="12\.5"[^>]*>\s*LOT-1234567890\s*</text>',
        svg,
    )
    exp_label_match = re.search(
        r'<text x="(?P<x>\d+)" y="94" font-size="8\.5"[^>]*>\s*Exp\.:\s*</text>',
        svg,
    )

    assert lot_value_match
    assert exp_label_match
    assert int(exp_label_match.group("x")) - int(lot_value_match.group("x")) >= 180


def test_long_product_name_wraps_inside_header_without_logo_box():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="CE Surfactant 336 PSA Extended Batch Name"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail")

    assert "CE Surfactant" in svg
    assert "336 PSA Exten..." in svg
    assert 'id="shipment-info"' in svg
    assert '<rect x="10" y="10" width="{{ logo_panel_width }}"' not in svg
    assert 'x2="175" y2="95"' not in svg


def test_shipment_fields_render_in_header():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge PSA 336"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
        shipment=ShipmentInfo(fill_amount="441 lb"),
    )

    svg = generator.generate_svg(data, mode="workplace", size="drum")

    assert 'id="shipment-info"' in svg
    assert "Lot #:" in svg
    assert 'font-size="10.5" font-weight="bold"' in svg
    assert "Exp.:" in svg
    assert "Net Wt.:" in svg
    assert "441 lb" in svg
    assert svg.count("________") == 2
    assert 'y="108" font-size="10.5" font-weight="bold"' in svg


def test_header_shipment_fields_fit_with_full_size_logo():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Highway Shipped Product"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
        shipment=ShipmentInfo(lot_number="LOT-12345", expiration_date="12/2027", fill_amount="441 lb"),
    )

    svg = generator.generate_svg(data, mode="workplace", size="drum")

    weight_match = re.search(r'<text x="(?P<x>\d+)" y="108" font-size="10.5"[^>]*>\s*441 lb', svg, re.S)
    assert weight_match
    assert int(weight_match.group("x")) <= 574


def test_container_size_name_is_not_printed_on_label():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge Size Test"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
        shipment=ShipmentInfo(fill_amount="441 lb"),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail")

    assert "Pail Label" not in svg
    assert "Drum Label" not in svg
    assert "441 lb" in svg


def test_fill_amount_defaults_numeric_values_to_pounds_and_preserves_kgs():
    assert LabelGenerator._format_fill_amount("441") == "441 lb"
    assert LabelGenerator._format_fill_amount("441 lb") == "441 lb"
    assert LabelGenerator._format_fill_amount("200 kg") == "200 kg"
    assert LabelGenerator._format_fill_amount("200 kgs") == "200 kgs"


def test_ghs_pictograms_render_only_approved_table_images():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="CE Flex Mod"),
        ghs=GHSClassification(pictograms=["GHS07", "GHS08", "GHS09"]),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="drum")

    assert 'id="pictogram-GHS07"' in svg
    assert 'id="pictogram-GHS08"' in svg
    assert 'id="pictogram-GHS09"' in svg
    assert "data:image/png;base64" in svg
    assert "GHS Pictogram Table.png" in {
        asset["source"] for asset in generator.ghs_pictogram_assets.values()
    }
    assert not hasattr(generator, "ghs_symbols")
    assert 'text-anchor="middle">!</text>' not in svg
    assert 'M27.5 32 L30 37 L36 37' not in svg
    assert 'M10 39 C18 32,28 32,35 39' not in svg
    assert '>GHS07<' not in svg
    assert '>GHS08<' not in svg
    assert '>GHS09<' not in svg


def test_all_ghs_assets_are_derived_from_approved_table_file():
    generator = LabelGenerator()
    asset_dir = Path(__file__).resolve().parents[1] / "app" / "assets" / "ghs_pictograms"

    assert (asset_dir / "GHS Pictogram Table.png").exists()
    assert set(generator.ghs_pictogram_assets) == {
        "GHS01",
        "GHS02",
        "GHS03",
        "GHS04",
        "GHS05",
        "GHS06",
        "GHS07",
        "GHS08",
        "GHS09",
    }
    for asset in generator.ghs_pictogram_assets.values():
        assert asset["data_uri"].startswith("data:image/png;base64,")
        assert asset["source"] == "GHS Pictogram Table.png"


def test_nfpa_704_diamond_is_not_rendered_on_product_labels():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge NFPA Test"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail")

    assert 'id="nfpa-704"' not in svg
    assert 'id="symbols-summary"' in svg
    assert "NFPA 704" not in svg
    assert "SDS not listed; default 0" not in svg


def test_nfpa_source_values_remain_metadata_only_and_are_not_rendered():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge NFPA Rated Test"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
        nfpa=NFPA704Ratings(
            health=2,
            flammability=3,
            instability=1,
            special="OX",
            source="sds",
        ),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail")

    assert 'id="nfpa-704"' not in svg
    assert "NFPA 704" not in svg
    assert "0=min 4=severe" not in svg


def test_silapox_horizontal_label_renders_all_source_h_and_p_statements_without_nfpa():
    generator = LabelGenerator()
    hazards = [
        ("H227", "Combustible liquid"),
        ("H315", "Causes skin irritation"),
        ("H317", "May cause an allergic skin reaction"),
        ("H319", "Causes serious eye irritation"),
        ("H341", "Suspected of causing genetic defects"),
        ("H351", "Suspected of causing cancer"),
        ("H361", "Suspected of damaging fertility or the unborn child"),
        ("H411", "Toxic to aquatic life with long lasting effects"),
    ]
    precautions = [
        ("P203", "Obtain, read and follow all safety instructions before use."),
        ("P210", "Keep away from heat, hot surfaces, sparks, open flames and other ignition sources. No smoking."),
        ("P261", "Avoid breathing dust/fume/gas/mist/vapours/spray."),
        ("P264", "Wash hands and other parts of the body thoroughly after handling."),
        ("P272", "Contaminated work clothing should not be allowed out of the workplace."),
        ("P273", "Avoid release to the environment."),
        ("P280", "Wear protective gloves/protective clothing/eye protection/face protection/hearing protection."),
        ("P264+P265", "Wash hands and other parts of the body thoroughly after handling. Do not touch eyes."),
        ("P318", "IF exposed or concerned, get medical advice."),
        ("P321", "Specific treatment (see measures on this label)."),
        ("P391", "Collect spillage."),
        ("P302+P352", "IF ON SKIN: Wash with plenty of water."),
        ("P332+P317", "If skin irritation occurs: Get medical help."),
        ("P333+P317", "If skin irritation or rash occurs: Get medical help."),
        ("P337+P317", "If eye irritation persists: Get medical help."),
        ("P362+P364", "Take off contaminated clothing and wash it before reuse."),
        ("P370+P378", "In case of fire: Use suitable extinguishing medium to extinguish."),
        ("P305+P351+P338", "IF IN EYES: Rinse cautiously with water for several minutes. Remove contact lenses, if present and easy to do. Continue rinsing."),
        ("P403", "Store in a well-ventilated place."),
        ("P405", "Store locked up."),
        ("P501", "Dispose of contents/container in accordance with local/regional/national/international regulations."),
    ]
    data = ExtractedData(
        product=ProductInfo(name="CE SilaPox EF", product_uses=["High-temperature coatings"]),
        shipment=ShipmentInfo(fill_amount="200 kg", container_type="drum"),
        ghs=GHSClassification(
            signal_word="Warning",
            pictograms=["GHS02", "GHS07", "GHS08"],
            hazard_statements=[HazardStatement(code=code, text=text) for code, text in hazards],
            precautionary_statements=[
                PrecautionaryStatement(code=code, text=text) for code, text in precautions
            ],
        ),
        transport=TransportClassification(
            un_number="UN3082",
            proper_shipping_name="ENVIRONMENTALLY HAZARDOUS SUBSTANCE, LIQUID, N.O.S.",
            hazard_class="9",
            packing_group="III",
            marine_pollutant=True,
        ),
    )

    svg = generator.generate_svg(
        data,
        mode="shipped_dot",
        size="drum",
        orientation="horizontal",
    )

    assert 'id="nfpa-704"' not in svg
    assert 'id="safety-statements"' in svg
    assert 'data-safety-columns="3"' in svg
    for code, text in hazards + precautions:
        assert code in svg
        assert text in svg
    safety_block = re.search(
        r'<g id="safety-statements"[^>]*>[\s\S]*?<rect x="10" y="(?P<y>[\d.]+)" width="[\d.]+" height="(?P<height>[\d.]+)"',
        svg,
    )
    transport_block = re.search(
        r'<g id="transport-info">[\s\S]*?<rect x="10" y="(?P<y>[\d.]+)" width="[\d.]+" height="(?P<height>[\d.]+)"',
        svg,
    )
    footer_line = re.search(r'<g id="footer">[\s\S]*?<line x1="10" y1="(?P<y>[\d.]+)"', svg)
    assert safety_block and transport_block and footer_line
    assert float(safety_block.group("y")) + float(safety_block.group("height")) < float(transport_block.group("y"))
    assert float(transport_block.group("y")) + float(transport_block.group("height")) <= float(footer_line.group("y")) - 8


def test_shipped_dot_not_regulated_state_renders():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge PSA 336"),
        ghs=GHSClassification(),
        transport=TransportClassification(proper_shipping_name="Not regulated"),
    )

    svg = generator.generate_svg(data, mode="shipped_dot", size="drum")

    assert "DOT TRANSPORT INFORMATION" in svg
    assert "NOT REGULATED FOR DOT TRANSPORT" in svg
    assert "Domestic ground: not regulated as a dangerous good based on the SDS." in svg


def test_dot_transport_panel_uses_packaged_dot_label_asset_for_class_3():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge Regulated Solvent"),
        ghs=GHSClassification(),
        transport=TransportClassification(
            un_number="UN1993",
            proper_shipping_name="Flammable liquids, n.o.s.",
            hazard_class="3",
            packing_group="II",
        ),
    )

    svg = generator.generate_svg(data, mode="shipped_dot", size="drum")

    assert 'id="dot-label-3"' in svg
    assert "data:image/png;base64" in svg
    assert "DOT Label:" in svg
    assert "FLAMMABLE LIQUID" in svg
    assert 'fill="#C8102E"' in svg


def test_dot_transport_panel_formats_id_number_with_prefix():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge Regulated Solvent"),
        ghs=GHSClassification(),
        transport=TransportClassification(
            un_number="1993",
            proper_shipping_name="Flammable liquids, n.o.s. (xylene)",
            hazard_class="3",
            packing_group="II",
        ),
    )

    svg = generator.generate_svg(data, mode="shipped_dot", size="drum")

    assert "UN/NA ID:" in svg
    assert "ID NUMBER:" not in svg
    assert "UN1993" in svg
    assert "Flammable liquids, n.o.s. (xylene)" in svg


def test_product_name_is_prominent_on_customer_drum_label():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Rucolac B-212", supplier_name="Rudolf"),
        ghs=GHSClassification(signal_word="Warning"),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(
        data,
        mode="workplace",
        size="drum",
        branding={"mode": "custom", "logo_data_uri": "data:image/png;base64,Y3VzdG9t"},
    )

    match = re.search(r'font-size="(?P<size>\d+)"\s+font-weight="bold" fill="#110251" text-anchor="middle">\s*Rucolac B-212', svg)
    assert match
    assert int(match.group("size")) >= 40


def test_dense_shipped_label_keeps_transport_panel_above_footer():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(
            name="Rucolac B-212",
            product_uses=[
                "Industrial coatings",
                "Waterproofing membranes",
                "Adhesive modification",
            ],
            supplier_name="RUDOLF GmbH",
            supplier_address="Altvaterstrasse 58-64, D-82538 Geretsried",
            supplier_phone="+49-(0)8171-53-0",
            emergency_phone="+49-8171-53-222",
            revision_date="2025-03-06",
        ),
        ghs=GHSClassification(
            signal_word="Warning",
            pictograms=["GHS02", "GHS07"],
            hazard_statements=[
                HazardStatement(code="H226", text="Flammable liquid and vapor."),
                HazardStatement(code="H319", text="Causes serious eye irritation."),
                HazardStatement(code="H336", text="May cause drowsiness or dizziness."),
                HazardStatement(code="H412", text="Harmful to aquatic life with long lasting effects."),
            ],
            precautionary_statements=[
                PrecautionaryStatement(code="P210", text="Keep away from heat, hot surfaces, sparks, open flames and other ignition sources. No smoking."),
                PrecautionaryStatement(code="P261", text="Avoid breathing vapors, spray, or mist."),
                PrecautionaryStatement(code="P280", text="Wear protective gloves, protective clothing, and eye protection."),
                PrecautionaryStatement(code="P403+P233", text="Store in a well-ventilated place. Keep container tightly closed."),
                PrecautionaryStatement(code="P501", text="Dispose of contents and container according to local regulations."),
            ],
        ),
        transport=TransportClassification(
            un_number="NA1993",
            proper_shipping_name="COMBUSTIBLE LIQUID, N.O.S (2-methoxy-1-methylethyl acetate)",
            hazard_class="3",
            packing_group="III",
        ),
    )

    svg = generator.generate_svg(
        data,
        mode="shipped_dot",
        size="drum",
        orientation="horizontal",
        branding={"mode": "custom", "logo_data_uri": "data:image/png;base64,Y3VzdG9t"},
    )

    footer_line = re.search(r'<g id="footer">[\s\S]*?<line x1="10" y1="(?P<y>\d+)" x2="\d+" y2="\d+"\s+stroke="#110251"', svg)
    transport_rect = re.search(r'<g id="transport-info">[\s\S]*?<rect x="10" y="(?P<y>[\d.]+)" width="[\d.]+" height="(?P<height>[\d.]+)"\s+fill="#FFF" stroke="#110251" stroke-width="[34]"', svg)

    assert footer_line
    assert transport_rect
    assert 'id="product-uses"' in svg
    transport_bottom = float(transport_rect.group("y")) + float(transport_rect.group("height"))
    assert transport_bottom <= float(footer_line.group("y")) - 8


def test_dot_transport_panel_offsets_fields_after_wrapped_shipping_name():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge Combustible"),
        ghs=GHSClassification(),
        transport=TransportClassification(
            un_number="NA1993",
            proper_shipping_name="COMBUSTIBLE LIQUID, N.O.S (2-methoxy-1-methylethyl acetate)",
            hazard_class="3",
            packing_group="III",
        ),
    )

    svg = generator.generate_svg(data, mode="shipped_dot", size="drum")

    def text_y_containing(needle: str) -> int:
        for match in re.finditer(r'<text[^>]* y="(?P<y>\d+)"[^>]*>(?P<body>.*?)</text>', svg, re.S):
            if needle in match.group("body"):
                return int(match.group("y"))
        raise AssertionError(f"Text not found in SVG: {needle}")

    shipping_line_y = text_y_containing("1-methylethyl acetate")
    hazard_y = text_y_containing("Hazard Class")
    packing_y = text_y_containing("Packing Group")
    dot_label_y = text_y_containing("DOT Label")

    assert hazard_y >= shipping_line_y + 15
    assert packing_y >= hazard_y + 18
    assert dot_label_y >= packing_y + 18


def test_dot_transport_panel_renders_optional_dot_marking_fields():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge Regulated Solvent"),
        ghs=GHSClassification(),
        transport=TransportClassification(
            un_number="UN1993",
            proper_shipping_name="Flammable liquids, n.o.s. (xylene)",
            hazard_class="3",
            packing_group="II",
            marine_pollutant=True,
            limited_quantity="Yes",
        ),
    )

    svg = generator.generate_svg(data, mode="shipped_dot", size="drum")

    assert "Marine Pollutant:" in svg
    assert "Limited Quantity:" in svg
