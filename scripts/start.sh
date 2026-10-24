#!/usr/bin/env bash
# Start FaceVision AI and open it in the browser. Stop with Ctrl+C.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ ! -x .venv/bin/python ]; then
  echo "Run bash scripts/setup.sh first."
  exit 1
fi
exec .venv/bin/python -m facevision serve --open "$@"
