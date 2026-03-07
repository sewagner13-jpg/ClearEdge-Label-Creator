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
<svg width="{{ width }}" height="{{ height }}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <!-- Background -->
  <rect width="{{ width }}" height="{{ height }}" fill="white"/>
  <rect x="5" y="5" width="{{ width - 10 }}" height="{{ height - 10 }}" fill="none" stroke="black" stroke-width="3"/>

  <!-- CLEAR EDGE Header with Logo Area -->
  <rect x="10" y="10" width="{{ width - 20 }}" height="90" fill="{{ header_color }}" rx="8"/>

  <!-- Logo placeholder (left side) -->
  <rect x="20" y="20" width="70" height="70" fill="white" rx="5"/>
  <text x="55" y="48" font-size="11" font-weight="bold" fill="{{ header_color }}" text-anchor="middle">CLEAR</text>
  <text x="55" y="62" font-size="11" font-weight="bold" fill="{{ header_color }}" text-anchor="middle">EDGE</text>
  <text x="55" y="78" font-size="8" fill="{{ header_color }}" text-anchor="middle">SOLUTIONS</text>

  <!-- Product Name (center/right) -->
  <text x="{{ width // 2 + 20 }}" y="45" font-size="22" font-weight="bold" fill="white" text-anchor="middle">
    {{ product_name }}
  </text>
  <text x="{{ width // 2 + 20 }}" y="75" font-size="11" fill="white" text-anchor="middle">
    CLEAREDGE SOLUTIONS
  </text>
  <text x="{{ width - 30 }}" y="90" font-size="9" fill="white" text-anchor="end">
    {{ size_label }}
  </text>

  <!-- Signal Word (if present) -->
  {% if signal_word %}
  <rect x="10" y="110" width="{{ width - 20 }}" height="55"
        fill="{{ '#DC143C' if signal_word == 'Danger' else '#FFA500' }}"
        stroke="black" stroke-width="3" rx="5"/>
  <text x="{{ width // 2 }}" y="145"
        font-size="32" font-weight="bold"
        fill="white" text-anchor="middle"
        style="text-transform: uppercase;">
    ⚠ {{ signal_word }} ⚠
  </text>
  {% set y_offset = 175 %}
  {% else %}
  {% set y_offset = 110 %}
  {% endif %}

  <!-- GHS Pictograms Section -->
  {% if pictograms %}
  <g id="pictograms">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="100"
          fill="#F5F5F5" stroke="#5A2D82" stroke-width="2" rx="5"/>
    <text x="20" y="{{ y_offset + 20 }}" font-size="13" font-weight="bold" fill="#333">
      HAZARD PICTOGRAMS:
    </text>

    <!-- Pictogram boxes -->
    {% for pictogram in pictograms[:8] %}
    <g transform="translate({{ 20 + (loop.index0 % 4) * 140 }}, {{ y_offset + 30 + (loop.index0 // 4) * 55 }})">
      <rect width="55" height="55" fill="white" stroke="#E74C3C" stroke-width="3"
            transform="rotate(45 27.5 27.5)"/>
      <text x="27.5" y="32" font-size="9" font-weight="bold"
            fill="#E74C3C" text-anchor="middle">{{ pictogram }}</text>
    </g>
    {% endfor %}
  </g>
  {% set y_offset = y_offset + 110 %}
  {% endif %}

  <!-- Hazard Statements Section -->
  {% if hazard_statements %}
  <g id="hazard-statements">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="auto"
          fill="#FFF3CD" stroke="#856404" stroke-width="2" rx="5"/>
    <text x="20" y="{{ y_offset + 20 }}" font-size="13" font-weight="bold" fill="#856404">
      HAZARD STATEMENTS (H):
    </text>
    {% for statement in hazard_statements[:6] %}
    <text x="25" y="{{ y_offset + 40 + loop.index0 * 16 }}" font-size="10" fill="#333">
      <tspan font-weight="bold">{{ statement.code or '•' }}:</tspan> {{ statement.text[:65] }}{% if statement.text|length > 65 %}...{% endif %}
    </text>
    {% endfor %}
  </g>
  {% set y_offset = y_offset + 40 + (hazard_statements[:6]|length * 16) + 15 %}
  {% endif %}

  <!-- Precautionary Statements Section -->
  {% if precautionary_statements %}
  <g id="precautionary-statements">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="auto"
          fill="#D1ECF1" stroke="#0C5460" stroke-width="2" rx="5"/>
    <text x="20" y="{{ y_offset + 20 }}" font-size="13" font-weight="bold" fill="#0C5460">
      PRECAUTIONARY STATEMENTS (P):
    </text>
    {% for statement in precautionary_statements[:6] %}
    <text x="25" y="{{ y_offset + 40 + loop.index0 * 16 }}" font-size="10" fill="#333">
      <tspan font-weight="bold">{{ statement.code or '•' }}:</tspan> {{ statement.text[:65] }}{% if statement.text|length > 65 %}...{% endif %}
    </text>
    {% endfor %}
  </g>
  {% set y_offset = y_offset + 40 + (precautionary_statements[:6]|length * 16) + 15 %}
  {% endif %}

  <!-- DOT TRANSPORT INFORMATION (if shipped_dot mode and UN number present) -->
  {% if mode == 'shipped_dot' and un_number %}
  <g id="transport-info">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="130"
          fill="#FFF" stroke="#DC143C" stroke-width="4" rx="5"/>

    <!-- Header -->
    <rect x="15" y="{{ y_offset + 5 }}" width="{{ width - 30 }}" height="30"
          fill="#DC143C" rx="3"/>
    <text x="{{ width // 2 }}" y="{{ y_offset + 25 }}"
          font-size="16" font-weight="bold" fill="white" text-anchor="middle">
      ⚠ DOT TRANSPORT INFORMATION ⚠
    </text>

    <!-- UN Number (large and prominent) -->
    <rect x="20" y="{{ y_offset + 45 }}" width="160" height="70"
          fill="#FFE5E5" stroke="#DC143C" stroke-width="3" rx="5"/>
    <text x="100" y="{{ y_offset + 70 }}" font-size="14" font-weight="bold"
          fill="#DC143C" text-anchor="middle">UN NUMBER:</text>
    <text x="100" y="{{ y_offset + 100 }}" font-size="28" font-weight="bold"
          fill="#DC143C" text-anchor="middle">{{ un_number }}</text>

    <!-- Shipping Details -->
    <g transform="translate(190, {{ y_offset + 45 }})">
      <text x="0" y="15" font-size="11" fill="#333">
        <tspan font-weight="bold">Proper Shipping Name:</tspan>
      </text>
      <text x="0" y="32" font-size="10" fill="#333">{{ shipping_name[:45] }}</text>

      <text x="0" y="50" font-size="11" fill="#333">
        <tspan font-weight="bold">Hazard Class:</tspan> {{ hazard_class or 'N/A' }}
      </text>

      {% if packing_group %}
      <text x="0" y="68" font-size="11" fill="#333">
        <tspan font-weight="bold">Packing Group:</tspan> {{ packing_group }}
      </text>
      {% endif %}
    </g>
  </g>
  {% set y_offset = y_offset + 140 %}
  {% endif %}

  <!-- Footer Section -->
  <g id="footer">
    <line x1="10" y1="{{ height - 110 }}" x2="{{ width - 10 }}" y2="{{ height - 110 }}"
          stroke="#5A2D82" stroke-width="2"/>

    <!-- Supplier Information -->
    <text x="20" y="{{ height - 90 }}" font-size="11" font-weight="bold" fill="#333">
      {{ supplier_name or 'ClearEdge Solutions' }}
    </text>
    <text x="20" y="{{ height - 75 }}" font-size="9" fill="#666">
      {{ supplier_address or '14301 CR Koon Highway, Newberry, SC 29108' }}
    </text>
    <text x="20" y="{{ height - 60 }}" font-size="10" fill="#666">
      {{ supplier_phone or 'www.clear-edge.net' }}
    </text>

    <!-- Emergency Contact (prominent) -->
    {% if emergency_phone %}
    <rect x="20" y="{{ height - 50 }}" width="240" height="30"
          fill="#DC143C" rx="5"/>
    <text x="30" y="{{ height - 30 }}" font-size="11" font-weight="bold" fill="white">
      24-HR EMERGENCY: {{ emergency_phone }}
    </text>
    {% endif %}

    <!-- QR Code Placeholder (right side) -->
    <rect x="{{ width - 95 }}" y="{{ height - 95 }}" width="80" height="80"
          fill="white" stroke="#5A2D82" stroke-width="2" rx="5"/>
    <text x="{{ width - 55 }}" y="{{ height - 50 }}" font-size="9"
          text-anchor="middle" fill="#5A2D82" font-weight="bold">
      SCAN FOR
    </text>
    <text x="{{ width - 55 }}" y="{{ height - 38 }}" font-size="9"
          text-anchor="middle" fill="#5A2D82" font-weight="bold">
      FULL SDS
    </text>

    <!-- Revision Date -->
    {% if revision_date %}
    <text x="{{ width // 2 }}" y="{{ height - 15 }}" font-size="9"
          text-anchor="middle" fill="#666">
      Revised: {{ revision_date }}
    </text>
    {% endif %}
  </g>
