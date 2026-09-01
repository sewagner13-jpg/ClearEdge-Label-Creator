import base64
import io
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw

from app.pdf_extract import PDFExtractor


def _image_pdf(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([8, 8, width - 8, height - 8], outline="purple", width=4)
    draw.text((24, max(12, height // 3)), "Vendor Logo", fill="purple")
    buffer = io.BytesIO()
    image.save(buffer, format="PDF")
    return buffer.getvalue()


def test_extract_suggested_logo_returns_wide_embedded_pdf_image():
    extractor = PDFExtractor()

    suggestion = extractor.extract_suggested_logo(
        _image_pdf(420, 90),
        doc_type="SDS",
        source_filename="vendor-sds.pdf",
    )

    assert suggestion is not None
    assert suggestion["source_document"] == "SDS"
    assert suggestion["source_file"] == "vendor-sds.pdf"
    assert suggestion["page"] == 1
    assert suggestion["width"] == 420
    assert suggestion["height"] == 90
    assert suggestion["media_type"] == "image/jpeg"
    assert suggestion["data_uri"].startswith("data:image/jpeg;base64,")


def test_extract_suggested_logo_skips_square_pictogram_like_images():
    extractor = PDFExtractor()

    suggestion = extractor.extract_suggested_logo(
        _image_pdf(120, 120),
        doc_type="SDS",
        source_filename="vendor-sds.pdf",
    )

    assert suggestion is None


def test_extract_text_detects_authoritative_embedded_silapox_pictograms():
    asset_dir = Path(__file__).resolve().parents[1] / "app" / "assets" / "ghs_pictograms"
    assets = [
        "GHS02_flame.png",
        "GHS07_exclamation_point.png",
        "GHS08_health_hazard.png",
    ]
    image_elements = []
    for index, filename in enumerate(assets):
        encoded = base64.b64encode((asset_dir / filename).read_bytes()).decode("ascii")
        image_elements.append(
            f'<image x="{20 + index * 180}" y="20" width="150" height="150" '
            f'href="data:image/png;base64,{encoded}"/>'
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="200">'
        '<text x="20" y="195">Section 2 Hazards Identification</text>'
        f'{"".join(image_elements)}</svg>'
    )
    pdf_bytes = cairosvg.svg2pdf(bytestring=svg.encode("utf-8"))

    extracted = PDFExtractor().extract_text(pdf_bytes, "SDS", use_ocr_fallback=False)

    assert [item.code for item in extracted.detected_ghs_pictograms] == [
        "GHS02",
        "GHS07",
        "GHS08",
    ]
    assert all(item.page == 1 for item in extracted.detected_ghs_pictograms)
