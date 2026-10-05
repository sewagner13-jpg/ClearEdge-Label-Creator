from pathlib import Path
import base64
from io import BytesIO
import re

from PIL import Image
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


def assert_safety_transport_footer_clearance(svg: str) -> None:
    safety_block = re.search(
        r'<g id="safety-statements"[^>]*>[\s\S]*?'
        r'<rect x="10" y="(?P<y>[\d.]+)" width="[\d.]+" height="(?P<height>[\d.]+)"',
        svg,
    )
    transport_block = re.search(
        r'<g id="transport-info">[\s\S]*?'
        r'<rect x="10" y="(?P<y>[\d.]+)" width="[\d.]+" height="(?P<height>[\d.]+)"',
        svg,
    )
    footer_line = re.search(r'<g id="footer">[\s\S]*?<line x1="10" y1="(?P<y>[\d.]+)"', svg)

    assert safety_block and transport_block and footer_line
    safety_bottom = float(safety_block.group("y")) + float(safety_block.group("height"))
    transport_top = float(transport_block.group("y"))
    transport_bottom = transport_top + float(transport_block.group("height"))
    assert safety_bottom < transport_top
    assert transport_bottom <= float(footer_line.group("y")) - 8


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


def test_sample_4x6_label_renders_every_approved_required_pictogram():
    generator = LabelGenerator()
    pictograms = [
        "GHS01", "GHS02", "GHS03", "GHS04", "GHS05",
        "GHS06", "GHS07", "GHS08", "GHS09",
    ]
    data = ExtractedData(
        product=ProductInfo(name="Five Mark Sample"),
        ghs=GHSClassification(signal_word="Danger", pictograms=pictograms),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="sample_4x6")

    for code in pictograms:
        assert svg.count(f'id="pictogram-{code}"') == 1


