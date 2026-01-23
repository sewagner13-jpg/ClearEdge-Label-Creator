"""
Controlled web retrieval for SDS/TDS documents.
Requires explicit user approval before downloading.
"""

import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse
import httpx

from .config import settings

logger = logging.getLogger(__name__)


class WebRetriever:
    """Controlled web retrieval with domain allowlist and approval workflow."""

    def __init__(self):
        self.allowed_domains = settings.allowed_domains
        self.timeout = settings.web_retrieval_timeout

    def is_domain_allowed(self, url: str) -> bool:
        """Check if URL domain is in allowlist."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check against allowlist
            for allowed in self.allowed_domains:
                if domain == allowed or domain.endswith(f".{allowed}"):
                    return True

            return False

        except Exception as e:
            logger.error(f"Error parsing URL {url}: {e}")
            return False

    def search_for_documents(
        self,
        product_name: str,
        manufacturer: Optional[str] = None,
        doc_type: str = "SDS"
    ) -> List[Dict[str, str]]:
        """
        Search for SDS/TDS documents (simulation).

        In production, this would use a search API or web scraping.
        For now, returns placeholder results requiring user input.

        Args:
            product_name: Product name to search for
            manufacturer: Optional manufacturer name
            doc_type: "SDS" or "TDS"

        Returns:
            List of candidate URLs with metadata
        """
        logger.info(
            f"Searching for {doc_type} for product '{product_name}' "
            f"(manufacturer: {manufacturer or 'any'})"
        )

        # Placeholder implementation
        # In production, implement actual search logic
        search_query = f"{product_name} {manufacturer or ''} {doc_type} PDF filetype:pdf"

        logger.warning(
            "Web search not implemented. User must provide URLs manually.\n"
            f"Suggested search: {search_query}"
        )

        return []

    def download_document(
        self,
        url: str,
        user_approved: bool = False
    ) -> bytes:
        """
        Download document from URL with approval check.

        Args:
            url: Document URL
            user_approved: Whether user has approved this download

        Returns:
            Downloaded file bytes

        Raises:
            ValueError: If domain not allowed or approval missing
            httpx.HTTPError: If download fails
        """
        # Check domain allowlist
        if not self.is_domain_allowed(url):
            raise ValueError(
                f"Domain not allowed: {urlparse(url).netloc}\n"
                f"Allowed domains: {', '.join(self.allowed_domains)}"
            )

        # Require explicit approval
        if not user_approved:
            raise ValueError(
                f"User approval required before downloading from: {url}\n"
                "Set user_approved=True to proceed"
            )

        logger.info(f"Downloading from approved URL: {url}")

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()

                # Verify content type
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" not in content_type and "octet-stream" not in content_type:
                    logger.warning(
                        f"Unexpected content type: {content_type}. "
                        "Expected application/pdf"
                    )

                file_bytes = response.content
                logger.info(f"Downloaded {len(file_bytes)} bytes from {url}")

                return file_bytes

        except httpx.HTTPError as e:
            logger.error(f"Download failed for {url}: {e}")
            raise

    def get_candidate_urls(
        self,
        product_name: str,
        manufacturer: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Get candidate URLs for user approval.

        Returns dictionary with 'sds' and 'tds' URL lists.
        User must review and approve before download.
        """
        # In production, this would perform actual web searches
        # For now, return empty lists requiring manual input

        logger.info(
            f"To retrieve documents for '{product_name}', search manually:\n"
            f"  SDS: {product_name} {manufacturer or ''} SDS PDF\n"
            f"  TDS: {product_name} {manufacturer or ''} TDS PDF\n"
            f"Then provide URLs via CLI or API"
        )

        return {
            "sds": [],
            "tds": []
        }

    def validate_url(self, url: str) -> Dict[str, any]:
        """
        Validate URL without downloading.

        Returns:
            Dictionary with validation results
        """
        result = {
            "url": url,
            "domain_allowed": False,
            "reachable": False,
            "is_pdf": False,
            "error": None
        }

        # Check domain
        result["domain_allowed"] = self.is_domain_allowed(url)
        if not result["domain_allowed"]:
            result["error"] = f"Domain not in allowlist: {urlparse(url).netloc}"
            return result

        # Check if reachable (HEAD request)
        try:
            with httpx.Client(timeout=10) as client:
                response = client.head(url, follow_redirects=True)
                result["reachable"] = response.status_code == 200

                content_type = response.headers.get("content-type", "").lower()
                result["is_pdf"] = "pdf" in content_type

                if not result["is_pdf"]:
                    result["error"] = f"Not a PDF (content-type: {content_type})"

        except Exception as e:
            result["error"] = str(e)

        return result
