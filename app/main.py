"""
FastAPI application for the CLEAR EDGE Product Label Pipeline.
Provides REST API endpoints for all pipeline operations.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import csv
import io
import os

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

from .config import settings
from .pdf_extract import PDFExtractor
from .openai_client import OpenAIClient
from .validator import ComplianceValidator
from .web_retrieval import WebRetriever
from .label_stub import LabelGenerator
from .agentcore_client import AgentCoreClient
from .api_models import (
    CorrectionRequest,
    GenerateLabelResponse,
    LabelMode,
    LabelSize,
    OverrideApprovalRequest,
)
from .canva_export import (
    canva_urls,
)
from .label_pipeline import LabelPipeline, LabelPipelineError
from .label_storage import (
    load_metadata_store,
    metadata_file,
    safe_label_id,
    save_metadata_store,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Shared clients
pdf_extractor: Optional[PDFExtractor] = None
openai_client: Optional[OpenAIClient] = None
validator: Optional[ComplianceValidator] = None
web_retriever: Optional[WebRetriever] = None
label_generator: Optional[LabelGenerator] = None
agentcore_client: Optional[AgentCoreClient] = None
startup_errors: Dict[str, str] = {}


DEFAULT_DATA_ROOT = Path(os.getenv("CLEAREDGE_DATA_DIR", str(Path.cwd() / "runtime_data")))
LABELS_DIR = DEFAULT_DATA_ROOT / "labels"
LABELS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory metadata store for Phase 1 API reads
label_metadata_store: Dict[str, dict] = {}


def _metadata_file() -> Path:
    """Return current metadata file path."""
    return metadata_file(LABELS_DIR)


def _load_label_metadata_store() -> None:
    """Load metadata store from disk if available."""
    global label_metadata_store
    try:
        label_metadata_store = load_metadata_store(LABELS_DIR)
    except Exception as exc:
        logger.warning(f"Unable to load label metadata store: {exc}")
        label_metadata_store = {}


def _save_label_metadata_store() -> None:
    """Persist metadata store to disk for restarts."""
    save_metadata_store(LABELS_DIR, label_metadata_store)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup shared resources."""
    global pdf_extractor, openai_client, validator, web_retriever, label_generator, agentcore_client, startup_errors

    logger.info("Initializing CLEAR EDGE Label Pipeline...")
    startup_errors = {}

    try:
        pdf_extractor = PDFExtractor()
        if settings.openai_api_key:
            openai_client = OpenAIClient()
        else:
            openai_client = None
            startup_errors["openai_client"] = "OPENAI_API_KEY is not configured"
        validator = ComplianceValidator()
        web_retriever = WebRetriever()
        label_generator = LabelGenerator()
        if settings.agentcore_enabled:
            try:
                agentcore_client = AgentCoreClient()
            except Exception as exc:
                agentcore_client = None
                startup_errors["agentcore_client"] = str(exc)
        else:
            agentcore_client = None
        _load_label_metadata_store()

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


