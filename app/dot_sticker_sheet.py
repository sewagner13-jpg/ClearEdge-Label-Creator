"""Separate DOT hazard-label sticker sheet rendering.

The product label may reference transport data, but exterior DOT hazard labels
are generated as a separate print artifact using only approved packaged assets.
"""

from __future__ import annotations

import base64
import html
import io
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
}
SUPPORTED_DOT_STICKER_CLASSES = frozenset(DOT_LABEL_ASSET_MANIFEST)


class DotStickerSheetUnavailable(ValueError):
    """Raised when a required DOT sticker cannot be produced from approved assets."""


@dataclass(frozen=True)
class DotStickerAsset:
    """Approved DOT sticker asset ready for SVG embedding."""

    hazard_class: str
    label_name: str
    asset_key: str
    data_uri: str


class DotStickerSheetRenderer:
    """Render US Letter sheets containing 100 mm DOT hazard-label stickers."""

    def __init__(self, asset_dir: Path | None = None):
        self.asset_dir = asset_dir or Path(__file__).resolve().parent / "assets" / "dot_labels"
        self.assets = self._load_assets()

    def render_svg_pages(self, stickers: list[dict]) -> list[str]:
        """Return one or more SVG pages filled with approved DOT sticker images."""
        expanded = self._expanded_stickers(stickers)
        pages = []
        for page_index in range(ceil(len(expanded) / DOT_STICKERS_PER_PAGE)):
            page_stickers = expanded[
                page_index * DOT_STICKERS_PER_PAGE:(page_index + 1) * DOT_STICKERS_PER_PAGE
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
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            assets[asset_key] = DotStickerAsset(
                hazard_class=manifest["hazard_class"],
                label_name=manifest["label_name"],
                asset_key=asset_key,
                data_uri=f"data:image/svg+xml;base64,{encoded}",
            )
        return assets

    def _expanded_stickers(self, stickers: list[dict]) -> list[dict]:
        requested = []
        for sticker in stickers or []:
            normalized = normalize_dot_hazard_class(
                sticker.get("asset_key") or sticker.get("hazard_class")
            )
            if not normalized:
                raise DotStickerSheetUnavailable(
                    f"DOT_STICKER_ASSET_UNAVAILABLE: Unsupported DOT hazard class {sticker.get('hazard_class')!r}"
                )
            if normalized not in self.assets:
                raise DotStickerSheetUnavailable(
                    f"DOT_STICKER_ASSET_UNAVAILABLE: No approved DOT sticker asset for hazard class {normalized}"
                )

            quantity = _positive_quantity(sticker.get("quantity"))
            for _ in range(quantity):
                requested.append({
                    **sticker,
                    "hazard_class": normalized,
                    "asset_key": normalized,
                    "label_name": sticker.get("label_name") or self.assets[normalized].label_name,
                })

        if not requested:
            raise DotStickerSheetUnavailable("DOT_STICKER_ASSET_UNAVAILABLE: No DOT stickers were requested")

        target_count = ceil(len(requested) / DOT_STICKERS_PER_PAGE) * DOT_STICKERS_PER_PAGE
        expanded = []
        for index in range(target_count):
            expanded.append(requested[index % len(requested)])
        return expanded

    def _render_svg_page(self, stickers: list[dict], page_number: int) -> str:
        positions = self._positions()
        images = []
        for index, sticker in enumerate(stickers):
            asset = self.assets[sticker["asset_key"]]
            x, y = positions[index]
            images.append(
                '<image class="dot-sticker" '
                f'id="dot-sticker-{page_number}-{index + 1}" '
                f'data-hazard-class="{html.escape(sticker["hazard_class"])}" '
                f'data-source="{html.escape(str(sticker.get("source") or "primary"))}" '
                f'x="{x:.3f}" y="{y:.3f}" '
                f'width="{DOT_STICKER_SIZE_PT:.3f}" height="{DOT_STICKER_SIZE_PT:.3f}" '
                f'href="{asset.data_uri}" preserveAspectRatio="xMidYMid meet"/>'
            )

        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{US_LETTER_WIDTH_PT}pt" '
            f'height="{US_LETTER_HEIGHT_PT}pt" viewBox="0 0 {US_LETTER_WIDTH_PT} {US_LETTER_HEIGHT_PT}">\n'
            '<rect width="100%" height="100%" fill="white"/>\n'
            + "\n".join(images)
            + "\n</svg>\n"
        )

    @staticmethod
    def _positions() -> list[tuple[float, float]]:
        gutter_x = (US_LETTER_WIDTH_PT - (DOT_STICKER_COLUMNS * DOT_STICKER_SIZE_PT)) / (
            DOT_STICKER_COLUMNS + 1
        )
        gutter_y = (US_LETTER_HEIGHT_PT - (DOT_STICKER_ROWS * DOT_STICKER_SIZE_PT)) / (
            DOT_STICKER_ROWS + 1
        )
        positions = []
        for row in range(DOT_STICKER_ROWS):
            for column in range(DOT_STICKER_COLUMNS):
                positions.append((
                    gutter_x + column * (DOT_STICKER_SIZE_PT + gutter_x),
                    gutter_y + row * (DOT_STICKER_SIZE_PT + gutter_y),
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


def unsupported_dot_sticker_classes(stickers: Iterable[dict]) -> list[str]:
    """Return required sticker classes that do not have approved assets."""
    unsupported = []
    for sticker in stickers or []:
        normalized = normalize_dot_hazard_class(sticker.get("asset_key") or sticker.get("hazard_class"))
        if normalized and normalized not in SUPPORTED_DOT_STICKER_CLASSES and normalized not in unsupported:
            unsupported.append(normalized)
    return unsupported


def _positive_quantity(value) -> int:
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, quantity)
