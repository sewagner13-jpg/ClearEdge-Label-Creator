# Changelog

All notable changes to the CLEAR EDGE Product Label Pipeline will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-15

### Added
- Initial production release
- Google Drive Shared Drive integration with proper API parameters
- PDF text extraction with automatic OCR fallback
- Gemini AI structured extraction with evidence tracking
- Pydantic v2 schemas for strict data validation
- DOT/OSHA/GHS compliance validation engine
- Dual compliance modes: shipped_dot and workplace
- SVG and PDF label generation
- Complete audit trail system with SHA-256 hashing
- Web retrieval with domain allowlist and approval workflow
- FastAPI REST API with comprehensive endpoints
- CLI interface for batch operations
- Unit tests with >80% coverage
- Comprehensive documentation

### Features
- `/health` endpoint for system monitoring
- `/products` endpoint to list all products
- `/ingest/drive` for scanning Shared Drive folders
- `/ingest/url` for controlled web retrieval
- `/extract/{product}` for end-to-end extraction and validation
- CLI commands: scan-drive, ingest-url, extract, info
- Automatic product folder creation with standard structure
- Dated audit folders (YYYY-MM-DD) for version tracking
- DOT/GHS pictogram overlap detection
- Confidence scoring for extracted fields
- JSON repair for malformed Gemini responses
- Configurable OCR thresholds
- Template-based label generation

### Security
- Service account authentication for Drive API
- API key based Gemini authentication
- Domain allowlist for web retrieval
- Explicit user approval required for downloads
- No credentials in repository
- SHA-256 file hashing for integrity
- Audit trail for all operations

### Documentation
- Complete README with setup instructions
- Google Cloud configuration guide
- API endpoint documentation
- CLI usage examples
- Troubleshooting guide
- Contributing guidelines
- Architecture diagrams

## [Unreleased]

### Planned
- Interactive label designer UI
- Additional label templates
- Batch processing for multiple products
- Email notifications for validation failures
- Export to external label printers
- Multi-language support
- Advanced GHS pictogram rendering with actual SVGs
- DOT placard integration
- QR code generation with actual SDS URLs
