"""Face image quality: transparent heuristics, each reported separately so users can see why a face was rejected."""

from __future__ import annotations

import cv2
import numpy as np

LIMITS = {
    "min_eye_distance_px": 24,
    "min_sharpness": 60.0,      # variance of the Laplacian on the aligned 112x112 crop
    "brightness_range": (50, 210),
    "min_contrast": 20.0,
    "max_abs_yaw": 35.0,
    "max_abs_pitch": 30.0,
    "min_detection_score": 0.75,
}


def assess(aligned: np.ndarray | None, face: dict, pose: dict | None) -> dict:
    kps = np.array(face["keypoints"], np.float32)
    eye_dist = float(np.linalg.norm(kps[0] - kps[1]))
    checks: dict[str, dict] = {}

    def add(name, value, ok, detail):
        checks[name] = {"value": value, "ok": bool(ok), "detail": detail}

    add("face_size", round(eye_dist, 1), eye_dist >= LIMITS["min_eye_distance_px"],
        f"eye distance in pixels, needs {LIMITS['min_eye_distance_px']}+")
    add("detector_confidence", face["score"], face["score"] >= LIMITS["min_detection_score"],
        f"needs {LIMITS['min_detection_score']}+")
    if aligned is not None:
        g = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY) if aligned.ndim == 3 else aligned
        g = cv2.resize(g, (112, 112))
        sharp = float(cv2.Laplacian(g, cv2.CV_64F).var())
        bright = float(g.mean())
        contrast = float(g.std())
        add("sharpness", round(sharp, 1), sharp >= LIMITS["min_sharpness"], f"Laplacian variance, needs {LIMITS['min_sharpness']}+")
        lo, hi = LIMITS["brightness_range"]
        add("brightness", round(bright, 1), lo <= bright <= hi, f"mean grey level, needs {lo}-{hi}")
        add("contrast", round(contrast, 1), contrast >= LIMITS["min_contrast"], f"grey level spread, needs {LIMITS['min_contrast']}+")
    if pose:
        add("pose", {"yaw": pose["yaw"], "pitch": pose["pitch"]},
            abs(pose["yaw"]) <= LIMITS["max_abs_yaw"] and abs(pose["pitch"]) <= LIMITS["max_abs_pitch"],
            f"needs |yaw| <= {LIMITS['max_abs_yaw']} and |pitch| <= {LIMITS['max_abs_pitch']} degrees")
    add("fully_in_frame", not face.get("truncated", False), not face.get("truncated", False), "face not cut off by the frame edge")
    passed = sum(c["ok"] for c in checks.values())
    score = passed / len(checks)
    return {
        "score": round(score, 3),
        "suitable_for_matching": all(c["ok"] for c in checks.values()),
        "failed": [k for k, c in checks.items() if not c["ok"]],
        "checks": checks,
    }
