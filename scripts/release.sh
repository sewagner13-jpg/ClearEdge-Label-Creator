#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_URL="${BACKEND_URL:-https://clearedgelabelcreator-production.up.railway.app}"
FRONTEND_URL="${FRONTEND_URL:-https://clearedge-label-creator.netlify.app}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PARITY_PORT="${PARITY_PORT:-8000}"
DEPLOY_TIMEOUT_SECONDS="${DEPLOY_TIMEOUT_SECONDS:-900}"
MODE="verify"
SDS_FILE=""
TDS_FILE=""
PARITY_PID=""
PARITY_DATA_DIR=""

usage() {
    cat <<'EOF'
Usage:
  ./scripts/release.sh --verify-only
  ./scripts/release.sh --deploy --sds /absolute/path/file.pdf --tds /absolute/path/file.pdf

Environment overrides:
  PYTHON_BIN, BACKEND_URL, FRONTEND_URL, PARITY_PORT, DEPLOY_TIMEOUT_SECONDS
EOF
}

log() {
    printf '[release] %s\n' "$*"
}

fail() {
    printf '[release] ERROR: %s\n' "$*" >&2
    exit 1
}

cleanup() {
    if [[ -n "$PARITY_PID" ]] && kill -0 "$PARITY_PID" 2>/dev/null; then
        kill "$PARITY_PID" 2>/dev/null || true
        wait "$PARITY_PID" 2>/dev/null || true
    fi
    if [[ -n "$PARITY_DATA_DIR" && -d "$PARITY_DATA_DIR" ]]; then
        rm -rf "$PARITY_DATA_DIR"
    fi
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
    case "$1" in
        --verify-only)
            MODE="verify"
            shift
            ;;
        --deploy)
            MODE="deploy"
            shift
            ;;
        --sds)
            [[ $# -ge 2 ]] || fail "--sds requires a file path"
            SDS_FILE="$2"
            shift 2
            ;;
        --tds)
            [[ $# -ge 2 ]] || fail "--tds requires a file path"
            TDS_FILE="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            usage >&2
            fail "Unknown argument: $1"
            ;;
    esac
done

cd "$REPO_ROOT"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python executable not found: $PYTHON_BIN"
command -v node >/dev/null 2>&1 || fail "Node.js is required for frontend syntax checks"
command -v curl >/dev/null 2>&1 || fail "curl is required for parity and live smoke checks"
command -v git >/dev/null 2>&1 || fail "git is required for release checks"

log "Checking deployment configuration"
"$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path

config = json.loads(Path("railway.json").read_text())
expected = "uvicorn app.main:app --host 0.0.0.0 --port 8000"
actual = config.get("deploy", {}).get("startCommand")
if actual != expected:
    raise SystemExit(f"Railway start command changed: {actual!r}")
PY

log "Running full test suite, including browser E2E"
"$PYTHON_BIN" -m pytest -q

log "Running static verification"
"$PYTHON_BIN" -m compileall -q app
node --check netlify-frontend/app.js
while IFS= read -r script; do
    node --check "$script"
done < <(find netlify-frontend/js -type f -name '*.js' -print | sort)
"$PYTHON_BIN" - <<'PY'
import yaml
from pathlib import Path

yaml.safe_load(Path(".github/workflows/test.yml").read_text())
PY
git diff --check

log "Starting local Railway-parity server"
if curl -fsS "http://127.0.0.1:${PARITY_PORT}/api/v1/health" >/dev/null 2>&1; then
    fail "Port ${PARITY_PORT} is already serving HTTP; choose PARITY_PORT explicitly"
fi
PARITY_DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/clearedge-release.XXXXXX")"
CLEAREDGE_DATA_DIR="$PARITY_DATA_DIR" \
    "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "$PARITY_PORT" \
    >"$PARITY_DATA_DIR/server.log" 2>&1 &
PARITY_PID="$!"

PARITY_READY=0
for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${PARITY_PORT}/api/v1/health" >"$PARITY_DATA_DIR/health.json" 2>/dev/null; then
        PARITY_READY=1
        break
    fi
    if ! kill -0 "$PARITY_PID" 2>/dev/null; then
        sed -n '1,120p' "$PARITY_DATA_DIR/server.log" >&2
        fail "Local Railway-parity server exited"
    fi
    sleep 0.25
done
[[ "$PARITY_READY" -eq 1 ]] || fail "Local Railway-parity server did not become healthy"
curl -fsSL "http://127.0.0.1:${PARITY_PORT}/" >"$PARITY_DATA_DIR/index.html"
curl -fsS "http://127.0.0.1:${PARITY_PORT}/frontend/app.js" >"$PARITY_DATA_DIR/app.js"
grep -q '<title>CLEAR EDGE Label Creator</title>' "$PARITY_DATA_DIR/index.html" \
    || fail "Local production frontend shell did not render"
grep -q 'createLabelCreatorApp' "$PARITY_DATA_DIR/app.js" \
    || fail "Local production frontend entrypoint did not render"
kill "$PARITY_PID"
wait "$PARITY_PID" || true
PARITY_PID=""
log "Local Railway-parity check passed"

if [[ "$MODE" == "verify" ]]; then
    log "Verification gate passed; no deployment was performed"
    exit 0
fi

[[ -f "$SDS_FILE" ]] || fail "SDS file not found: $SDS_FILE"
[[ -f "$TDS_FILE" ]] || fail "TDS file not found: $TDS_FILE"
[[ "${SDS_FILE##*.}" == "pdf" || "${SDS_FILE##*.}" == "PDF" ]] || fail "SDS must be a PDF"
[[ "${TDS_FILE##*.}" == "pdf" || "${TDS_FILE##*.}" == "PDF" ]] || fail "TDS must be a PDF"

CURRENT_BRANCH="$(git branch --show-current)"
PRODUCTION_BRANCH="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
[[ -n "$PRODUCTION_BRANCH" ]] || fail "origin/HEAD is not configured"
[[ "$CURRENT_BRANCH" == "$PRODUCTION_BRANCH" ]] \
    || fail "Current branch ${CURRENT_BRANCH} is not production branch ${PRODUCTION_BRANCH}"
[[ -z "$(git status --porcelain)" ]] || fail "Working tree must be clean before deployment"

git fetch --quiet origin "$PRODUCTION_BRANCH"
BEHIND_COUNT="$(git rev-list --count "HEAD..origin/${PRODUCTION_BRANCH}")"
[[ "$BEHIND_COUNT" == "0" ]] || fail "Production branch is ahead remotely; reconcile before deployment"

COMMIT_SHA="$(git rev-parse HEAD)"
log "Pushing commit ${COMMIT_SHA} to ${PRODUCTION_BRANCH}"
git push origin "HEAD:${PRODUCTION_BRANCH}"

log "Waiting for Railway to serve commit ${COMMIT_SHA}"
DEADLINE=$((SECONDS + DEPLOY_TIMEOUT_SECONDS))
DEPLOYED=0
while (( SECONDS < DEADLINE )); do
    LIVE_SHA="$(curl -fsS "${BACKEND_URL%/}/api/v1/health?release=${COMMIT_SHA}" 2>/dev/null \
        | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("build", {}).get("commit_sha", ""))' \
        2>/dev/null || true)"
    if [[ "$LIVE_SHA" == "$COMMIT_SHA" ]]; then
        DEPLOYED=1
        break
    fi
    sleep 10
done
[[ "$DEPLOYED" -eq 1 ]] || fail "Railway did not report commit ${COMMIT_SHA} before timeout"

ARTIFACT_DIR="$REPO_ROOT/test_output/release/${COMMIT_SHA:0:12}"
mkdir -p "$ARTIFACT_DIR"
log "Running live Edgemer SDS/TDS generation smoke"
HTTP_CODE="$(curl -sS -o "$ARTIFACT_DIR/generation-response.json" -w '%{http_code}' \
    -X POST "${BACKEND_URL%/}/api/v1/labels/generate" \
    -F "files=@${SDS_FILE};type=application/pdf" \
    -F "files=@${TDS_FILE};type=application/pdf" \
    -F 'product_name=Edgemer E618' \
    -F 'mode=shipped_dot' \
    -F 'size=drum' \
    -F 'orientation=horizontal' \
    -F 'lot_number=RELEASE-SMOKE' \
    -F 'expiration_date=08-13-2028' \
    -F 'fill_amount=500 lb' \
    -F 'transport_status=not_regulated')"
[[ "$HTTP_CODE" == "200" ]] || {
    "$PYTHON_BIN" - "$ARTIFACT_DIR/generation-response.json" <<'PY' >&2
import json
import sys

try:
    payload = json.load(open(sys.argv[1]))
    print(payload.get("detail") or payload.get("error") or "Unknown generation error")
except Exception:
    print("Generation response was not valid JSON")
PY
    fail "Live label generation returned HTTP ${HTTP_CODE}"
}

"$PYTHON_BIN" - "$ARTIFACT_DIR/generation-response.json" "$ARTIFACT_DIR" <<'PY'
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
artifact_dir = Path(sys.argv[2])
payload = json.loads(response_path.read_text())
label_id = payload.get("label_id")
preview_url = (payload.get("preview") or {}).get("url")
download_url = (payload.get("download") or {}).get("url")
if not preview_url:
    pages = (payload.get("preview") or {}).get("pages") or []
    preview_url = pages[0].get("url") if pages else None
if not download_url:
    download_url = (payload.get("label") or {}).get("download_url")
if not label_id or not preview_url or not download_url:
    raise SystemExit("Generation response did not expose label, preview, and PDF download URLs")

(artifact_dir / "label-id.txt").write_text(label_id)
(artifact_dir / "preview-url.txt").write_text(preview_url)
(artifact_dir / "download-url.txt").write_text(download_url)
(artifact_dir / "summary.json").write_text(json.dumps({
    "label_id": label_id,
    "status": payload.get("status"),
    "success": payload.get("success"),
    "preview_url": preview_url,
    "download_url": download_url,
}, indent=2))
PY

PREVIEW_URL="$(cat "$ARTIFACT_DIR/preview-url.txt")"
DOWNLOAD_URL="$(cat "$ARTIFACT_DIR/download-url.txt")"
[[ "$PREVIEW_URL" == http* ]] || PREVIEW_URL="${BACKEND_URL%/}${PREVIEW_URL}"
[[ "$DOWNLOAD_URL" == http* ]] || DOWNLOAD_URL="${BACKEND_URL%/}${DOWNLOAD_URL}"
curl -fsS "$PREVIEW_URL" -o "$ARTIFACT_DIR/preview.svg"
curl -fsS "$DOWNLOAD_URL" -o "$ARTIFACT_DIR/label.pdf"
"$PYTHON_BIN" - "$ARTIFACT_DIR/preview.svg" "$ARTIFACT_DIR/label.pdf" <<'PY'
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

svg_path = Path(sys.argv[1])
pdf_path = Path(sys.argv[2])
root = ET.fromstring(svg_path.read_bytes())
if not root.tag.endswith("svg"):
    raise SystemExit("Live preview is not an SVG document")
if not pdf_path.read_bytes().startswith(b"%PDF"):
    raise SystemExit("Live download is not a PDF document")
PY
curl -fsS "${FRONTEND_URL%/}/?release=${COMMIT_SHA}" -o "$ARTIFACT_DIR/frontend.html"
grep -q '<title>CLEAR EDGE Label Creator</title>' "$ARTIFACT_DIR/frontend.html" \
    || fail "Live Netlify frontend did not return the label creator shell"

LABEL_ID="$(cat "$ARTIFACT_DIR/label-id.txt")"
log "Release passed: commit=${COMMIT_SHA} label_id=${LABEL_ID}"
