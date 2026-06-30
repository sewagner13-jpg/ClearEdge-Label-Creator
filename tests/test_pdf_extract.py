import io

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