def test_sample_4x6_six_pictograms_stay_inside_the_ghs_panel():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Six Mark Sample"),
        ghs=GHSClassification(
            signal_word="Danger",
            pictograms=["GHS01", "GHS02", "GHS03", "GHS04", "GHS05", "GHS06"],
        ),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="sample_4x6")
    pictograms = re.findall(
        r'<image id="pictogram-GHS\d{2}" x="(?P<x>[\d.]+)" y="[\d.]+" '
        r'width="(?P<width>[\d.]+)"',
        svg,
    )

    assert len(pictograms) == 6
    assert max(float(x) + float(width) for x, width in pictograms) <= 414


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
        image_bytes = base64.b64decode(asset["data_uri"].split(",", 1)[1])
        with Image.open(BytesIO(image_bytes)) as image:
            rgba = image.convert("RGBA")
            assert rgba.getpixel((0, 0))[3] == 0
            assert rgba.getpixel((rgba.width - 1, rgba.height - 1))[3] == 0
            assert rgba.getpixel((rgba.width // 2, rgba.height // 2))[3] == 255
            interior = rgba.crop(
                (
                    rgba.width // 4,
                    rgba.height // 4,
                    (rgba.width * 3) // 4,
                    (rgba.height * 3) // 4,
                )
            )
            assert any(
                alpha == 255 and min(red, green, blue) >= 240
                for red, green, blue, alpha in interior.getdata()
            )


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


def test_source_backed_nfpa_values_render_in_standard_orientation():
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

    assert 'id="nfpa-704"' in svg
    assert 'data-nfpa-source="sds"' in svg
    assert 'data-quadrant="health"' in svg
    assert 'data-quadrant="flammability"' in svg
    assert 'data-quadrant="instability"' in svg
    assert 'data-quadrant="special"' in svg
    assert 'data-rating="health">2</text>' in svg
    assert 'data-rating="flammability">3</text>' in svg
    assert 'data-rating="instability">1</text>' in svg
    assert 'data-rating="special">OX</text>' in svg
    assert "#0072BC" in svg
    assert "#ED1C24" in svg
    assert "#FFF200" in svg
    assert "NFPA 704" not in svg
    assert "SUPPLEMENTAL" not in svg
    nfpa_group = re.search(r'<g id="nfpa-704"[\s\S]*?>(?P<body>[\s\S]*?)</g>', svg)
    assert nfpa_group
    assert "NFPA 704" not in nfpa_group.group("body")
    assert "SUPPLEMENTAL" not in nfpa_group.group("body")
    assert "<rect" not in nfpa_group.group("body")


def test_silacure_nfpa_panel_preserves_required_us_label_content():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(
            name="CE SilaCure SC",
            emergency_phone="704-799-5769",
            revision_date="2026-09-02",
        ),
        shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
        ghs=GHSClassification(
            signal_word="Danger",
            pictograms=["GHS05", "GHS07"],
            hazard_statements=[
                HazardStatement(code="H314", text="Causes severe skin burns and eye damage"),
                HazardStatement(code="H317", text="May cause an allergic skin reaction"),
            ],
            precautionary_statements=[
                PrecautionaryStatement(code="P260", text="Do not breathe vapors"),
                PrecautionaryStatement(code="P280", text="Wear protective gloves and eye protection"),
            ],
        ),
        transport=TransportClassification(
            un_number="UN2735",
            proper_shipping_name="AMINES, LIQUID, CORROSIVE, N.O.S. (Amidoamine)",
            hazard_class="8",
            packing_group="III",
            marine_pollutant=False,
        ),
        nfpa=NFPA704Ratings(
            health=3,
            flammability=1,
            instability=0,
            special=None,
            source="sds",
        ),
    )

    svg = generator.generate_svg(
        data,
        mode="shipped_dot",
        size="drum",
        orientation="horizontal",
    )

    assert 'id="nfpa-704"' in svg
    assert 'data-rating="health">3</text>' in svg
    assert 'data-rating="flammability">1</text>' in svg
    assert 'data-rating="instability">0</text>' in svg
    assert 'data-rating="special"></text>' in svg
    assert 'id="dot-label-8"' in svg
    assert "UN2735" in svg
    assert "AMINES, LIQUID, CORROSIVE, N.O.S. (Amidoamine)" in svg
    assert 'id="pictogram-GHS05"' in svg
    assert 'id="pictogram-GHS07"' in svg
    assert "Danger" in svg
    assert "H314" in svg and "H317" in svg
    assert "P260" in svg and "P280" in svg


def test_dense_us_shipped_label_keeps_safety_and_transport_marks_print_legible():
    generator = LabelGenerator()
    hazard_statements = [
        HazardStatement(code="H314", text="Causes severe skin burns and eye damage"),
        HazardStatement(code="H317", text="May cause an allergic skin reaction"),
        HazardStatement(code="H318", text="Causes serious eye damage"),
        HazardStatement(code="H402", text="Harmful to aquatic life"),
    ]
    precautionary_codes = [
        "P260", "P264", "P272", "P273", "P280", "P301+P330+P331", "P310",
        "P302+P352", "P303+P361+P353", "P304+P340", "P305+P351+P338", "P321",
        "P333+P313", "P363", "P405", "P501",
    ]
    precautionary_statements = [
        PrecautionaryStatement(code=code, text=f"Source-backed precaution {index}")
        for index, code in enumerate(precautionary_codes, start=1)
    ]
    data = ExtractedData(
        product=ProductInfo(
            name="CE SilaCure SC",
            supplier_name="ClearEdge Solutions",
            supplier_address="14301 CR Koon Highway, Newberry, SC 29108",
            supplier_phone="704-799-5769",
            emergency_phone="704-799-5769",
        ),
        shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
        ghs=GHSClassification(
            signal_word="Danger",
            pictograms=["GHS05", "GHS07"],
            hazard_statements=hazard_statements,
            precautionary_statements=precautionary_statements,
        ),
        transport=TransportClassification(
            un_number="UN2735",
            proper_shipping_name="AMINES, LIQUID, CORROSIVE, N.O.S. (Amidoamine)",
            hazard_class="8",
            packing_group="III",
        ),
        nfpa=NFPA704Ratings(
            health=3,
            flammability=1,
            instability=0,
            source="sds",
        ),
    )

    svg = generator.generate_svg(
        data,
        mode="shipped_dot",
        size="drum",
        orientation="horizontal",
    )

    assert re.search(r'id="pictogram-GHS05"[^>]*width="64" height="64"', svg)
    assert re.search(r'id="pictogram-GHS07"[^>]*width="64" height="64"', svg)
    assert re.search(r'id="un-identification-number"[^>]*font-size="48"', svg)
    assert re.search(r'id="dot-label-8"[^>]*width="96" height="96"', svg)
    assert 'data-nfpa-diamond-size-mm="25.4"' in svg
    assert 'data-nfpa-role="supplemental"' in svg
    for statement in [*hazard_statements, *precautionary_statements]:
        assert statement.code in svg
    assert_safety_transport_footer_clearance(svg)


def test_standard_label_renders_every_approved_required_pictogram():
    generator = LabelGenerator()
    pictograms = ["GHS02", "GHS05", "GHS06", "GHS07", "GHS08"]
    data = ExtractedData(
        product=ProductInfo(name="Five Mark Product"),
        shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
        ghs=GHSClassification(signal_word="Danger", pictograms=pictograms),
        transport=TransportClassification(not_regulated=True),
    )

    svg = generator.generate_svg(
        data,
        mode="shipped_dot",
        size="drum",
        orientation="horizontal",
    )

    for code in pictograms:
        assert svg.count(f'id="pictogram-{code}"') == 1


def test_dense_vertical_us_shipped_label_keeps_safety_and_transport_marks_print_legible():
    generator = LabelGenerator()
    hazard_statements = [
        HazardStatement(code=f"H31{index}", text="Source-backed hazard statement")
        for index in range(4)
    ]
    precautionary_statements = [
        PrecautionaryStatement(code=f"P2{index:02d}", text="Source-backed precautionary statement")
        for index in range(18)
    ]
    data = ExtractedData(
        product=ProductInfo(name="Dense Portrait Product", product_uses=["Industrial coating additive"]),
        shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
        ghs=GHSClassification(
            signal_word="Danger",
            pictograms=["GHS05", "GHS07", "GHS08"],
            hazard_statements=hazard_statements,
            precautionary_statements=precautionary_statements,
        ),
        transport=TransportClassification(
            un_number="UN2735",
            proper_shipping_name="AMINES, LIQUID, CORROSIVE, N.O.S. (Amidoamine)",
            hazard_class="8",
            packing_group="III",
        ),
    )

    svg = generator.generate_svg(
        data,
        mode="shipped_dot",
        size="drum",
        orientation="vertical",
    )

    for statement in [*hazard_statements, *precautionary_statements]:
        assert statement.code in svg
    assert re.search(r'id="un-identification-number"[^>]*font-size="48"', svg)
    assert_safety_transport_footer_clearance(svg)


def test_saturated_vertical_layout_reserves_footer_clearance():
    class SaturatingLabelGenerator(LabelGenerator):
        def _build_compact_safety_layout(self, data, *, width, available_height, dense):
            statement = {
                "code": "H314",
                "text": "Causes severe skin burns and eye damage",
                "lines": ["Causes severe skin burns and eye damage"],
                "y": 0.0,
            }
            return {
                "hazard_statements": [statement],
                "precautionary_statements": [],
                "groups": [{"heading": "HAZARD STATEMENTS (H)", "statements": [statement]}],
                "block_height": available_height,
                "font_size": 7.2,
                "line_height": 7.8,
                "column_width": width - 40,
                "continuation_indent": 14.0,
                "fits": True,
            }

    generator = SaturatingLabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Saturated Portrait Product"),
        shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
        ghs=GHSClassification(
            signal_word="Danger",
            pictograms=["GHS05", "GHS07"],
            hazard_statements=[HazardStatement(code="H314", text="Causes severe skin burns and eye damage")],
        ),
        transport=TransportClassification(
            un_number="UN2735",
            proper_shipping_name="AMINES, LIQUID, CORROSIVE, N.O.S. (Amidoamine)",
            hazard_class="8",
            packing_group="III",
        ),
    )

    svg = generator.generate_svg(data, mode="shipped_dot", size="drum", orientation="vertical")

    assert_safety_transport_footer_clearance(svg)
    transport_block = re.search(
        r'<g id="transport-info">[\s\S]*?'
        r'<rect x="10" y="(?P<y>[\d.]+)" width="[\d.]+" height="(?P<height>[\d.]+)"',
        svg,
    )
    footer_line = re.search(r'<g id="footer">[\s\S]*?<line x1="10" y1="(?P<y>[\d.]+)"', svg)
    assert transport_block and footer_line
    transport_bottom = float(transport_block.group("y")) + float(transport_block.group("height"))
    assert transport_bottom <= float(footer_line.group("y")) - 15


