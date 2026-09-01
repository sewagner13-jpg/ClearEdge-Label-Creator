"""
Label generation stub - SVG and PDF creation.
Generates DOT/OSHA-compliant labels from extracted data.
"""

import io
import logging
import base64
from html import escape as html_escape
from pathlib import Path
from typing import Optional
import svgwrite
from jinja2 import Environment
import qrcode
import cairosvg

from .config import settings
from .schema import ExtractedData

logger = logging.getLogger(__name__)


class LabelGenerator:
    """Generate SVG and PDF labels from extracted product data."""

    CLEAREDGE_SUPPLIER_NAME = "ClearEdge Solutions"
    CLEAREDGE_SUPPLIER_ADDRESS = "14301 CR Koon Highway, Newberry, SC 29108"
    CLEAREDGE_SUPPLIER_PHONE = "704-799-5769"
    CLEAREDGE_LOGO_ASPECT_RATIO = 2794 / 596

    SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="{{ width }}pt" height="{{ height }}pt" viewBox="0 0 {{ width }} {{ height }}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" font-family="{{ body_font }}">
  <!-- Background -->
  <rect width="{{ width }}" height="{{ height }}" fill="white"/>
  <rect x="5" y="5" width="{{ width - 10 }}" height="{{ height - 10 }}" fill="none" stroke="black" stroke-width="2"/>

  <!-- CLEAR EDGE Header -->
  <rect x="10" y="10" width="{{ width - 20 }}" height="102" fill="white"/>
  <rect x="10" y="10" width="{{ width - 20 }}" height="8" fill="{{ brand_purple }}"/>
  <line x1="10" y1="112" x2="{{ width - 10 }}" y2="112" stroke="{{ brand_purple }}" stroke-width="2"/>

  <!-- Brand logo -->
  {% if logo_data_uri %}
  <image id="brand-logo" x="20" y="{{ logo_y }}" width="{{ logo_width }}" height="{{ logo_height }}"
         href="{{ logo_data_uri }}" xlink:href="{{ logo_data_uri }}"
         preserveAspectRatio="xMinYMid meet"/>
  {% else %}
  <text x="20" y="62" font-size="18" font-weight="bold"
        fill="{{ header_color }}">Custom Label</text>
  {% endif %}

  <!-- Product Name (center/right) -->
  <text x="{{ product_text_x }}" y="{{ product_name_y }}" font-size="{{ product_name_font_size }}"
        font-weight="bold" fill="{{ brand_purple }}" text-anchor="middle">
    {{ product_name_lines[0] }}
  </text>
  {% for line in product_name_lines[1:] %}
  <text x="{{ product_text_x }}" y="{{ product_name_y + (loop.index * product_name_line_gap) }}"
        font-size="{{ product_name_font_size }}" font-weight="bold" fill="{{ brand_purple }}"
        text-anchor="middle">
    {{ line }}
  </text>
  {% endfor %}
  <g id="shipment-info">
    <line x1="{{ product_area_x }}" y1="83" x2="{{ width - 22 }}" y2="83" stroke="#D7D0E8" stroke-width="1"/>
    <text x="{{ lot_label_x }}" y="94" font-size="8.5" font-weight="bold" fill="{{ brand_purple }}">
      Lot #:
    </text>
    <text x="{{ lot_value_x }}" y="108" font-size="{{ shipment_value_font_size }}" font-weight="bold" fill="{{ text_color }}">
      {{ lot_number_display }}
    </text>
    <text x="{{ expiration_label_x }}" y="94" font-size="8.5" font-weight="bold" fill="{{ brand_purple }}">
      Exp.:
    </text>
    <text x="{{ expiration_value_x }}" y="108" font-size="{{ shipment_value_font_size }}" font-weight="bold" fill="{{ text_color }}">
      {{ expiration_date_display }}
    </text>
    <text x="{{ weight_label_x }}" y="94" font-size="8.5" font-weight="bold" fill="{{ brand_purple }}">
      Net Wt.:
    </text>
    <text x="{{ weight_value_x }}" y="108" font-size="{{ shipment_value_font_size }}" font-weight="bold" fill="{{ text_color }}">
      {{ fill_amount_display }}
    </text>
  </g>

  <!-- Signal word brand band (kept blank by design) -->
  {% if signal_word %}
  <rect id="signal-strip" x="10" y="122" width="{{ width - 20 }}" height="30"
        fill="{{ brand_purple }}"
        rx="2"/>
  {% set y_offset = 160 %}
  {% else %}
  {% set y_offset = 124 %}
  {% endif %}

  <!-- Safety symbols band -->
  <g id="symbols-summary">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="96"
          fill="#FBFAFE" stroke="#C8BEDD" stroke-width="1.5" rx="3"/>
    {% if signal_word %}
    <text id="signal-word-heading" x="20" y="{{ y_offset + 30 }}" font-size="21"
          font-weight="bold" fill="{{ brand_purple }}" style="text-transform: uppercase;">
      {{ signal_word }}
    </text>
    {% endif %}

    <!-- Pictogram images pulled only from the approved GHS pictogram table asset. -->
    {% for pictogram in pictogram_icons[:4] %}
    <g transform="translate({{ 20 + (loop.index0 % 4) * 64 }}, {{ y_offset + 36 }})">
      <image id="pictogram-{{ pictogram.code }}" x="0" y="0" width="58" height="58"
             href="{{ pictogram.data_uri }}" xlink:href="{{ pictogram.data_uri }}"
             preserveAspectRatio="xMidYMid meet"/>
    </g>
    {% endfor %}

    <!-- NFPA 704 Diamond: included on every label. -->
    <g id="nfpa-704" transform="translate({{ width - 136 }}, {{ y_offset + 4 }})">
      <rect x="0" y="0" width="116" height="88" fill="white" stroke="#D8D3E6" stroke-width="1" rx="3"/>
      <text x="58" y="12" font-size="10" text-anchor="middle" fill="{{ text_color }}" font-weight="bold">
        NFPA 704
      </text>
      <text x="58" y="22" font-size="7" text-anchor="middle" fill="{{ text_color }}" opacity="0.75">
        {% if nfpa_source == "clearedge_default" %}SDS not listed; default 0{% else %}0=min 4=severe{% endif %}
      </text>
      <g transform="translate(28, 28) scale(0.49)">
        <polygon points="60,0 120,60 60,120 0,60" fill="#222222"/>
        <polygon points="60,8 87,35 60,60 33,35" fill="#ED1C24"/>
        <polygon points="8,60 33,35 60,60 33,87" fill="#0094D8"/>
        <polygon points="112,60 87,35 60,60 87,87" fill="#FFD700"/>
        <polygon points="60,112 33,87 60,60 87,87" fill="white"/>
        <text x="60" y="45" font-size="22" font-weight="bold" text-anchor="middle" fill="white">{{ nfpa_flammability }}</text>
        <text x="34" y="68" font-size="22" font-weight="bold" text-anchor="middle" fill="white">{{ nfpa_health }}</text>
        <text x="87" y="68" font-size="22" font-weight="bold" text-anchor="middle" fill="black">{{ nfpa_instability }}</text>
        <text x="60" y="94" font-size="14" font-weight="bold" text-anchor="middle" fill="black">{{ nfpa_special }}</text>
      </g>
    </g>
  </g>
  {% set y_offset = y_offset + 104 %}

  <!-- Compact TDS product uses. Kept short so compliance blocks keep priority. -->
  {% if product_uses %}
  <g id="product-uses">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="{{ product_uses_block_height }}"
          fill="#FFFFFF" stroke="#D8D3E6" stroke-width="1.5" rx="3"/>
    <text x="20" y="{{ y_offset + 17 }}" font-size="10" font-weight="bold" fill="{{ brand_purple }}">
      PRODUCT USES:
    </text>
    {% for line in product_uses %}
    <text x="116" y="{{ y_offset + 17 + (loop.index0 * 11) }}" font-size="8.8" fill="{{ text_color }}">
      {{ line }}
    </text>
    {% endfor %}
  </g>
  {% set y_offset = y_offset + product_uses_block_height + 8 %}
  {% endif %}

  <!-- Hazard Statements Section -->
  {% if hazard_statements %}
  <g id="hazard-statements">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="{{ hazard_block_height }}"
          fill="white" stroke="#D8D3E6" stroke-width="1.5" rx="3"/>
    <text x="20" y="{{ y_offset + 18 }}" font-size="11.5" font-weight="bold" fill="{{ brand_purple }}">
      HAZARD STATEMENTS (H):
    </text>
    {% for statement in hazard_statements %}
    <text x="25" y="{{ y_offset + 36 + statement.y }}" font-size="9" fill="{{ text_color }}">
      <tspan font-weight="bold">{{ statement.code }}:</tspan> {{ statement.lines[0] }}
    </text>
      {% for line in statement.lines[1:] %}
    <text x="55" y="{{ y_offset + 36 + statement.y + loop.index * 10 }}" font-size="9" fill="{{ text_color }}">
      {{ line }}
    </text>
      {% endfor %}
    {% endfor %}
  </g>
  {% set y_offset = y_offset + hazard_block_height + 10 %}
  {% endif %}

  <!-- Precautionary Statements Section -->
  {% if precautionary_statements %}
  <g id="precautionary-statements">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="{{ precautionary_block_height }}"
          fill="white" stroke="#D8D3E6" stroke-width="1.5" rx="3"/>
    <text x="20" y="{{ y_offset + 18 }}" font-size="11.5" font-weight="bold" fill="{{ brand_purple }}">
      PRECAUTIONARY STATEMENTS (P):
    </text>
    {% for statement in precautionary_statements %}
    <text x="25" y="{{ y_offset + 36 + statement.y }}" font-size="8.8" fill="{{ text_color }}">
      <tspan font-weight="bold">{{ statement.code }}:</tspan> {{ statement.lines[0] }}
    </text>
      {% for line in statement.lines[1:] %}
    <text x="55" y="{{ y_offset + 36 + statement.y + loop.index * 10 }}" font-size="8.8" fill="{{ text_color }}">
      {{ line }}
    </text>
      {% endfor %}
    {% endfor %}
  </g>
  {% set y_offset = y_offset + precautionary_block_height + 10 %}
  {% endif %}

  <!-- DOT TRANSPORT INFORMATION -->
  {% if mode == 'shipped_dot' and un_number %}
  <g id="transport-info">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="{{ dot_panel_height }}"
          fill="#FFF" stroke="{{ brand_purple }}" stroke-width="4" rx="5"/>

    <!-- Header -->
    <rect x="15" y="{{ y_offset + 5 }}" width="{{ width - 30 }}" height="30"
          fill="{{ brand_purple }}" rx="3"/>
    <text x="{{ width // 2 }}" y="{{ y_offset + 25 }}"
          font-size="16" font-weight="bold" fill="white" text-anchor="middle">
      DOT TRANSPORT INFORMATION
    </text>

    <!-- Identification number (large and prominent) -->
    <rect x="20" y="{{ y_offset + 45 }}" width="145" height="70"
          fill="{{ brand_purple_light }}" stroke="{{ brand_purple }}" stroke-width="3" rx="5"/>
    <text x="92" y="{{ y_offset + 70 }}" font-size="14" font-weight="bold"
          fill="{{ brand_purple }}" text-anchor="middle">UN/NA ID:</text>
    <text x="92" y="{{ y_offset + 100 }}" font-size="28" font-weight="bold"
          fill="{{ brand_purple }}" text-anchor="middle">{{ identification_number }}</text>

    <!-- Shipping Details -->
    <g transform="translate(180, {{ y_offset + 45 }})">
      <text x="0" y="15" font-size="11" fill="{{ text_color }}">
        <tspan font-weight="bold">Proper Shipping Name:</tspan>
      </text>
      {% for line in shipping_name_lines %}
      <text x="0" y="{{ 32 + (loop.index0 * 13) }}" font-size="10" fill="{{ text_color }}">{{ line }}</text>
      {% endfor %}

      <text x="0" y="{{ hazard_class_y }}" font-size="11" fill="{{ text_color }}">
        <tspan font-weight="bold">Hazard Class:</tspan> {{ hazard_class or 'N/A' }}
      </text>

      {% if packing_group %}
      <text x="0" y="{{ packing_group_y }}" font-size="11" fill="{{ text_color }}">
        <tspan font-weight="bold">Packing Group:</tspan> {{ packing_group }}
      </text>
      {% endif %}
      <text x="0" y="{{ dot_label_y }}" font-size="11" fill="{{ text_color }}">
        <tspan font-weight="bold">DOT Label:</tspan> {{ dot_label_name or 'Review required' }}
      </text>
      {% if marine_pollutant_display %}
      <text x="0" y="{{ marine_pollutant_y }}" font-size="10.5" fill="{{ text_color }}">
        <tspan font-weight="bold">Marine Pollutant:</tspan> {{ marine_pollutant_display }}
      </text>
      {% endif %}
      {% if limited_quantity_display %}
      <text x="0" y="{{ limited_quantity_y }}" font-size="10.5" fill="{{ text_color }}">
        <tspan font-weight="bold">Limited Quantity:</tspan> {{ limited_quantity_display }}
      </text>
      {% endif %}
    </g>

    {% if dot_labels %}
    {% for dot_label in dot_labels[:1] %}
    {% if dot_label.background %}
    <polygon points="{{ width - 90 }},{{ y_offset + 42 }} {{ width - 35 }},{{ y_offset + 97 }} {{ width - 90 }},{{ y_offset + 152 }} {{ width - 145 }},{{ y_offset + 97 }}"
             fill="{{ dot_label.background }}"/>
    {% endif %}
    <image id="dot-label-{{ dot_label.hazard_class }}" x="{{ width - 145 }}" y="{{ y_offset + 42 }}"
           width="110" height="110"
           href="{{ dot_label.data_uri }}" xlink:href="{{ dot_label.data_uri }}"
           preserveAspectRatio="xMidYMid meet"/>
    {% endfor %}
    {% endif %}
  </g>
  {% set y_offset = y_offset + dot_panel_height + 10 %}
  {% elif mode == 'shipped_dot' and transport_not_regulated %}
  <g id="transport-info">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="70"
          fill="#FFF" stroke="{{ brand_purple }}" stroke-width="2" rx="4"/>
    <rect x="15" y="{{ y_offset + 5 }}" width="{{ width - 30 }}" height="24"
          fill="{{ brand_purple }}" rx="3"/>
    <text x="{{ width // 2 }}" y="{{ y_offset + 25 }}"
          font-size="14" font-weight="bold" fill="white" text-anchor="middle">
      DOT TRANSPORT INFORMATION
    </text>
    <text x="{{ width // 2 }}" y="{{ y_offset + 49 }}"
          font-size="15" font-weight="bold" fill="{{ brand_purple }}" text-anchor="middle">
      NOT REGULATED FOR DOT TRANSPORT
    </text>
    <text x="{{ width // 2 }}" y="{{ y_offset + 63 }}"
          font-size="8.8" fill="{{ text_color }}" text-anchor="middle">
      Domestic ground: not regulated as a dangerous good based on the SDS.
    </text>
  </g>
  {% set y_offset = y_offset + 78 %}
  {% endif %}

  <!-- Footer Section -->
  <g id="footer">
    <line x1="10" y1="{{ height - 94 }}" x2="{{ width - 10 }}" y2="{{ height - 94 }}"
          stroke="{{ brand_purple }}" stroke-width="2"/>

    <!-- Supplier Information -->
    <text x="20" y="{{ height - 77 }}" font-size="10.5" font-weight="bold" fill="{{ text_color }}">
      {{ supplier_name or 'ClearEdge Solutions' }}
    </text>
    <text x="20" y="{{ height - 63 }}" font-size="8" fill="{{ text_color }}" opacity="0.75">
      {{ supplier_address or '14301 CR Koon Highway, Newberry, SC 29108' }}
    </text>
    <text x="20" y="{{ height - 50 }}" font-size="8.5" fill="{{ text_color }}" opacity="0.75">
      {{ supplier_phone }}
    </text>

    {% if show_clearedge_mark %}
    <g id="clearedge-process-mark" transform="translate({{ process_mark_x }}, {{ height - process_mark_bottom_offset }})">
      <rect x="0" y="0" width="{{ process_mark_width }}" height="{{ process_mark_height }}" fill="#FFFFFF" stroke="{{ brand_purple }}" stroke-width="1.2" rx="4"/>
      {% if clearedge_mark_logo_data_uri %}
      <image id="clearedge-process-logo" x="{{ process_mark_logo_x }}" y="{{ process_mark_logo_y }}" width="{{ process_mark_logo_width }}" height="{{ process_mark_logo_height }}"
             href="{{ clearedge_mark_logo_data_uri }}" xlink:href="{{ clearedge_mark_logo_data_uri }}"
             preserveAspectRatio="xMidYMid meet"/>
      {% else %}
      <text x="{{ process_mark_width // 2 }}" y="{{ process_mark_height - 11 }}" font-size="10" font-weight="bold" fill="{{ brand_purple }}" text-anchor="middle">
        ClearEdge
      </text>
      {% endif %}
    </g>
    {% endif %}

    <!-- Emergency Contact (prominent) -->
    {% if emergency_phone %}
    <rect x="20" y="{{ height - 40 }}" width="{{ emergency_box_width }}" height="26"
          fill="{{ brand_purple }}" rx="4"/>
    <text x="30" y="{{ height - 23 }}" font-size="10" font-weight="bold" fill="white">
      24-HR EMERGENCY: {{ emergency_phone }}
    </text>
    {% endif %}

    <!-- Revision Date -->
    {% if revision_date %}
    <text x="{{ width // 2 }}" y="{{ height - 8 }}" font-size="7.5"
          text-anchor="middle" fill="{{ text_color }}" opacity="0.75">
      Revised: {{ revision_date }}
    </text>
    {% endif %}
  </g>
