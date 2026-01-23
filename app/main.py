"""
FastAPI application for the CLEAR EDGE Product Label Pipeline.
Provides REST API endpoints for all pipeline operations.
"""

import logging
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup shared resources."""
    global drive_client, pdf_extractor, gemini_client, validator, web_retriever, label_generator

    logger.info("Initializing CLEAR EDGE Label Pipeline...")

    try:
        drive_client = DriveClient()
        pdf_extractor = PDFExtractor()
        gemini_client = GeminiClient()
        validator = ComplianceValidator()
        web_retriever = WebRetriever()
        label_generator = LabelGenerator()

        logger.info("All clients initialized successfully")
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


# Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "gemini_model": settings.gemini_model,
        "shared_drive_id": settings.shared_drive_id
    }


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(settings.env == "development")
    )