def test_compact_safety_layout_rejects_a_height_fit_with_overlapping_columns():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Narrow Column Product"),
        ghs=GHSClassification(
            hazard_statements=[HazardStatement(code="H314", text="ABCDEFGH")],
            precautionary_statements=[
                PrecautionaryStatement(code="P301+P310+P330", text="ABCDEFGH")
                for _ in range(4)
            ],
        ),
        transport=TransportClassification(),
    )

    layout = generator._build_compact_safety_layout(
        data,
        width=320,
        available_height=50,
        dense=True,
    )

    # At 6.4 pt the block fits vertically but the combination code crosses
    # the column boundary. The horizontal guard must select the safe 6.0 pt candidate.
    assert layout["font_size"] == 6.0
    assert layout["block_height"] <= 50


def test_long_dense_safety_text_stays_above_transport_and_footer():
    generator = LabelGenerator()
    hazards = [
        HazardStatement(
            code=f"H31{index}",
            text="Causes serious adverse health effects after exposure and requires immediate attention",
        )
        for index in range(4)
    ]
    precautions = [
        PrecautionaryStatement(
            code=f"P2{index:02d}",
            text=(
                "Obtain and follow all source safety instructions, wear suitable protective equipment, "
                "and obtain medical attention when exposure symptoms occur"
            ),
        )
        for index in range(18)
    ]
    data = ExtractedData(
        product=ProductInfo(name="Dense Source-Backed Product", product_uses=["Industrial coating additive"]),
        shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
        ghs=GHSClassification(
            signal_word="Danger",
            pictograms=["GHS05", "GHS07", "GHS08"],
            hazard_statements=hazards,
            precautionary_statements=precautions,
        ),
        transport=TransportClassification(
            un_number="UN2735",
            proper_shipping_name="AMINES, LIQUID, CORROSIVE, N.O.S. (Amidoamine)",
            hazard_class="8",
            packing_group="III",
        ),
    )

    svg = generator.generate_svg(
        data,
        mode="shipped_dot",
        size="drum",
        orientation="horizontal",
    )

    for statement in [*hazards, *precautions]:
        assert statement.code in svg
        assert statement.text in svg
    assert_safety_transport_footer_clearance(svg)


