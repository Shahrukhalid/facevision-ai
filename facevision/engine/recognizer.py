"""Face embedding models: SFace (default, Apache-2.0) and InsightFace ArcFace MobileFaceNet (research licence)."""

from __future__ import annotations

import threading

import cv2
import numpy as np

from .runtime import make_session

ARCFACE_DST = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655],
                        [70.7299, 92.2041]], dtype=np.float32)


def align_5pt(image: np.ndarray, keypoints: np.ndarray, size: int = 112) -> np.ndarray:
    """Similarity-transform the face so the 5 key points land on the ArcFace template."""
    dst = ARCFACE_DST * (size / 112.0)
    m, _ = cv2.estimateAffinePartial2D(np.asarray(keypoints, np.float32), dst, method=cv2.LMEDS)
    if m is None:
        raise ValueError("could not align face")
    return cv2.warpAffine(image, m, (size, size), borderValue=0)


class SFaceRecognizer:
    model_id = "sface"
    dim = 128

    def __init__(self, model_path: str):
        self._rec = cv2.FaceRecognizerSF.create(model_path, "")
        self._lock = threading.Lock()
        self.provider = "OpenCV DNN (CPU)"

    def align(self, image: np.ndarray, face: dict) -> np.ndarray:
        with self._lock:
            return self._rec.alignCrop(image, face["_raw"])

    def embed_aligned(self, aligned: np.ndarray) -> np.ndarray:
        with self._lock:
            e = self._rec.feature(aligned).ravel().astype(np.float32)
        return e / (np.linalg.norm(e) + 1e-12)

    def embed(self, image: np.ndarray, face: dict) -> tuple[np.ndarray, np.ndarray]:
        aligned = self.align(image, face)
        return self.embed_aligned(aligned), aligned


class ArcFaceRecognizer:
    model_id = "insightface_buffalo_s"
    dim = 512

    def __init__(self, model_path: str):
        self.sess, self.provider = make_session(model_path)
        self.input_name = self.sess.get_inputs()[0].name

    def align(self, image: np.ndarray, face: dict) -> np.ndarray:
        return align_5pt(image, np.array(face["keypoints"], np.float32))

    def embed_aligned(self, aligned: np.ndarray) -> np.ndarray:
        blob = cv2.dnn.blobFromImage(aligned, 1.0 / 127.5, (112, 112), (127.5, 127.5, 127.5), swapRB=True)
        e = self.sess.run(None, {self.input_name: blob})[0].ravel().astype(np.float32)
        return e / (np.linalg.norm(e) + 1e-12)

    def embed(self, image: np.ndarray, face: dict) -> tuple[np.ndarray, np.ndarray]:
        aligned = self.align(image, face)
        return self.embed_aligned(aligned), aligned


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12))
