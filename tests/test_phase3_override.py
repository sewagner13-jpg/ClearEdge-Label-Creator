import asyncio

from app import main


def test_override_approval_enables_download_url(tmp_path):
    label_id = "label_test123"
    main.LABELS_DIR = tmp_path

    pdf_path = tmp_path / f"{label_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")

    main.label_metadata_store[label_id] = {
        "label_id": label_id,
        "validation_passed": False,
        "override_approved": False,
        "download_url": None,
        "status": "blocked",
    }

    req = main.OverrideApprovalRequest(
        approver="QA Lead",
        reason="Validated temporary exception for controlled release"
    )

    result = asyncio.run(main.override_label_approval(label_id, req))
    assert result["override_approved"] is True
    assert result["download_url"].endswith(f"/{label_id}/download")


def test_download_available_without_override_for_operator_review(tmp_path):
    label_id = "label_blocked"
    main.LABELS_DIR = tmp_path
    (tmp_path / f"{label_id}.pdf").write_bytes(b"%PDF-1.4 test")

    main.label_metadata_store[label_id] = {
        "label_id": label_id,
        "validation_passed": False,
        "override_approved": False,
        "download_url": None,
    }

    response = asyncio.run(main.download_label_v1(label_id))
    assert str(response.path).endswith(f"{label_id}.pdf")
