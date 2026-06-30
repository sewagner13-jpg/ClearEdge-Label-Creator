"""Filesystem-backed reusable company logo library."""

import base64
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


MAX_LOGO_FILE_SIZE_BYTES = 2 * 1024 * 1024

ALLOWED_LOGO_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/svg+xml": "svg",
    "image/webp": "webp",
}
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "svg", "webp"}


class LogoLibraryError(ValueError):
    """Raised when logo library input or lookup fails."""


class LogoLibrary:
    """Persist and retrieve company logos by stable IDs."""

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.root_dir / "manifest.json"

    def list_logos(self) -> list[dict]:
        """Return saved logos sorted by display name."""
        records = list(self._load_manifest().values())
        return sorted((self._public_record(record) for record in records), key=lambda item: item["name"].lower())

    def save_logo(self, *, name: str, filename: str, content_type: str, content: bytes) -> dict:
        """Validate and persist a logo image."""
        display_name = self._clean_name(name) or self._clean_name(Path(filename or "").stem)
        if not display_name:
            raise LogoLibraryError("LOGO_NAME_REQUIRED: Enter a company/logo name")

        extension = self._validate_logo_file(filename=filename, content_type=content_type, content=content)
        logo_id = self._new_logo_id(display_name)
        storage_filename = f"{logo_id}.{extension}"
        storage_path = self.root_dir / storage_filename
        storage_path.write_bytes(content)

        record = {
            "logo_id": logo_id,
            "name": display_name,
            "filename": Path(filename or storage_filename).name,
            "content_type": content_type,
            "extension": extension,
            "storage_filename": storage_filename,
            "size_bytes": len(content),
            "created_at": datetime.utcnow().isoformat(),
        }
        manifest = self._load_manifest()
        manifest[logo_id] = record
        self._save_manifest(manifest)
        return self._public_record(record)

    def get_logo(self, logo_id: str) -> dict:
        """Return a saved logo record by ID."""
        safe_id = self.safe_logo_id(logo_id)
        record = self._load_manifest().get(safe_id)
        if not record:
            raise LogoLibraryError("LOGO_NOT_FOUND: Saved logo was not found")
        path = self.logo_path(record)
        if not path.exists():
            raise LogoLibraryError("LOGO_FILE_MISSING: Saved logo image file is missing")
        return self._public_record(record)

    def logo_path(self, record: dict) -> Path:
        """Return the on-disk path for a public or internal logo record."""
        storage_filename = Path(record.get("storage_filename") or "").name
        if not storage_filename:
            raise LogoLibraryError("LOGO_FILE_MISSING: Saved logo image file is missing")
        path = (self.root_dir / storage_filename).resolve()
        root = self.root_dir.resolve()
        if not str(path).startswith(str(root)):
            raise LogoLibraryError("LOGO_ACCESS_DENIED: Invalid saved logo path")
        return path

    def logo_data_uri(self, logo_id: str) -> str:
        """Return a saved logo as a browser/SVG-safe data URI."""
        record = self.get_logo(logo_id)
        content = self.logo_path(record).read_bytes()
        encoded = base64.b64encode(content).decode("ascii")
        return f"data:{record['content_type']};base64,{encoded}"

    @staticmethod
    def safe_logo_id(logo_id: str) -> str:
        """Validate a public logo ID."""
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", logo_id or "")
        if not safe_id or safe_id != logo_id:
            raise LogoLibraryError("INVALID_LOGO_ID: Saved logo ID is invalid")
        return safe_id

    def _load_manifest(self) -> dict:
        if not self._manifest_path.exists():
            return {}
        try:
            loaded = json.loads(self._manifest_path.read_text())
        except json.JSONDecodeError as exc:
            raise LogoLibraryError("LOGO_LIBRARY_CORRUPT: Logo manifest is not valid JSON") from exc
        return loaded if isinstance(loaded, dict) else {}

    def _save_manifest(self, manifest: dict) -> None:
        temp_path = self._manifest_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        temp_path.replace(self._manifest_path)

    @classmethod
    def _validate_logo_file(cls, *, filename: str, content_type: str, content: bytes) -> str:
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if content_type not in ALLOWED_LOGO_CONTENT_TYPES or suffix not in ALLOWED_LOGO_EXTENSIONS:
            raise LogoLibraryError("UNSUPPORTED_LOGO_FILE_TYPE: Upload a PNG, JPG, SVG, or WebP logo image")
        if not content:
            raise LogoLibraryError("EMPTY_LOGO_FILE: Uploaded logo file is empty")
        if len(content) > MAX_LOGO_FILE_SIZE_BYTES:
            raise LogoLibraryError("LOGO_FILE_TOO_LARGE: Logo image must be 2 MB or smaller")
        return ALLOWED_LOGO_CONTENT_TYPES[content_type]

    @staticmethod
    def _clean_name(name: Optional[str]) -> str:
        return " ".join(str(name or "").strip().split())[:100]

    @classmethod
    def _new_logo_id(cls, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")[:40]
        return f"logo_{slug or 'company'}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _public_record(record: dict) -> dict:
        logo_id = record["logo_id"]
        return {
            "logo_id": logo_id,
            "name": record["name"],
            "filename": record.get("filename"),
            "content_type": record["content_type"],
            "size_bytes": record.get("size_bytes", 0),
            "created_at": record.get("created_at"),
            "image_url": f"/api/v1/logos/{logo_id}/image",
            "storage_filename": record.get("storage_filename"),
        }
