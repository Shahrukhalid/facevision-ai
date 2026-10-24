"""Lazily loads the installed, enabled models and reloads them when the Model Manager changes something."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np

from ..models.registry import Registry

log = logging.getLogger(__name__)


class ModelHub:
    def __init__(self, registry: Registry):
        self.registry = registry
        self._models: dict[str, Any] = {}
        self._errors: dict[str, str] = {}
        self._load_ms: dict[str, float] = {}
        self._lock = threading.RLock()
        registry.on_change.append(self.unload)

    def unload(self, model_id: str | None = None) -> None:
        with self._lock:
            keys = [k for k in self._models if model_id is None or k.split(":")[0] == model_id]
            for k in keys:
                m = self._models.pop(k)
                close = getattr(m, "close", None)
                if close:
                    try:
                        close()
                    except Exception:  # pragma: no cover
                        pass
            for k in [k for k in self._errors if model_id is None or k.split(":")[0] == model_id]:
                self._errors.pop(k, None)

    def _load(self, key: str, model_id: str, factory):
        with self._lock:
            if key in self._models:
                return self._models[key]
            if not self.registry.enabled(model_id):
                return None
            if key in self._errors:
                return None
            t = time.perf_counter()
            try:
                obj = factory()
            except Exception as e:
                log.exception("failed to load %s", key)
                self._errors[key] = str(e)
                return None
            self._load_ms[key] = round((time.perf_counter() - t) * 1000, 1)
            self._models[key] = obj
            return obj

    def path(self, model_id: str, key: str) -> str:
        return str(self.registry.file_path(model_id, key))

    # ---- accessors (None when the model is not installed/enabled or failed to load)
    def detector(self):
        from .detector import YuNetDetector
        return self._load("yunet", "yunet", lambda: YuNetDetector(self.path("yunet", "model")))

    def landmarker(self):
        from .landmarks import FaceLandmarker
        return self._load("face_landmarker", "face_landmarker", lambda: FaceLandmarker(self.path("face_landmarker", "model")))

    def expression(self):
        from .classifiers import ExpressionModel
        return self._load("ferplus", "ferplus", lambda: ExpressionModel(self.path("ferplus", "model")))

    def antispoof(self):
        from .antispoof import AntiSpoof
        return self._load("antispoof", "antispoof",
                          lambda: AntiSpoof(self.path("antispoof", "v2"), self.path("antispoof", "v1se")))

    def clip(self):
        from .classifiers import ClipAttributeModel
        return self._load("clip_attributes", "clip_attributes",
                          lambda: ClipAttributeModel(self.path("clip_attributes", "image"),
                                                     self.path("clip_attributes", "text")))

    def genderage(self):
        from .classifiers import GenderAgeModel
        return self._load("insightface_buffalo_s:genderage", "insightface_buffalo_s",
                          lambda: GenderAgeModel(self.path("insightface_buffalo_s", "genderage")))

    def recognizer(self, preferred: str = "sface"):
        """The active recognizer. Falls back to SFace when the preferred one is unavailable."""
        from .recognizer import ArcFaceRecognizer, SFaceRecognizer
        if preferred == "insightface_buffalo_s":
            r = self._load("insightface_buffalo_s:arcface", "insightface_buffalo_s",
                           lambda: ArcFaceRecognizer(self.path("insightface_buffalo_s", "arcface")))
            if r is not None:
                return r
        return self._load("sface", "sface", lambda: SFaceRecognizer(self.path("sface", "model")))

    def status(self) -> dict:
        with self._lock:
            loaded = {}
            for k, m in self._models.items():
                loaded[k] = {"provider": getattr(m, "provider", "OpenCV / MediaPipe (CPU)"), "load_ms": self._load_ms.get(k)}
            return {"loaded": loaded, "errors": dict(self._errors)}

    def warmup(self) -> dict:
        """Run each available model once so the first real request is not slow."""
        img = np.zeros((240, 320, 3), np.uint8)
        face = {"box": [110.0, 60.0, 100.0, 120.0], "score": 0.9,
                "keypoints": [[140, 100], [180, 100], [160, 125], [145, 150], [175, 150]],
                "_raw": np.array([110, 60, 100, 120, 140, 100, 180, 100, 160, 125, 145, 150, 175, 150, 0.9], np.float32)}
        timings = {}
        for name, getter, call in [
            ("detection", self.detector, lambda m: m.detect(img)),
            ("landmarks", self.landmarker, lambda m: m.landmarks(img, face["box"])),
            ("recognition", self.recognizer, lambda m: m.embed(img, face)),
            ("expression", self.expression, lambda m: m.predict(img, face["box"])),
            ("antispoof", self.antispoof, lambda m: m.predict(img, face["box"])),
            ("attributes", self.clip, lambda m: m.predict(img, face["box"])),
            ("age", self.genderage, lambda m: m.predict(img, face["box"])),
        ]:
            model = getter()
            if model is None:
                continue
            t = time.perf_counter()
            try:
                call(model)
                timings[name] = round((time.perf_counter() - t) * 1000, 1)
            except Exception as e:  # pragma: no cover
                timings[name] = f"error: {e}"
        return timings
