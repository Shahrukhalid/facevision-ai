"""Face anonymisation: blur, pixelate or solid mask, applied to selected faces."""

from __future__ import annotations

import cv2
import numpy as np

METHODS = ("blur", "pixelate", "solid")


def _region(box: list[float], shape: tuple[int, int], pad: float) -> tuple[int, int, int, int]:
    x, y, w, h = box
    px, py = w * pad, h * pad
    x0, y0 = int(max(0, x - px)), int(max(0, y - py * 1.2))
    x1, y1 = int(min(shape[1], x + w + px)), int(min(shape[0], y + h + py))
    return x0, y0, x1, y1


def anonymize(image: np.ndarray, boxes: list[list[float]], method: str = "blur", strength: float = 0.6,
              pad: float = 0.15, color: tuple[int, int, int] = (20, 20, 20)) -> np.ndarray:
    """strength 0-1: blur kernel size or pixel block size relative to the face."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    out = image.copy()
    strength = float(min(1.0, max(0.05, strength)))
    for box in boxes:
        x0, y0, x1, y1 = _region(box, out.shape[:2], pad)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        roi = out[y0:y1, x0:x1]
        h, w = roi.shape[:2]
        mask = np.zeros((h, w), np.uint8)
        cv2.ellipse(mask, (w // 2, h // 2), (w // 2, h // 2), 0, 0, 360, 255, -1)
        if method == "blur":
            k = max(3, int(max(w, h) * strength) | 1)
            filled = cv2.GaussianBlur(roi, (k, k), 0)
            filled = cv2.GaussianBlur(filled, (k, k), 0)
        elif method == "pixelate":
            blocks = max(2, int(round(12 * (1.05 - strength))))
            small = cv2.resize(roi, (blocks, max(2, int(blocks * h / w))), interpolation=cv2.INTER_LINEAR)
            filled = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
            mask[:] = 255
        else:
            filled = np.empty_like(roi)
            filled[:] = color
        roi[mask > 0] = filled[mask > 0]
    return out
