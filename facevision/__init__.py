"""FaceVision AI: local, consent-based face detection, analysis, recognition and anonymisation."""

import os as _os

# ONNX Runtime ships a telemetry client that contacts Microsoft's event collector when the library loads.
# FaceVision AI promises no telemetry, so it is switched off before onnxruntime can be imported anywhere.
# tests/test_privacy.py checks that analysis makes no outbound connections.
_os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

# Decompression-bomb guard: a small, highly compressed PNG can expand to gigabytes when decoded. OpenCV reads this
# limit once, when cv2 is first imported, so it is set here before any FaceVision module imports cv2. It matches the
# 50-megapixel limit enforced on uploads (facevision/api/deps.py).
MAX_IMAGE_PIXELS = 50_000_000
_os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", str(MAX_IMAGE_PIXELS))

__version__ = "0.1.0"
