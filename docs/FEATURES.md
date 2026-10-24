# Features and test status

Legend: **Tested** = covered by automated tests that ran and passed (unit, API, or browser end-to-end). **Experimental** = works and is tested for function, but its accuracy is not evaluated or the approach is limited. **Not implemented** = planned or out of scope.

Automated suites: `tests/test_core.py` (no models), `tests/test_engine.py` and `tests/test_api.py` (real models and images), `tests/test_privacy.py` (no network connections), `tests/e2e/run_ui.py` (real web app in headless Chromium with a fake camera), and `frontend/tests`. CI runs them on Linux, macOS (Apple Silicon runner) and Windows; see the [CI workflow](../.github/workflows/ci.yml).

## Detection and tracking

| Feature | Status | How it was tested |
| --- | --- | --- |
| Automatic detection when the camera starts | Tested | Browser test: one face found within seconds of Start camera |
| Multiple faces, small and large | Tested | 3 faces including one about 28 px wide in a 1600×900 frame |
| No-face frames | Tested | Blank and random-noise images return no faces |
| Faces at an angle / partly visible | Tested for function | Turned AT&T faces detected (400/400); `truncated` and `low_confidence` flags |
| Adjustable threshold, confidence, face count | Tested | Threshold respected; scores in every result |
| Tracking IDs, enter/exit events, expiry, smoothing | Tested | Moving face keeps one ID; exit event after it leaves; browser test sees an enter event |
| FPS and latency | Tested | Reported per frame; measured by `facevision bench` |
| Automatic face cropping | Tested | `crops=true` thumbnails; crop export in Image Analyzer |
| Glasses / masks | Experimental | CLIP probabilities, not evaluated |

## Facial analysis

| Feature | Status | Notes |
| --- | --- | --- |
| 478-point landmarks, mesh overlay | Tested | MediaPipe Face Landmarker, run on a crop around each detected face |
| Head pose (yaw, pitch, roll), direction | Tested | Sign conventions verified with rotations, mirroring and 400 AT&T faces |
| Eye state, blink count | Tested for function | Blendshapes; blink counting over time on tracked faces |
| Mouth state, smile | Tested | Smiling portrait detected as smiling |
| Face quality | Tested | Blur makes the sharpness check fail; checks listed individually |
| Occlusion indicators | Experimental | Reasons from frame edge, detector confidence, landmark failure, CLIP mask/sunglasses |
| Symmetry and proportions | Tested for function | Geometric measurements; pose-dependent |
| Expression with uncertainty | Tested | FER+ probabilities, uncertainty flag, appearance-only wording |
| Age range | Experimental | CLIP brackets (zero-shot) or InsightFace estimate (research pack); not evaluated |
| Appearance classifier | Tested | Off by default; needs a setting and the research pack; never labelled as gender identity |
| Beard / mustache | Experimental | CLIP zero-shot |
| Race, ethnicity, religion, health or similar | Not implemented, by design | |

## Recognition

| Feature | Status | Notes |
| --- | --- | --- |
| Consented enrolment, multiple photos | Tested | Consent required by the API; camera capture or upload |
| Encrypted templates, permanent deletion | Tested | Ciphertext checked not to contain the embedding; deletion removes rows and compacts the database |
| Duplicate and consistency warnings | Tested | Same face under a second name triggers a duplicate warning |
| 1:N matching, Unknown, threshold | Tested | Held-out photos match; other people stay Unknown; a 0.999 threshold rejects everyone |
| 1:1 verification | Tested | |
| Ambiguous and low-quality handling | Tested | |
| Cached recognition per track | Tested for function | Re-checked about every 60 frames after a match |
| Diagnostics | Tested | Similarity, threshold, candidates, quality checks per result |
| Accuracy | Measured | AT&T results in [EVALUATION.md](EVALUATION.md); per-group results need a suitable dataset |

## Tools

| Feature | Status | Notes |
| --- | --- | --- |
| Face comparison | Tested | Same person matched; different people not; no-face image rejected |
| Image analyzer and exports (PNG, JSON, CSV, crops) | Tested | |
| Video analysis with events, sampling, annotated export, cancellation | Tested | Synthetic clip: one track, enter then exit |
| Batch processing with errors and concurrency | Tested | 3 images plus 1 corrupt file |
| Anonymisation (blur, pixelate, solid, per face) in photos, video and live | Tested | |
| Reports, export, backup, delete | Tested | |
| Liveness: active challenge | Tested for function | Not evaluated against attacks; see [LIVENESS.md](LIVENESS.md) |
| Liveness: passive model | Experimental | Upstream models, not independently evaluated |

## App, API and platform

| Feature | Status | Notes |
| --- | --- | --- |
| 16 dashboard pages | Tested | Each rendered in the browser test with no console errors |
| Camera controls (start, stop, screenshot, record, mirror, fullscreen, blur) | Tested with a fake camera | Switching between two physical cameras and real webcams need a manual check |
| Camera permission errors | Implemented | Clear messages per browser error; not automated |
| Server-side RTSP / camera index source | Experimental | Not tested against real IP cameras |
| REST API, OpenAPI docs, WebSockets | Tested | |
| Authentication, rate limits, host and origin checks | Tested | |
| No outbound connections | Tested | Fails the build if analysis connects anywhere |
| Offline operation after model download | Tested | Same privacy test; `FV_OFFLINE=1` blocks downloads |
| Model download, checksum verification, fallback mirror | Tested in CI | Downloads from the real URLs on each CI runner |
| Core ML / DirectML acceleration | Implemented, not verified | Selection and CPU fallback are implemented; no Apple Silicon GPU/ANE or DirectML device was available to test |
| macOS and Windows | Tested on CI runners | GitHub's macOS 14 (Apple Silicon) and Windows Server 2022 runners; not on a physical Mac or Windows PC with a webcam |
| Desktop bundle (PyInstaller) | Built and smoke-tested | See [PACKAGING.md](PACKAGING.md); unsigned |
