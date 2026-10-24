# Changelog

## Unreleased

- Security: web app dependencies updated (Vite 6.4.5, Vitest 4.1.12, React Router 7.18.4, PostCSS selector parser 7); `npm audit` reports 0 vulnerabilities. Building the web app now needs Node.js 20 or newer.
- Fixed: live frame-rate counter could divide by zero on Windows.
- Linux: MediaPipe needs `libgles2` and `libegl1` (see Troubleshooting).

## 0.1.0

First public release.

- Live face detection with tracking, overlays, screenshots, recording, blur-in-view and three performance modes.
- Facial analysis: 478-point landmarks, head pose, eyes, blinks, mouth, smile, expression, quality, symmetry, proportions and occlusion indicators.
- Optional estimates: age range (CLIP brackets or InsightFace research pack), glasses/mask/facial hair (CLIP), appearance classifier (off by default).
- Consent-based recognition with encrypted templates, 1:1 verification, 1:N matching, ambiguity and quality checks and duplicate warnings.
- Face comparison, image analyzer, background video and batch jobs with JSON/CSV/TXT reports.
- Liveness: random challenges plus passive anti-spoofing.
- Privacy toolkit: blur, pixelate or mask faces in photos, videos and the live view.
- Model Manager with checksum-verified downloads, licences and CPU/accelerator selection.
- Local REST API and WebSockets with authentication, rate limits and same-origin protection.
- ONNX Runtime telemetry disabled; a test checks that analysis makes no network connections.