def _health_payload() -> dict:
    """Shared liveness payload."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "ai_provider": "openai",
        "openai_model": settings.openai_model,
    }


def _readiness_payload() -> dict:
    """Dependency-oriented readiness payload for Phase 0 diagnostics."""
    required_checks = {
        "pdf_extractor_initialized": pdf_extractor is not None,
        "openai_client_initialized": openai_client is not None,
        "validator_initialized": validator is not None,
        "web_retriever_initialized": web_retriever is not None,
        "label_generator_initialized": label_generator is not None,
        "openai_api_key_present": bool(settings.openai_api_key),
    }
    agentcore_checks = {
        "agentcore_enabled": settings.agentcore_enabled,
        "agentcore_runtime_configured": bool(settings.agentcore_runtime_arn),
        "agentcore_client_initialized": agentcore_client is not None if settings.agentcore_enabled else True,
    }
    checks = {**required_checks, **agentcore_checks}
    agentcore_ready = True
    if settings.agentcore_enabled:
        agentcore_ready = (
            agentcore_checks["agentcore_runtime_configured"]
            and agentcore_checks["agentcore_client_initialized"]
        )
    status = "ready" if all(required_checks.values()) and agentcore_ready else "degraded"
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "startup_errors": startup_errors,
    }


def _safe_label_id(label_id: str) -> str:
    """Validate a public label id and convert validation failures to HTTP errors."""
    try:
        return safe_label_id(label_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _get_exportable_label(label_id: str) -> tuple[str, dict]:
    """Fetch metadata and enforce the same approval gate as PDF downloads."""
    safe_id = _safe_label_id(label_id)
    metadata = label_metadata_store.get(safe_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Label not found")
    if not metadata.get("validation_passed") and not metadata.get("override_approved"):
        raise HTTPException(status_code=403, detail="CANVA_EXPORT_BLOCKED_VALIDATION_FAILED")
    if not metadata.get("canva_export"):
        raise HTTPException(status_code=404, detail="Canva export data not found")
    return safe_id, metadata


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


@app.post("/api/v1/labels/generate", response_model=GenerateLabelResponse)
@app.post("/api/generate-label", response_model=GenerateLabelResponse)
async def generate_label_v1(
    files: List[UploadFile] = File(...),
    product_name: str = Form(...),
    mode: LabelMode = Form(LabelMode.SHIPPED_DOT),
    size: LabelSize = Form(LabelSize.PAIL),
    lot_number: Optional[str] = Form(None),
    expiration_date: Optional[str] = Form(None),
    fill_amount: Optional[str] = Form(None),
    manufacture_date: Optional[str] = Form(None),
    ghs_pictograms: Optional[str] = Form(None)
):
    """Phase 1 label generation endpoint with unified response payload."""
    try:
        pipeline = LabelPipeline(
            pdf_extractor=pdf_extractor,
            openai_client=openai_client,
            validator=validator,
            label_generator=label_generator,
            agentcore_client=agentcore_client,
            labels_dir=LABELS_DIR,
            metadata_store=label_metadata_store,
            save_metadata_store=_save_label_metadata_store,
        )
        return await pipeline.generate_label_from_uploads(
            files=files,
            product_name=product_name,
            mode=mode.value,
            size=size.value,
            lot_number=lot_number,
            expiration_date=expiration_date,
            fill_amount=fill_amount,
            manufacture_date=manufacture_date,
            ghs_pictograms=ghs_pictograms,
        )
    except HTTPException:
        raise
    except LabelPipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"INVALID_DATA: {exc}")
    except Exception as exc:
        logger.error(f"Label generation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="LABEL_GENERATION_FAILED")


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
    metadata.update(canva_urls(label_id, True))
    metadata["download"] = {
        "available": True,
        "url": metadata["download_url"],
        "reason": None,
    }
    if metadata.get("canva_export"):
        metadata["canva_export"]["validation_status"] = metadata["status"]
        metadata["canva_export"]["override_approved"] = "True"
        metadata["canva_export"]["override_approver"] = metadata["override_approver"]
        metadata["canva_export"]["override_reason"] = metadata["override_reason"]
    label_metadata_store[label_id] = metadata
    _save_label_metadata_store()

    return {
        "label_id": label_id,
        "status": metadata["status"],
        "override_approved": True,
        "download_url": metadata["download_url"],
        "canva_csv_url": metadata.get("canva_csv_url"),
        "canva_json_url": metadata.get("canva_json_url"),
    }


@app.patch("/api/v1/labels/{label_id}/corrections", response_model=GenerateLabelResponse)
async def correct_label_fields(label_id: str, request: CorrectionRequest):
    """Apply operator corrections, rerender, and rerun validation."""
    try:
        pipeline = LabelPipeline(
            pdf_extractor=pdf_extractor,
            openai_client=openai_client,
            validator=validator,
            label_generator=label_generator,
            agentcore_client=agentcore_client,
            labels_dir=LABELS_DIR,
            metadata_store=label_metadata_store,
            save_metadata_store=_save_label_metadata_store,
        )
        return pipeline.apply_corrections(label_id, request)
    except LabelPipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"INVALID_DATA: {exc}")


@app.get("/api/v1/labels/{label_id}/canva-export.json")
async def canva_export_json(label_id: str):
    """Return flat label data for manual Canva template entry."""
    safe_id, metadata = _get_exportable_label(label_id)
    return {
        "label_id": safe_id,
        "canva_bulk_create": metadata["canva_export"],
    }


@app.get("/api/v1/labels/{label_id}/canva-export.csv")
async def canva_export_csv(label_id: str):
    """Return a one-row CSV that can be imported into Canva Bulk Create."""
    safe_id, metadata = _get_exportable_label(label_id)
    output = io.StringIO()
    fieldnames = list(metadata["canva_export"].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow(metadata["canva_export"])
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_id}-canva-bulk-create.csv"'
        },
    )


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
    safe_id = _safe_label_id(label_id)

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
