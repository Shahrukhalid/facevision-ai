"""MediaPipe Face Landmarker (478 landmarks + 52 blendshapes), run on a crop around each detected face.

Running it per detected face (instead of on the whole frame) ties every mesh to a YuNet detection and tracking ID,
and lets small faces in large images be upscaled before landmarking.
"""

from __future__ import annotations

import threading

import cv2
import numpy as np


class FaceLandmarker:
    def __init__(self, model_path: str):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        with open(model_path, "rb") as f:
            buf = f.read()
        opts = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_buffer=buf),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.3,
            min_face_presence_confidence=0.3,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._lm = vision.FaceLandmarker.create_from_options(opts)
        self._lock = threading.Lock()
        self.version = mp.__version__

    def landmarks(self, image: np.ndarray, box: list[float], crop_scale: float = 1.8, crop_px: int = 256) -> dict | None:
        """Return {'points': (478, 3) array in image pixels, 'blendshapes': {name: score}} or None."""
        h, w = image.shape[:2]
        x, y, bw, bh = box
        side = max(bw, bh) * crop_scale
        cx, cy = x + bw / 2, y + bh / 2
        x0, y0 = int(round(cx - side / 2)), int(round(cy - side / 2))
        s = int(round(side))
        if s < 8:
            return None
        # crop with zero padding where the square leaves the frame
        crop = np.zeros((s, s, 3), dtype=np.uint8)
        sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(w, x0 + s), min(h, y0 + s)
        if sx1 <= sx0 or sy1 <= sy0:
            return None
        crop[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = image[sy0:sy1, sx0:sx1, :3]
        crop = cv2.resize(crop, (crop_px, crop_px), interpolation=cv2.INTER_LINEAR if s < crop_px else cv2.INTER_AREA)
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        with self._lock:
            res = self._lm.detect(mp_image)
        if not res.face_landmarks:
            return None
        pts = np.array([[p.x, p.y, p.z] for p in res.face_landmarks[0]], dtype=np.float32)
        k = s  # crop pixels -> image pixels
        pts[:, 0] = pts[:, 0] * k + x0
        pts[:, 1] = pts[:, 1] * k + y0
        pts[:, 2] = pts[:, 2] * k
        blend = {}
        if res.face_blendshapes:
            blend = {c.category_name: float(c.score) for c in res.face_blendshapes[0]}
        matrix = None
        if res.facial_transformation_matrixes:
            matrix = np.array(res.facial_transformation_matrixes[0], dtype=np.float64)
        return {"points": pts, "blendshapes": blend, "matrix": matrix}

    def close(self):
        self._lm.close()
