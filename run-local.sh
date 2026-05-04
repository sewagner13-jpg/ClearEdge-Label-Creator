#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
APP_MODULE="app.main:app"

printf "\n🚀 Starting ClearEdge Label Creator locally...\n"
printf "   Host: %s\n" "$HOST"
printf "   Port: %s\n" "$PORT"
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

echo "\n📍 URLs after startup:"
echo "   Health:   http://localhost:${PORT}/api/v1/health"
echo "   Readiness:http://localhost:${PORT}/api/v1/readiness"
echo "   Docs:     http://localhost:${PORT}/docs"
echo

exec uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT"
