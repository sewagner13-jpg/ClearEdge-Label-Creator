"""
Google Drive client with Shared Drive support.
Handles all Drive API operations with proper Shared Drive parameters.
"""

import io
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from googleapiclient.errors import HttpError

from .config import settings

logger = logging.getLogger(__name__)


class DriveClient:
    """Google Drive client with Shared Drive support."""

    SCOPES = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file'
    ]

    def __init__(self):
        """Initialize Drive client with service account credentials."""
        self.root_folder_id = settings.root_folder_id
        self.shared_drive_id = settings.shared_drive_id
        self.root_folder_name = settings.root_folder_name
        self.service = self._build_service()

    def _build_service(self):
        """Build Google Drive API service."""
        try:
            # Support multiple authentication methods
            if settings.google_service_account_json:
                # Cloud Run: credentials from Secret Manager as JSON string
                logger.info("Loading service account from JSON string (production)")
                service_account_info = json.loads(settings.google_service_account_json)
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=self.SCOPES
                )
            elif settings.google_service_account_file:
                # Local: credentials from file
                logger.info("Loading service account from file (development)")
                credentials = service_account.Credentials.from_service_account_file(
                    settings.google_service_account_file,
                    scopes=self.SCOPES
                )
            else:
                # Cloud Run with Application Default Credentials (no keys needed)
                logger.info("Using Application Default Credentials (Cloud Run default service account)")
                credentials, project = google.auth.default(scopes=self.SCOPES)
                logger.info(f"Authenticated with project: {project}")

            return build('drive', 'v3', credentials=credentials)
        except Exception as e:
            logger.error(f"Failed to build Drive service: {e}")
            raise

    def _get_root_folder(self) -> str:
        """Get the root 'Product Labels' folder ID."""
        logger.info(f"Using root folder ID: {self.root_folder_id}")
        return self.root_folder_id

    def find_product_folder(self, product_name: str) -> Optional[str]:
        """Find product folder by exact name match. Returns folder ID or None."""
        try:
            root_id = self._get_root_folder()
            query = (
                f"name='{product_name}' and "
                f"'{root_id}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"trashed=false"
            )

            # Build list parameters - include Shared Drive params only if configured
            list_params = {
                'q': query,
                'includeItemsFromAllDrives': True,
                'supportsAllDrives': True,
                'fields': 'files(id, name)'
            }

            if self.shared_drive_id:
                list_params['corpora'] = 'drive'
                list_params['driveId'] = self.shared_drive_id

            results = self.service.files().list(**list_params).execute()

            files = results.get('files', [])
            if not files:
                return None

            if len(files) > 1:
                logger.warning(f"Multiple folders found for product '{product_name}'")

            return files[0]['id']

        except HttpError as e:
            logger.error(f"Error finding product folder: {e}")
            raise

    def create_product_folder(self, product_name: str) -> str:
        """Create product folder structure. Returns product folder ID."""
        try:
            root_id = self._get_root_folder()

            # Check if already exists
            existing = self.find_product_folder(product_name)
            if existing:
                logger.info(f"Product folder already exists: {product_name}")
                return existing

            # Create product folder
            product_metadata = {
                'name': product_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [root_id]
            }
            product_folder = self.service.files().create(
                body=product_metadata,
                supportsAllDrives=True,
                fields='id'
            ).execute()
            product_id = product_folder['id']
            logger.info(f"Created product folder: {product_name} ({product_id})")

            # Create subfolders: SDS, TDS, Extracted, Labels
            for subfolder_name in ['SDS', 'TDS', 'Extracted', 'Labels']:
                subfolder_metadata = {
                    'name': subfolder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [product_id]
                }
                self.service.files().create(
                    body=subfolder_metadata,
                    supportsAllDrives=True,
                    fields='id'
                ).execute()
                logger.info(f"Created subfolder: {subfolder_name}")

            return product_id

        except HttpError as e:
            logger.error(f"Error creating product folder: {e}")
            raise

    def find_subfolder(self, parent_id: str, subfolder_name: str) -> Optional[str]:
        """Find subfolder by name within parent. Returns folder ID or None."""
        try:
            query = (
                f"name='{subfolder_name}' and "
                f"'{parent_id}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"trashed=false"
            )

            # Build list parameters - include Shared Drive params only if configured
            list_params = {
                'q': query,
                'includeItemsFromAllDrives': True,
                'supportsAllDrives': True,
                'fields': 'files(id, name)'
            }

            if self.shared_drive_id:
                list_params['corpora'] = 'drive'
                list_params['driveId'] = self.shared_drive_id

            results = self.service.files().list(**list_params).execute()

            files = results.get('files', [])
            return files[0]['id'] if files else None

        except HttpError as e:
            logger.error(f"Error finding subfolder: {e}")
            raise

    def create_dated_folder(self, parent_id: str, date_str: Optional[str] = None) -> str:
        """Create dated folder (YYYY-MM-DD) within parent. Returns folder ID."""
        if date_str is None:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        try:
            # Check if exists
            existing = self.find_subfolder(parent_id, date_str)
            if existing:
                return existing

            metadata = {
                'name': date_str,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            folder = self.service.files().create(
                body=metadata,
                supportsAllDrives=True,
                fields='id'
            ).execute()
            return folder['id']

        except HttpError as e:
            logger.error(f"Error creating dated folder: {e}")
            raise

    def upload_file(
        self,
        file_content: bytes,
        filename: str,
        parent_id: str,
        mime_type: str = 'application/octet-stream'
    ) -> str:
        """Upload file to Drive. Returns file ID."""
        try:
            file_metadata = {
                'name': filename,
                'parents': [parent_id]
            }
            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=mime_type,
                resumable=True
            )
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                supportsAllDrives=True,
                fields='id'
            ).execute()
            logger.info(f"Uploaded file: {filename} ({file['id']})")
            return file['id']

        except HttpError as e:
            logger.error(f"Error uploading file: {e}")
            raise

    def upload_json(
        self,
        data: Dict[Any, Any],
        filename: str,
        parent_id: str
    ) -> str:
        """Upload JSON data as file. Returns file ID."""
        json_bytes = json.dumps(data, indent=2, default=str).encode('utf-8')
        return self.upload_file(json_bytes, filename, parent_id, 'application/json')

    def download_file(self, file_id: str) -> bytes:
        """Download file content by ID."""
        try:
            request = self.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download progress: {int(status.progress() * 100)}%")

            return file_buffer.getvalue()

        except HttpError as e:
            logger.error(f"Error downloading file: {e}")
            raise

    def list_files_in_folder(
        self,
        folder_id: str,
        mime_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List files in folder. Optionally filter by MIME type."""
        try:
            query_parts = [
                f"'{folder_id}' in parents",
                "trashed=false"
            ]
            if mime_type:
                query_parts.append(f"mimeType='{mime_type}'")

            query = " and ".join(query_parts)

            # Build list parameters - include Shared Drive params only if configured
            list_params = {
                'q': query,
                'includeItemsFromAllDrives': True,
                'supportsAllDrives': True,
                'fields': 'files(id, name, mimeType, size, createdTime, modifiedTime)',
                'orderBy': 'modifiedTime desc'
            }

            if self.shared_drive_id:
                list_params['corpora'] = 'drive'
                list_params['driveId'] = self.shared_drive_id

            results = self.service.files().list(**list_params).execute()

            return results.get('files', [])

        except HttpError as e:
            logger.error(f"Error listing files: {e}")
            raise

    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get file metadata."""
        try:
            file = self.service.files().get(
                fileId=file_id,
                supportsAllDrives=True,
                fields='id, name, mimeType, size, createdTime, modifiedTime, md5Checksum'
            ).execute()
            return file

        except HttpError as e:
            logger.error(f"Error getting file metadata: {e}")
            raise

    def list_all_products(self) -> List[str]:
        """List all product folder names."""
        try:
            root_id = self._get_root_folder()
            query = (
                f"'{root_id}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"trashed=false"
            )

            # Build list parameters - include Shared Drive params only if configured
            list_params = {
                'q': query,
                'includeItemsFromAllDrives': True,
                'supportsAllDrives': True,
                'fields': 'files(name)',
                'orderBy': 'name'
            }

            if self.shared_drive_id:
                list_params['corpora'] = 'drive'
                list_params['driveId'] = self.shared_drive_id

            results = self.service.files().list(**list_params).execute()

            return [f['name'] for f in results.get('files', [])]

        except HttpError as e:
            logger.error(f"Error listing products: {e}")
            raise
