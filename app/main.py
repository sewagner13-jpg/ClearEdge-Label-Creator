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
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .pdf_extract import PDFExtractor
from .openai_client import OpenAIClient
from .validator import ComplianceValidator
from .web_retrieval import WebRetriever
from .label_stub import LabelGenerator
from .api_models import (
    AnalyzeDocumentsResponse,
    CorrectionRequest,
    GenerateLabelResponse,
    LabelOrientation,
    LabelMode,
    LabelSize,
    OverrideApprovalRequest,
    SalespersonCreateRequest,
)
from .canva_export import (
    canva_urls,
    canva_template_manifest,
)
from .label_pipeline import LabelPipeline, LabelPipelineError
from .logo_library import LogoLibrary, LogoLibraryError
from .salesperson_library import SalespersonLibrary, SalespersonLibraryError
from .dot_sticker_sheet import DotStickerSheetRenderer, DotStickerSheetUnavailable
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
logo_library: Optional[LogoLibrary] = None
salesperson_library: Optional[SalespersonLibrary] = None
startup_errors: Dict[str, str] = {}


DEFAULT_DATA_ROOT = Path(os.getenv("CLEAREDGE_DATA_DIR", str(Path.cwd() / "runtime_data")))
LABELS_DIR = DEFAULT_DATA_ROOT / "labels"
LOGOS_DIR = DEFAULT_DATA_ROOT / "logos"
SALESPEOPLE_DIR = DEFAULT_DATA_ROOT / "salespeople"
LABELS_DIR.mkdir(parents=True, exist_ok=True)
LOGOS_DIR.mkdir(parents=True, exist_ok=True)
SALESPEOPLE_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "netlify-frontend"

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
    global pdf_extractor, openai_client, validator, web_retriever, label_generator, logo_library, salesperson_library, startup_errors

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
        logo_library = LogoLibrary(LOGOS_DIR)
        salesperson_library = SalespersonLibrary(SALESPEOPLE_DIR)
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
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,null").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


