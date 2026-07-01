from io import BytesIO

from pypdf import PdfReader
import pytest

from app.dot_sticker_sheet import (
    DOT_STICKER_SIZE_PT,
    DOT_STICKERS_PER_PAGE,
    DotStickerSheetRenderer,
    DotStickerSheetUnavailable,
)


def _sticker(hazard_class="3", source="primary", quantity=1):
    return {
        "hazard_class": hazard_class,
        "label_name": "FLAMMABLE LIQUID" if hazard_class == "3" else "CORROSIVE",
        "asset_key": hazard_class,
        "source": source,
        "quantity": quantity,
    }


def test_one_required_dot_sticker_fills_letter_sheet_with_four_100mm_placements():
    renderer = DotStickerSheetRenderer()

    pages = renderer.render_svg_pages([_sticker("3")])

    assert len(pages) == 1
    assert pages[0].count('class="dot-sticker"') == DOT_STICKERS_PER_PAGE
    assert f'width="{DOT_STICKER_SIZE_PT:.3f}"' in pages[0]
    assert f'height="{DOT_STICKER_SIZE_PT:.3f}"' in pages[0]

    pdf = renderer.generate_pdf([_sticker("3")])
    assert len(PdfReader(BytesIO(pdf)).pages) == 1


def test_multiple_required_dot_sticker_types_alternate_on_sheet():
    renderer = DotStickerSheetRenderer()

    pages = renderer.render_svg_pages([_sticker("3", "primary"), _sticker("8", "subsidiary")])

    assert len(pages) == 1
    assert pages[0].count('data-hazard-class="3"') == 2
    assert pages[0].count('data-hazard-class="8"') == 2


def test_five_required_dot_stickers_create_second_page_and_fill_both_pages():
    renderer = DotStickerSheetRenderer()

    pdf = renderer.generate_pdf([_sticker("3", quantity=5)])
    pages = renderer.render_svg_pages([_sticker("3", quantity=5)])

    assert len(pages) == 2
    assert all(page.count('class="dot-sticker"') == DOT_STICKERS_PER_PAGE for page in pages)
    assert len(PdfReader(BytesIO(pdf)).pages) == 2


def test_unsupported_dot_sticker_class_fails_with_clear_reason():
    renderer = DotStickerSheetRenderer()

    with pytest.raises(DotStickerSheetUnavailable, match="DOT_STICKER_ASSET_UNAVAILABLE"):
        renderer.render_svg_pages([_sticker("6.1")])
