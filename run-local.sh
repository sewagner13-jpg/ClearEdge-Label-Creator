#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
APP_MODULE="app.main:app"
VENV_DIR="${VENV_DIR:-.venv}"

if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python3.11}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

printf "\n🚀 Starting ClearEdge Label Creator locally...\n"
printf "   Host: %s\n" "$HOST"
printf "   Port: %s\n" "$PORT"
printf "   Python: %s\n" "$PYTHON_BIN"
printf "\n🔎 Quick preflight:\n"

if [[ -z "${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}" ]]; then
  echo "  ⚠️  No GEMINI_API_KEY/GOOGLE_API_KEY detected. Live extraction may fail."
else
  echo "  ✅ API key detected."
fi

if [[ -z "${SHARED_DRIVE_ID:-}" ]]; then
  echo "  ⚠️  SHARED_DRIVE_ID not set. Drive-backed flows may be unavailable."
else
  echo "  ✅ SHARED_DRIVE_ID detected."
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "  Creating virtual environment at $VENV_DIR..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

echo "  Installing/updating Python dependencies..."
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

printf "\n📍 URLs after startup:\n"
echo "   Health:   http://localhost:${PORT}/api/v1/health"
echo "   Readiness:http://localhost:${PORT}/api/v1/readiness"
echo "   Docs:     http://localhost:${PORT}/docs"
echo

exec python -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT"
