"""Draw analysis results onto images for exports (the live view draws its own overlay in the browser)."""

from __future__ import annotations

import cv2
import numpy as np

STATUS_COLORS = {  # BGR
    "match": (90, 200, 60),
    "unknown": (60, 160, 240),
    "ambiguous": (40, 200, 240),
    "low_quality": (160, 160, 160),
    "locked": (200, 160, 80),
    None: (240, 170, 40),
}


def _label(face: dict) -> list[str]:
    lines = []
    rec = face.get("recognition") or {}
    if rec.get("status") == "match":
        lines.append(f"{rec['name']} ({rec['similarity']:.2f})")
    elif rec.get("status"):
        lines.append(rec["status"].replace("_", " ").capitalize() if rec["status"] != "unknown" else "Unknown")
    head = f"#{face['track_id']} " if face.get("track_id") else f"Face {face.get('index', 0) + 1} "
    lines.insert(0, f"{head}{face['score']:.2f}")
    a = face.get("analysis", {})
    if a.get("age", {}).get("range"):
        lo, hi = a["age"]["range"]
        lines.append(f"age ~{lo}-{hi}" if hi is not None else f"age {lo}+")
    if a.get("expression"):
        lines.append(f"{a['expression']['label']} {a['expression']['probability']:.0%}")
    return lines


def annotate(image: np.ndarray, result: dict, draw_landmarks: bool = True, draw_pose: bool = True) -> np.ndarray:
    out = image.copy()
    scale = max(1.0, max(out.shape[:2]) / 900)
    thick = max(1, int(round(2 * scale)))
    for face in result.get("faces", []):
        x, y, w, h = [int(round(v)) for v in face.get("smooth_box", face["box"])]
        color = STATUS_COLORS.get((face.get("recognition") or {}).get("status"), STATUS_COLORS[None])
        cv2.rectangle(out, (x, y), (x + w, y + h), color, thick, cv2.LINE_AA)
        if draw_landmarks and face.get("landmarks"):
            for px, py in face["landmarks"]["points"]:
                cv2.circle(out, (int(px), int(py)), max(1, thick // 2), (255, 255, 255), -1, cv2.LINE_AA)
        elif draw_landmarks:
            for px, py in face["keypoints"]:
                cv2.circle(out, (int(px), int(py)), thick + 1, (255, 255, 255), -1, cv2.LINE_AA)
        pose = face.get("analysis", {}).get("head_pose") or {}
        if draw_pose and pose.get("axes"):
            o = tuple(int(v) for v in pose["axes"][0])
            for end, c in zip(pose["axes"][1:], [(60, 60, 255), (60, 255, 60), (255, 120, 60)]):
                cv2.line(out, o, tuple(int(v) for v in end), c, thick, cv2.LINE_AA)
        fs = 0.5 * scale
        ty = y - 6
        for line in reversed(_label(face)):
            (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, fs, max(1, thick - 1))
            ty = max(th + 4, ty)
            cv2.rectangle(out, (x, ty - th - 4), (x + tw + 6, ty + 3), (20, 20, 20), -1)
            cv2.putText(out, line, (x + 3, ty), cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), max(1, thick - 1), cv2.LINE_AA)
            ty -= th + 8
    return out


def encode(image: np.ndarray, fmt: str = "jpg", quality: int = 90) -> bytes:
    ext = ".png" if fmt == "png" else ".webp" if fmt == "webp" else ".jpg"
    params = [cv2.IMWRITE_JPEG_QUALITY, quality] if ext == ".jpg" else []
    ok, buf = cv2.imencode(ext, image, params)
    if not ok:
        raise ValueError("could not encode image")
    return buf.tobytes()


def thumbnail(image: np.ndarray, box: list[float], size: int = 160, pad: float = 0.25) -> np.ndarray:
    x, y, w, h = box
    side = max(w, h) * (1 + 2 * pad)
    cx, cy = x + w / 2, y + h / 2
    k = size / side
    m = np.array([[k, 0, size / 2 - cx * k], [0, k, size / 2 - cy * k]], np.float32)
    return cv2.warpAffine(image, m, (size, size), borderValue=(0, 0, 0))
