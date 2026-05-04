"""
FastAPI application for the CLEAR EDGE Product Label Pipeline.
Provides REST API endpoints for all pipeline operations.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .drive_client import DriveClient
from .pdf_extract import PDFExtractor
from .gemini_client import GeminiClient
from .validator import ComplianceValidator
from .audit import AuditLogger
from .web_retrieval import WebRetriever
from .label_stub import LabelGenerator
from .schema import ExtractedData, ValidationResult

from fastapi.responses import FileResponse, RedirectResponse
from enum import Enum
from pathlib import Path
import tempfile
import os
import re
import uuid
import secrets
import json

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Shared clients
drive_client: Optional[DriveClient] = None
pdf_extractor: Optional[PDFExtractor] = None
gemini_client: Optional[GeminiClient] = None
validator: Optional[ComplianceValidator] = None
web_retriever: Optional[WebRetriever] = None
label_generator: Optional[LabelGenerator] = None
startup_errors: Dict[str, str] = {}


class LabelMode(str, Enum):
    """Label mode options."""
    SHIPPED_DOT = "shipped_dot"
    WORKPLACE = "workplace"


class LabelSize(str, Enum):
    """Label size options."""
    PAIL = "pail"
    DRUM = "drum"


DEFAULT_DATA_ROOT = Path(os.getenv("CLEAREDGE_DATA_DIR", str(Path.cwd() / "runtime_data")))
LABELS_DIR = DEFAULT_DATA_ROOT / "labels"
LABELS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory metadata store for Phase 1 API reads
label_metadata_store: Dict[str, dict] = {}


def _metadata_file() -> Path:
    """Return current metadata file path."""
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    return LABELS_DIR / "label_metadata_store.json"


def _load_label_metadata_store() -> None:
    """Load metadata store from disk if available."""
    global label_metadata_store
    metadata_file = _metadata_file()
    if metadata_file.exists():
        try:
            label_metadata_store = json.loads(metadata_file.read_text())
        except Exception as exc:
            logger.warning(f"Unable to load label metadata store: {exc}")
            label_metadata_store = {}


def _save_label_metadata_store() -> None:
    """Persist metadata store to disk for restarts."""
    _metadata_file().write_text(json.dumps(label_metadata_store))



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup shared resources."""
    global drive_client, pdf_extractor, gemini_client, validator, web_retriever, label_generator, startup_errors

    logger.info("Initializing CLEAR EDGE Label Pipeline...")
    startup_errors = {}

    try:
        pdf_extractor = PDFExtractor()
        gemini_client = GeminiClient()
        validator = ComplianceValidator()
        web_retriever = WebRetriever()
        label_generator = LabelGenerator()
        _load_label_metadata_store()

        try:
            drive_client = DriveClient()
        except Exception as exc:
            drive_client = None
            startup_errors["drive_client"] = str(exc)
            logger.warning("Drive client unavailable; Drive-backed routes will be degraded: %s", exc)

        logger.info("Core clients initialized successfully")
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        raise

    yield

    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="CLEAR EDGE Product Label Pipeline",
    description="Production-grade DOT/OSHA-compliant chemical product label automation",
    version="1.0.0",
    lifespan=lifespan
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class IngestDriveRequest(BaseModel):
    """Request to ingest PDFs from Drive."""
    product_name: str = Field(..., min_length=1)


class IngestURLRequest(BaseModel):
    """Request to ingest PDF from URL."""
    product_name: str
    url: str
    doc_type: str = Field(..., pattern="^(SDS|TDS)$")
    user_approved: bool = Field(default=False)


class ExtractRequest(BaseModel):
    """Request to extract data from PDFs."""
    product_name: str
    mode: str = Field(default="shipped_dot", pattern="^(workplace|shipped_dot)$")
    force_reextract: bool = Field(default=False)


class ProductListResponse(BaseModel):
    """Response with list of products."""
    products: List[str]





