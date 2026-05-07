"""
Label generation stub - SVG and PDF creation.
Generates DOT/OSHA-compliant labels from extracted data.
"""

import io
import logging
import base64
from pathlib import Path
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
<svg width="{{ width }}" height="{{ height }}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" font-family="{{ body_font }}">
  <!-- Background -->
  <rect width="{{ width }}" height="{{ height }}" fill="white"/>
  <rect x="5" y="5" width="{{ width - 10 }}" height="{{ height - 10 }}" fill="none" stroke="black" stroke-width="2"/>

  <!-- CLEAR EDGE Header -->
  <rect x="10" y="10" width="{{ width - 20 }}" height="102" fill="white"/>
  <rect x="10" y="10" width="{{ width - 20 }}" height="8" fill="{{ brand_purple }}"/>
  <line x1="10" y1="112" x2="{{ width - 10 }}" y2="112" stroke="{{ brand_purple }}" stroke-width="2"/>

  <!-- Brand logo -->
  {% if logo_data_uri %}
  <image x="20" y="29" width="{{ logo_panel_width }}" height="48"
         href="{{ logo_data_uri }}" xlink:href="{{ logo_data_uri }}"
         preserveAspectRatio="xMidYMid meet"/>
  {% else %}
  <text x="{{ 20 + logo_panel_width // 2 }}" y="58" font-size="18" font-weight="bold"
        fill="{{ header_color }}" text-anchor="middle">ClearEdge</text>
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
    <text x="{{ product_area_x }}" y="101" font-size="9.5" fill="{{ text_color }}">
      <tspan font-weight="bold" fill="{{ brand_purple }}">Lot No.:</tspan> {{ lot_number_display }}
    </text>
    <text x="{{ product_area_x + 112 }}" y="101" font-size="9.5" fill="{{ text_color }}">
      <tspan font-weight="bold" fill="{{ brand_purple }}">Exp.:</tspan> {{ expiration_date_display }}
    </text>
    <text x="{{ product_area_x + 210 }}" y="101" font-size="9.5" fill="{{ text_color }}">
      <tspan font-weight="bold" fill="{{ brand_purple }}">Net Wt.:</tspan> {{ fill_amount_display }}
    </text>
  </g>
  <text x="{{ width - 22 }}" y="28" font-size="8.5" fill="{{ brand_purple }}" text-anchor="end">
    {{ size_label }}
  </text>

  <!-- Signal Word (if present) -->
  {% if signal_word %}
  <rect x="10" y="122" width="{{ width - 20 }}" height="42"
        fill="{{ brand_purple }}"
        rx="2"/>
  <text x="{{ width // 2 }}" y="151"
        font-size="25" font-weight="bold"
        fill="white" text-anchor="middle"
        style="text-transform: uppercase;">
    {{ signal_word }}
  </text>
  {% set y_offset = 174 %}
  {% else %}
  {% set y_offset = 124 %}
  {% endif %}

  <!-- Safety symbols band -->
  <g id="symbols-summary">
    <rect x="10" y="{{ y_offset }}" width="{{ width - 20 }}" height="112"
          fill="#FBFAFE" stroke="#C8BEDD" stroke-width="1.5" rx="3"/>
    <text x="20" y="{{ y_offset + 19 }}" font-size="11.5" font-weight="bold" fill="{{ brand_purple }}">
      GHS PICTOGRAMS
    </text>

    <!-- Pictogram images pulled only from the approved GHS pictogram table asset. -->
    {% for pictogram in pictogram_icons[:4] %}
    <g transform="translate({{ 20 + (loop.index0 % 4) * 72 }}, {{ y_offset + 32 }})">
      <image id="pictogram-{{ pictogram.code }}" x="0" y="0" width="66" height="66"
             href="{{ pictogram.data_uri }}" xlink:href="{{ pictogram.data_uri }}"
             preserveAspectRatio="xMidYMid meet"/>
    </g>
    {% endfor %}

    <!-- NFPA 704 Diamond: included on every label. -->
    <g id="nfpa-704" transform="translate({{ width - 150 }}, {{ y_offset + 7 }})">
      <rect x="0" y="0" width="130" height="98" fill="white" stroke="#D8D3E6" stroke-width="1" rx="3"/>
      <text x="65" y="12" font-size="10" text-anchor="middle" fill="{{ text_color }}" font-weight="bold">
        NFPA 704
      </text>
      <text x="65" y="22" font-size="7" text-anchor="middle" fill="{{ text_color }}" opacity="0.75">
        0=min 4=severe
      </text>
      <g transform="translate(29, 27) scale(0.56)">
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
  {% set y_offset = y_offset + 120 %}

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

    <!-- UN Number (large and prominent) -->
    <rect x="20" y="{{ y_offset + 45 }}" width="145" height="70"
          fill="{{ brand_purple_light }}" stroke="{{ brand_purple }}" stroke-width="3" rx="5"/>
    <text x="92" y="{{ y_offset + 70 }}" font-size="14" font-weight="bold"
          fill="{{ brand_purple }}" text-anchor="middle">UN NUMBER:</text>
    <text x="92" y="{{ y_offset + 100 }}" font-size="28" font-weight="bold"
          fill="{{ brand_purple }}" text-anchor="middle">{{ un_number }}</text>

    <!-- Shipping Details -->
    <g transform="translate(180, {{ y_offset + 45 }})">
      <text x="0" y="15" font-size="11" fill="{{ text_color }}">
        <tspan font-weight="bold">Proper Shipping Name:</tspan>
      </text>
      <text x="0" y="32" font-size="10" fill="{{ text_color }}">{{ shipping_name[:36] }}</text>

      <text x="0" y="50" font-size="11" fill="{{ text_color }}">
        <tspan font-weight="bold">Hazard Class:</tspan> {{ hazard_class or 'N/A' }}
      </text>

      {% if packing_group %}
      <text x="0" y="68" font-size="11" fill="{{ text_color }}">
        <tspan font-weight="bold">Packing Group:</tspan> {{ packing_group }}
      </text>
      {% endif %}
      <text x="0" y="88" font-size="11" fill="{{ text_color }}">
        <tspan font-weight="bold">DOT Label:</tspan> {{ dot_label_name or 'Review required' }}
      </text>
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
          stroke="#5A2D82" stroke-width="2"/>

    <!-- Supplier Information -->
    <text x="20" y="{{ height - 77 }}" font-size="10.5" font-weight="bold" fill="{{ text_color }}">
      {{ supplier_name or 'ClearEdge Solutions' }}
    </text>
    <text x="20" y="{{ height - 63 }}" font-size="8" fill="{{ text_color }}" opacity="0.75">
      {{ supplier_address or '14301 CR Koon Highway, Newberry, SC 29108' }}
    </text>
    <text x="20" y="{{ height - 50 }}" font-size="8.5" fill="{{ text_color }}" opacity="0.75">
      {{ supplier_phone or 'www.clear-edge.net' }}
    </text>

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
        self.logo_data_uri = self._load_logo_data_uri()
        self.brand_palette = {
            "primary": "#1B006E",
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
    def _fit_text(text: Optional[str], max_chars: int, fallback: str = "N/A") -> str:
        """Simple deterministic text fitting with truncation."""
        if not text:
            return fallback
        clean = " ".join(str(text).split())
        if len(clean) <= max_chars:
            return clean
        return clean[: max_chars - 3].rstrip() + "..."



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
            one_line_limit = 27
            two_line_limit = 24
            base_font = 30
        else:
            one_line_limit = 22
            two_line_limit = 20
            base_font = 28

        if len(clean) <= one_line_limit:
            return {
                "lines": [clean],
                "font_size": base_font,
                "y": 52,
                "line_gap": 27,
            }

        lines = cls._wrap_lines(clean, line_width=two_line_limit, max_lines=2) or [clean]
        longest = max(len(line) for line in lines)
        if longest > two_line_limit:
            font_size = 23
        elif longest > one_line_limit:
            font_size = 24
        else:
            font_size = 25

        return {
            "lines": lines,
            "font_size": font_size,
            "y": 43,
            "line_gap": font_size + 5,
        }


    def _format_statements(self, statements, line_width: int = 65, max_items: int = 6):
        """Normalize hazard/precautionary statements with deterministic clipping."""
        formatted = []
        y = 0
        for statement in (statements or [])[:max_items]:
            code = getattr(statement, "code", None)
            text = getattr(statement, "text", "")
            wrapped = self._wrap_lines(text, line_width=line_width, max_lines=3) or [""]
            formatted.append({
                "code": code or "•",
                "text": " ".join(wrapped).strip(),
                "lines": wrapped,
                "y": y,
            })
            y += (len(wrapped) * 10) + 3
        return formatted

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
        return 44 + last["y"] + (len(last["lines"]) * 10)

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

    def generate_svg(
        self,
        data: ExtractedData,
        mode: str = "shipped_dot",
        size: str = "pail",
        template_name: str = "default",
        template_id: Optional[str] = None
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

        template_key = template_id if template_id in self.templates else None
        if not template_key and template_name in self.templates:
            template_key = template_name
        template_config = self.get_template_config(template_key, size)

        width = template_config["width"]
        height = template_config["height"]
        size_label = template_config["name"]
        brand = template_config["brand"]
        logo_panel_width = 165 if width <= 612 else 182
        product_area_x = logo_panel_width + 34
        product_area_width = width - product_area_x - 22
        heading = self._format_product_heading(data.product.name, product_area_width)
        shipment = data.shipment
        hazard_statements = self._format_statements(
            data.ghs.hazard_statements,
            line_width=74 if width > 612 else 68,
            max_items=6,
        )
        precautionary_statements = self._format_statements(
            data.ghs.precautionary_statements,
            line_width=74 if width > 612 else 68,
            max_items=6,
        )
        dot_labels = self._format_dot_labels(data.transport)

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
            "size_label": size_label,
            "logo_data_uri": self.logo_data_uri,
            "logo_panel_width": logo_panel_width,
            "product_area_x": product_area_x,
            "product_text_x": product_area_x + (product_area_width // 2),
            "product_name_font_size": heading["font_size"],
            "product_name_y": heading["y"],
            "product_name_line_gap": heading["line_gap"],
            "product_name_lines": heading["lines"],
            "product_name": " ".join(heading["lines"]),
            "lot_number_display": self._fit_text(shipment.lot_number, 14, "________"),
            "expiration_date_display": self._fit_text(shipment.expiration_date, 14, "________"),
            "fill_amount_display": self._fit_text(shipment.fill_amount, 18, "________"),
            "signal_word": data.ghs.signal_word,
            "pictograms": data.ghs.pictograms,
            "pictogram_icons": self._format_pictograms(data.ghs.pictograms),
            "hazard_statements": hazard_statements,
            "hazard_block_height": self._statement_block_height(hazard_statements),
            "precautionary_statements": precautionary_statements,
            "precautionary_block_height": self._statement_block_height(precautionary_statements),
            "un_number": data.transport.un_number,
            "shipping_name": self._fit_text(data.transport.proper_shipping_name, 45),
            "transport_not_regulated": self._is_not_regulated_for_transport(data.transport),
            "hazard_class": data.transport.hazard_class,
            "packing_group": data.transport.packing_group,
            "dot_labels": dot_labels,
            "dot_label_name": dot_labels[0]["name"] if dot_labels else None,
            "dot_panel_height": 165,
            "supplier_name": self._fit_text(data.product.supplier_name, 50, "ClearEdge Solutions"),
            "supplier_address": self._fit_text(data.product.supplier_address, 70, "14301 CR Koon Highway, Newberry, SC 29108"),
            "supplier_phone": self._fit_text(data.product.supplier_phone, 35, "www.clear-edge.net"),
            "emergency_phone": self._fit_text(data.product.emergency_phone, 45, "") if data.product.emergency_phone else None,
            "emergency_box_width": min(width - 40, 370),
            "revision_date": data.product.revision_date,
            "nfpa_health": data.nfpa.health,
            "nfpa_flammability": data.nfpa.flammability,
            "nfpa_instability": data.nfpa.instability,
            "nfpa_special": data.nfpa.special or "",
            "template_id": template_key or self.default_template_id,
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
