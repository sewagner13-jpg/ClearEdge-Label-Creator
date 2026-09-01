import base64
from io import BytesIO

from pypdf import PdfReader
import pytest

from app.dot_sticker_sheet import (
    DOT_STICKERS_PER_PAGE,
    DotStickerSheetRenderer,
    DotStickerSheetUnavailable,
    US_LETTER_HEIGHT_PT,
    US_LETTER_WIDTH_PT,
)


def _sticker(hazard_class="3", source="primary", quantity=1):
    return {
        "hazard_class": hazard_class,
        "label_name": "FLAMMABLE LIQUID" if hazard_class == "3" else "CORROSIVE",
        "asset_key": hazard_class,
        "source": source,
        "quantity": quantity,
    }


def _marine_pollutant_mark():
    return {
        "hazard_class": None,
        "label_name": "MARINE POLLUTANT",
        "asset_key": "marine_pollutant",
        "mark_type": "marine_pollutant",
        "source": "marine_pollutant",
        "quantity": 1,
    }


def test_one_required_dot_sticker_renders_two_135mm_copies_on_landscape_sheet():
    renderer = DotStickerSheetRenderer()
    expected_size_pt = 135 * 72 / 25.4

    pages = renderer.render_svg_pages([_sticker("3")])

    assert len(pages) == 1
    assert pages[0].count('class="dot-sticker"') == DOT_STICKERS_PER_PAGE
    assert pages[0].count('data-hazard-class="3"') == 2
    assert pages[0].count(f'width="{expected_size_pt:.3f}"') == 2
    assert pages[0].count(f'height="{expected_size_pt:.3f}"') == 2

    pdf = renderer.generate_pdf([_sticker("3")])
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) == 1
    assert float(reader.pages[0].mediabox.width) == US_LETTER_HEIGHT_PT
    assert float(reader.pages[0].mediabox.height) == US_LETTER_WIDTH_PT


def test_dot_sticker_assets_are_normalized_to_square_viewbox():
    renderer = DotStickerSheetRenderer()
    asset = renderer.assets["3"]
    raw_svg = base64.b64decode(asset.data_uri.split(",", 1)[1]).decode("utf-8")

    assert 'viewBox="0 0 656 656"' in raw_svg
    assert 'width="656"' in raw_svg
    assert 'height="656"' in raw_svg


def test_class_3_sticker_sheet_renders_required_red_background():
    renderer = DotStickerSheetRenderer()
    pages = renderer.render_svg_pages([_sticker("3")])

    assert 'class="dot-sticker-background"' in pages[0]
    assert 'fill="#D71920"' in pages[0]


def test_two_required_dot_sticker_types_render_once_each():
    renderer = DotStickerSheetRenderer()

    pages = renderer.render_svg_pages([_sticker("3", "primary"), _sticker("8", "subsidiary")])

    assert len(pages) == 1
    assert pages[0].count('class="dot-sticker"') == 2
    assert pages[0].count('data-hazard-class="3"') == 1
    assert pages[0].count('data-hazard-class="8"') == 1


def test_class_9_and_marine_pollutant_render_once_each_as_large_landscape_pair():
    renderer = DotStickerSheetRenderer()

    pages = renderer.render_svg_pages([_sticker("9"), _marine_pollutant_mark()])

    large_size_pt = 135 * 72 / 25.4
    assert len(pages) == 1
    assert '<svg xmlns="http://www.w3.org/2000/svg" width="792pt" height="612pt"' in pages[0]
    assert pages[0].count('class="dot-sticker"') == 2
    assert pages[0].count('data-hazard-class="9"') == 1
    assert pages[0].count('data-mark-type="marine_pollutant"') == 1
    assert pages[0].count(f'width="{large_size_pt:.3f}" height="{large_size_pt:.3f}"') == 2

    pdf = renderer.generate_pdf([_sticker("9"), _marine_pollutant_mark()])
    page = PdfReader(BytesIO(pdf)).pages[0]
    assert float(page.mediabox.width) == US_LETTER_HEIGHT_PT
    assert float(page.mediabox.height) == US_LETTER_WIDTH_PT


def test_marine_pollutant_mark_uses_packaged_official_image_asset():
    asset = DotStickerSheetRenderer().assets["marine_pollutant"]

    assert asset.asset_key == "marine_pollutant"
    assert asset.data_uri.startswith("data:image/png;base64,")


def test_three_unique_required_assets_create_two_filled_two_up_pages():
    renderer = DotStickerSheetRenderer()

    stickers = [_sticker("3"), _sticker("8", source="subsidiary"), _sticker("9", source="subsidiary")]
    pdf = renderer.generate_pdf(stickers)
    pages = renderer.render_svg_pages(stickers)

    assert len(pages) == 2
    assert all(page.count('class="dot-sticker"') == DOT_STICKERS_PER_PAGE for page in pages)
    assert pages[0].count('data-hazard-class="3"') == 1
    assert pages[0].count('data-hazard-class="8"') == 1
    assert pages[1].count('data-hazard-class="9"') == 2
    assert len(PdfReader(BytesIO(pdf)).pages) == 2


def test_unsupported_dot_sticker_class_fails_with_clear_reason():
    renderer = DotStickerSheetRenderer()

    with pytest.raises(DotStickerSheetUnavailable, match="DOT_STICKER_ASSET_UNAVAILABLE"):
        renderer.render_svg_pages([_sticker("6.1")])