class ValidationSummary(BaseModel):
    """Validation summary payload."""
    passed: bool
    warnings: List[dict]
    errors: List[dict]


class LabelPayload(BaseModel):
    """Label artifact payload."""
    mode: str
    size: str
    download_url: Optional[str] = None


class AuditPayload(BaseModel):
    """Audit metadata payload."""
    created_at: str
    phase: str




class OverrideApprovalRequest(BaseModel):
    """Manual override request for compliance-blocked exports."""
    approver: str = Field(..., min_length=2, max_length=100)
    reason: str = Field(..., min_length=10, max_length=500)

class GenerateLabelResponse(BaseModel):
    """Unified Phase 1 label generation response."""
    label_id: str
    extracted: dict
    validation: ValidationSummary
    label: LabelPayload
    warnings: List[dict]
    errors: List[dict]
    audit: AuditPayload
    success: bool

def _health_payload() -> dict:
    """Shared liveness payload."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "gemini_model": settings.gemini_model,
        "shared_drive_id": settings.shared_drive_id
    }


def _readiness_payload() -> dict:
    """Dependency-oriented readiness payload for Phase 0 diagnostics."""
    checks = {
        "drive_client_initialized": drive_client is not None,
        "pdf_extractor_initialized": pdf_extractor is not None,
        "gemini_client_initialized": gemini_client is not None,
        "validator_initialized": validator is not None,
        "web_retriever_initialized": web_retriever is not None,
        "label_generator_initialized": label_generator is not None,
        "gemini_api_key_present": bool(settings.gemini_api_key),
        "shared_drive_id_present": bool(settings.shared_drive_id),
    }
    status = "ready" if all(checks.values()) else "degraded"
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "startup_errors": startup_errors,
    }


# Endpoints

@app.get("/", include_in_schema=False)
async def root():
    """Send browser users to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return _health_payload()


@app.get("/api/v1/readiness")
async def readiness_check():
    """Readiness check endpoint with dependency diagnostics."""
    return _readiness_payload()


@app.get("/products", response_model=ProductListResponse)
async def list_products():
    """List all product folders in the Shared Drive."""
    try:
        products = drive_client.list_all_products()
        return ProductListResponse(products=products)
    except Exception as e:
        logger.error(f"Error listing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/drive")
async def ingest_from_drive(request: IngestDriveRequest):
    """
    Scan product folder in Drive for new SDS/TDS PDFs.
    Creates product folder if it doesn't exist.
    """
    try:
        product_name = request.product_name

        # Find or create product folder
        product_folder_id = drive_client.find_product_folder(product_name)
        if not product_folder_id:
            logger.info(f"Creating new product folder: {product_name}")
            product_folder_id = drive_client.create_product_folder(product_name)

        # Scan for PDFs in SDS and TDS folders
        sds_folder_id = drive_client.find_subfolder(product_folder_id, "SDS")
        tds_folder_id = drive_client.find_subfolder(product_folder_id, "TDS")

        sds_files = drive_client.list_files_in_folder(sds_folder_id, "application/pdf") if sds_folder_id else []
        tds_files = drive_client.list_files_in_folder(tds_folder_id, "application/pdf") if tds_folder_id else []

        return {
            "product_name": product_name,
            "product_folder_id": product_folder_id,
            "sds_files": len(sds_files),
            "tds_files": len(tds_files),
            "files": {
                "sds": [{"id": f["id"], "name": f["name"]} for f in sds_files],
                "tds": [{"id": f["id"], "name": f["name"]} for f in tds_files]
            }
        }

    except Exception as e:
        logger.error(f"Drive ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/url")
