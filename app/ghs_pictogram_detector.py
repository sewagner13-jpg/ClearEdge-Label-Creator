"""Detect embedded SDS GHS artwork by matching approved pictogram assets."""

import io
import logging
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops
from pypdf import PdfReader

from .schema import DetectedGHSPictogram


logger = logging.getLogger(__name__)

ASSET_FILES = {
    "GHS01": "GHS01_exploding_bomb.png",
    "GHS02": "GHS02_flame.png",
    "GHS03": "GHS03_flame_over_circle.png",
    "GHS04": "GHS04_gas_cylinder.png",
    "GHS05": "GHS05_corrosion.png",
    "GHS06": "GHS06_skull_and_crossbones.png",
    "GHS07": "GHS07_exclamation_point.png",
    "GHS08": "GHS08_health_hazard.png",
    "GHS09": "GHS09_environment.png",
}

MAX_SCAN_PAGES = 3
MIN_MATCH_SCORE = 0.62
MIN_MATCH_MARGIN = 0.10
MASK_SIZE = 80
MAX_SYMBOL_SIZE = 68


class GHSPictogramDetector:
    """Identify square red-diamond images embedded in the first SDS pages."""

    @classmethod
    def detect_pdf(cls, pdf_bytes: bytes) -> list[DetectedGHSPictogram]:
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as exc:
            logger.info("GHS artwork detection skipped; PDF could not be read: %s", exc)
            return []

        detections: list[DetectedGHSPictogram] = []
        seen_codes: set[str] = set()
        for page_number, page in enumerate(reader.pages[:MAX_SCAN_PAGES], start=1):
            try:
                images = list(page.images)
            except Exception as exc:
                logger.info("GHS artwork detection skipped on page %s: %s", page_number, exc)
                continue
            for embedded in images:
                match = cls.identify_image(embedded.image)
                if not match:
                    continue
                code, confidence = match
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                detections.append(
                    DetectedGHSPictogram(
                        code=code,
                        page=page_number,
                        confidence=round(confidence, 4),
                    )
                )
        return detections

    @classmethod
    def identify_image(cls, image: Image.Image) -> tuple[str, float] | None:
        if not cls._looks_like_red_diamond(image):
            return None
        candidate_mask = cls._symbol_mask(image)
        if candidate_mask is None:
            return None

        scores = sorted(
            (
                (cls._best_iou(candidate_mask, asset_mask), code)
                for code, asset_mask in cls._approved_masks()
            ),
            reverse=True,
        )
        best_score, best_code = scores[0]
        second_score = scores[1][0]
        if best_score < MIN_MATCH_SCORE or best_score - second_score < MIN_MATCH_MARGIN:
            return None
        return best_code, best_score

    @staticmethod
    def _looks_like_red_diamond(image: Image.Image) -> bool:
        flattened = GHSPictogramDetector._flatten(image)
        width, height = flattened.size
        if min(width, height) < 40 or not 0.75 <= width / height <= 1.25:
            return False
        pixels = list(flattened.getdata())
        red_pixels = sum(
            1
            for red, green, blue in pixels
            if red >= 145 and red >= green * 1.35 and red >= blue * 1.35
        )
        return red_pixels / max(len(pixels), 1) >= 0.012

    @staticmethod
    def _flatten(image: Image.Image) -> Image.Image:
        source = image.convert("RGBA")
        background = Image.new("RGBA", source.size, "white")
        background.alpha_composite(source)
        return background.convert("RGB")

    @classmethod
    def _symbol_mask(cls, image: Image.Image) -> Image.Image | None:
        source = cls._flatten(image)
        mask = Image.new("1", source.size)
        source_pixels = source.load()
        mask_pixels = mask.load()
        for y in range(source.height):
            for x in range(source.width):
                red, green, blue = source_pixels[x, y]
                mask_pixels[x, y] = 255 if max(red, green, blue) < 110 else 0

        bounds = mask.getbbox()
        if not bounds:
            return None
        symbol = mask.crop(bounds)
        symbol.thumbnail((MAX_SYMBOL_SIZE, MAX_SYMBOL_SIZE), Image.Resampling.LANCZOS)
        normalized = Image.new("1", (MASK_SIZE, MASK_SIZE))
        normalized.paste(
            symbol,
            ((MASK_SIZE - symbol.width) // 2, (MASK_SIZE - symbol.height) // 2),
        )
        return normalized

    @staticmethod
    def _best_iou(first: Image.Image, second: Image.Image) -> float:
        best = 0.0
        for offset_x in range(-4, 5):
            for offset_y in range(-4, 5):
                shifted = Image.new("1", first.size)
                shifted.paste(second, (offset_x, offset_y))
                intersection = ImageChops.logical_and(first, shifted).histogram()[255]
                union = ImageChops.logical_or(first, shifted).histogram()[255]
                if union:
                    best = max(best, intersection / union)
        return best

    @staticmethod
    @lru_cache(maxsize=1)
    def _approved_masks() -> tuple[tuple[str, Image.Image], ...]:
        asset_dir = Path(__file__).resolve().parent / "assets" / "ghs_pictograms"
        masks = []
        for code, filename in ASSET_FILES.items():
            with Image.open(asset_dir / filename) as image:
                mask = GHSPictogramDetector._symbol_mask(image.copy())
            if mask is not None:
                masks.append((code, mask))
        return tuple(masks)
