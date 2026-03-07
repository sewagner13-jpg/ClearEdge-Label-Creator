"""
PDF text extraction with automatic OCR fallback.
Extracts text from PDFs page-by-page with quality detection.
"""

import io
import logging
from typing import List, Tuple
import pdfplumber
from pypdf import PdfReader

from .config import settings
from .schema import ExtractedText, ExtractedTextPage

logger = logging.getLogger(__name__)


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
