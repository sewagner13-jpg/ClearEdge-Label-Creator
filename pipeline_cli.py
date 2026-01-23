#!/usr/bin/env python3
"""
Command-line interface for the CLEAR EDGE Product Label Pipeline.
Provides batch operations and testing capabilities.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from app.config import settings
from app.drive_client import DriveClient
from app.pdf_extract import PDFExtractor
from app.gemini_client import GeminiClient
from app.validator import ComplianceValidator
from app.audit import AuditLogger
from app.web_retrieval import WebRetriever
from app.label_stub import LabelGenerator

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

console = Console()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """CLEAR EDGE Product Label Pipeline CLI."""
    pass


@cli.command()
def scan_drive():
    """Scan Shared Drive and list all products."""
    try:
        console.print("\n[bold cyan]Scanning Shared Drive...[/bold cyan]\n")

        drive_client = DriveClient()
        products = drive_client.list_all_products()

        if not products:
            console.print("[yellow]No products found.[/yellow]")
            return

        table = Table(title="Products in Shared Drive")
        table.add_column("Product Name", style="cyan")
        table.add_column("Count", style="green")

        for idx, product in enumerate(products, 1):
            table.add_row(product, str(idx))

        console.print(table)
        console.print(f"\n[green]Total: {len(products)} products[/green]\n")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


@cli.command()
@click.option("--product", required=True, help="Product name")
@click.option("--url", required=True, help="PDF URL to download")
@click.option("--doc-type", type=click.Choice(["SDS", "TDS"]), default="SDS", help="Document type")
@click.option("--approve", is_flag=True, help="Approve download (required)")
def ingest_url(product: str, url: str, doc_type: str, approve: bool):
    """Download PDF from URL and upload to Drive."""
    try:
        console.print(f"\n[bold cyan]Ingesting {doc_type} from URL...[/bold cyan]\n")

        if not approve:
            console.print("[bold red]Error:[/bold red] Must use --approve flag to confirm download")
            console.print(f"URL: {url}")
            sys.exit(1)

        # Initialize clients
        drive_client = DriveClient()
        web_retriever = WebRetriever()

        # Validate URL
        console.print(f"Validating URL: {url}")
        validation = web_retriever.validate_url(url)

        if not validation["domain_allowed"]:
            console.print(f"[bold red]Error:[/bold red] {validation['error']}")
            sys.exit(1)

        if not validation["is_pdf"]:
            console.print(f"[yellow]Warning:[/yellow] {validation['error']}")

        # Download
        console.print("Downloading...")
        pdf_bytes = web_retriever.download_document(url, user_approved=True)
        console.print(f"Downloaded {len(pdf_bytes)} bytes")

        # Find or create product folder
        product_folder_id = drive_client.find_product_folder(product)
        if not product_folder_id:
            console.print(f"Creating product folder: {product}")
            product_folder_id = drive_client.create_product_folder(product)

        # Upload
        folder_id = drive_client.find_subfolder(product_folder_id, doc_type)
        filename = f"{product}_{doc_type}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"

        file_id = drive_client.upload_file(
            pdf_bytes,
            filename,
            folder_id,
            "application/pdf"
        )

        file_hash = AuditLogger.compute_sha256(pdf_bytes)

        console.print(Panel(
            f"[green]✓[/green] Successfully uploaded\n\n"
            f"Product: {product}\n"
            f"File ID: {file_id}\n"
            f"Filename: {filename}\n"
            f"SHA-256: {file_hash[:16]}...",
            title="Upload Complete",
            border_style="green"
        ))

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.exception("Ingestion failed")
        sys.exit(1)


@cli.command()
@click.option("--product", required=True, help="Product name")
@click.option("--mode", type=click.Choice(["workplace", "shipped_dot"]), default="shipped_dot")
@click.option("--reextract", is_flag=True, help="Force re-extraction even if data exists")
def extract(product: str, mode: str, reextract: bool):
    """Extract structured data from SDS/TDS PDFs."""
    try:
        import time

        console.print(f"\n[bold cyan]Extracting data for: {product}[/bold cyan]\n")
        console.print(f"Mode: {mode}\n")

        start_time = time.time()

        # Initialize clients
        drive_client = DriveClient()
        pdf_extractor = PDFExtractor()
        gemini_client = GeminiClient()
        validator_client = ComplianceValidator()
        label_gen = LabelGenerator()

        # Find product
        product_folder_id = drive_client.find_product_folder(product)
        if not product_folder_id:
            console.print(f"[bold red]Error:[/bold red] Product '{product}' not found")
            console.print("Use 'pipeline-cli scan-drive' to see available products")
            sys.exit(1)

        # Get PDFs
        console.print("Scanning for PDFs...")
        sds_folder_id = drive_client.find_subfolder(product_folder_id, "SDS")
        tds_folder_id = drive_client.find_subfolder(product_folder_id, "TDS")

        sds_files = drive_client.list_files_in_folder(sds_folder_id, "application/pdf") if sds_folder_id else []
        tds_files = drive_client.list_files_in_folder(tds_folder_id, "application/pdf") if tds_folder_id else []

        if not sds_files and not tds_files:
            console.print("[bold red]Error:[/bold red] No SDS or TDS PDFs found")
            sys.exit(1)

        console.print(f"Found: {len(sds_files)} SDS, {len(tds_files)} TDS")

        # Extract text
        sds_text = None
        sds_file_id = None
        sds_bytes = None

        if sds_files:
            console.print("\n[cyan]Extracting text from SDS...[/cyan]")
            sds_file_id = sds_files[0]["id"]
            sds_bytes = drive_client.download_file(sds_file_id)
            sds_text = pdf_extractor.extract_text(sds_bytes, "SDS")
            console.print(f"  Pages: {len(sds_text.pages)}")
            console.print(f"  Method: {sds_text.method_used}")

        tds_text = None
        tds_file_id = None
        tds_bytes = None

        if tds_files:
            console.print("\n[cyan]Extracting text from TDS...[/cyan]")
            tds_file_id = tds_files[0]["id"]
            tds_bytes = drive_client.download_file(tds_file_id)
            tds_text = pdf_extractor.extract_text(tds_bytes, "TDS")
            console.print(f"  Pages: {len(tds_text.pages)}")
            console.print(f"  Method: {tds_text.method_used}")

        # Call Gemini
        console.print("\n[cyan]Calling Gemini for structured extraction...[/cyan]")
        extracted_data = gemini_client.extract_from_documents(sds_text, tds_text, product)

        console.print(f"[green]✓[/green] Extraction complete")
        console.print(f"  Signal word: {extracted_data.ghs.signal_word or 'None'}")
        console.print(f"  Pictograms: {len(extracted_data.ghs.pictograms)}")
        console.print(f"  Hazard statements: {len(extracted_data.ghs.hazard_statements)}")
        console.print(f"  UN number: {extracted_data.transport.un_number or 'None'}")

        # Validate
        console.print(f"\n[cyan]Validating for {mode} compliance...[/cyan]")
        validation_result = validator_client.validate(extracted_data, mode)

        if validation_result.passed:
            console.print("[green]✓ Validation PASSED[/green]")
        else:
            console.print("[red]✗ Validation FAILED[/red]")

        if validation_result.errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in validation_result.errors:
                console.print(f"  • {error.field}: {error.message}")

        if validation_result.warnings:
            console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for warning in validation_result.warnings:
                console.print(f"  • {warning.field}: {warning.message}")

        # Save audit trail
        console.print("\n[cyan]Saving audit trail...[/cyan]")
        duration = time.time() - start_time

        extraction_meta = AuditLogger.create_extraction_meta(
            product_name=product,
            gemini_model=settings.gemini_model,
            sds_file_id=sds_file_id,
            sds_bytes=sds_bytes,
            tds_file_id=tds_file_id,
            tds_bytes=tds_bytes,
            duration_seconds=duration
        )

        date_folder = datetime.utcnow().strftime("%Y-%m-%d")
        file_ids = AuditLogger.save_audit_trail(
            drive_client,
            product_folder_id,
            date_folder,
            extraction_meta,
            extracted_data,
            validation_result
        )

        console.print(f"[green]✓[/green] Saved to: Extracted/{date_folder}/")

        # Generate label if passed
        if validation_result.passed:
            console.print("\n[cyan]Generating label...[/cyan]")

            svg_content = label_gen.generate_svg(extracted_data, mode)
            pdf_content = label_gen.generate_pdf(svg_content)

            svg_id, pdf_id = label_gen.save_label_files(
                drive_client,
                product_folder_id,
                date_folder,
                svg_content,
                pdf_content
            )

            label_report = AuditLogger.create_label_report(
                product_name=product,
                mode=mode,
                template_used="default",
                validation_passed=True,
                svg_file_id=svg_id,
                pdf_file_id=pdf_id
            )

            AuditLogger.save_label_audit(drive_client, product_folder_id, date_folder, label_report)

            console.print(f"[green]✓[/green] Label saved to: Labels/{date_folder}/")

        # Summary
        console.print(Panel(
            f"[bold]Extraction Summary[/bold]\n\n"
            f"Product: {product}\n"
            f"Duration: {duration:.2f}s\n"
            f"Validation: {'PASSED' if validation_result.passed else 'FAILED'}\n"
            f"Errors: {len(validation_result.errors)}\n"
            f"Warnings: {len(validation_result.warnings)}",
            border_style="green" if validation_result.passed else "red"
        ))

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        logger.exception("Extraction failed")
        sys.exit(1)


@cli.command()
@click.option("--product", required=True, help="Product name")
def info(product: str):
    """Show product information and available data."""
    try:
        console.print(f"\n[bold cyan]Product Information: {product}[/bold cyan]\n")

        drive_client = DriveClient()

        # Find product
        product_folder_id = drive_client.find_product_folder(product)
        if not product_folder_id:
            console.print(f"[bold red]Error:[/bold red] Product '{product}' not found")
            sys.exit(1)

        # Check each folder
        folders = ["SDS", "TDS", "Extracted", "Labels"]
        info_table = Table(title=f"Product: {product}")
        info_table.add_column("Folder", style="cyan")
        info_table.add_column("Files", style="green")

        for folder_name in folders:
            folder_id = drive_client.find_subfolder(product_folder_id, folder_name)
            if folder_id:
                files = drive_client.list_files_in_folder(folder_id)
                info_table.add_row(folder_name, str(len(files)))
            else:
                info_table.add_row(folder_name, "0")

        console.print(info_table)
        console.print(f"\nFolder ID: {product_folder_id}\n")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
