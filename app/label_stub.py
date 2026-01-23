"""
Label generation stub - SVG and PDF creation.
Generates DOT/OSHA-compliant labels from extracted data.
"""

import io
import logging
from typing import Optional
import svgwrite
from jinja2 import Template
import qrcode
import cairosvg

from .config import settings
from .schema import ExtractedData

logger = logging.getLogger(__name__)


class LabelGenerator:
    """Generate SVG and PDF labels from extracted product data."""

    SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="{{ width }}" height="{{ height }}" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect width="{{ width }}" height="{{ height }}" fill="white" stroke="black" stroke-width="2"/>

  <!-- Header with logo area -->
  <rect x="10" y="10" width="{{ width - 20 }}" height="80" fill="{{ header_color }}" rx="5"/>
  <text x="{{ width // 2 }}" y="50" font-size="24" font-weight="bold" fill="white" text-anchor="middle">
    {{ product_name }}
  </text>
  <text x="{{ width // 2 }}" y="75" font-size="12" fill="white" text-anchor="middle">
    CLEAR EDGE FILTRATION PRODUCTS
  </text>

  <!-- Signal Word -->
  {% if signal_word %}
  <rect x="10" y="100" width="{{ width - 20 }}" height="40" fill="#FFD700" stroke="black" stroke-width="2"/>
  <text x="{{ width // 2 }}" y="125" font-size="20" font-weight="bold" text-anchor="middle">
    {{ signal_word }}
  </text>
  {% endif %}

  <!-- GHS Pictograms -->
  {% if pictograms %}
  <text x="20" y="{{ 160 if signal_word else 120 }}" font-size="14" font-weight="bold">
    Hazard Pictograms:
  </text>
  <!-- Placeholder for pictogram images -->
  {% for pictogram in pictograms %}
  <rect x="{{ 20 + loop.index0 * 60 }}" y="{{ 170 if signal_word else 130 }}"
        width="50" height="50" fill="#E8E8E8" stroke="black"/>
  <text x="{{ 45 + loop.index0 * 60 }}" y="{{ 200 if signal_word else 160 }}"
        font-size="10" text-anchor="middle">{{ pictogram }}</text>
  {% endfor %}
  {% endif %}

  <!-- Hazard Statements -->
  {% if hazard_statements %}
  <text x="20" y="{{ 250 if signal_word else 210 }}" font-size="14" font-weight="bold">
    Hazard Statements:
  </text>
  {% for statement in hazard_statements[:5] %}
  <text x="30" y="{{ (270 if signal_word else 230) + loop.index0 * 20 }}" font-size="11">
    {{ statement.code or '•' }}: {{ statement.text[:80] }}...
  </text>
  {% endfor %}
  {% endif %}

  <!-- DOT Shipping Information (if shipped_dot mode) -->
  {% if mode == 'shipped_dot' and un_number %}
  <rect x="10" y="{{ height - 200 }}" width="{{ width - 20 }}" height="120"
        fill="#FFF3CD" stroke="#FF0000" stroke-width="3"/>
  <text x="20" y="{{ height - 180 }}" font-size="16" font-weight="bold" fill="#CC0000">
    TRANSPORT INFORMATION
  </text>
  <text x="30" y="{{ height - 155 }}" font-size="12">UN {{ un_number }}</text>
  <text x="30" y="{{ height - 135 }}" font-size="11">{{ shipping_name[:50] }}</text>
  <text x="30" y="{{ height - 115 }}" font-size="11">Hazard Class: {{ hazard_class }}</text>
  {% if packing_group %}
  <text x="30" y="{{ height - 95 }}" font-size="11">Packing Group: {{ packing_group }}</text>
  {% endif %}
  {% endif %}

  <!-- Supplier Information -->
  <text x="20" y="{{ height - 60 }}" font-size="10">{{ supplier_name or 'Clear Edge' }}</text>
  {% if emergency_phone %}
  <text x="20" y="{{ height - 45 }}" font-size="10" font-weight="bold">
    Emergency: {{ emergency_phone }}
  </text>
  {% endif %}

  <!-- QR Code Placeholder -->
  <rect x="{{ width - 90 }}" y="{{ height - 90 }}" width="70" height="70"
        fill="white" stroke="black"/>
  <text x="{{ width - 55 }}" y="{{ height - 50 }}" font-size="8" text-anchor="middle">
    SCAN FOR
  </text>
  <text x="{{ width - 55 }}" y="{{ height - 40 }}" font-size="8" text-anchor="middle">
    SDS
  </text>

  <!-- Revision Date -->
  {% if revision_date %}
  <text x="{{ width // 2 }}" y="{{ height - 15 }}" font-size="9" text-anchor="middle">
    Rev. {{ revision_date }}
  </text>
  {% endif %}