def _health_payload() -> dict:
    """Shared liveness payload."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "ai_provider": "openai",
        "openai_model": settings.openai_model,
        "build": {
            "commit_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown"),
            "branch": os.getenv("RAILWAY_GIT_BRANCH", "unknown"),
        },
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
    source_review_checks = {
        "openai_review_enabled": settings.openai_review_enabled,
        "openai_review_client_initialized": openai_client is not None if settings.openai_review_enabled else True,
    }
    checks = {**required_checks, **source_review_checks}
    status = "ready" if all(required_checks.values()) and all(source_review_checks.values()) else "degraded"
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
    if not metadata.get("canva_export"):
        raise HTTPException(status_code=404, detail="Canva export data not found")
    return safe_id, metadata


def _get_logo_library() -> LogoLibrary:
    """Return a logo library bound to the current runtime logo directory."""
    global logo_library
    if logo_library is None or getattr(logo_library, "root_dir", None) != LOGOS_DIR:
        logo_library = LogoLibrary(LOGOS_DIR)
    return logo_library


def _get_salesperson_library() -> SalespersonLibrary:
    """Return a sales contact library bound to the current runtime directory."""
    global salesperson_library
    if salesperson_library is None or getattr(salesperson_library, "root_dir", None) != SALESPEOPLE_DIR:
        salesperson_library = SalespersonLibrary(SALESPEOPLE_DIR)
    return salesperson_library


def _safe_logo_id(logo_id: str) -> str:
    """Validate a public logo id and convert validation failures to HTTP errors."""
    try:
        return LogoLibrary.safe_logo_id(logo_id)
    except LogoLibraryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _build_label_pipeline() -> LabelPipeline:
    """Build the shared pipeline with the current application dependencies."""
    return LabelPipeline(
        pdf_extractor=pdf_extractor,
        openai_client=openai_client,
        validator=validator,
        label_generator=label_generator,
        logo_library=_get_logo_library(),
        salesperson_library=_get_salesperson_library(),
        labels_dir=LABELS_DIR,
        metadata_store=label_metadata_store,
        save_metadata_store=_save_label_metadata_store,
    )


# Endpoints

@app.get("/", include_in_schema=False)
async def root():
    """Send browser users to the local label creator UI when available."""
    if (FRONTEND_DIR / "index.html").exists():
        return RedirectResponse(url="/frontend/index.html")
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


@app.post("/api/v1/documents/analyze", response_model=AnalyzeDocumentsResponse)
async def analyze_documents(
    files: List[UploadFile] = File(...),
    product_name: Optional[str] = Form(None),
):
    """Parse uploaded SDS/TDS files without requiring shipment fields or rendering a label."""
    try:
        return await _build_label_pipeline().analyze_documents(
            files=files,
            product_name=product_name,
        )
    except LabelPipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"INVALID_DATA: {exc}")
    except Exception as exc:
        logger.error("Document analysis failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="DOCUMENT_ANALYSIS_FAILED")


@app.post("/api/v1/labels/generate", response_model=GenerateLabelResponse)
@app.post("/api/generate-label", response_model=GenerateLabelResponse)
async def generate_label_v1(
    files: List[UploadFile] = File(...),
    brand_logo: Optional[UploadFile] = File(None),
    brand_logo_id: Optional[str] = Form(None),
    save_brand_logo: bool = Form(False),
    brand_logo_name: Optional[str] = Form(None),
    product_name: str = Form(...),
    mode: LabelMode = Form(LabelMode.SHIPPED_DOT),
    size: LabelSize = Form(LabelSize.PAIL),
    orientation: LabelOrientation = Form(LabelOrientation.VERTICAL),
    lot_number: Optional[str] = Form(None),
    expiration_date: Optional[str] = Form(None),
    fill_amount: Optional[str] = Form(None),
    manufacture_date: Optional[str] = Form(None),
    ghs_pictograms: Optional[str] = Form(None),
    label_brand: Optional[str] = Form(None),
    show_clearedge_mark: bool = Form(True),
    supplier_name: Optional[str] = Form(None),
    supplier_address: Optional[str] = Form(None),
    supplier_phone: Optional[str] = Form(None),
    emergency_phone: Optional[str] = Form(None),
    transport_status: Optional[str] = Form(None),
    un_number: Optional[str] = Form(None),
    proper_shipping_name: Optional[str] = Form(None),
    hazard_class: Optional[str] = Form(None),
    packing_group: Optional[str] = Form(None),
    marine_pollutant: Optional[str] = Form(None),
    hazardous_substance: Optional[str] = Form(None),
    hazardous_waste: Optional[str] = Form(None),
    limited_quantity: Optional[str] = Form(None),
    subsidiary_hazard_classes: Optional[str] = Form(None),
    salesperson_id: Optional[str] = Form(None),
    salesperson_name: Optional[str] = Form(None),
    salesperson_email: Optional[str] = Form(None),
    salesperson_phone: Optional[str] = Form(None),
):
    """Phase 1 label generation endpoint with unified response payload."""
    try:
        pipeline = _build_label_pipeline()
        return await pipeline.generate_label_from_uploads(
            files=files,
            product_name=product_name,
            mode=mode.value,
            size=size.value,
            orientation=orientation.value,
            lot_number=lot_number,
            expiration_date=expiration_date,
            fill_amount=fill_amount,
            manufacture_date=manufacture_date,
            ghs_pictograms=ghs_pictograms,
            label_brand=label_brand,
            show_clearedge_mark=show_clearedge_mark,
            brand_logo=brand_logo,
            brand_logo_id=brand_logo_id,
            save_brand_logo=save_brand_logo,
            brand_logo_name=brand_logo_name,
            supplier_name=supplier_name,
            supplier_address=supplier_address,
            supplier_phone=supplier_phone,
            emergency_phone=emergency_phone,
            transport_status=transport_status,
            un_number=un_number,
            proper_shipping_name=proper_shipping_name,
            hazard_class=hazard_class,
            packing_group=packing_group,
            marine_pollutant=marine_pollutant,
            hazardous_substance=hazardous_substance,
            hazardous_waste=hazardous_waste,
            limited_quantity=limited_quantity,
            subsidiary_hazard_classes=subsidiary_hazard_classes,
            salesperson_id=salesperson_id,
            salesperson_name=salesperson_name,
            salesperson_email=salesperson_email,
            salesperson_phone=salesperson_phone,
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


@app.get("/api/v1/salespeople")
async def list_salespeople():
    """List reusable sales contacts."""
    return {"salespeople": _get_salesperson_library().list_salespeople()}


@app.post("/api/v1/salespeople")
async def create_salesperson(request: SalespersonCreateRequest):
    """Save a reusable sales contact for sample labels."""
    try:
        return _get_salesperson_library().create_salesperson(
            name=request.name,
            email=request.email,
            phone=request.phone,
        )
    except SalespersonLibraryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/v1/salespeople/{salesperson_id}")
async def delete_salesperson(salesperson_id: str):
    """Delete a reusable sales contact."""
    try:
        return {"deleted": _get_salesperson_library().delete_salesperson(salesperson_id)}
    except SalespersonLibraryError as exc:
        status_code = 404 if "NOT_FOUND" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.get("/api/v1/logos")
async def list_saved_logos():
    """List reusable company logos."""
    return {"logos": _get_logo_library().list_logos()}


@app.post("/api/v1/logos")
async def save_company_logo(
    logo: UploadFile = File(...),
    name: str = Form(...),
):
    """Save a reusable company logo for future custom labels."""
    content = await logo.read()
    try:
        return _get_logo_library().save_logo(
            name=name,
            filename=logo.filename or "",
            content_type=logo.content_type or "",
            content=content,
        )
    except LogoLibraryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/logos/{logo_id}/image")
async def get_company_logo_image(logo_id: str):
    """Return a saved logo image."""
    safe_id = _safe_logo_id(logo_id)
    try:
        record = _get_logo_library().get_logo(safe_id)
        return FileResponse(
            _get_logo_library().logo_path(record),
            media_type=record["content_type"],
            filename=record.get("filename") or f"{safe_id}.{record.get('extension', 'png')}",
        )
    except LogoLibraryError as exc:
        status_code = 404 if "NOT_FOUND" in str(exc) or "MISSING" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@app.get("/api/v1/canva/template-fields")
async def get_canva_template_fields():
    """Return the stable Canva Bulk Create field manifest."""
    return canva_template_manifest()


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
    dot_stickers = metadata.get("dot_stickers")
    if dot_stickers and metadata.get("dot_sticker_artifact_path"):
        sticker_path = Path(metadata["dot_sticker_artifact_path"])
        if sticker_path.exists():
            dot_stickers["available"] = True
            dot_stickers["url"] = f"/api/v1/labels/{label_id}/dot-stickers.pdf"
            dot_stickers["reason"] = None
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
        "dot_sticker_pdf_url": metadata.get("dot_stickers", {}).get("url"),
        "dot_stickers": metadata.get("dot_stickers"),
        "canva_csv_url": metadata.get("canva_csv_url"),
        "canva_json_url": metadata.get("canva_json_url"),
    }


@app.patch("/api/v1/labels/{label_id}/corrections", response_model=GenerateLabelResponse)
async def correct_label_fields(label_id: str, request: CorrectionRequest):
    """Apply operator corrections, rerender, and rerun validation."""
    try:
        pipeline = _build_label_pipeline()
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


@app.get("/api/v1/labels/{label_id}/preview.svg")
async def preview_label_svg(label_id: str):
    """Return the generated SVG label preview without bypassing PDF download gating."""
    safe_id = _safe_label_id(label_id)
    metadata = label_metadata_store.get(safe_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Label not found")

    preview_path = LABELS_DIR / f"{safe_id}.svg"
    try:
        preview_path_resolved = preview_path.resolve()
        labels_dir_resolved = LABELS_DIR.resolve()
        if not str(preview_path_resolved).startswith(str(labels_dir_resolved)):
            raise HTTPException(status_code=403, detail="Access denied")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")

    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="Label preview not found")

    return Response(
        preview_path.read_bytes(),
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'inline; filename="{safe_id}.svg"'},
    )


@app.get("/api/v1/labels/{label_id}/dot-stickers/preview-page-{page_number}.svg")
async def preview_dot_sticker_sheet_svg(label_id: str, page_number: int):
    """Return one DOT sticker sheet SVG page for in-app preview rendering."""
    safe_id = _safe_label_id(label_id)
    if page_number < 1:
        raise HTTPException(status_code=400, detail="Invalid DOT sticker preview page")

    metadata = label_metadata_store.get(safe_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Label not found")

    dot_stickers = metadata.get("dot_stickers") or {}
    required_stickers = dot_stickers.get("stickers") or []
    if not dot_stickers.get("available") or not required_stickers:
        raise HTTPException(status_code=404, detail=dot_stickers.get("reason") or "DOT sticker preview not available")

    try:
        sticker_pages = DotStickerSheetRenderer().render_svg_pages(required_stickers)
    except DotStickerSheetUnavailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    page_index = page_number - 1
    if page_index >= len(sticker_pages):
        raise HTTPException(status_code=404, detail="DOT sticker preview page not found")

    return Response(
        sticker_pages[page_index].encode("utf-8"),
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": f'inline; filename="{safe_id}-dot-stickers-page-{page_number}.svg"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/v1/labels/{label_id}/download")
@app.get("/api/download-label/{label_id}")
async def download_label_v1(label_id: str):
    """Download generated label PDF with path traversal protection."""
    safe_id = _safe_label_id(label_id)
    metadata = label_metadata_store.get(safe_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Label not found")
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


@app.get("/api/v1/labels/{label_id}/dot-stickers.pdf")
async def download_dot_stickers_pdf_v1(label_id: str):
    """Download the separate DOT sticker sheet PDF with the same approval gate as labels."""
    safe_id = _safe_label_id(label_id)
    metadata = label_metadata_store.get(safe_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Label not found")
    dot_stickers = metadata.get("dot_stickers") or {}
    if not metadata.get("dot_sticker_artifact_path"):
        raise HTTPException(status_code=404, detail=dot_stickers.get("reason") or "DOT sticker PDF not available")

    sticker_path = Path(metadata["dot_sticker_artifact_path"])
    try:
        sticker_path_resolved = sticker_path.resolve()
        labels_dir_resolved = LABELS_DIR.resolve()
        if not str(sticker_path_resolved).startswith(str(labels_dir_resolved)):
            raise HTTPException(status_code=403, detail="Access denied")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")

    if not sticker_path.exists():
        raise HTTPException(status_code=404, detail="DOT sticker PDF not found")

    return FileResponse(
        sticker_path,
        media_type="application/pdf",
        filename=f"{safe_id}-dot-stickers.pdf",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(settings.env == "development")
    )
