"""YuNet face detection through OpenCV's FaceDetectorYN."""

from __future__ import annotations

import threading

import cv2
import numpy as np

# YuNet key point order: right eye, left eye (from the viewer's point of view: image-left eye first), nose tip,
# right mouth corner, left mouth corner.
KEYPOINT_NAMES = ["eye_1", "eye_2", "nose", "mouth_1", "mouth_2"]


class YuNetDetector:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._det = cv2.FaceDetectorYN.create(model_path, "", (320, 320), 0.5, 0.3, 5000)
        self._lock = threading.Lock()

    def detect(self, image: np.ndarray, score_threshold: float = 0.6, max_side: int = 640,
               nms_threshold: float = 0.3) -> list[dict]:
        """Return faces as dicts with box [x, y, w, h], score and 5 key points, in original image pixels."""
        h, w = image.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        img = image if scale == 1.0 else cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))),
                                                    interpolation=cv2.INTER_AREA)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        with self._lock:
            self._det.setInputSize((img.shape[1], img.shape[0]))
            self._det.setScoreThreshold(float(score_threshold))
            self._det.setNMSThreshold(float(nms_threshold))
            _, faces = self._det.detect(img)
        out: list[dict] = []
        if faces is None:
            return out
        for raw in faces:
            score = float(raw[14])
            f = raw.astype(np.float64)
            f[:14] /= scale
            x, y, bw, bh = f[:4]
            # clip to the image while recording whether the face extends past the frame edge
            x0, y0 = max(0.0, x), max(0.0, y)
            x1, y1 = min(float(w), x + bw), min(float(h), y + bh)
            if x1 - x0 < 2 or y1 - y0 < 2:
                continue
            kps = f[4:14].reshape(5, 2)
            out.append({
                "box": [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)],
                "score": round(score, 4),
                "keypoints": [[round(float(px), 1), round(float(py), 1)] for px, py in kps],
                "truncated": bool(x < 0 or y < 0 or x + bw > w or y + bh > h),
                "_raw": f[:15].astype(np.float32),
            })
        out.sort(key=lambda d: -d["box"][2] * d["box"][3])
        return out
