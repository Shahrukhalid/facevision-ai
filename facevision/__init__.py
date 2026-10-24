"""FaceVision AI: local, consent-based face detection, analysis, recognition and anonymisation."""

import os as _os

# ONNX Runtime ships a telemetry client that contacts Microsoft's event collector when the library loads.
# FaceVision AI promises no telemetry, so it is switched off before onnxruntime can be imported anywhere.
# tests/test_privacy.py checks that analysis makes no outbound connections.
_os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

__version__ = "0.1.0"
