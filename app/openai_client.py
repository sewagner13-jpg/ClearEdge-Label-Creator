"""
OpenAI (ChatGPT) client for structured SDS/TDS extraction.
Sends extracted text and returns validated JSON with evidence.
"""

import json
import logging
import time
from typing import Dict, Any, Optional

from openai import OpenAI

from .config import settings
from .schema import ExtractedData, ExtractedText

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI (ChatGPT) client for SDS/TDS structured extraction."""

    SYSTEM_PROMPT = """You are an expert chemical safety data extraction system. Your task is to extract structured information from Safety Data Sheets (SDS) and Technical Data Sheets (TDS).

CRITICAL RULES:
1. Return ONLY valid JSON - no markdown, no explanations, no additional text
2. Unknown or missing fields MUST be null (never use text like "not specified", "N/A", "unknown")
3. Extract EXACTLY what is stated in the documents - do not infer or assume
4. For every extracted field, provide evidence with verbatim quotes (max 240 chars)
5. Include section name/number and page number when available
6. Use confidence scores: 1.0 = explicit statement, 0.8 = clear but indirect, 0.5 = inferred, 0.3 = uncertain

SCHEMA TO FOLLOW:
{
  "product": {
    "name": "string (required)",
    "supplier_name": "string|null",
    "supplier_address": "string|null",
    "supplier_phone": "string|null",
    "emergency_phone": "string|null",
    "revision_date": "string|null (ISO format preferred)"
  },
  "ghs": {
    "signal_word": "Danger|Warning|null",
    "pictograms": ["GHS01", "GHS02", ...],  // Valid: GHS01-GHS09
    "hazard_statements": [
      {"code": "H225|null", "text": "string"}
    ],
    "precautionary_statements": [
      {"code": "P210|null", "text": "string"}
    ],
    "supplemental_statements": ["string"]|null
  },
  "transport": {
    "un_number": "string|null (e.g., UN1090)",
    "proper_shipping_name": "string|null",
    "hazard_class": "string|null (e.g., 3, 6.1, 8)",
    "packing_group": "I|II|III|null",
    "marine_pollutant": true|false|null,
    "limited_quantity": "string|null",
    "special_provisions": "string|null",
    "erg_guide_number": "string|null"
  },
  "evidence": [
    {
      "field_path": "product.name",
      "doc": "SDS|TDS",
      "section": "Section 1|null",
      "page": 1|null,
      "quote": "verbatim quote max 240 chars"
    }
  ],
  "confidence": [
    {"field_path": "product.name", "confidence": 0.0-1.0}
  ],
  "warnings": ["string array of extraction warnings"]
}

TRANSPORT CLASSIFICATION (Section 14):
- Extract UN number, proper shipping name, hazard class, packing group
- Look for DOT, IATA, IMDG classifications
- Marine pollutant status if mentioned

GHS PICTOGRAMS:
- GHS01: Explosive
- GHS02: Flammable
- GHS03: Oxidizing
- GHS04: Compressed Gas
- GHS05: Corrosive
- GHS06: Acute Toxicity
- GHS07: Harmful/Irritant
- GHS08: Health Hazard
- GHS09: Environmental Hazard

Extract only pictograms explicitly mentioned or shown in the SDS."""

    def __init__(self):
        """Initialize OpenAI client."""
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model_name = settings.openai_model
        self.temperature = settings.openai_temperature
        self.max_retries = settings.openai_max_retries

    def extract_from_documents(
        self,
        sds_text: Optional[ExtractedText],
        tds_text: Optional[ExtractedText],
        product_name: str
    ) -> ExtractedData:
        """
        Extract structured data from SDS and/or TDS.

        Args:
            sds_text: Extracted SDS text (optional)
            tds_text: Extracted TDS text (optional)
            product_name: Expected product name

        Returns:
            ExtractedData with validated fields
        """
        if not sds_text and not tds_text:
            raise ValueError("At least one document (SDS or TDS) is required")

        # Build prompt with document text
        user_prompt = self._build_user_prompt(sds_text, tds_text, product_name)

        # Call OpenAI with retries
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"OpenAI extraction attempt {attempt}/{self.max_retries}")
                start_time = time.time()

                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature,
                    response_format={"type": "json_object"}
                )

                duration = time.time() - start_time
                logger.info(f"OpenAI responded in {duration:.2f}s")

                # Parse and validate response
                response_text = response.choices[0].message.content
                return self._parse_response(response_text, product_name)

            except json.JSONDecodeError as e:
                logger.warning(f"Attempt {attempt}: Invalid JSON: {e}")
                if attempt == self.max_retries:
                    # Final attempt - try to repair JSON
                    logger.info("Attempting JSON repair")
                    try:
                        return self._repair_and_parse(response_text, product_name)
                    except Exception as repair_error:
                        logger.error(f"JSON repair failed: {repair_error}")
                        raise ValueError(
                            f"OpenAI returned invalid JSON after {self.max_retries} attempts. "
                            f"Raw response saved for debugging."
                        )
                time.sleep(2 ** attempt)  # Exponential backoff

            except Exception as e:
                logger.error(f"Attempt {attempt}: OpenAI error: {e}")
                if attempt == self.max_retries:
                    raise
                time.sleep(2 ** attempt)

        raise ValueError("All OpenAI extraction attempts failed")

    def _build_user_prompt(
        self,
        sds_text: Optional[ExtractedText],
        tds_text: Optional[ExtractedText],
        product_name: str
    ) -> str:
        """Build extraction prompt with document text."""
        parts = [
            f"EXPECTED PRODUCT NAME: {product_name}\n"
        ]

        if sds_text:
            parts.append("\n=== SAFETY DATA SHEET (SDS) ===\n")
            for page in sds_text.pages:
                parts.append(f"\n--- Page {page.page} ---\n{page.text}\n")

        if tds_text:
            parts.append("\n=== TECHNICAL DATA SHEET (TDS) ===\n")
            for page in tds_text.pages:
                parts.append(f"\n--- Page {page.page} ---\n{page.text}\n")

        parts.append(
            "\n\nEXTRACT all structured information following the JSON schema. "
            "Return ONLY the JSON object, no additional text."
        )

        return "".join(parts)

    def _parse_response(self, response_text: str, product_name: str) -> ExtractedData:
        """Parse and validate OpenAI JSON response."""
        # Remove markdown code blocks if present
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Parse JSON
        data = json.loads(cleaned)

        # Validate with Pydantic
        extracted = ExtractedData(**data)

        # Verify product name matches
        if extracted.product.name.lower() != product_name.lower():
            extracted.warnings.append(
                f"Product name mismatch: expected '{product_name}', "
                f"got '{extracted.product.name}'"
            )

        return extracted

    def _repair_and_parse(self, response_text: str, product_name: str) -> ExtractedData:
        """Attempt to repair malformed JSON (single retry)."""
        logger.info("Attempting JSON repair with OpenAI")

        repair_prompt = f"""The following JSON is malformed. Fix it and return ONLY valid JSON:

{response_text}

Return ONLY the corrected JSON, no explanations."""

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a JSON repair expert. Return only valid JSON."},
                {"role": "user", "content": repair_prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )

        return self._parse_response(response.choices[0].message.content, product_name)

    def get_model_info(self) -> Dict[str, Any]:
        """Get current model information."""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_retries": self.max_retries
        }