async def ingest_from_url(request: IngestURLRequest):
    """
    Download PDF from URL and upload to Drive.
    Requires user approval for security.
    """
    try:
        # Validate and download
        pdf_bytes = web_retriever.download_document(
            request.url,
            user_approved=request.user_approved
        )

        # Find or create product folder
        product_folder_id = drive_client.find_product_folder(request.product_name)
        if not product_folder_id:
            product_folder_id = drive_client.create_product_folder(request.product_name)

        # Upload to appropriate folder
        folder_name = request.doc_type  # "SDS" or "TDS"
        target_folder_id = drive_client.find_subfolder(product_folder_id, folder_name)

        if not target_folder_id:
            raise ValueError(f"{folder_name} folder not found")

        # Generate filename
        filename = f"{request.product_name}_{request.doc_type}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"

        # Upload
        file_id = drive_client.upload_file(
            pdf_bytes,
            filename,
            target_folder_id,
            "application/pdf"
        )

        # Compute hash
        file_hash = AuditLogger.compute_sha256(pdf_bytes)

        return {
            "product_name": request.product_name,
            "doc_type": request.doc_type,
            "file_id": file_id,
            "filename": filename,
            "size_bytes": len(pdf_bytes),
            "sha256": file_hash,
            "source_url": request.url
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"URL ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract/{product_name}")
async def extract_product(product_name: str, mode: str = "shipped_dot"):
    """
    Extract structured data from SDS/TDS PDFs for a product.
    Validates and saves to Drive with audit trail.
    """
    try:
        import time

        start_time = time.time()

        # Find product folder
        product_folder_id = drive_client.find_product_folder(product_name)
        if not product_folder_id:
            raise HTTPException(
                status_code=404,
                detail=f"Product '{product_name}' not found. Use /ingest/drive to create."
            )

        # Find SDS/TDS folders
        sds_folder_id = drive_client.find_subfolder(product_folder_id, "SDS")
        tds_folder_id = drive_client.find_subfolder(product_folder_id, "TDS")

        # Get latest PDFs
        sds_files = drive_client.list_files_in_folder(sds_folder_id, "application/pdf") if sds_folder_id else []
        tds_files = drive_client.list_files_in_folder(tds_folder_id, "application/pdf") if tds_folder_id else []

        if not sds_files and not tds_files:
            raise HTTPException(
                status_code=400,
                detail="No SDS or TDS PDFs found for this product"
            )

        # Download and extract text from SDS
        sds_text = None
        sds_file_id = None
        sds_bytes = None
        if sds_files:
            sds_file_id = sds_files[0]["id"]
            sds_bytes = drive_client.download_file(sds_file_id)
            sds_text = pdf_extractor.extract_text(sds_bytes, "SDS")
            logger.info(f"Extracted SDS: {len(sds_text.pages)} pages")

        # Download and extract text from TDS
        tds_text = None
        tds_file_id = None
        tds_bytes = None
        if tds_files:
            tds_file_id = tds_files[0]["id"]
            tds_bytes = drive_client.download_file(tds_file_id)
            tds_text = pdf_extractor.extract_text(tds_bytes, "TDS")
            logger.info(f"Extracted TDS: {len(tds_text.pages)} pages")

        # Extract structured data with Gemini
        logger.info("Calling Gemini for structured extraction...")
        extracted_data = gemini_client.extract_from_documents(
            sds_text,
            tds_text,
            product_name
        )

        # Validate
        validation_result = validator.validate(extracted_data, mode)

        # Create audit metadata
        duration = time.time() - start_time
        extraction_meta = AuditLogger.create_extraction_meta(
            product_name=product_name,
            gemini_model=settings.gemini_model,
            sds_file_id=sds_file_id,
            sds_bytes=sds_bytes,
            tds_file_id=tds_file_id,
            tds_bytes=tds_bytes,
            duration_seconds=duration
        )

        # Save audit trail
        date_folder = datetime.utcnow().strftime("%Y-%m-%d")
        file_ids = AuditLogger.save_audit_trail(
            drive_client,
            product_folder_id,
            date_folder,
            extraction_meta,
            extracted_data,
            validation_result
        )

        # Generate label if validation passed
        label_ids = None
        if validation_result.passed:
            logger.info("Validation passed, generating label...")
            svg_content = label_generator.generate_svg(extracted_data, mode)
            pdf_content = label_generator.generate_pdf(svg_content)

            svg_id, pdf_id = label_generator.save_label_files(
                drive_client,
                product_folder_id,
                date_folder,
                svg_content,
                pdf_content
            )

            # Save label report
            label_report = AuditLogger.create_label_report(
                product_name=product_name,
                mode=mode,
                template_used="default",
                validation_passed=True,
                svg_file_id=svg_id,
                pdf_file_id=pdf_id
            )

            report_id = AuditLogger.save_label_audit(
                drive_client,
                product_folder_id,
                date_folder,
                label_report
            )

            label_ids = {"svg": svg_id, "pdf": pdf_id, "report": report_id}

        return {
            "product_name": product_name,
            "mode": mode,
            "extraction_duration_seconds": duration,
            "validation_passed": validation_result.passed,
            "errors": [e.model_dump() for e in validation_result.errors],
            "warnings": [w.model_dump() for w in validation_result.warnings],
            "audit_files": file_ids,
            "label_files": label_ids,
            "extracted_data": extracted_data.model_dump(mode='json')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/labels/generate", response_model=GenerateLabelResponse)
@app.post("/api/generate-label", response_model=GenerateLabelResponse)
async def generate_label_v1(
    files: List[UploadFile] = File(...),
    product_name: str = Form(...),
    mode: LabelMode = Form(LabelMode.SHIPPED_DOT),
    size: LabelSize = Form(LabelSize.PAIL)
):
    """Phase 1 label generation endpoint with unified response payload."""
    temp_files: List[Path] = []

    try:
        cleaned_product_name = product_name.strip()
        if not cleaned_product_name or len(cleaned_product_name) < 2:
            raise HTTPException(status_code=400, detail="Product name is required")
        if len(cleaned_product_name) > 100:
            raise HTTPException(status_code=400, detail="Product name too long (max 100 chars)")

        sds_text = None
        tds_text = None

        for upload in files:
            if not upload.filename or not upload.filename.lower().endswith('.pdf'):
                continue

            content = await upload.read()
            temp_filename = f"{secrets.token_hex(8)}.pdf"
            temp_path = LABELS_DIR / temp_filename
            temp_path.write_bytes(content)
            temp_files.append(temp_path)

            doc_type = "SDS" if "sds" in upload.filename.lower() else "TDS"
            extracted = pdf_extractor.extract_text(content, doc_type)
            if doc_type == "SDS":
                sds_text = extracted
            else:
                tds_text = extracted

        if not sds_text and not tds_text:
            raise HTTPException(status_code=400, detail="No valid PDF files provided")

        extracted_data = gemini_client.extract_from_documents(sds_text, tds_text, cleaned_product_name)
        extracted_data.product.name = cleaned_product_name

        validation_result = validator.validate(extracted_data, mode.value)

        template_id = f"clearedge_{size.value}_v1"
        svg_content = label_generator.generate_svg(
            extracted_data,
            mode=mode.value,
            size=size.value,
            template_id=template_id
        )

        safe_product_name = re.sub(r'[^a-zA-Z0-9_-]', '', cleaned_product_name[:50])
        unique_id = uuid.uuid4().hex[:8]
        label_id = f"label_{safe_product_name}_{unique_id}"

        LABELS_DIR.mkdir(parents=True, exist_ok=True)
        pdf_content = label_generator.generate_pdf(svg_content)
        label_path = LABELS_DIR / f"{label_id}.pdf"
        label_path.write_bytes(pdf_content)

        download_url = f"/api/v1/labels/{label_id}/download" if validation_result.passed else None

        metadata = {
            "label_id": label_id,
            "product_name": cleaned_product_name,
            "mode": mode.value,
            "size": size.value,
            "created_at": datetime.utcnow().isoformat(),
            "validation_passed": validation_result.passed,
            "warnings": [w.model_dump() for w in validation_result.warnings],
            "errors": [e.model_dump() for e in validation_result.errors],
            "download_url": download_url,
            "status": "approved" if validation_result.passed else "blocked",
            "override_approved": False,
            "override_reason": None,
            "override_approver": None,
            "override_timestamp": None,
        }
        label_metadata_store[label_id] = metadata

        _save_label_metadata_store()

        return {
            "label_id": label_id,
            "extracted": extracted_data.model_dump(mode='json'),
            "validation": {
                "passed": validation_result.passed,
                "warnings": metadata["warnings"],
                "errors": metadata["errors"],
            },
            "label": {
                "mode": mode.value,
                "size": size.value,
                "download_url": metadata["download_url"],
            },
            "warnings": metadata["warnings"],
            "errors": metadata["errors"],
            "audit": {
                "created_at": metadata["created_at"],
                "phase": "phase_1"
            },
            "success": True
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"INVALID_DATA: {exc}")
    except Exception as exc:
        logger.error(f"Label generation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="LABEL_GENERATION_FAILED")
    finally:
        for temp_file in temp_files:
            temp_file.unlink(missing_ok=True)


@app.get("/api/v1/labels/{label_id}")
async def get_label_metadata_v1(label_id: str):
    """Fetch label metadata for UI rendering and status checks."""
    metadata = label_metadata_store.get(label_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Label not found")
    return metadata




@app.post("/api/v1/labels/{label_id}/override-approval")
async def override_label_approval(label_id: str, request: OverrideApprovalRequest):
    """Approve a compliance-blocked label with required reason logging."""
    metadata = label_metadata_store.get(label_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Label not found")

    if metadata.get("validation_passed"):
        return {
            "label_id": label_id,
            "status": "already_approved",
            "download_url": metadata.get("download_url")
        }

    label_path = LABELS_DIR / f"{label_id}.pdf"
    if not label_path.exists():
        raise HTTPException(status_code=404, detail="Label artifact not found for override")

    metadata["override_approved"] = True
    metadata["override_reason"] = request.reason.strip()
    metadata["override_approver"] = request.approver.strip()
    metadata["override_timestamp"] = datetime.utcnow().isoformat()
    metadata["status"] = "override_approved"
    metadata["download_url"] = f"/api/v1/labels/{label_id}/download"
    label_metadata_store[label_id] = metadata
    _save_label_metadata_store()

    return {
        "label_id": label_id,
        "status": metadata["status"],
        "override_approved": True,
        "download_url": metadata["download_url"]
    }

@app.get("/api/v1/labels/{label_id}/download")
@app.get("/api/download-label/{label_id}")
async def download_label_v1(label_id: str):
    """Download generated label PDF with path traversal protection."""
    metadata = label_metadata_store.get(label_id)
    if metadata and not metadata.get("validation_passed") and not metadata.get("override_approved"):
        raise HTTPException(
            status_code=403,
            detail="DOWNLOAD_BLOCKED_VALIDATION_FAILED"
        )
    safe_id = re.sub(r'[^a-zA-Z0-9_-]', '', label_id)
    if not safe_id or safe_id != label_id:
        raise HTTPException(status_code=400, detail="Invalid label ID")
    if len(safe_id) > 100:
        raise HTTPException(status_code=400, detail="Label ID too long")

    label_path = LABELS_DIR / f"{safe_id}.pdf"
    try:
        label_path_resolved = label_path.resolve()
        labels_dir_resolved = LABELS_DIR.resolve()
        if not str(label_path_resolved).startswith(str(labels_dir_resolved)):
            raise HTTPException(status_code=403, detail="Access denied")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")

    if not label_path.exists():
        raise HTTPException(status_code=404, detail="Label not found")

    return FileResponse(label_path, media_type="application/pdf", filename=f"{safe_id}.pdf")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(settings.env == "development")
    )
