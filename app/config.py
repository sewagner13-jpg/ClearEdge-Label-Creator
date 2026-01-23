"""
Configuration management for the label pipeline.
Loads settings from environment variables with validation.
"""

from typing import List
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration with strict validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Gemini AI
    gemini_api_key: str = Field(..., description="Gemini API key from Google AI Studio")
    gemini_model: str = Field(default="gemini-1.5-pro", description="Gemini model name")
    gemini_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    gemini_max_retries: int = Field(default=3, ge=1, le=10)

    # Google Drive
    shared_drive_id: str = Field(
        default="0APFlqBVg60o6Uk9PVA",
        description="Shared Drive ID"
    )
    google_service_account_file: str = Field(
        ...,
        description="Path to service account JSON key file"
    )
    root_folder_name: str = Field(
        default="Product Labels",
        description="Root folder name in Shared Drive"
    )

    # Application
    env: str = Field(default="development", pattern="^(development|production|testing)$")
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    api_port: int = Field(default=8000, ge=1024, le=65535)
    api_host: str = Field(default="0.0.0.0")

    # OCR Configuration
    tesseract_cmd: str = Field(default="/usr/bin/tesseract")
    ocr_lang: str = Field(default="eng")
    ocr_threshold_chars: int = Field(
        default=100,
        description="Min chars per page before OCR fallback"
    )

    # Web Retrieval
    allowed_domains: List[str] = Field(
        default_factory=lambda: [
            "msds.com",
            "fishersci.com",
            "sigmaaldrich.com",
            "chemicalsafety.com",
            "ehs.com"
        ]
    )
    web_retrieval_timeout: int = Field(default=30, ge=5, le=300)

    # Label Generation
    default_label_width: int = Field(default=800, ge=200, le=2000)
    default_label_height: int = Field(default=1000, ge=200, le=3000)
    purple_header_color: str = Field(default="#5A2D82")

    @validator("allowed_domains", pre=True)
    def parse_allowed_domains(cls, v):
        """Parse comma-separated string or list."""
        if isinstance(v, str):
            return [d.strip() for d in v.split(",") if d.strip()]
        return v


# Global settings instance
settings = Settings()