def test_transport_identification_number_is_not_ellipsized_and_uses_fitted_font_size():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Invalid Multi-ID Product"),
        shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
        ghs=GHSClassification(
            signal_word="Warning",
            pictograms=["GHS07"],
            hazard_statements=[HazardStatement(code="H315", text="Causes skin irritation")],
        ),
        transport=TransportClassification(
            un_number="UN1234/UN5678",
            proper_shipping_name="TEST MATERIAL",
            hazard_class="8",
            packing_group="III",
        ),
    )

    svg = generator.generate_svg(
        data,
        mode="shipped_dot",
        size="drum",
        orientation="horizontal",
    )
    match = re.search(
        r'id="un-identification-number"[^>]*font-size="(?P<size>[\d.]+)"[^>]*>'
        r'(?P<value>[^<]+)</text>',
        svg,
    )

    assert match
    assert match.group("value") == "UN1234/UN5678"
    assert "..." not in match.group("value")
    assert float(match.group("size")) < 48


def test_nfpa_footer_reserves_space_for_emergency_contact_and_clearedge_mark():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(
            name="Customer NFPA Product",
            supplier_name="Customer Chemical Manufacturing and Distribution Company International",
            supplier_address=(
                "200 Customer Industrial Manufacturing and Distribution Lane, "
                "Charlotte, North Carolina 28202"
            ),
            supplier_phone="+1 (704) 555-0199 extension 123456",
            emergency_phone="800-555-0111",
        ),
        ghs=GHSClassification(),
        transport=TransportClassification(),
        nfpa=NFPA704Ratings(
            health=3,
            flammability=1,
            instability=0,
            source="sds",
        ),
    )
    branding = {
        "mode": "custom",
        "logo_data_uri": "data:image/png;base64,Y3VzdG9tLWxvZ28=",
        "show_clearedge_mark": True,
    }

    for size in ("pail", "drum", "tote"):
        for orientation in ("vertical", "horizontal"):
            svg = generator.generate_svg(
                data,
                mode="workplace",
                size=size,
                orientation=orientation,
                branding=branding,
            )
            emergency = re.search(
                r'id="emergency-contact-box" x="(?P<x>[\d.]+)"[^>]*'
                r'width="(?P<width>[\d.]+)"',
                svg,
            )
            nfpa = re.search(
                r'id="nfpa-704"[^>]*transform="translate\((?P<x>[\d.]+),',
                svg,
            )
            process_mark = re.search(
                r'id="clearedge-process-mark"[^>]*transform="translate\((?P<x>[\d.]+),',
                svg,
            )

            assert emergency and nfpa and process_mark
            emergency_right = float(emergency.group("x")) + float(emergency.group("width"))
            nfpa_x = float(nfpa.group("x"))
            process_mark_x = float(process_mark.group("x"))
            assert emergency_right + 12 <= nfpa_x
            assert nfpa_x + 104 + 12 <= process_mark_x

            for element_id, font_size in (
                ("supplier-name", 10.5),
                ("supplier-address", 8.0),
                ("supplier-phone", 8.5),
            ):
                supplier = re.search(
                    rf'id="{element_id}"[^>]*>(?P<value>[^<]*)</text>',
                    svg,
                )
                assert supplier
                rendered_width = (
                    generator._estimated_text_width_units(supplier.group("value").strip())
                    * font_size
                )
                assert 20 + rendered_width + 8 <= nfpa_x


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
    assert 'data-safety-columns="5"' in svg
    assert "High-temperature coatings" not in svg
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