</svg>
"""

    def __init__(self):
        self.header_color = settings.purple_header_color

        # Label sizes in points (1 inch = 72 points)
        # Standard 8.5" x 11" = 612 x 792 points
        self.sizes = {
            "pail": {"width": 612, "height": 792, "name": "Pail Label"},
            "drum": {"width": 612, "height": 792, "name": "Drum Label"}
        }

    def generate_svg(
        self,
        data: ExtractedData,
        mode: str = "shipped_dot",
        size: str = "pail",
        template_name: str = "default"
    ) -> str:
        """
        Generate SVG label from extracted data.

        Args:
            data: Extracted product data
            mode: "shipped_dot" or "workplace"
            size: "pail" or "drum"
            template_name: Template identifier

        Returns:
            SVG content as string
        """
        logger.info(f"Generating SVG label for '{data.product.name}' in {mode} mode, {size} size")

        # Get dimensions for selected size
        size_config = self.sizes.get(size, self.sizes["pail"])
        width = size_config["width"]
        height = size_config["height"]
        size_label = size_config["name"]

        # Prepare template context
        context = {
            "width": width,
            "height": height,
            "header_color": self.header_color,
            "mode": mode,
            "size_label": size_label,
            "product_name": data.product.name,
            "signal_word": data.ghs.signal_word,
            "pictograms": data.ghs.pictograms,
            "hazard_statements": data.ghs.hazard_statements,
            "precautionary_statements": data.ghs.precautionary_statements,
            "un_number": data.transport.un_number,
            "shipping_name": data.transport.proper_shipping_name or "N/A",
            "hazard_class": data.transport.hazard_class,
            "packing_group": data.transport.packing_group,
            "supplier_name": data.product.supplier_name,
            "supplier_address": data.product.supplier_address,
            "supplier_phone": data.product.supplier_phone,
            "emergency_phone": data.product.emergency_phone,
            "revision_date": data.product.revision_date
        }

        # Render template
        template = Template(self.SVG_TEMPLATE)
        svg_content = template.render(**context)

        logger.info(f"Generated SVG ({len(svg_content)} bytes) for {size} label")
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
