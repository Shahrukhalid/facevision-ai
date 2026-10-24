"""Model-backed tests of the analysis engine on real images."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from facevision.engine.pipeline import Context, LiveSession, Options
from tests.conftest import att_images, need


def analyze(state, img, **opts):
    return state.analyzer.analyze_image(img, Options.from_dict({"preset": "balanced", **opts}), Context(settings=state.settings()))


def test_detects_single_face(state, portrait):
    need(state, "yunet")
    r = analyze(state, portrait, landmarks=False, quality=False, expression=False)
    assert r["face_count"] == 1
    f = r["faces"][0]
    assert f["score"] > 0.8 and len(f["keypoints"]) == 5
    x, y, w, h = f["box"]
    assert 150 < x < 210 and 40 < y < 90 and 70 < w < 120


@pytest.mark.parametrize("img", [np.zeros((480, 640, 3), np.uint8),
                                 np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8)])
def test_no_face(state, img):
    need(state, "yunet")
    assert analyze(state, img)["face_count"] == 0


def test_multiple_and_small_faces(state, portrait):
    need(state, "yunet")
    canvas = np.full((900, 1600, 3), 30, np.uint8)
    canvas[0:512, 0:512] = portrait
    canvas[0:512, 900:1412] = cv2.flip(portrait, 1)
    small = cv2.resize(portrait, (160, 160))  # face about 28 px wide
    canvas[650:810, 600:760] = small
    r = analyze(state, canvas, landmarks=False, quality=False, expression=False, max_side=1600)
    assert r["face_count"] == 3
    widths = sorted(f["box"][2] for f in r["faces"])
    assert widths[0] < 40 < widths[-1]


def test_detection_threshold_is_respected(state, portrait):
    need(state, "yunet")
    blurred = cv2.GaussianBlur(cv2.resize(portrait, (128, 128)), (9, 9), 0)
    loose = analyze(state, blurred, score_threshold=0.3, landmarks=False, quality=False, expression=False)
    strict = analyze(state, blurred, score_threshold=0.99, landmarks=False, quality=False, expression=False)
    assert strict["face_count"] <= loose["face_count"]
    assert all(f["score"] >= 0.99 for f in strict["faces"])


def test_landmarks_pose_eyes_smile(state, portrait):
    need(state, "yunet", "face_landmarker")
    r = analyze(state, portrait, overlay="detailed")
    a = r["faces"][0]["analysis"]
    assert a["landmark_count"] == 478 and len(r["faces"][0]["landmarks"]["points"]) == 478
    assert a["head_pose"]["method"] == "mesh-transform"
    assert abs(a["head_pose"]["yaw"]) < 15 and abs(a["head_pose"]["roll"]) < 10
    assert a["eyes"]["left_open"] and a["eyes"]["right_open"]
    assert a["smile"]["smiling"] is True  # the portrait is smiling
    assert 0 < a["symmetry"]["score"] <= 1


def test_pose_conventions(state, portrait):
    """Yaw flips sign with a mirrored image; a clockwise image rotation gives positive roll."""
    need(state, "yunet", "face_landmarker")
    a = analyze(state, portrait)["faces"][0]["analysis"]["head_pose"]
    b = analyze(state, cv2.flip(portrait, 1))["faces"][0]["analysis"]["head_pose"]
    assert np.sign(a["roll"]) != np.sign(b["roll"]) or abs(a["roll"]) < 1
    m = cv2.getRotationMatrix2D((256, 256), -20, 1.0)  # negative angle = clockwise in OpenCV
    rot = analyze(state, cv2.warpAffine(portrait, m, (512, 512)))["faces"][0]["analysis"]["head_pose"]
    assert 12 < rot["roll"] - a["roll"] < 30


def test_yaw_sign_on_turned_faces(state):
    """AT&T subjects turn their heads; the mesh yaw must agree in sign with the 5-point nose offset."""
    need(state, "yunet", "face_landmarker")
    from facevision.engine import geometry as G
    agree = total = 0
    for person in ("s1", "s2", "s3", "s5", "s8", "s10", "s14", "s20"):
        for img in att_images(person):
            r = analyze(state, img)
            if not r["faces"]:
                continue
            f = r["faces"][0]
            mesh = f["analysis"]["head_pose"]["yaw"]
            five = G.head_pose_from_keypoints(np.array(f["keypoints"]))["yaw"]
            if abs(five) > 12:
                total += 1
                agree += np.sign(mesh) == np.sign(five)
    if total < 3:
        pytest.skip("not enough turned faces")
    assert agree / total >= 0.9


def test_quality_flags_blur(state, portrait):
    need(state, "yunet", "sface")
    sharp = analyze(state, portrait)["faces"][0]["analysis"]["quality"]
    blurry = analyze(state, cv2.GaussianBlur(portrait, (21, 21), 0))["faces"]
    assert sharp["suitable_for_matching"]
    if blurry:
        assert "sharpness" in blurry[0]["analysis"]["quality"]["failed"]


def test_expression_is_reported_with_uncertainty(state, portrait):
    need(state, "yunet", "ferplus")
    e = analyze(state, portrait)["faces"][0]["analysis"]["expression"]
    assert e["label"] == "happiness"
    assert abs(sum(e["probabilities"].values()) - 1) < 0.01
    assert "not what the person feels" in e["note"]


def test_appearance_is_off_by_default(state, portrait):
    need(state, "yunet", "insightface_buffalo_s")
    a = analyze(state, portrait, age=True, appearance=True)["faces"][0]["analysis"]
    assert "appearance" not in a and "Turned off" in a["unavailable"]["appearance"]
    lo, hi = a["age"]["range"]
    assert 0 <= lo < hi <= 110
    state.update_settings({"allow_appearance": True})
    a = analyze(state, portrait, age=True, appearance=True)["faces"][0]["analysis"]
    assert "gender identity" in a["appearance"]["note"]


def test_clip_attributes(state, portrait):
    need(state, "yunet", "clip_attributes")
    a = analyze(state, portrait, attributes=True, age=True)["faces"][0]["analysis"]
    probs = a["attributes"]["probabilities"]
    assert set(probs) == {"eyeglasses", "sunglasses", "face_mask", "beard", "mustache"}
    assert probs["sunglasses"] < 0.5 and probs["face_mask"] < 0.5
    assert abs(sum(a["age"]["clip_bracket"]["distribution"].values()) - 1) < 0.02


def test_antispoof_scores(state, portrait):
    need(state, "yunet", "antispoof")
    s = analyze(state, portrait, antispoof=True)["faces"][0]["analysis"]["antispoof"]
    assert 0 <= s["real_score"] <= 1 and abs(sum(s["class_probabilities"]) - 1) < 0.01


def test_missing_model_is_reported_not_faked(state, portrait):
    need(state, "yunet")
    state.registry.set_model_enabled("ferplus", False) if "ferplus" in state.installed else None
    a = analyze(state, portrait, expression=True)["faces"][0]["analysis"]
    assert "expression" not in a and "expression" in a["unavailable"]


def test_live_tracking_is_stable(state, portrait):
    need(state, "yunet")
    session = LiveSession(state.analyzer)
    ids = set()
    for i in range(12):
        frame = np.zeros((600, 800, 3), np.uint8)
        frame[40:552, 10 + i * 10:522 + i * 10] = portrait
        r = session.process(frame, Options.from_dict({"preset": "fast"}), Context(), t=i / 15)
        ids.update(f["track_id"] for f in r["faces"])
    assert ids == {1}
    r = session.process(np.zeros((600, 800, 3), np.uint8), Options.from_dict({"preset": "fast"}), Context(), t=3.0)
    assert any(e["type"] == "exit" for e in r["events"])


def test_recognition_accuracy_on_att_subset(state):
    """Same person matches, different people do not, at the default threshold."""
    need(state, "yunet", "sface")
    rec = state.hub.recognizer("sface")
    embs = {}
    for person in ("s1", "s2", "s3", "s4", "s5", "s6"):
        for img in att_images(person, n=5):
            f = state.analyzer.detect(img, Options.from_dict({"preset": "fast"}))[0]
            embs.setdefault(person, []).append(rec.embed(img, f)[0])
    thr = 0.363
    gen = [float(a @ b) for p in embs for i, a in enumerate(embs[p]) for b in embs[p][i + 1:]]
    imp = [float(a @ b) for p in embs for q in embs if p < q for a in embs[p] for b in embs[q]]
    assert np.mean(np.array(gen) >= thr) > 0.95
    assert np.mean(np.array(imp) >= thr) < 0.02
