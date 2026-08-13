from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = REPO_ROOT / "docs" / "STATE.md"


def test_state_file_exists_and_stays_concise():
    assert STATE_FILE.is_file(), "docs/STATE.md is required for cross-session handoffs"

    line_count = len(STATE_FILE.read_text(encoding="utf-8").splitlines())
    assert line_count <= 150, f"docs/STATE.md has {line_count} lines; maximum is 150"
