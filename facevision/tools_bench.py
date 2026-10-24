"""Benchmark the performance presets on the current machine."""

from __future__ import annotations

import platform
import time

import cv2
import numpy as np

from .engine import runtime
from .engine.pipeline import PRESETS, LiveSession, Options


def _test_image(path: str | None) -> np.ndarray:
    if path:
        img = cv2.imread(path)
        if img is None:
            raise SystemExit(f"cannot read {path}")
        return img
    try:
        from skimage import data  # public-domain NASA portrait shipped with scikit-image
    except ImportError:
        raise SystemExit("Pass --image, or pip install scikit-image to use its sample portrait.")
    return cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR)


def run_benchmark(state, image_path: str | None = None, seconds: float = 5.0, width: int = 1280) -> dict:
    img = _test_image(image_path)
    if img.shape[1] < width:  # emulate a 720p camera frame with the face at its original size
        canvas = np.full((int(width * 9 / 16), width, 3), 40, np.uint8)
        h, w = img.shape[:2]
        canvas[: min(h, canvas.shape[0]), :w] = img[: canvas.shape[0]]
        img = canvas
    class _EmptyGallery:  # measures embedding cost without touching enrolled data
        def match(self, *a, **k):
            return {"status": "no_gallery", "candidates": []}

    from .engine.pipeline import Context
    ctx = Context(identity_access=True, identities=_EmptyGallery(), settings=state.settings())
    state.hub.warmup()
    results = {"machine": {"system": platform.system(), "machine": platform.machine(),
                           "processor": platform.processor(), "python": platform.python_version(),
                           "providers": runtime.available_providers()},
               "frame": {"width": img.shape[1], "height": img.shape[0]}, "presets": {}}
    for name in PRESETS:
        opts = Options.from_dict({"preset": name})
        session = LiveSession(state.analyzer)
        lat, stages = [], {}
        t_end = time.perf_counter() + seconds
        n = 0
        while time.perf_counter() < t_end:
            r = session.process(img, opts, ctx)
            lat.append(r["latency_ms"])
            for k, v in r["timings_ms"].items():
                stages.setdefault(k, []).append(v)
            n += 1
        lat_a = np.array(lat[1:] or lat)
        results["presets"][name] = {
            "frames": n, "faces": r["face_count"],
            "mean_latency_ms": round(float(lat_a.mean()), 1), "p95_latency_ms": round(float(np.percentile(lat_a, 95)), 1),
            "max_fps": round(1000 / float(lat_a.mean()), 1),
            "mean_stage_ms": {k: round(float(np.mean(v)), 1) for k, v in stages.items()},
        }
    return results
