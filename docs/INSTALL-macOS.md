# Installing on macOS

Works on Apple Silicon (M1–M4) and Intel Macs running macOS 12 or later.

## 1. Install the requirements

With [Homebrew](https://brew.sh):

```bash
brew install python@3.12 node git
```

Or download Python 3.12 from [python.org](https://www.python.org/downloads/macos/) and Node.js LTS from [nodejs.org](https://nodejs.org).

## 2. Set up FaceVision AI

```bash
git clone https://github.com/Shahrukhalid/facevision-ai.git
cd facevision-ai
bash scripts/setup.sh
```

The script:

1. creates a virtual environment in `.venv` and installs the pinned dependencies from `requirements.lock`;
2. builds the web app (`frontend/` → `facevision/web/`);
3. downloads the default models (about 80 MB), verifying each one's SHA-256 checksum.

Set `FV_SKIP_MODELS=1` to skip step 3 and install models later from the Model Manager.

## 3. Start it

```bash
bash scripts/start.sh
```

Your browser opens `http://localhost:8600`. Stop the server with Ctrl+C.

## 4. Allow camera access

The first time you press **Start camera**, the browser asks for permission. If it was blocked:

1. Open **System Settings → Privacy & Security → Camera** and turn on your browser (Safari, Chrome, Firefox or Edge).
2. In the browser, allow the camera for `localhost` (click the camera icon in the address bar).
3. Reload the page.

Only one app can use the camera at a time; close video-call apps first.

## Apple Silicon acceleration

The standard `onnxruntime` package for macOS includes the Core ML execution provider. FaceVision AI uses it automatically for its ONNX models (expression, anti-spoofing, CLIP, research pack) and falls back to the CPU for any model Core ML cannot run. YuNet, SFace and MediaPipe run on the CPU, which is fast on Apple Silicon. The Dashboard shows which engine each loaded model uses; Settings can force CPU only.

Measure your Mac with:

```bash
.venv/bin/python -m facevision bench
```

## Updating

```bash
git pull
bash scripts/setup.sh
```

Your data folder (`~/Library/Application Support/FaceVision AI`) is kept.

## Uninstalling

Delete the project folder and, to remove your data and models, `~/Library/Application Support/FaceVision AI`.
