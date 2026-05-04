from pathlib import Path

from app import main


def test_metadata_persists_across_reload(tmp_path):
    # Arrange isolated runtime storage
    main.LABELS_DIR = tmp_path / "labels"
    main.LABELS_DIR.mkdir(parents=True, exist_ok=True)

    label_id = "label_persist_001"
    main.label_metadata_store = {
        label_id: {
            "label_id": label_id,
            "status": "override_approved",
            "validation_passed": False,
            "override_approved": True,
            "override_reason": "Approved for controlled shipment",
            "override_approver": "QA Lead",
            "override_timestamp": "2026-05-04T00:00:00",
            "download_url": f"/api/v1/labels/{label_id}/download",
        }
    }

    # Act: persist then clear in-memory and reload
    main._save_label_metadata_store()
    main.label_metadata_store = {}
    main._load_label_metadata_store()

    # Assert lifecycle + override fields survive reload
    reloaded = main.label_metadata_store[label_id]
    assert reloaded["status"] == "override_approved"
    assert reloaded["override_approved"] is True
    assert reloaded["override_reason"] == "Approved for controlled shipment"
    assert reloaded["override_approver"] == "QA Lead"
    assert reloaded["download_url"].endswith(f"/{label_id}/download")

    # Assert file landed in expected runtime path
    metadata_file = main._metadata_file()
    assert metadata_file.exists()
    assert metadata_file.parent == main.LABELS_DIR