def test_compact_dot_flags_respect_the_space_before_the_reference_diamond():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Compact Flag Layout"),
        shipment=ShipmentInfo(fill_amount="50 lb", container_type="pail"),
        ghs=GHSClassification(
            signal_word="Warning",
            pictograms=["GHS07"],
            hazard_statements=[HazardStatement(code="H315", text="Causes skin irritation")],
        ),
        transport=TransportClassification(
            un_number="UN1993",
            proper_shipping_name="FLAMMABLE LIQUIDS, N.O.S. (xylene)",
            hazard_class="3",
            packing_group="II",
            marine_pollutant=True,
            limited_quantity="5 L inner packaging",
        ),
    )

    svg = generator.generate_svg(
        data,
        mode="shipped_dot",
        size="pail",
        orientation="horizontal",
    )

    flags = re.findall(
        r'<text class="compact-dot-flag" x="(?P<x>[\d.]+)" y="(?P<y>[\d.]+)"[^>]*'
        r'data-absolute-x="(?P<absolute_x>[\d.]+)"[^>]*'
        r'data-max-width="(?P<max_width>[\d.]+)"[^>]*>(?P<text>[^<]+)</text>',
        svg,
    )
    dot_image = re.search(r'id="dot-label-3"[^>]* x="(?P<x>[\d.]+)"', svg)
    assert len(flags) == 2
    assert dot_image
    for _x, _y, absolute_x, max_width, text in flags:
        assert float(absolute_x) + float(max_width) <= float(dot_image.group("x")) - 8
        assert text.strip()

    hazard_y = re.search(r'data-row="hazard-class"[^>]* y="(?P<y>[\d.]+)"', svg)
    packing_y = re.search(r'data-row="packing-group"[^>]* y="(?P<y>[\d.]+)"', svg)
    assert hazard_y and packing_y
    assert float(flags[0][1]) == float(hazard_y.group("y"))
    assert float(flags[1][1]) == float(packing_y.group("y"))


def test_product_label_dot_art_is_visibly_marked_as_reference_only():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Reference Marking Product"),
        shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
        ghs=GHSClassification(
            signal_word="Warning",
            pictograms=["GHS07"],
            hazard_statements=[HazardStatement(code="H315", text="Causes skin irritation")],
        ),
        transport=TransportClassification(
            un_number="UN1993",
            proper_shipping_name="FLAMMABLE LIQUIDS, N.O.S.",
            hazard_class="3",
            packing_group="II",
        ),
    )

    for orientation in ("horizontal", "vertical"):
        svg = generator.generate_svg(
            data,
            mode="shipped_dot",
            size="drum",
            orientation=orientation,
        )
        assert 'data-dot-role="reference"' in svg
        assert "REFERENCE ONLY" in svg
        assert "APPLY SEPARATE DOT LABEL" in svg

        if orientation == "horizontal":
            band = re.search(
                r'<rect x="15" y="(?P<y>[\d.]+)" width="[\d.]+" height="23" '
                r'fill="#110251"',
                svg,
            )
            caption = re.search(
                r'<text x="[\d.]+" y="(?P<y>[\d.]+)" font-size="6.5"[\s\S]*?'
                r'REFERENCE ONLY',
                svg,
            )
            assert band and caption
            band_bottom = float(band.group("y")) + 23
            assert float(caption.group("y")) >= band_bottom + 6


def test_signal_word_has_clearance_before_the_pictogram_row():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="Signal Clearance Product"),
        shipment=ShipmentInfo(fill_amount="441 lb", container_type="drum"),
        ghs=GHSClassification(
            signal_word="Danger",
            pictograms=["GHS05"],
            hazard_statements=[HazardStatement(code="H314", text="Causes severe skin burns")],
        ),
        transport=TransportClassification(
            un_number="UN2735",
            proper_shipping_name="AMINES, LIQUID, CORROSIVE, N.O.S.",
            hazard_class="8",
            packing_group="III",
        ),
    )

    svg = generator.generate_svg(data, mode="shipped_dot", size="drum", orientation="vertical")
    signal = re.search(r'id="signal-word-heading" x="20" y="(?P<y>[\d.]+)"', svg)
    pictogram = re.search(
        r'<g transform="translate\(20(?:\.0)?, (?P<y>[\d.]+)\)">\s*'
        r'<image id="pictogram-GHS05"',
        svg,
    )

    assert signal and pictogram
    assert float(pictogram.group("y")) >= float(signal.group("y")) + 6
