"""Filesystem-backed label artifact and metadata helpers."""

import json
import re
from pathlib import Path


def metadata_file(labels_dir: Path) -> Path:
    """Return the metadata file path for a label artifact directory."""
    labels_dir.mkdir(parents=True, exist_ok=True)
    return labels_dir / "label_metadata_store.json"


def load_metadata_store(labels_dir: Path) -> dict:
    """Load label metadata from disk if available."""
    path = metadata_file(labels_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_metadata_store(labels_dir: Path, store: dict) -> None:
    """Persist label metadata to disk."""
    metadata_file(labels_dir).write_text(json.dumps(store))


def safe_label_id(label_id: str) -> str:
    """Validate a public label id before reading from runtime storage."""
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", label_id)
    if not safe_id or safe_id != label_id:
        raise ValueError("Invalid label ID")
    if len(safe_id) > 100:
        raise ValueError("Label ID too long")
    return safe_id