</svg>
"""

    def __init__(self):
        self.header_color = settings.purple_header_color
        self.default_template_id = "clearedge_pail_v1"
        self.svg_template = Environment(autoescape=True).from_string(self.SVG_TEMPLATE)
        self.logo_data_uri = self._load_logo_data_uri()
        self.brand_palette = {
            "primary": "#110251",
            "primary_light": "#F0E9FF",
            "accent": "#B67CFF",
            "text": "#222222",
            "muted": "#666666"
        }
        self.dot_label_assets = self._load_dot_label_assets()
        self.ghs_pictogram_assets = self._load_ghs_pictogram_assets()

        # Phase 2: template registry (print area + brand token map)
        self.templates = {
            "clearedge_pail_v1": {
                "size": "pail",
                "width": 612,
                "height": 792,
                "name": "Pail Label",
                "safe_margin": 10,
                "header_height": 90,
                "max_product_name_chars": 30,
                "brand": {
                    "header_color": self.brand_palette["primary"],
                    "accent_color": self.brand_palette["accent"],
                    "body_font": "Arial, sans-serif",
                    "text_color": self.brand_palette["text"]
                }
            },
            "clearedge_drum_v1": {
                "size": "drum",
                "width": 648,
                "height": 864,
                "name": "Drum Label",
                "safe_margin": 12,
                "header_height": 100,
                "max_product_name_chars": 34,
                "brand": {
                    "header_color": self.brand_palette["primary"],
                    "accent_color": self.brand_palette["accent"],
                    "body_font": "Arial, sans-serif",
                    "text_color": self.brand_palette["text"]
                }
            },
            "clearedge_tote_v1": {
                "size": "tote",
                "width": 648,
                "height": 864,
                "name": "Tote Label",
                "safe_margin": 12,
                "header_height": 100,
                "max_product_name_chars": 34,
                "brand": {
                    "header_color": self.brand_palette["primary"],
                    "accent_color": self.brand_palette["accent"],
                    "body_font": "Arial, sans-serif",
                    "text_color": self.brand_palette["text"]
                }
            },
            "clearedge_sample_4x6_v1": {
                "size": "sample_4x6",
                "width": 432,
                "height": 288,
                "name": "Sample 4x6 Thermal Label",
                "safe_margin": 10,
                "header_height": 76,
                "max_product_name_chars": 38,
                "brand": {
                    "header_color": self.brand_palette["primary"],
                    "accent_color": self.brand_palette["accent"],
                    "body_font": "Arial, sans-serif",
                    "text_color": self.brand_palette["text"]
                }
            }
        }

    @staticmethod
    def _asset_data_uri(path: Path, media_type: str = "image/svg+xml") -> Optional[str]:
        """Load a packaged vector asset as an SVG-safe data URI."""
        if not path.exists():
            logger.warning("Label asset not found: %s", path)
            return None
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{media_type};base64,{encoded}"

    @staticmethod
    def _svg_asset_png_data_uri(path: Path, output_width: int = 580) -> Optional[str]:
        """Rasterize packaged SVG label assets so CairoSVG embeds them reliably."""
        if not path.exists():
            logger.warning("DOT label asset not found: %s", path)
            return None
        png_bytes = cairosvg.svg2png(
            bytestring=path.read_bytes(),
            output_width=output_width,
        )
        encoded = base64.b64encode(png_bytes).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    @classmethod
    def _load_dot_label_assets(cls) -> dict:
        """Load DOT hazard label SVGs based on 49 CFR Part 172 examples."""
        asset_dir = Path(__file__).resolve().parent / "assets" / "dot_labels"
        label_files = {
            "3": ("FLAMMABLE LIQUID", asset_dir / "class_3_flammable_liquid.svg", "#C8102E"),
            "8": ("CORROSIVE", asset_dir / "class_8_corrosive.svg", None),
            "9": ("CLASS 9", asset_dir / "class_9_miscellaneous.svg", None),
        }
        loaded = {}
        for hazard_class, (name, path, background) in label_files.items():
            data_uri = cls._svg_asset_png_data_uri(path)
            if data_uri:
                loaded[hazard_class] = {
                    "hazard_class": hazard_class,
                    "name": name,
                    "data_uri": data_uri,
                    "background": background,
                }
        return loaded

    @classmethod
    def _load_ghs_pictogram_assets(cls) -> dict:
        """Load only approved GHS pictogram crops from the source table image."""
        asset_dir = Path(__file__).resolve().parent / "assets" / "ghs_pictograms"
        source_table = asset_dir / "GHS Pictogram Table.png"
        if not source_table.exists():
            logger.warning("Approved GHS pictogram source table is missing: %s", source_table)

        pictogram_files = {
            "GHS01": ("Exploding Bomb", asset_dir / "GHS01_exploding_bomb.png"),
            "GHS02": ("Flame", asset_dir / "GHS02_flame.png"),
            "GHS03": ("Flame Over Circle", asset_dir / "GHS03_flame_over_circle.png"),
            "GHS04": ("Gas Cylinder", asset_dir / "GHS04_gas_cylinder.png"),
            "GHS05": ("Corrosive", asset_dir / "GHS05_corrosion.png"),
            "GHS06": ("Skull and Crossbones", asset_dir / "GHS06_skull_and_crossbones.png"),
            "GHS07": ("Exclamation Point", asset_dir / "GHS07_exclamation_point.png"),
            "GHS08": ("Health Hazard", asset_dir / "GHS08_health_hazard.png"),
            "GHS09": ("Environment", asset_dir / "GHS09_environment.png"),
        }
        loaded = {}
        for code, (name, path) in pictogram_files.items():
            data_uri = cls._asset_data_uri(path, "image/png")
            if data_uri:
                loaded[code] = {
                    "code": code,
                    "name": name,
                    "data_uri": data_uri,
                    "source": source_table.name,
                }
        return loaded

    @staticmethod
    def _load_logo_data_uri() -> Optional[str]:
        """Load the packaged ClearEdge logo as an SVG-safe data URI."""
        logo_path = Path(__file__).resolve().parent.parent / "High Res Logo.png"
        if not logo_path.exists():
            logger.warning("ClearEdge logo asset not found: %s", logo_path)
            return None
        encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def get_template_config(self, template_id: Optional[str], size: str) -> dict:
        """Return Phase 2 template configuration by template ID or size."""
        if template_id and template_id in self.templates:
            return self.templates[template_id]

        for tid, config in self.templates.items():
            if config["size"] == size:
                return config

        logger.warning(f"Unknown size '{size}', using default template '{self.default_template_id}'")
        return self.templates[self.default_template_id]

    @staticmethod
    def _normalize_orientation(orientation: Optional[str]) -> str:
        clean = str(orientation or "vertical").strip().lower()
        if clean in {"horizontal", "landscape"}:
            return "horizontal"
        return "vertical"

    @classmethod
    def _oriented_dimensions(cls, template_config: dict, orientation: Optional[str]) -> tuple[int, int]:
        """Return the same physical label dimensions in the requested orientation."""
        width = int(template_config["width"])
        height = int(template_config["height"])
        if cls._normalize_orientation(orientation) == "horizontal":
            return max(width, height), min(width, height)
        return min(width, height), max(width, height)

    @staticmethod
    def _fit_text(text: Optional[str], max_chars: int, fallback: str = "N/A") -> str:
        """Simple deterministic text fitting with truncation."""
        if not text:
            return fallback
        clean = " ".join(str(text).split())
        if len(clean) <= max_chars:
            return clean
        return clean[: max_chars - 3].rstrip() + "..."

    @staticmethod
    def _estimated_text_width_units(text: str) -> float:
        """Estimate Arial bold text width in font-size units for SVG fitting."""
        total = 0.0
        for char in text:
            if char in "MW@#%&":
                total += 0.95
            elif char.isupper():
                total += 0.72
            elif char.isdigit():
                total += 0.58
            elif char in "ilI1":
                total += 0.32
            elif char in " .,;:'|":
                total += 0.30
            elif char in "-_/":
                total += 0.36
            else:
                total += 0.56
        return max(total, 1.0)

    @classmethod
    def _fit_font_size_for_width(
        cls,
        lines: list[str],
        *,
        max_width: float,
        preferred_size: int,
        minimum_size: int,
    ) -> int:
        """Return the largest shared font size that keeps all lines inside max_width."""
        fitted_size = preferred_size
        for line in lines:
            required_units = cls._estimated_text_width_units(line)
            fitted_size = min(fitted_size, int(max_width / required_units))
        return max(minimum_size, fitted_size)

    @classmethod
    def _fit_text_for_width(
        cls,
        text: Optional[str],
        *,
        max_width: float,
        font_size: float,
        fallback: str = "",
    ) -> str:
        """Fit a single SVG text run inside a known width using deterministic ellipsis."""
        if not text:
            return fallback
        clean = " ".join(str(text).split())
        if not clean:
            return fallback

        def rendered_width(value: str) -> float:
            return cls._estimated_text_width_units(value) * font_size

        if rendered_width(clean) <= max_width:
            return clean

        suffix = "..."
        available = max_width - rendered_width(suffix)
        if available <= 0:
            return suffix

        fitted = clean
        while fitted and rendered_width(fitted) > available:
            fitted = fitted[:-1].rstrip()
        return f"{fitted}{suffix}" if fitted else suffix

    @staticmethod
    def _wrap_lines(text: Optional[str], line_width: int = 40, max_lines: int = 2) -> list[str]:
        """Deterministic word wrapping with max lines and ellipsis."""
        if not text:
            return []

        words = " ".join(str(text).split()).split(" ")
        lines: list[str] = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= line_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
                if len(lines) >= max_lines:
                    break

        if current and len(lines) < max_lines:
            lines.append(current)

        overflow = len(" ".join(words)) > len(" ".join(lines))
        if overflow and lines:
            lines[-1] = (lines[-1][: max(1, line_width - 3)].rstrip() + "...")

        return lines

    @classmethod
    def _format_product_heading(cls, product_name: Optional[str], available_width: int) -> dict:
        """Fit a product name into the header without clipping the right edge."""
        clean = cls._fit_text(product_name, 72, "UNNAMED PRODUCT")
        if available_width >= 430:
            one_line_limit = 25
            two_line_limit = 22
            base_font = 44
        elif available_width >= 330:
            one_line_limit = 18
            two_line_limit = 18
            base_font = 42
        else:
            one_line_limit = 16
            two_line_limit = 16
            base_font = 34

        if len(clean) <= one_line_limit:
            return {
                "lines": [clean],
                "font_size": base_font,
                "y": 66 if base_font >= 40 else 56,
                "line_gap": base_font + 5,
            }

        lines = cls._wrap_lines(clean, line_width=two_line_limit, max_lines=2) or [clean]
        longest = max(len(line) for line in lines)
        if longest > two_line_limit:
            font_size = 27
        elif longest > one_line_limit:
            font_size = 29
        else:
            font_size = 31

        return {
            "lines": lines,
            "font_size": font_size,
            "y": 43,
            "line_gap": min(font_size + 1, 30),
        }

    @classmethod
    def _format_sample_product_heading(cls, product_name: Optional[str]) -> dict:
        """Fit a sample-label product heading inside the right-side header area."""
        lines = ["UNNAMED PRODUCT"]
        font_size = 20
        for line_width in range(22, 7, -1):
            candidate_lines = cls._wrap_lines(product_name, line_width=line_width, max_lines=2) or ["UNNAMED PRODUCT"]
            longest = max(len(line) for line in candidate_lines)
            preferred_size = 34 if len(candidate_lines) == 1 and longest <= 18 else (29 if longest <= 23 else 25)
            candidate_font_size = cls._fit_font_size_for_width(
                candidate_lines,
                max_width=205,
                preferred_size=preferred_size,
                minimum_size=20,
            )
            fits = all(
                cls._estimated_text_width_units(line) * candidate_font_size <= 205
                for line in candidate_lines
            )
            lines = candidate_lines
            font_size = candidate_font_size
            if fits:
                break
        else:
            lines = [
                cls._fit_text_for_width(line, max_width=205, font_size=font_size, fallback="")
                for line in lines
            ]
        return {
            "lines": lines,
            "font_size": font_size,
            "y": 43 if len(lines) == 1 else 34,
            "line_gap": font_size + 2,
        }

    @classmethod
    def _format_fill_amount(cls, fill_amount: Optional[str], max_chars: int = 16) -> str:
        """Return fill amount with an explicit lb/kg unit for label readability."""
        fallback = "________"
        if not fill_amount:
            return fallback

        clean = " ".join(str(fill_amount).split())
        if not clean:
            return fallback

        normalized = clean.lower().replace(".", "")
        unit_markers = (
            " lb",
            " lbs",
            " pound",
            " pounds",
            " kg",
            " kgs",
            " kilogram",
            " kilograms",
        )
        if any(marker in f" {normalized}" for marker in unit_markers):
            return cls._fit_text(clean, max_chars, fallback)

        numeric = normalized.replace(",", "").replace(" ", "")
        if numeric.replace(".", "", 1).isdigit():
            return cls._fit_text(f"{clean} lb", max_chars, fallback)

        return cls._fit_text(clean, max_chars, fallback)

    @staticmethod
    def _shipment_header_spacing(width: int, product_area_x: int) -> dict:
        """Keep Lot, Expiration, and Net Weight fields visually separated."""
        available_width = max(280, width - product_area_x - 22)
        if available_width >= 460:
            lot_width = 185
            expiration_width = 150
            font_size = 12.5
            lot_chars = 18
            expiration_chars = 14
            fill_chars = 14
        else:
            lot_width = 138
            expiration_width = 108
            font_size = 10.5
            lot_chars = 13
            expiration_chars = 10
            fill_chars = 10

        expiration_x = product_area_x + lot_width
        weight_x = product_area_x + lot_width + expiration_width

        return {
            "lot_label_x": product_area_x,
            "lot_value_x": product_area_x,
            "expiration_label_x": expiration_x,
            "expiration_value_x": expiration_x,
            "weight_label_x": weight_x,
            "weight_value_x": weight_x,
            "shipment_value_font_size": font_size,
            "lot_max_chars": lot_chars,
            "expiration_max_chars": expiration_chars,
            "fill_max_chars": fill_chars,
        }

    @classmethod
    def _format_identification_number(cls, un_number: Optional[str]) -> str:
        """Render a DOT identification number with a UN/NA/ID prefix."""
        if not un_number:
            return ""

        clean = "".join(str(un_number).upper().split())
        if clean.startswith(("UN", "NA", "ID")):
            return cls._fit_text(clean, 12, clean)

        if clean.isdigit():
            return cls._fit_text(f"UN{clean}", 12, clean)

        return cls._fit_text(clean, 12, clean)

    @staticmethod
    def _format_true_transport_flag(value: Optional[bool]) -> Optional[str]:
        """Show optional transport markings only when the SDS says they apply."""
        return "Yes" if value is True else None

    @classmethod
    def _format_limited_quantity(cls, value: Optional[str]) -> Optional[str]:
        """Return a concise limited quantity display when Section 14 provides one."""
        if value is None:
            return None

        clean = " ".join(str(value).split())
        if not clean:
            return None

        normalized = clean.lower().replace(".", "")
        if normalized in {"false", "no", "none", "n/a", "na", "not applicable", "0"}:
            return None
        if normalized in {"true", "yes", "y"}:
            return "Yes"
        return cls._fit_text(clean, 22, clean)


    def _format_statements(
        self,
        statements,
        line_width: int = 65,
        max_items: int = 6,
        max_lines: int = 3,
    ):
        """Normalize hazard/precautionary statements with deterministic clipping."""
        formatted = []
        y = 0
        for statement in (statements or [])[:max_items]:
            code = getattr(statement, "code", None)
            text = getattr(statement, "text", "")
            wrapped = self._wrap_lines(text, line_width=line_width, max_lines=max_lines) or [""]
            formatted.append({
                "code": code or "•",
                "text": " ".join(wrapped).strip(),
                "lines": wrapped,
                "y": y,
            })
            y += (len(wrapped) * 10) + 3
        return formatted

    def _fit_safety_statements_for_page(
        self,
        data: ExtractedData,
        *,
        mode: str,
        width: int,
        height: int,
        signal_word: Optional[str],
        transport_layout: dict,
    ) -> tuple[list[dict], list[dict]]:
        """Format safety statements so downstream transport content stays above the footer."""
        base_line_width = 96 if width >= 760 else (78 if width > 612 else 68)
        if mode == "shipped_dot":
            candidates = (
                [(4, 2, 4, 2), (3, 2, 3, 2), (2, 2, 2, 1), (1, 1, 1, 1), (1, 1, 0, 0)]
                if width <= height
                else [(3, 2, 2, 1), (2, 1, 1, 1), (1, 1, 0, 0), (0, 0, 0, 0)]
            )
        else:
            candidates = [(6, 3, 6, 3), (5, 2, 5, 2), (4, 2, 4, 2), (3, 2, 3, 2), (2, 2, 2, 2)]

        product_uses_height = 50 if getattr(data.product, "product_uses", None) else 0
        content_start = (160 if signal_word else 124) + 104 + product_uses_height
        transport_height = 0
        if mode == "shipped_dot" and data.transport.un_number:
            transport_height = transport_layout["dot_panel_height"] + 10
        elif mode == "shipped_dot" and self._is_not_regulated_for_transport(data.transport):
            transport_height = 78

        footer_limit = height - 102
        fallback = ([], [])
        for hazard_max_items, hazard_max_lines, precautionary_max_items, precautionary_max_lines in candidates:
            hazard_statements = self._format_statements(
                data.ghs.hazard_statements,
                line_width=base_line_width,
                max_items=hazard_max_items,
                max_lines=hazard_max_lines,
            )
            precautionary_statements = self._format_statements(
                data.ghs.precautionary_statements,
                line_width=base_line_width,
                max_items=precautionary_max_items,
                max_lines=precautionary_max_lines,
            )
            fallback = (hazard_statements, precautionary_statements)

            projected_bottom = content_start
            if hazard_statements:
                projected_bottom += self._statement_block_height(hazard_statements) + 10
            if precautionary_statements:
                projected_bottom += self._statement_block_height(precautionary_statements) + 10
            projected_bottom += transport_height

            if projected_bottom <= footer_limit:
                return hazard_statements, precautionary_statements

        return fallback

    def _format_pictograms(self, pictograms):
        """Return approved GHS pictogram images; never draw synthetic fallback symbols."""
        formatted = []
        for code in pictograms or []:
            asset = self.ghs_pictogram_assets.get(code)
            if asset:
                formatted.append(asset)
            else:
                logger.warning("Skipping GHS pictogram without approved table asset: %s", code)
        return formatted

    def _format_product_uses(self, product_uses, *, width: int) -> list[str]:
        """Return at most two compact product-use lines for the printed label."""
        uses = [
            self._fit_text(str(item), 42, "")
            for item in (product_uses or [])[:2]
            if str(item).strip()
        ]
        if not uses:
            return []
        line_width = 82 if width >= 760 else 62
        return self._wrap_lines(" | ".join(uses), line_width=line_width, max_lines=2)

    @staticmethod
    def _normalize_hazard_class(hazard_class: Optional[str]) -> Optional[str]:
        """Normalize a DOT hazard class string for label lookup."""
        if not hazard_class:
            return None
        clean = str(hazard_class).strip().lower()
        if "not regulated" in clean or "not applicable" in clean:
            return None
        if clean.startswith("class "):
            clean = clean[6:]
        for candidate in ("6.1", "5.1", "5.2", "2.1", "2.2", "2.3", "4.1", "4.2", "4.3"):
            if candidate in clean:
                return candidate
        for char in clean:
            if char.isdigit():
                return char
        return None

    def _format_dot_labels(self, transport):
        """Return DOT hazard labels for regulated shipped labels."""
        hazard_class = self._normalize_hazard_class(getattr(transport, "hazard_class", None))
        if not hazard_class:
            return []
        label = self.dot_label_assets.get(hazard_class)
        return [label] if label else []

    @staticmethod
    def _statement_block_height(formatted_statements) -> int:
        """Return enough SVG block height for wrapped statement text."""
        if not formatted_statements:
            return 0
        last = formatted_statements[-1]
        return 38 + last["y"] + (len(last["lines"]) * 10)

    @staticmethod
    def _is_not_regulated_for_transport(transport) -> bool:
        """Detect explicit SDS language that a shipped label is not DOT regulated."""
        if getattr(transport, "not_regulated", None) is True:
            return True

        fields = [
            getattr(transport, "proper_shipping_name", None),
            getattr(transport, "hazard_class", None),
            getattr(transport, "un_number", None),
            getattr(transport, "special_provisions", None),
        ]
        joined = " ".join(str(field).lower() for field in fields if field)
        return (
            "not regulated" in joined
            or "not restricted" in joined
            or "not dangerous goods" in joined
            or "not hazardous for transport" in joined
        )

    @staticmethod
    def _transport_detail_layout(
        *,
        shipping_name_lines: list[str],
        packing_group: Optional[str],
        marine_pollutant_display: Optional[str],
        limited_quantity_display: Optional[str],
    ) -> dict:
        """Stack DOT detail fields below the rendered shipping-name lines."""
        line_count = max(1, len(shipping_name_lines))
        hazard_class_y = 32 + ((line_count - 1) * 12) + 16
        cursor_y = hazard_class_y

        packing_group_y = None
        if packing_group:
            cursor_y += 18
            packing_group_y = cursor_y

        cursor_y += 18
        dot_label_y = cursor_y

        marine_pollutant_y = None
        if marine_pollutant_display:
            cursor_y += 16
            marine_pollutant_y = cursor_y

        limited_quantity_y = None
        if limited_quantity_display:
            cursor_y += 16
            limited_quantity_y = cursor_y

        return {
            "hazard_class_y": hazard_class_y,
            "packing_group_y": packing_group_y,
            "dot_label_y": dot_label_y,
            "marine_pollutant_y": marine_pollutant_y,
            "limited_quantity_y": limited_quantity_y,
            "dot_panel_height": max(154, 45 + cursor_y + 15),
        }

    def _resolve_branding(self, data: ExtractedData, branding: Optional[dict]) -> dict:
        """Resolve print branding without letting SDS supplier data override ClearEdge labels."""
        mode = str((branding or {}).get("mode") or "clearedge").lower()
        if mode != "custom":
            return {
                "mode": "clearedge",
                "logo_data_uri": self.logo_data_uri,
                "supplier_name": self.CLEAREDGE_SUPPLIER_NAME,
                "supplier_address": self.CLEAREDGE_SUPPLIER_ADDRESS,
                "supplier_phone": self.CLEAREDGE_SUPPLIER_PHONE,
                "is_clearedge": True,
            }

        return {
            "mode": "custom",
            "logo_data_uri": (branding or {}).get("logo_data_uri"),
            "supplier_name": data.product.supplier_name or "Custom Label",
            "supplier_address": data.product.supplier_address or "",
            "supplier_phone": data.product.supplier_phone or "",
            "show_clearedge_mark": (branding or {}).get("show_clearedge_mark", True) is not False,
            "is_clearedge": False,
        }

    @staticmethod
    def _svg_text(value: Optional[str]) -> str:
        """Escape dynamic text for SVG text nodes."""
        return html_escape(str(value or ""), quote=False)

    def _generate_sample_4x6_svg(
        self,
        data: ExtractedData,
        *,
        mode: str,
        branding: Optional[dict],
    ) -> str:
        """Render a compact 6x4 thermal sample label."""
        width = 432
        height = 288
        resolved_branding = self._resolve_branding(data, branding)
        logo_data_uri = resolved_branding.get("logo_data_uri")
        salesperson = (branding or {}).get("salesperson") or {}
        heading = self._format_sample_product_heading(data.product.name)
        product_lines = heading["lines"]
        product_font_size = heading["font_size"]
        product_start_y = heading["y"]
        use_line = ""
        if data.product.product_uses:
            use_line = self._fit_text_for_width(
                data.product.product_uses[0],
                max_width=286,
                font_size=10,
                fallback="",
            )
        fill_amount = self._format_fill_amount(data.shipment.fill_amount, max_chars=18) if data.shipment.fill_amount else ""
        pictograms = self._format_pictograms(data.ghs.pictograms)
        signal_word = (data.ghs.signal_word or "").upper()
        contact_parts = [
            salesperson.get("name"),
            salesperson.get("email"),
            salesperson.get("phone"),
        ]
        contact_line = self._fit_text_for_width(
            " | ".join(part for part in contact_parts if part),
            max_width=390,
            font_size=10.5,
            fallback="",
        )

        product_text = "\n".join(
            f'<text x="154" y="{product_start_y + index * heading["line_gap"]}" '
            f'font-size="{product_font_size}" font-weight="bold" fill="{self.brand_palette["primary"]}">'
            f'{self._svg_text(line)}</text>'
            for index, line in enumerate(product_lines)
        )
        pictogram_images = "\n".join(
            f'<image id="pictogram-{self._svg_text(icon["code"])}" x="{204 + index * 48}" y="116" '
            f'width="42" height="42" href="{icon["data_uri"]}" xlink:href="{icon["data_uri"]}" '
            f'preserveAspectRatio="xMidYMid meet"/>'
            for index, icon in enumerate(pictograms[:4])
        )
        weight_text = (
            f'<text x="392" y="87" font-size="10" font-weight="bold" fill="{self.brand_palette["text"]}" '
            f'text-anchor="end">Net Wt.: {self._svg_text(fill_amount)}</text>'
            if fill_amount else ""
        )
        signal_text = (
            f'<text x="24" y="145" font-size="22" font-weight="bold" fill="{self.brand_palette["primary"]}">'
            f'{self._svg_text(signal_word)}</text>'
            if signal_word else ""
        )
        contact_text = (
            f'<text x="20" y="255" font-size="10.5" font-weight="bold" fill="{self.brand_palette["text"]}">'
            f'{self._svg_text(contact_line)}</text>'
            if contact_line else ""
        )
        logo_image = (
            f'<image id="brand-logo" x="18" y="28" width="118" height="38" href="{logo_data_uri}" '
            f'xlink:href="{logo_data_uri}" preserveAspectRatio="xMinYMid meet"/>'
            if logo_data_uri else
            f'<text x="18" y="50" font-size="17" font-weight="bold" fill="{self.brand_palette["primary"]}">'
            f'{self._svg_text(resolved_branding.get("supplier_name") or "Sample Label")}</text>'
        )

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}pt" height="{height}pt" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" font-family="Arial, sans-serif">
  <rect width="{width}" height="{height}" fill="white"/>
  <rect x="5" y="5" width="{width - 10}" height="{height - 10}" fill="none" stroke="black" stroke-width="1.5"/>
  <rect x="10" y="10" width="{width - 20}" height="7" fill="{self.brand_palette["primary"]}"/>
  {logo_image}
  {product_text}
  <line x1="18" y1="76" x2="{width - 18}" y2="76" stroke="{self.brand_palette["primary"]}" stroke-width="2"/>
  <text x="20" y="97" font-size="10" font-weight="bold" fill="{self.brand_palette["primary"]}">PRODUCT USE:</text>
  <text x="104" y="97" font-size="10" fill="{self.brand_palette["text"]}">{self._svg_text(use_line)}</text>
  {weight_text}
  <rect x="18" y="108" width="{width - 36}" height="62" fill="#FBFAFE" stroke="#D8D3E6" stroke-width="1.2" rx="3"/>
  <text x="24" y="126" font-size="9" font-weight="bold" fill="{self.brand_palette["primary"]}">COMPACT GHS</text>
  {signal_text}
  {pictogram_images}
  <rect x="18" y="184" width="{width - 36}" height="76" fill="white" stroke="#D8D3E6" stroke-width="1.2" rx="3"/>
  <text x="24" y="205" font-size="11" font-weight="bold" fill="{self.brand_palette["primary"]}">SALES CONTACT</text>
  {contact_text}
  <text x="20" y="274" font-size="8.5" fill="{self.brand_palette["muted"]}">Sample label - verify SDS/TDS before production shipment.</text>
</svg>
"""

    def generate_svg(
        self,
        data: ExtractedData,
        mode: str = "shipped_dot",
        size: str = "pail",
        template_name: str = "default",
        template_id: Optional[str] = None,
        branding: Optional[dict] = None,
        orientation: str = "vertical",
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

        if size == "sample_4x6":
            svg_content = self._generate_sample_4x6_svg(data, mode=mode, branding=branding)
            logger.info("Generated SVG (%s bytes) for sample_4x6 label", len(svg_content))
            return svg_content

        template_key = template_id if template_id in self.templates else None
        if not template_key and template_name in self.templates:
            template_key = template_name
        template_config = self.get_template_config(template_key, size)

        width, height = self._oriented_dimensions(template_config, orientation)
        brand = template_config["brand"]
        resolved_branding = self._resolve_branding(data, branding)
        if resolved_branding["is_clearedge"]:
            logo_width = 218 if width <= 612 else 238
            logo_height = int(round(logo_width / self.CLEAREDGE_LOGO_ASPECT_RATIO))
            logo_y = 34 if width <= 612 else 32
        else:
            logo_width = 198 if width <= 612 else 220
            logo_height = 88
            logo_y = 20
        process_mark_width = 210 if width >= 760 else 180
        process_mark_height = 40 if width >= 760 else 36
        process_mark_logo_width = process_mark_width - 20
        process_mark_logo_height = process_mark_height - 12
        process_mark_bottom_offset = process_mark_height + 13
        product_area_x = 20 + logo_width + 24
        product_area_width = width - product_area_x - 22
        shipment_spacing = self._shipment_header_spacing(width, product_area_x)
        heading = self._format_product_heading(data.product.name, product_area_width)
        product_uses = self._format_product_uses(data.product.product_uses, width=width)
        shipment = data.shipment
        dot_labels = self._format_dot_labels(data.transport)
        shipping_name_lines = self._wrap_lines(
            data.transport.proper_shipping_name,
            line_width=44 if width > 612 else 38,
            max_lines=2,
        )
        marine_pollutant_display = self._format_true_transport_flag(data.transport.marine_pollutant)
        limited_quantity_display = self._format_limited_quantity(data.transport.limited_quantity)
        transport_layout = self._transport_detail_layout(
            shipping_name_lines=shipping_name_lines,
            packing_group=data.transport.packing_group,
            marine_pollutant_display=marine_pollutant_display,
            limited_quantity_display=limited_quantity_display,
        )
        hazard_statements, precautionary_statements = self._fit_safety_statements_for_page(
            data,
            mode=mode,
            width=width,
            height=height,
            signal_word=data.ghs.signal_word,
            transport_layout=transport_layout,
        )

        # Prepare template context
        context = {
            "width": width,
            "height": height,
            "header_color": brand["header_color"],
            "accent_color": brand["accent_color"],
            "brand_purple": self.brand_palette["primary"],
            "brand_purple_light": self.brand_palette["primary_light"],
            "ghs_red": "#D71920",
            "text_color": brand["text_color"],
            "body_font": brand["body_font"],
            "mode": mode,
            "logo_data_uri": resolved_branding["logo_data_uri"],
            "clearedge_mark_logo_data_uri": self.logo_data_uri,
            "show_clearedge_mark": resolved_branding.get("show_clearedge_mark", False),
            "process_mark_width": process_mark_width,
            "process_mark_x": width - process_mark_width - 20,
            "process_mark_height": process_mark_height,
            "process_mark_bottom_offset": process_mark_bottom_offset,
            "process_mark_logo_width": process_mark_logo_width,
            "process_mark_logo_height": process_mark_logo_height,
            "process_mark_logo_x": (process_mark_width - process_mark_logo_width) // 2,
            "process_mark_logo_y": (process_mark_height - process_mark_logo_height) // 2,
            "logo_width": logo_width,
            "logo_height": logo_height,
            "logo_y": logo_y,
            "product_area_x": product_area_x,
            "product_text_x": product_area_x + (product_area_width // 2),
            "lot_label_x": shipment_spacing["lot_label_x"],
            "lot_value_x": shipment_spacing["lot_value_x"],
            "expiration_label_x": shipment_spacing["expiration_label_x"],
            "expiration_value_x": shipment_spacing["expiration_value_x"],
            "weight_label_x": shipment_spacing["weight_label_x"],
            "weight_value_x": shipment_spacing["weight_value_x"],
            "shipment_value_font_size": shipment_spacing["shipment_value_font_size"],
            "product_name_font_size": heading["font_size"],
            "product_name_y": heading["y"],
            "product_name_line_gap": heading["line_gap"],
            "product_name_lines": heading["lines"],
            "product_name": " ".join(heading["lines"]),
            "lot_number_display": self._fit_text(
                shipment.lot_number,
                shipment_spacing["lot_max_chars"],
                "________",
            ),
            "expiration_date_display": self._fit_text(
                shipment.expiration_date,
                shipment_spacing["expiration_max_chars"],
                "________",
            ),
            "fill_amount_display": self._format_fill_amount(
                shipment.fill_amount,
                shipment_spacing["fill_max_chars"],
            ),
            "signal_word": data.ghs.signal_word,
            "pictograms": data.ghs.pictograms,
            "pictogram_icons": self._format_pictograms(data.ghs.pictograms),
            "product_uses": product_uses,
            "product_uses_block_height": 40,
            "hazard_statements": hazard_statements,
            "hazard_block_height": self._statement_block_height(hazard_statements),
            "precautionary_statements": precautionary_statements,
            "precautionary_block_height": self._statement_block_height(precautionary_statements),
            "un_number": data.transport.un_number,
            "identification_number": self._format_identification_number(data.transport.un_number),
            "shipping_name_lines": shipping_name_lines,
            "transport_not_regulated": self._is_not_regulated_for_transport(data.transport),
            "hazard_class": data.transport.hazard_class,
            "packing_group": data.transport.packing_group,
            "dot_labels": dot_labels,
            "dot_label_name": dot_labels[0]["name"] if dot_labels else None,
            "marine_pollutant_display": marine_pollutant_display,
            "limited_quantity_display": limited_quantity_display,
            **transport_layout,
            "supplier_name": self._fit_text(
                resolved_branding["supplier_name"],
                50,
                self.CLEAREDGE_SUPPLIER_NAME if resolved_branding["is_clearedge"] else "Custom Label",
            ),
            "supplier_address": self._fit_text(
                resolved_branding["supplier_address"],
                70,
                self.CLEAREDGE_SUPPLIER_ADDRESS if resolved_branding["is_clearedge"] else "",
            ),
            "supplier_phone": self._fit_text(
                resolved_branding["supplier_phone"],
                35,
                self.CLEAREDGE_SUPPLIER_PHONE if resolved_branding["is_clearedge"] else "",
            ),
            "emergency_phone": self._fit_text(data.product.emergency_phone, 45, "") if data.product.emergency_phone else None,
            "emergency_box_width": min(width - 40, 370),
            "revision_date": data.product.revision_date,
            "nfpa_health": data.nfpa.health,
            "nfpa_flammability": data.nfpa.flammability,
            "nfpa_instability": data.nfpa.instability,
            "nfpa_special": data.nfpa.special or "",
            "nfpa_source": data.nfpa.source,
            "template_id": template_key or self.default_template_id,
        }

        # Render template
        svg_content = self.svg_template.render(**context)

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
        storage_client,
        product_folder_id: str,
        date_folder: str,
        svg_content: str,
        pdf_bytes: bytes
    ) -> tuple[str, str]:
        """
        Save SVG and PDF labels to the configured storage backend.

        Returns:
            Tuple of (svg_file_id, pdf_file_id)
        """
        # Find or create Labels/{date} folder
        labels_folder_id = storage_client.find_subfolder(product_folder_id, "Labels")
        if not labels_folder_id:
            raise ValueError("Labels folder not found")

        dated_folder_id = storage_client.create_dated_folder(labels_folder_id, date_folder)

        # Upload SVG
        svg_id = storage_client.upload_file(
            svg_content.encode('utf-8'),
            "label.svg",
            dated_folder_id,
            "image/svg+xml"
        )
        logger.info(f"Uploaded label.svg: {svg_id}")

        # Upload PDF
        pdf_id = storage_client.upload_file(
            pdf_bytes,
            "label.pdf",
            dated_folder_id,
            "application/pdf"
        )
        logger.info(f"Uploaded label.pdf: {pdf_id}")

        return svg_id, pdf_id
