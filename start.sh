#!/usr/bin/env bash
# Start DataTalk: backend + built frontend on one port (8100).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f frontend/dist/index.html ]; then
  echo "[build] frontend/dist missing, building..."
  (cd frontend && npm ci --no-audit --no-fund && npm run build)
fi

echo "[run] http://127.0.0.1:8100"
exec ./.venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port 8100 --app-dir backend