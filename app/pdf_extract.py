"""
PDF text extraction with automatic OCR fallback.
Extracts text from PDFs page-by-page with quality detection.
"""

import base64
import io
import logging
from typing import List, Optional
import pdfplumber
from pypdf import PdfReader
from PIL import Image

from .config import settings
from .schema import ExtractedText, ExtractedTextPage

logger = logging.getLogger(__name__)


MAX_SUGGESTED_LOGO_BYTES = 750 * 1024
MIN_LOGO_WIDTH = 120
MIN_LOGO_HEIGHT = 25
MIN_LOGO_ASPECT_RATIO = 2.2
SUPPORTED_LOGO_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


class PDFExtractor:
    """PDF text extraction with OCR fallback support."""

    def __init__(self):
        self.ocr_threshold = settings.ocr_threshold_chars

    def extract_text(
        self,
        pdf_bytes: bytes,
        doc_type: str,
        use_ocr_fallback: bool = True
    ) -> ExtractedText:
        """
        Extract text from PDF with automatic OCR fallback.

        Args:
            pdf_bytes: PDF file content
            doc_type: "SDS" or "TDS"
            use_ocr_fallback: Whether to use OCR for low-quality pages

        Returns:
            ExtractedText object with pages and method used
        """
        pages_data = []
        methods_used = set()

        try:
            # Try pdfplumber first (better text extraction)
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"Processing {total_pages} pages from {doc_type}")

                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    text = text.strip()

                    # Check if OCR fallback is needed
                    if len(text) < self.ocr_threshold and use_ocr_fallback:
                        logger.info(
                            f"Page {page_num}: Low text quality ({len(text)} chars), "
                            "attempting OCR"
                        )
                        try:
                            from .ocr import OCREngine
                            ocr_engine = OCREngine()
                            text = ocr_engine.extract_from_page(pdf_bytes, page_num - 1)
                            methods_used.add("ocr")
                            logger.info(f"Page {page_num}: OCR extracted {len(text)} chars")
                        except Exception as e:
                            logger.warning(f"Page {page_num}: OCR failed: {e}")
                            methods_used.add("text")
                    else:
                        methods_used.add("text")
                        logger.debug(f"Page {page_num}: Extracted {len(text)} chars")

                    pages_data.append(ExtractedTextPage(page=page_num, text=text))

        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}, trying pypdf")
            # Fallback to pypdf
            try:
                pages_data = self._extract_with_pypdf(pdf_bytes, use_ocr_fallback)
                methods_used.add("text")
            except Exception as e2:
                logger.error(f"pypdf extraction also failed: {e2}")
                raise ValueError(f"All PDF extraction methods failed: {e}, {e2}")

        # Determine overall method
        if "ocr" in methods_used and "text" in methods_used:
            method = "mixed"
        elif "ocr" in methods_used:
            method = "ocr"
        else:
            method = "text"

        return ExtractedText(
            doc=doc_type,
            method_used=method,
            pages=pages_data
        )

    def _extract_with_pypdf(
        self,
        pdf_bytes: bytes,
        use_ocr_fallback: bool
    ) -> List[ExtractedTextPage]:
        """Fallback extraction using pypdf."""
        pages_data = []
        reader = PdfReader(io.BytesIO(pdf_bytes))

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()

            if len(text) < self.ocr_threshold and use_ocr_fallback:
                try:
                    from .ocr import OCREngine
                    ocr_engine = OCREngine()
                    text = ocr_engine.extract_from_page(pdf_bytes, page_num - 1)
                    logger.info(f"Page {page_num}: OCR extracted {len(text)} chars (pypdf)")
                except Exception as e:
                    logger.warning(f"Page {page_num}: OCR failed (pypdf): {e}")

            pages_data.append(ExtractedTextPage(page=page_num, text=text))

        return pages_data

    def get_page_count(self, pdf_bytes: bytes) -> int:
        """Get total number of pages in PDF."""
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                return len(pdf.pages)
        except Exception:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            return len(reader.pages)

    def extract_suggested_logo(
        self,
        pdf_bytes: bytes,
        doc_type: str,
        source_filename: Optional[str] = None,
    ) -> Optional[dict]:
        """Return the best wide embedded image candidate as a suggested company logo."""
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as exc:
            logger.info("Logo suggestion skipped; PDF image scan failed: %s", exc)
            return None

        best_candidate = None
        for page_index, page in enumerate(reader.pages[:2], start=1):
            try:
                page_images = list(page.images)
            except Exception as exc:
                logger.info("Logo suggestion skipped on page %s: %s", page_index, exc)
                continue

            for image_index, image_file in enumerate(page_images):
                candidate = self._logo_candidate_from_image(
                    image_file=image_file,
                    doc_type=doc_type,
                    source_filename=source_filename,
                    page=page_index,
                    image_index=image_index,
                )
                if not candidate:
                    continue
                if not best_candidate or candidate["_score"] > best_candidate["_score"]:
                    best_candidate = candidate

        if not best_candidate:
            return None

        best_candidate.pop("_score", None)
        return best_candidate

    @staticmethod
    def _logo_candidate_from_image(
        *,
        image_file,
        doc_type: str,
        source_filename: Optional[str],
        page: int,
        image_index: int,
    ) -> Optional[dict]:
        image_bytes = getattr(image_file, "data", None)
        if not image_bytes or len(image_bytes) > MAX_SUGGESTED_LOGO_BYTES:
            return None

        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                width, height = image.size
                image_format = image.format
        except Exception:
            return None

        if not width or not height:
            return None

        aspect_ratio = width / height
        if (
            width < MIN_LOGO_WIDTH
            or height < MIN_LOGO_HEIGHT
            or aspect_ratio < MIN_LOGO_ASPECT_RATIO
        ):
            return None

        media_type = SUPPORTED_LOGO_FORMATS.get(str(image_format).upper())
        if not media_type:
            return None

        area = width * height
        score = aspect_ratio + min(area / 100000, 2.0)
        confidence = min(0.95, 0.55 + min(aspect_ratio / 12, 0.25) + min(area / 200000, 0.15))
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return {
            "available": True,
            "source_document": doc_type,
            "source_file": source_filename,
            "page": page,
            "name": getattr(image_file, "name", None) or f"image-{image_index + 1}",
            "width": width,
            "height": height,
            "media_type": media_type,
            "data_uri": f"data:{media_type};base64,{encoded}",
            "confidence": round(confidence, 2),
            "_score": score,
        }
