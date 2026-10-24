#!/usr/bin/env bash
# FaceVision AI setup for macOS and Linux: Python environment, web app build and default models.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  for c in python3.12 python3.13 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)'; then
      PYTHON="$c"; break
    fi
  done
fi
if [ -z "$PYTHON" ]; then
  echo "Python 3.10-3.13 is required. On macOS: brew install python@3.12 (or download it from python.org)."
  exit 1
fi
echo "Using $($PYTHON --version)"

"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.lock -q
.venv/bin/python -m pip install -e . --no-deps -q

if [ -f facevision/web/index.html ]; then
  echo "Web app already built."
elif command -v npm >/dev/null 2>&1; then
  echo "Building the web app..."
  (cd frontend && npm ci --no-audit --no-fund && npm run build)
else
  echo "Node.js was not found, so the web app was not built. Install Node.js 20+ (brew install node) and run this script again."
  echo "The API still works without it: http://localhost:8600/api/docs"
fi

if [ "${FV_SKIP_MODELS:-0}" != "1" ]; then
  echo "Downloading the default models (about 80 MB, verified with SHA-256)..."
  .venv/bin/python -m facevision models install --defaults || echo "Model download failed. You can retry from the Model Manager page."
fi
echo
echo "Done. Start FaceVision AI with: bash scripts/start.sh"
