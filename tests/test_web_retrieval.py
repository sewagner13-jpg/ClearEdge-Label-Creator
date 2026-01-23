"""
Tests for web retrieval module.
"""

import pytest
from unittest.mock import Mock, patch

from app.web_retrieval import WebRetriever
from app.config import settings


class TestWebRetriever:
    """Test web retrieval with domain allowlist."""

    @pytest.fixture
    def retriever(self):
        return WebRetriever()

    def test_domain_allowed(self, retriever):
        """Test domain allowlist checking."""
        # Should be allowed (in default allowlist)
        assert retriever.is_domain_allowed("https://www.fishersci.com/sds.pdf") is True
        assert retriever.is_domain_allowed("https://sigmaaldrich.com/sds.pdf") is True

        # Subdomain should work
        assert retriever.is_domain_allowed("https://www.msds.com/file.pdf") is True

    def test_domain_not_allowed(self, retriever):
        """Test blocked domains."""
        assert retriever.is_domain_allowed("https://malicious-site.com/file.pdf") is False
        assert retriever.is_domain_allowed("https://random.net/sds.pdf") is False

    def test_download_without_approval_fails(self, retriever):
        """Download requires explicit approval."""
        with pytest.raises(ValueError, match="approval required"):
            retriever.download_document(
                "https://fishersci.com/test.pdf",
                user_approved=False
            )

    def test_download_blocked_domain_fails(self, retriever):
        """Download from blocked domain fails."""
        with pytest.raises(ValueError, match="not allowed"):
            retriever.download_document(
                "https://blocked-domain.com/file.pdf",
                user_approved=True
            )

    @patch('httpx.Client')
    def test_download_success(self, mock_client, retriever):
        """Test successful download."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.content = b"PDF content here"
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client.return_value = mock_client_instance

        result = retriever.download_document(
            "https://fishersci.com/test.pdf",
            user_approved=True
        )

        assert result == b"PDF content here"

    def test_validate_url(self, retriever):
        """Test URL validation."""
        result = retriever.validate_url("https://random-domain.com/file.pdf")

        assert result["url"] == "https://random-domain.com/file.pdf"
        assert result["domain_allowed"] is False
        assert result["error"] is not None
