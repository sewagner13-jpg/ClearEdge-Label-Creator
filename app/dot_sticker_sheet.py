"""Separate DOT hazard-label sticker sheet rendering.

The product label may reference transport data, but exterior DOT hazard labels
are generated as a separate print artifact using only approved packaged assets.
"""

from __future__ import annotations

import base64
import html
import io
import re
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Iterable

import cairosvg
from pypdf import PdfReader, PdfWriter


US_LETTER_WIDTH_PT = 612
US_LETTER_HEIGHT_PT = 792
MM_TO_PT = 72 / 25.4
DOT_STICKER_SIZE_MM = 100
DOT_STICKER_SIZE_PT = DOT_STICKER_SIZE_MM * MM_TO_PT
LARGE_PAIR_STICKER_SIZE_MM = 120
LARGE_PAIR_STICKER_SIZE_PT = LARGE_PAIR_STICKER_SIZE_MM * MM_TO_PT
DOT_STICKERS_PER_PAGE = 4
DOT_STICKER_COLUMNS = 2
DOT_STICKER_ROWS = 2

DOT_LABEL_ASSET_MANIFEST = {
    "3": {
        "hazard_class": "3",
        "label_name": "FLAMMABLE LIQUID",
        "filename": "class_3_flammable_liquid.svg",
    },
    "8": {
        "hazard_class": "8",
        "label_name": "CORROSIVE",
        "filename": "class_8_corrosive.svg",
    },
    "9": {
        "hazard_class": "9",
        "label_name": "CLASS 9",
        "filename": "class_9_miscellaneous.svg",
    },
    "marine_pollutant": {
        "hazard_class": None,
        "label_name": "MARINE POLLUTANT",
        "filename": "marine_pollutant_mark.png",
        "media_type": "image/png",
        "mark_type": "marine_pollutant",
    },
}
SUPPORTED_DOT_STICKER_CLASSES = frozenset(
    key for key, manifest in DOT_LABEL_ASSET_MANIFEST.items() if manifest["hazard_class"]
)
DOT_LABEL_BACKGROUND_COLORS = {
    "3": "#D71920",
}


class DotStickerSheetUnavailable(ValueError):
    """Raised when a required DOT sticker cannot be produced from approved assets."""


@dataclass(frozen=True)
class DotStickerAsset:
    """Approved DOT sticker asset ready for SVG embedding."""

    hazard_class: str | None
    label_name: str
    asset_key: str
    mark_type: str
    data_uri: str


