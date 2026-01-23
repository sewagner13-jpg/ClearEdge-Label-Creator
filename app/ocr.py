"""
OCR engine using pytesseract for fallback text extraction.
Used when PDF text extraction yields poor results.
"""

import io
import logging
from typing import Optional
from pdf2image import convert_from_bytes
from PIL import Image
import pytesseract

from .config import settings

logger = logging.getLogger(__name__)


class OCREngine:
    """OCR text extraction using Tesseract."""

    def __init__(self):
        self.tesseract_cmd = settings.tesseract_cmd
        self.lang = settings.ocr_lang

        # Set tesseract command path
        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

    def extract_from_page(
        self,
        pdf_bytes: bytes,
        page_index: int,
        dpi: int = 300
    ) -> str:
        """
        Extract text from a specific PDF page using OCR.

        Args:
            pdf_bytes: PDF file content
            page_index: 0-based page index
            dpi: Resolution for PDF rasterization

        Returns:
            Extracted text
        """
        try:
            # Convert specific page to image
            images = convert_from_bytes(
                pdf_bytes,
                dpi=dpi,
                first_page=page_index + 1,
                last_page=page_index + 1
            )

            if not images:
                logger.warning(f"No image generated for page {page_index}")
                return ""

            image = images[0]

            # Perform OCR
            text = pytesseract.image_to_string(
                image,
                lang=self.lang,
                config='--psm 1'  # Automatic page segmentation with OSD
            )

            return text.strip()

        except Exception as e:
            logger.error(f"OCR extraction failed for page {page_index}: {e}")
            raise

    def extract_from_image(self, image: Image.Image) -> str:
        """Extract text from PIL Image."""
        try:
            text = pytesseract.image_to_string(image, lang=self.lang)
            return text.strip()
        except Exception as e:
            logger.error(f"OCR from image failed: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Tesseract is available."""
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
