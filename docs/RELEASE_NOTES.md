FaceVision AI 0.1.0, the first public release: local, consent-based face detection, analysis, recognition and anonymisation.

## Downloads

- **Source install (recommended)**: follow the [macOS](https://github.com/Shahrukhalid/facevision-ai/blob/main/docs/INSTALL-macOS.md) or [Windows](https://github.com/Shahrukhalid/facevision-ai/blob/main/docs/INSTALL-Windows.md) guide.
- **Wheel** (`facevision_ai-0.1.0-py3-none-any.whl`): includes the built web app, so Node.js is not needed. `pip install -r requirements.lock facevision_ai-0.1.0-py3-none-any.whl`, then `python -m facevision serve --open`.
- **Desktop bundles** (`FaceVisionAI-macos-arm64.zip`, `-windows-x64.zip`, `-linux-x64.tar.gz`): built and smoke-tested by CI. They are **not code-signed**; see [packaging](https://github.com/Shahrukhalid/facevision-ai/blob/main/docs/PACKAGING.md) for how to open them.

Models are downloaded on first use from the Model Manager and verified by SHA-256. `SHA256SUMS.txt` lists checksums for the files in this release.

## Highlights

- Live detection and tracking with three performance modes, overlays, screenshots, recording and blur-in-view.
- Facial analysis: 478 landmarks, head pose, eyes and blinks, mouth, smile, expression with uncertainty, quality, symmetry and proportions.
- Recognition only against people enrolled on your computer with their consent; templates encrypted with AES-256-GCM.
- Face comparison, photo/video/batch processing with reports, liveness checks and a privacy toolkit.
- No telemetry: ONNX Runtime's telemetry is disabled and a test checks for network connections.

## Known limitations

- Accuracy figures come from a small, controlled dataset (AT&T faces). Per-group performance has not been measured.
- Age, attributes and passive anti-spoofing are experimental and not evaluated.
- Core ML and DirectML acceleration are implemented with CPU fallback but were not tested on real accelerator hardware.
- Tested on GitHub's macOS (Apple Silicon) and Windows runners and with a fake camera in Chromium, not on physical webcams.
- Server-side RTSP sources are experimental.

Full details: [features and test status](https://github.com/Shahrukhalid/facevision-ai/blob/main/docs/FEATURES.md).
