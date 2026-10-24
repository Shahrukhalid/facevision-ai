# Packaging as a desktop app

## Options considered

| Option | Verdict |
| --- | --- |
| **PyInstaller** (one-folder bundle, `.app` on macOS) | **Chosen.** Bundles Python, OpenCV, MediaPipe and ONNX Runtime with no code changes. The app starts the local server and opens the browser, so the web UI is unchanged. |
| Tauri (Rust shell + Python sidecar) | Gives a native window, but still needs a frozen Python sidecar (that is, PyInstaller anyway) plus a Rust toolchain and per-platform signing. Worth revisiting for a native window later. |
| Briefcase / Nuitka | Viable alternatives. MediaPipe's native libraries and data files are well supported by PyInstaller's hooks today, so they were not pursued. |
| Docker | Not suitable for a webcam app on macOS and Windows (no direct camera access from containers). |

## Building

```bash
cd frontend && npm ci && npm run build && cd ..
pip install -r requirements.lock pyinstaller
pyinstaller packaging/facevision.spec --noconfirm
```

The output is `dist/FaceVisionAI/` (and `dist/FaceVisionAI.app` on macOS). Run `FaceVisionAI` (or open the app). It picks a free port starting at 8600, opens the browser and stores data in the normal data folder. Models are not bundled: the Model Manager downloads them on first use, the same as the source install.

## Status

- The bundle has been built and smoke-tested on Linux x86-64 in development: the binary started, served the web app, and ran a full Detailed analysis.
- The [release workflow](../.github/workflows/release.yml) builds bundles on macOS (Apple Silicon), Windows and Linux runners and smoke-tests each one: start the binary, install the face detector, detect a face over HTTP. Bundles that pass are attached to the GitHub release.
- The bundles are **not code-signed or notarised**. On macOS, right-click the app and choose *Open* the first time, or run `xattr -dr com.apple.quarantine FaceVisionAI.app`. On Windows, SmartScreen may warn about an unknown publisher.
- The camera has not been tested inside the packaged app on real hardware. The browser does the camera access, so it behaves the same as the source install.
