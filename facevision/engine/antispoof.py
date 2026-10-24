"""Passive presentation-attack detection with Minivision's MiniFASNet models (Apache-2.0).

The two models look at the face at two context scales (2.7x and 4x the face box). Following the upstream
implementation, their softmax outputs are averaged and class 1 means "real". This is a signal that can be fooled;
see docs/LIVENESS.md.
"""

from __future__ import annotations

import cv2
import numpy as np

from .runtime import make_session


def _crop(image: np.ndarray, box: list[float], scale: float, out: int = 80) -> np.ndarray:
    """Port of Silent-Face's CropImage._get_new_box + crop."""
    src_h, src_w = image.shape[:2]
    x, y, bw, bh = box
    scale = min((src_h - 1) / bh, min((src_w - 1) / bw, scale))
    nw, nh = bw * scale, bh * scale
    cx, cy = bw / 2 + x, bh / 2 + y
    x0, y0, x1, y1 = cx - nw / 2, cy - nh / 2, cx + nw / 2, cy + nh / 2
    if x0 < 0:
        x1 -= x0
        x0 = 0
    if y0 < 0:
        y1 -= y0
        y0 = 0
    if x1 > src_w - 1:
        x0 -= x1 - src_w + 1
        x1 = src_w - 1
    if y1 > src_h - 1:
        y0 -= y1 - src_h + 1
        y1 = src_h - 1
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    return cv2.resize(image[y0:y1 + 1, x0:x1 + 1], (out, out))


class AntiSpoof:
    def __init__(self, v2_path: str, v1se_path: str):
        self.models = []
        for path, scale in ((v2_path, 2.7), (v1se_path, 4.0)):
            sess, provider = make_session(path)
            self.models.append((sess, sess.get_inputs()[0].name, scale))
        self.provider = provider

    def predict(self, image: np.ndarray, box: list[float]) -> dict:
        total = np.zeros(3, np.float64)
        for sess, inp, scale in self.models:
            crop = _crop(image, box, scale)
            x = crop.astype(np.float32).transpose(2, 0, 1)[None]
            logits = sess.run(None, {inp: x})[0][0].astype(np.float64)
            e = np.exp(logits - logits.max())
            total += e / e.sum()
        p = total / len(self.models)
        real = float(p[1])
        return {"real_score": round(real, 3), "label": "real" if int(np.argmax(p)) == 1 else "spoof",
                "class_probabilities": [round(float(v), 3) for v in p]}
