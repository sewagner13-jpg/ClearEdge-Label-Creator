"""Filesystem-backed reusable sales contact library."""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


class SalespersonLibraryError(ValueError):
    """Raised when salesperson library input or lookup fails."""


class SalespersonLibrary:
    """Persist and retrieve reusable sales contacts by stable IDs."""

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.root_dir / "salespeople.json"

    def list_salespeople(self) -> list[dict]:
        """Return saved sales contacts sorted by name."""
        records = list(self._load_manifest().values())
        return sorted((self._public_record(record) for record in records), key=lambda item: item["name"].lower())

    def create_salesperson(self, *, name: str, email: Optional[str] = None, phone: Optional[str] = None) -> dict:
        """Validate and persist a reusable sales contact."""
        clean_name = self._clean_text(name)
        clean_email = self._clean_text(email)
        clean_phone = self._clean_text(phone)

        if not clean_name:
            raise SalespersonLibraryError("SALESPERSON_NAME_REQUIRED: Enter the sales contact name")
        if not clean_email and not clean_phone:
            raise SalespersonLibraryError("SALESPERSON_CONTACT_REQUIRED: Enter an email or phone number")

        salesperson_id = self._new_salesperson_id(clean_name)
        record = {
            "salesperson_id": salesperson_id,
            "name": clean_name,
            "email": clean_email,
            "phone": clean_phone,
            "created_at": datetime.utcnow().isoformat(),
        }
        manifest = self._load_manifest()
        manifest[salesperson_id] = record
        self._save_manifest(manifest)
        return self._public_record(record)

    def get_salesperson(self, salesperson_id: str) -> dict:
        """Return a saved sales contact by ID."""
        safe_id = self.safe_salesperson_id(salesperson_id)
        record = self._load_manifest().get(safe_id)
        if not record:
            raise SalespersonLibraryError("SALESPERSON_NOT_FOUND: Saved sales contact was not found")
        return self._public_record(record)

    def delete_salesperson(self, salesperson_id: str) -> bool:
        """Delete a saved sales contact."""
        safe_id = self.safe_salesperson_id(salesperson_id)
        manifest = self._load_manifest()
        if safe_id not in manifest:
            raise SalespersonLibraryError("SALESPERSON_NOT_FOUND: Saved sales contact was not found")
        del manifest[safe_id]
        self._save_manifest(manifest)
        return True

    @staticmethod
    def safe_salesperson_id(salesperson_id: str) -> str:
        """Validate a public sales contact ID."""
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", salesperson_id or "")
        if not safe_id or safe_id != salesperson_id:
            raise SalespersonLibraryError("INVALID_SALESPERSON_ID: Saved sales contact ID is invalid")
        return safe_id

    def _load_manifest(self) -> dict:
        if not self._manifest_path.exists():
            return {}
        try:
            loaded = json.loads(self._manifest_path.read_text())
        except json.JSONDecodeError as exc:
            raise SalespersonLibraryError("SALESPERSON_LIBRARY_CORRUPT: Sales contact manifest is not valid JSON") from exc
        return loaded if isinstance(loaded, dict) else {}

    def _save_manifest(self, manifest: dict) -> None:
        temp_path = self._manifest_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        temp_path.replace(self._manifest_path)

    @staticmethod
    def _clean_text(value: Optional[str], max_length: int = 120) -> str:
        return " ".join(str(value or "").strip().split())[:max_length]

    @classmethod
    def _new_salesperson_id(cls, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")[:40]
        return f"sales_{slug or 'contact'}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _public_record(record: dict) -> dict:
        return {
            "salesperson_id": record["salesperson_id"],
            "name": record["name"],
            "email": record.get("email") or "",
            "phone": record.get("phone") or "",
            "created_at": record.get("created_at"),
        }
