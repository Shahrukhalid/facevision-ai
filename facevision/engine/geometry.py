"""Geometric measurements from landmarks: head pose, eye/mouth openness, symmetry and facial proportions.

All of these are measurements of landmark positions. They depend on head pose, camera angle and landmark accuracy,
and they say nothing about a person's identity, health or character.
"""

from __future__ import annotations

import math

import numpy as np

EYE_IMG_LEFT = [33, 160, 158, 133, 153, 144]   # p1..p6 for the eye aspect ratio
EYE_IMG_RIGHT = [263, 387, 385, 362, 380, 373]
MOUTH_INNER = (13, 14, 78, 308)

SYMMETRY_PAIRS = [(33, 263), (133, 362), (70, 300), (105, 334), (61, 291), (234, 454), (172, 397), (98, 327),
                  (159, 386), (145, 374)]


def head_pose_from_matrix(matrix: np.ndarray, points: np.ndarray) -> dict:
    """Pose from MediaPipe's facial transformation matrix (canonical face model fitted to all 478 landmarks).

    Converted to this project's convention (checked against image rotations and 5-point geometry, see
    tests/test_engine.py): yaw > 0 = face turned towards the image's right, pitch > 0 = face tilted up,
    roll > 0 = head tilted clockwise in the image."""
    r = matrix[:3, :3]
    mp_pitch, mp_yaw, mp_roll = _euler_xyz(r)
    nose = points[1, :2]
    length = 0.5 * float(np.linalg.norm(points[234, :2] - points[454, :2]))
    axes = [[round(float(nose[0]), 1), round(float(nose[1]), 1)]]
    for col in range(3):  # canonical axes: x right, y up, z towards the camera
        v = r[:, col]
        axes.append([round(float(nose[0] + v[0] * length), 1), round(float(nose[1] - v[1] * length), 1)])
    return {"yaw": round(mp_yaw, 1), "pitch": round(-mp_pitch, 1), "roll": round(-mp_roll, 1), "axes": axes,
            "method": "mesh-transform"}


def _euler_xyz(r: np.ndarray) -> tuple[float, float, float]:
    sy = math.hypot(r[0, 0], r[1, 0])
    return (math.degrees(math.atan2(r[2, 1], r[2, 2])), math.degrees(math.atan2(-r[2, 0], sy)),
            math.degrees(math.atan2(r[1, 0], r[0, 0])))


def head_pose_from_keypoints(kps: np.ndarray) -> dict:
    """Rough pose from YuNet's 5 key points (used when the landmark model is unavailable)."""
    e1, e2, nose, m1, m2 = [np.asarray(p, np.float64) for p in kps]
    eye_mid, mouth_mid = (e1 + e2) / 2, (m1 + m2) / 2
    eye_dist = np.linalg.norm(e2 - e1) + 1e-6
    roll = math.degrees(math.atan2(e2[1] - e1[1], e2[0] - e1[0]))
    # horizontal nose offset relative to the eye/mouth midline, scaled to approximate degrees
    mid_x = (eye_mid[0] + mouth_mid[0]) / 2
    yaw = math.degrees(math.asin(max(-1.0, min(1.0, (nose[0] - mid_x) / (eye_dist * 0.6)))))
    # nose height between the eye line and the mouth line (about 0.5 when level)
    span = mouth_mid[1] - eye_mid[1] + 1e-6
    t = (nose[1] - eye_mid[1]) / span
    pitch = (0.55 - t) * 120
    return {"yaw": round(yaw, 1), "pitch": round(pitch, 1), "roll": round(roll, 1), "axes": None,
            "method": "approximate-5pt"}


def direction(pose: dict, yaw_th: float = 15, pitch_th: float = 12) -> str:
    parts = []
    if pose["pitch"] > pitch_th:
        parts.append("up")
    elif pose["pitch"] < -pitch_th:
        parts.append("down")
    if pose["yaw"] > yaw_th:
        parts.append("right")
    elif pose["yaw"] < -yaw_th:
        parts.append("left")
    return "-".join(parts) if parts else "forward"


def eye_aspect_ratio(points: np.ndarray, idx: list[int]) -> float:
    p = points[idx, :2]
    vertical = np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])
    horizontal = 2 * np.linalg.norm(p[0] - p[3]) + 1e-6
    return float(vertical / horizontal)


def mouth_aspect_ratio(points: np.ndarray) -> float:
    up, low, left, right = MOUTH_INNER
    return float(np.linalg.norm(points[up, :2] - points[low, :2]) / (np.linalg.norm(points[left, :2] - points[right, :2]) + 1e-6))


def symmetry(points: np.ndarray) -> dict:
    a, b = points[168, :2], points[152, :2]  # nose bridge -> chin midline
    axis = (b - a) / (np.linalg.norm(b - a) + 1e-6)
    normal = np.array([-axis[1], axis[0]])
    width = np.linalg.norm(points[234, :2] - points[454, :2]) + 1e-6
    devs = []
    for i, j in SYMMETRY_PAIRS:
        di, dj = np.dot(points[i, :2] - a, normal), np.dot(points[j, :2] - a, normal)
        ti, tj = np.dot(points[i, :2] - a, axis), np.dot(points[j, :2] - a, axis)
        devs.append(math.hypot(di + dj, ti - tj) / width)
    mean_dev = float(np.mean(devs))
    return {"mean_deviation_pct": round(mean_dev * 100, 2), "score": round(max(0.0, 1 - mean_dev * 5), 3)}


def proportions(points: np.ndarray) -> dict:
    def d(i, j):
        return float(np.linalg.norm(points[i, :2] - points[j, :2]))

    height, cheek, jaw, forehead = d(10, 152), d(234, 454), d(172, 397), d(54, 284)
    hw = height / (cheek + 1e-6)
    return {
        "height_to_width": round(hw, 3),
        "jaw_to_cheek": round(jaw / (cheek + 1e-6), 3),
        "forehead_to_cheek": round(forehead / (cheek + 1e-6), 3),
        "outline": "longer than wide" if hw > 1.35 else "about as long as wide" if hw > 1.15 else "wider than long",
    }