class DotStickerSheetRenderer:
    """Render approved DOT hazard labels and package marks on US Letter sheets."""

    def __init__(self, asset_dir: Path | None = None):
        self.asset_dir = asset_dir or Path(__file__).resolve().parent / "assets" / "dot_labels"
        self.assets = self._load_assets()

    def render_svg_pages(self, stickers: list[dict]) -> list[str]:
        """Return one or more SVG pages filled with approved DOT sticker images."""
        expanded = self._expanded_stickers(stickers)
        page_capacity = 2 if _uses_large_marine_pair_layout(expanded) else DOT_STICKERS_PER_PAGE
        pages = []
        for page_index in range(ceil(len(expanded) / page_capacity)):
            page_stickers = expanded[
                page_index * page_capacity:(page_index + 1) * page_capacity
            ]
            pages.append(self._render_svg_page(page_stickers, page_index + 1))
        return pages

    def generate_pdf(self, stickers: list[dict]) -> bytes:
        """Render a multi-page PDF sticker sheet."""
        writer = PdfWriter()
        for svg_page in self.render_svg_pages(stickers):
            page_pdf = cairosvg.svg2pdf(bytestring=svg_page.encode("utf-8"))
            reader = PdfReader(io.BytesIO(page_pdf))
            writer.add_page(reader.pages[0])

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    def write_pdf(self, stickers: list[dict], path: Path) -> Path:
        """Write the sticker sheet PDF to disk and return the path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.generate_pdf(stickers))
        return path

    def _load_assets(self) -> dict[str, DotStickerAsset]:
        assets = {}
        for asset_key, manifest in DOT_LABEL_ASSET_MANIFEST.items():
            path = self.asset_dir / manifest["filename"]
            if not path.exists():
                continue
            media_type = manifest.get("media_type", "image/svg+xml")
            if media_type == "image/svg+xml":
                asset_bytes = self._normalize_svg_square_viewbox(path.read_text()).encode("utf-8")
            else:
                asset_bytes = path.read_bytes()
            encoded = base64.b64encode(asset_bytes).decode("ascii")
            assets[asset_key] = DotStickerAsset(
                hazard_class=manifest["hazard_class"],
                label_name=manifest["label_name"],
                asset_key=asset_key,
                mark_type=manifest.get("mark_type", "hazard_label"),
                data_uri=f"data:{media_type};base64,{encoded}",
            )
        return assets

    @staticmethod
    def _normalize_svg_square_viewbox(svg_text: str) -> str:
        """Ensure legacy DOT SVG assets scale cleanly inside square sticker slots."""
        svg_match = re.search(r"<svg\b(?P<attrs>[^>]*)>", svg_text, flags=re.IGNORECASE | re.DOTALL)
        if not svg_match:
            raise DotStickerSheetUnavailable("DOT_STICKER_ASSET_INVALID: SVG root not found")

        attrs = svg_match.group("attrs")
        width_match = re.search(r'\bwidth="(?P<value>[\d.]+)"', attrs)
        height_match = re.search(r'\bheight="(?P<value>[\d.]+)"', attrs)
        if not width_match or not height_match:
            raise DotStickerSheetUnavailable("DOT_STICKER_ASSET_INVALID: SVG dimensions missing")

        square_size = int(round(max(float(width_match.group("value")), float(height_match.group("value")))))
        attrs = re.sub(r'\swidth="[^"]*"', f' width="{square_size}"', attrs, count=1)
        attrs = re.sub(r'\sheight="[^"]*"', f' height="{square_size}"', attrs, count=1)
        attrs = re.sub(r'\sviewBox="[^"]*"', "", attrs, count=1)
        attrs = attrs.rstrip() + f' viewBox="0 0 {square_size} {square_size}"'

        return svg_text[:svg_match.start()] + "<svg" + attrs + ">" + svg_text[svg_match.end():]

    def _expanded_stickers(self, stickers: list[dict]) -> list[dict]:
        requested = []
        for sticker in stickers or []:
            asset_key = normalize_dot_sticker_asset_key(
                sticker.get("asset_key") or sticker.get("hazard_class")
            )
            if not asset_key:
                raise DotStickerSheetUnavailable(
                    "DOT_STICKER_ASSET_UNAVAILABLE: Unsupported DOT sticker asset "
                    f"{sticker.get('asset_key') or sticker.get('hazard_class')!r}"
                )
            if asset_key not in self.assets:
                raise DotStickerSheetUnavailable(
                    f"DOT_STICKER_ASSET_UNAVAILABLE: No approved DOT sticker asset for {asset_key}"
                )

            quantity = _positive_quantity(sticker.get("quantity"))
            asset = self.assets[asset_key]
            for _ in range(quantity):
                requested.append({
                    **sticker,
                    "hazard_class": asset.hazard_class,
                    "asset_key": asset_key,
                    "mark_type": asset.mark_type,
                    "label_name": sticker.get("label_name") or asset.label_name,
                })

        if not requested:
            raise DotStickerSheetUnavailable("DOT_STICKER_ASSET_UNAVAILABLE: No DOT stickers were requested")

        if _uses_large_marine_pair_layout(requested):
            return requested

        target_count = ceil(len(requested) / DOT_STICKERS_PER_PAGE) * DOT_STICKERS_PER_PAGE
        expanded = []
        for index in range(target_count):
            expanded.append(requested[index % len(requested)])
        return expanded

    def _render_svg_page(self, stickers: list[dict], page_number: int) -> str:
        large_pair_layout = _uses_large_marine_pair_layout(stickers)
        page_width = US_LETTER_HEIGHT_PT if large_pair_layout else US_LETTER_WIDTH_PT
        page_height = US_LETTER_WIDTH_PT if large_pair_layout else US_LETTER_HEIGHT_PT
        sticker_size = LARGE_PAIR_STICKER_SIZE_PT if large_pair_layout else DOT_STICKER_SIZE_PT
        positions = self._positions(
            page_width=page_width,
            page_height=page_height,
            sticker_size=sticker_size,
            columns=2,
            rows=1 if large_pair_layout else 2,
        )
        images = []
        for index, sticker in enumerate(stickers):
            asset = self.assets[sticker["asset_key"]]
            x, y = positions[index]
            background_color = DOT_LABEL_BACKGROUND_COLORS.get(asset.asset_key)
            if background_color:
                center_x = x + (sticker_size / 2)
                center_y = y + (sticker_size / 2)
                images.append(
                    '<polygon class="dot-sticker-background" '
                    f'id="dot-sticker-background-{page_number}-{index + 1}" '
                    f'points="{center_x:.3f},{y:.3f} {x + sticker_size:.3f},{center_y:.3f} '
                    f'{center_x:.3f},{y + sticker_size:.3f} {x:.3f},{center_y:.3f}" '
                    f'fill="{background_color}"/>'
                )
            hazard_class_attr = (
                f' data-hazard-class="{html.escape(asset.hazard_class)}"'
                if asset.hazard_class
                else ""
            )
            images.append(
                '<image class="dot-sticker" '
                f'id="dot-sticker-{page_number}-{index + 1}" '
                f'data-asset-key="{html.escape(asset.asset_key)}"'
                f'{hazard_class_attr} '
                f'data-mark-type="{html.escape(asset.mark_type)}" '
                f'data-source="{html.escape(str(sticker.get("source") or "primary"))}" '
                f'x="{x:.3f}" y="{y:.3f}" '
                f'width="{sticker_size:.3f}" height="{sticker_size:.3f}" '
                f'href="{asset.data_uri}" preserveAspectRatio="xMidYMid meet"/>'
            )

        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_width}pt" '
            f'height="{page_height}pt" viewBox="0 0 {page_width} {page_height}">\n'
            '<rect width="100%" height="100%" fill="white"/>\n'
            + "\n".join(images)
            + "\n</svg>\n"
        )

    @staticmethod
    def _positions(
        *,
        page_width: float,
        page_height: float,
        sticker_size: float,
        columns: int,
        rows: int,
    ) -> list[tuple[float, float]]:
        gutter_x = (page_width - (columns * sticker_size)) / (columns + 1)
        gutter_y = (page_height - (rows * sticker_size)) / (rows + 1)
        positions = []
        for row in range(rows):
            for column in range(columns):
                positions.append((
                    gutter_x + column * (sticker_size + gutter_x),
                    gutter_y + row * (sticker_size + gutter_y),
                ))
        return positions


def required_sticker_asset_name(hazard_class: str | None) -> str | None:
    """Return the approved asset key for a hazard class, if one is supported."""
    return normalize_dot_hazard_class(hazard_class)


def dot_label_name_for_class(hazard_class: str | None) -> str | None:
    """Return the approved DOT label display name for a normalized class."""
    normalized = normalize_dot_hazard_class(hazard_class)
    if not normalized:
        return None
    manifest = DOT_LABEL_ASSET_MANIFEST.get(normalized)
    return manifest["label_name"] if manifest else None


def normalize_dot_hazard_class(hazard_class: str | None) -> str | None:
    """Normalize DOT hazard class wording into an approved asset lookup key."""
    if not hazard_class:
        return None
    clean = str(hazard_class).strip().lower()
    if not clean or any(marker in clean for marker in ("not regulated", "not applicable", "none", "void")):
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


def normalize_dot_sticker_asset_key(value: str | None) -> str | None:
    """Normalize either an approved package mark key or a DOT hazard class."""
    clean = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if clean == "marine_pollutant":
        return clean
    return normalize_dot_hazard_class(value)


def _uses_large_marine_pair_layout(stickers: Iterable[dict]) -> bool:
    """Use the large two-up sheet only for one hazard label plus one marine mark."""
    items = list(stickers or [])
    asset_keys = [
        normalize_dot_sticker_asset_key(item.get("asset_key") or item.get("hazard_class"))
        for item in items
    ]
    return len(asset_keys) == 2 and "marine_pollutant" in asset_keys


def sticker_size_mm_for(stickers: list[dict]) -> int:
    """Return the physical side length used by the selected sheet layout."""
    return LARGE_PAIR_STICKER_SIZE_MM if _uses_large_marine_pair_layout(stickers) else DOT_STICKER_SIZE_MM


def sheet_size_for(stickers: list[dict]) -> str:
    """Return the operator-facing paper size and orientation."""
    return "US Letter landscape" if _uses_large_marine_pair_layout(stickers) else "US Letter"


def unsupported_dot_sticker_classes(stickers: Iterable[dict]) -> list[str]:
    """Return required sticker classes that do not have approved assets."""
    unsupported = []
    for sticker in stickers or []:
        asset_key = normalize_dot_sticker_asset_key(
            sticker.get("asset_key") or sticker.get("hazard_class")
        )
        if asset_key == "marine_pollutant":
            if asset_key not in DOT_LABEL_ASSET_MANIFEST and asset_key not in unsupported:
                unsupported.append(asset_key)
            continue
        if asset_key and asset_key not in SUPPORTED_DOT_STICKER_CLASSES and asset_key not in unsupported:
            unsupported.append(asset_key)
    return unsupported


def _positive_quantity(value) -> int:
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, quantity)
