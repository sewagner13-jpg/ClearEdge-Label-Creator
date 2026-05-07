from pathlib import Path

from app.label_stub import LabelGenerator
from app.schema import (
    ExtractedData,
    GHSClassification,
    HazardStatement,
    NFPA704Ratings,
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
    assert svg.count("#1B006E") >= 6
    assert 'id="pictogram-GHS02"' in svg
    assert "data:image/png;base64" in svg


def test_product_name_uses_logo_purple():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="CE Flex Mod"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="drum")

    assert 'font-weight="bold" fill="#1B006E"' in svg
    assert 'text-anchor="middle"' in svg
    assert "CE Flex Mod" in svg


def test_long_product_name_wraps_inside_header_without_logo_box():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="CE Surfactant 336 PSA Extended Batch Name"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail")

    assert "CE Surfactant 336" in svg
    assert "PSA Extended Batc..." in svg
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
    assert 'font-size="15.5" font-weight="bold"' in svg
    assert "Exp.:" in svg
    assert "Net Wt.:" in svg
    assert "441 lb" in svg
    assert svg.count("________") == 2
    assert 'font-size="13.5" font-weight="bold"' in svg


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


def test_nfpa_704_diamond_is_rendered_on_every_label():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge NFPA Test"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail")

    assert 'id="nfpa-704"' in svg
    assert 'id="symbols-summary"' in svg
    assert 'id="nfpa-704" transform="translate(462, 131)"' in svg
    assert "NFPA 704" in svg
    assert "0=min 4=severe" in svg
    assert "#ED1C24" in svg
    assert "#0094D8" in svg
    assert "#FFD700" in svg
    assert svg.count(">0<") == 3


def test_nfpa_704_diamond_renders_source_values():
    generator = LabelGenerator()
    data = ExtractedData(
        product=ProductInfo(name="ClearEdge NFPA Rated Test"),
        ghs=GHSClassification(),
        transport=TransportClassification(),
        nfpa=NFPA704Ratings(health=2, flammability=3, instability=1, special="OX"),
    )

    svg = generator.generate_svg(data, mode="workplace", size="pail")

    assert ">2<" in svg
    assert ">3<" in svg
    assert ">1<" in svg
    assert ">OX<" in svg


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
