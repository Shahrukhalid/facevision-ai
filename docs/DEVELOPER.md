# Developer guide

## Architecture

```
Browser (React + TypeScript)                       Python (FastAPI)
┌───────────────────────────────┐   REST / WS   ┌───────────────────────────────────────────────┐
│ pages/   16 screens           │ ────────────▶ │ api/        routes, auth, limits, security     │
│ CameraView: getUserMedia,     │   JPEG frames │ engine/pipeline.py  Analyzer + LiveSession     │
│   canvas overlay, recording   │ ◀──────────── │   detector (YuNet)      landmarks (MediaPipe)  │
│ lib/overlay.ts drawing        │  JSON results │   recognizer (SFace/ArcFace)  classifiers      │
└───────────────────────────────┘               │   antispoof  liveness  tracker  anonymize     │
                                                │ engine/hub.py  lazy model loading            │
                                                │ models/registry.py  download + SHA-256       │
                                                │ storage/  SQLite, encrypted templates        │
                                                │ jobs.py   video / batch worker pool          │
                                                └───────────────────────────────────────────────┘
```

- The **browser owns the camera**. It sends downscaled JPEG frames over `/ws/live` and draws results itself, so the preview stays smooth even when analysis is slower than the camera. The next frame is sent only after the previous result arrives.
- The **engine is shared**: live frames, uploaded images, video jobs and the CLI all go through `Analyzer` in `engine/pipeline.py`.
- **Per-track caching** (`LiveSession`): recognition, expression, CLIP and age results are stored on the track and refreshed every few frames instead of on every frame.
- **Models are optional** except YuNet. Each analysis step reports `unavailable` with a reason when its model is missing, rather than inventing a value.

## Repository layout

```
facevision/          Python package
  api/               FastAPI app, routes, dependencies, WebSockets
  engine/            detection, landmarks, geometry, quality, recognizers, classifiers, liveness, tracker, drawing
  models/            manifest.json (model registry), registry.py (install/verify), CLIP prompts
  storage/           SQLite database and identity store
  security.py        passphrase, sessions, API keys, template encryption, rate limiting
  jobs.py            video and batch jobs
  evaluation.py      recognition evaluation CLI
  tools_bench.py     performance benchmark
  web/               built frontend (generated, not committed)
frontend/            React app (Vite, Tailwind)
tests/               pytest suite and tests/e2e/run_ui.py (browser test)
tools/               model pack build script
packaging/           PyInstaller launcher and spec
scripts/             setup and start scripts for macOS/Linux and Windows
docs/                documentation
```

## Development setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock -r requirements-dev.lock
.venv/bin/pip install -e . --no-deps
.venv/bin/python -m facevision models install --defaults
(cd frontend && npm ci)

# terminal 1: API on :8600
.venv/bin/python -m facevision serve
# terminal 2: web app with hot reload on :5173 (proxies /api and /ws to :8600)
cd frontend && npm run dev
```

## Tests

```bash
# fast tests (no models needed)
.venv/bin/python -m pytest

# everything, with models and the AT&T face set
FV_TEST_MODELS=/path/to/flat/model/files FV_TEST_ATT=/path/to/att_faces .venv/bin/python -m pytest

# frontend
cd frontend && npm test && npx tsc --noEmit

# browser end-to-end (server running with default models)
pip install playwright && python -m playwright install chromium
python tests/e2e/run_ui.py http://localhost:8600
```

`FV_TEST_MODELS` is a folder containing the model files themselves (for example `face_detection_yunet_2023mar.onnx`). CI builds it from a normal install. Tests for models that are missing are skipped, never faked.

## Code style

- Python: `ruff check facevision tests tools` (configured in `pyproject.toml`).
- TypeScript: `npx tsc --noEmit` with `strict` on.
- User-facing text: plain, specific sentences. Estimates are always described as estimates.

## Configuration

See [`.env.example`](../.env.example). Everything is optional; the defaults are safe.

## Ground rules for contributions

- No feature may send images, embeddings or analytics off the machine.
- No inference of race, ethnicity, religion, health, sexual orientation, criminality or similar traits.
- Every model needs a licence that allows its use, a pinned checksum and an honest evaluation note.
- Never mark a test as passing that was not run.