</svg>
"""

    def __init__(self):
        self.width = settings.default_label_width
        self.height = settings.default_label_height
        self.header_color = settings.purple_header_color

    def generate_svg(
        self,
        data: ExtractedData,
        mode: str = "shipped_dot",
        template_name: str = "default"
    ) -> str:
        """
        Generate SVG label from extracted data.

        Args:
            data: Extracted product data
            mode: "shipped_dot" or "workplace"
            template_name: Template identifier

        Returns:
            SVG content as string
        """
        logger.info(f"Generating SVG label for '{data.product.name}' in {mode} mode")

        # Prepare template context
        context = {
            "width": self.width,
            "height": self.height,
            "header_color": self.header_color,
            "mode": mode,
            "product_name": data.product.name,
            "signal_word": data.ghs.signal_word,
            "pictograms": data.ghs.pictograms[:6],  # Max 6 pictograms
            "hazard_statements": data.ghs.hazard_statements,
            "precautionary_statements": data.ghs.precautionary_statements,
            "un_number": data.transport.un_number,
            "shipping_name": data.transport.proper_shipping_name,
            "hazard_class": data.transport.hazard_class,
            "packing_group": data.transport.packing_group,
            "supplier_name": data.product.supplier_name,
            "emergency_phone": data.product.emergency_phone,
            "revision_date": data.product.revision_date
        }

        # Render template
        template = Template(self.SVG_TEMPLATE)
        svg_content = template.render(**context)

        logger.info(f"Generated SVG ({len(svg_content)} bytes)")
        return svg_content

    def generate_pdf(self, svg_content: str) -> bytes:
        """
        Convert SVG to PDF.

        Args:
            svg_content: SVG markup

        Returns:
            PDF file bytes
        """
        logger.info("Converting SVG to PDF")

        try:
            pdf_bytes = cairosvg.svg2pdf(bytestring=svg_content.encode('utf-8'))
            logger.info(f"Generated PDF ({len(pdf_bytes)} bytes)")
            return pdf_bytes

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise

    def generate_qr_code(self, url: str, size: int = 200) -> bytes:
        """
        Generate QR code for SDS URL.

        Args:
            url: URL to encode
            size: QR code size in pixels

        Returns:
            PNG image bytes
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def save_label_files(
        self,
        drive_client,
        product_folder_id: str,
        date_folder: str,
        svg_content: str,
        pdf_bytes: bytes
    ) -> tuple[str, str]:
        """
        Save SVG and PDF labels to Drive.

        Returns:
            Tuple of (svg_file_id, pdf_file_id)
        """
        # Find or create Labels/{date} folder
        labels_folder_id = drive_client.find_subfolder(product_folder_id, "Labels")
        if not labels_folder_id:
            raise ValueError("Labels folder not found")

        dated_folder_id = drive_client.create_dated_folder(labels_folder_id, date_folder)

        # Upload SVG
        svg_id = drive_client.upload_file(
            svg_content.encode('utf-8'),
            "label.svg",
            dated_folder_id,
            "image/svg+xml"
        )
        logger.info(f"Uploaded label.svg: {svg_id}")

        # Upload PDF
        pdf_id = drive_client.upload_file(
            pdf_bytes,
            "label.pdf",
            dated_folder_id,
            "application/pdf"
        )
        logger.info(f"Uploaded label.pdf: {pdf_id}")

        return svg_id, pdf_id
