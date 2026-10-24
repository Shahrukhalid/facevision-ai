"""The analysis pipeline shared by the live camera, image analysis, video jobs and the API."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field, fields
from typing import Any

import numpy as np

from . import geometry as G
from . import quality as Q
from .hub import ModelHub
from .tracker import FaceTracker

LOW_CONFIDENCE = 0.75
APPEARANCE_NOTE = ("Appearance-based model prediction trained on binary labels. "
                   "It cannot determine anyone's gender identity.")
EXPRESSION_NOTE = "Describes the visible expression only, not what the person feels or intends."


@dataclass
class Options:
    preset: str = "balanced"
    detection: bool = True
    score_threshold: float = 0.6
    max_side: int = 640
    tracking: bool = True
    landmarks: bool = True
    overlay: str = "basic"          # none | basic | detailed | mesh  (what point data to return)
    quality: bool = True
    expression: bool = True
    recognition: bool = False
    age: bool = False
    appearance: bool = False         # also requires the 'allow_appearance' setting
    attributes: bool = False
    antispoof: bool = False
    expression_every: int = 3
    attributes_every: int = 15
    age_every: int = 15

    @classmethod
    def from_dict(cls, d: dict | None) -> "Options":
        d = dict(d or {})
        preset = d.get("preset", "balanced")
        base = asdict(PRESETS.get(preset, PRESETS["balanced"]))
        names = {f.name for f in fields(cls)}
        for k, v in d.items():
            if k in names and v is not None:
                base[k] = v
        o = cls(**base)
        o.score_threshold = float(min(0.99, max(0.05, o.score_threshold)))
        o.max_side = int(min(1920, max(160, o.max_side)))
        if o.overlay not in {"none", "basic", "detailed", "mesh"}:
            o.overlay = "basic"
        return o


PRESETS = {
    "fast": Options(preset="fast", max_side=480, landmarks=False, overlay="none", quality=False, expression=False,
                    recognition=False),
    "balanced": Options(preset="balanced", max_side=640, landmarks=True, overlay="basic", quality=True,
                        expression=True, expression_every=3, recognition=True),
    "detailed": Options(preset="detailed", max_side=960, landmarks=True, overlay="detailed", quality=True,
                        expression=True, expression_every=1, recognition=True, age=True, attributes=True,
                        attributes_every=10, age_every=10),
}

_basic_idx: list[int] | None = None


def basic_landmark_indices() -> list[int]:
    global _basic_idx
    if _basic_idx is None:
        from mediapipe.tasks.python.vision.face_landmarker import FaceLandmarksConnections as C
        idx = set()
        for group in (C.FACE_LANDMARKS_CONTOURS, C.FACE_LANDMARKS_NOSE, C.FACE_LANDMARKS_LEFT_IRIS,
                      C.FACE_LANDMARKS_RIGHT_IRIS):
            for c in group:
                idx.add(c.start)
                idx.add(c.end)
        _basic_idx = sorted(idx)
    return _basic_idx


def mesh_topology() -> dict:
    from mediapipe.tasks.python.vision.face_landmarker import FaceLandmarksConnections as C

    def pairs(g):
        return [[c.start, c.end] for c in g]

    return {
        "basic_indices": basic_landmark_indices(),
        "groups": {
            "face_oval": pairs(C.FACE_LANDMARKS_FACE_OVAL), "lips": pairs(C.FACE_LANDMARKS_LIPS),
            "left_eye": pairs(C.FACE_LANDMARKS_LEFT_EYE), "right_eye": pairs(C.FACE_LANDMARKS_RIGHT_EYE),
            "left_eyebrow": pairs(C.FACE_LANDMARKS_LEFT_EYEBROW), "right_eyebrow": pairs(C.FACE_LANDMARKS_RIGHT_EYEBROW),
            "left_iris": pairs(C.FACE_LANDMARKS_LEFT_IRIS), "right_iris": pairs(C.FACE_LANDMARKS_RIGHT_IRIS),
            "nose": pairs(C.FACE_LANDMARKS_NOSE),
        },
        "tesselation": pairs(C.FACE_LANDMARKS_TESSELATION),
    }


@dataclass
class Context:
    """Who is asking and with which saved settings."""
    identity_access: bool = False
    identities: Any = None                   # IdentityStore
    settings: dict = field(default_factory=dict)


class Analyzer:
    def __init__(self, hub: ModelHub):
        self.hub = hub

    # ------------------------------------------------------------------ helpers
    def recognition_threshold(self, ctx: Context, model_id: str) -> float:
        per_model = ctx.settings.get("recognition_thresholds", {})
        if model_id in per_model:
            return float(per_model[model_id])
        return float(self.hub.registry.models[model_id].get("recognizer", {}).get("default_threshold", 0.363))

    def detect(self, image: np.ndarray, opts: Options) -> list[dict]:
        det = self.hub.detector()
        if det is None:
            raise RuntimeError("The YuNet face detector is not installed. Open the Model Manager to install it.")
        faces = det.detect(image, opts.score_threshold, opts.max_side)
        for f in faces:
            f["low_confidence"] = f["score"] < LOW_CONFIDENCE
        return faces

    # ------------------------------------------------------------------ per-face analysis
    def analyze_face(self, image: np.ndarray, face: dict, opts: Options, ctx: Context, frame: int = 0,
                     cache: dict | None = None, state: dict | None = None, timings: dict | None = None) -> dict:
        cache = cache if cache is not None else {}
        state = state if state is not None else {}
        timings = timings if timings is not None else {}
        a: dict[str, Any] = {}
        unavailable: dict[str, str] = {}

        def timed(name, fn):
            t = time.perf_counter()
            r = fn()
            timings[name] = round(timings.get(name, 0) + (time.perf_counter() - t) * 1000, 2)
            return r

        def due(key, every):
            c = cache.get(key)
            return c is None or frame - c[0] >= max(1, every)

        # landmarks, pose, eyes, mouth
        lm = None
        if opts.landmarks:
            model = self.hub.landmarker()
            if model is None:
                unavailable["landmarks"] = "MediaPipe Face Landmarker is not installed or is turned off."
            else:
                lm = timed("landmarks", lambda: model.landmarks(image, face["box"]))
                if lm is None:
                    unavailable["landmarks"] = "The landmark model did not find a face in this crop."
        if lm is not None:
            pts = lm["points"]
            if opts.overlay == "basic":
                idx = basic_landmark_indices()
                face["landmarks"] = {"indices": "basic", "points": np.round(pts[idx, :2], 1).tolist()}
            elif opts.overlay in {"detailed", "mesh"}:
                face["landmarks"] = {"indices": "all", "points": np.round(pts[:, :2], 1).tolist()}
            if lm["matrix"] is not None:
                pose = G.head_pose_from_matrix(lm["matrix"], pts)
            else:
                pose = G.head_pose_from_keypoints(np.array(face["keypoints"]))
            bs = lm["blendshapes"]
            blink_l, blink_r = bs.get("eyeBlinkLeft", 0.0), bs.get("eyeBlinkRight", 0.0)
            both_closed = blink_l > 0.5 and blink_r > 0.5
            # temporal blink counting per track
            if both_closed and not state.get("closed"):
                state["closed"], state["closed_at"] = True, time.time()
            elif not both_closed and state.get("closed"):
                state["closed"] = False
                if time.time() - state.get("closed_at", 0) < 0.8:
                    state["blinks"] = state.get("blinks", 0) + 1
            a["eyes"] = {
                "left_closed_score": round(blink_l, 3), "right_closed_score": round(blink_r, 3),
                "left_open": blink_l <= 0.5, "right_open": blink_r <= 0.5, "both_closed": both_closed,
                "ear_image_left": round(G.eye_aspect_ratio(pts, G.EYE_IMG_LEFT), 3),
                "ear_image_right": round(G.eye_aspect_ratio(pts, G.EYE_IMG_RIGHT), 3),
                "blink_count": state.get("blinks", 0),
            }
            jaw = bs.get("jawOpen", 0.0)
            mar = G.mouth_aspect_ratio(pts)
            a["mouth"] = {"open": jaw > 0.25 or mar > 0.3, "jaw_open_score": round(jaw, 3), "mouth_aspect_ratio": round(mar, 3),
                          "center": np.round((pts[13, :2] + pts[14, :2]) / 2, 1).tolist()}
            smile = (bs.get("mouthSmileLeft", 0.0) + bs.get("mouthSmileRight", 0.0)) / 2
            a["smile"] = {"smiling": smile > 0.5, "score": round(smile, 3)}
            a["symmetry"] = G.symmetry(pts)
            a["proportions"] = G.proportions(pts) if abs(pose["yaw"]) < 20 and abs(pose["pitch"]) < 20 else \
                {"note": "Turn towards the camera to measure proportions (pose too large)."}
            a["landmark_count"] = int(pts.shape[0])
        else:
            pose = G.head_pose_from_keypoints(np.array(face["keypoints"]))
        a["head_pose"] = pose
        a["direction"] = G.direction(pose)

        # recognition (embedding also used for the quality check's aligned crop)
        aligned = None
        rec_model_id = ctx.settings.get("recognizer", "sface")
        if opts.recognition or opts.quality:
            rec = self.hub.recognizer(rec_model_id)
            if rec is not None:
                need_rec = opts.recognition and ctx.identity_access and ctx.identities is not None
                cached = cache.get("recognition")
                stale = cached is None or (frame - cached[0] >= (60 if cached[1].get("status") == "match" else 10))
                if need_rec and stale or opts.quality:
                    aligned = timed("align", lambda: rec.align(image, face))
                if opts.quality:
                    a["quality"] = timed("quality", lambda: Q.assess(aligned, face, pose))
                if opts.recognition:
                    if not ctx.identity_access:
                        face["recognition"] = {"status": "locked", "note": "Sign in to use recognition."}
                    elif stale:
                        q_ok = a.get("quality", Q.assess(aligned, face, pose))["suitable_for_matching"] if aligned is not None else False
                        emb = timed("embedding", lambda: rec.embed_aligned(aligned))
                        thr = self.recognition_threshold(ctx, rec.model_id)
                        m = timed("matching", lambda: ctx.identities.match(rec.model_id, emb, thr))
                        result = {"status": m["status"], "model": rec.model_id, "threshold": thr,
                                  "similarity": m["candidates"][0]["similarity"] if m["candidates"] else None}
                        if m["status"] == "match" and not q_ok:
                            result["status"] = "low_quality"
                            result["note"] = "Image quality is too low to confirm a match."
                        if result["status"] == "match":
                            result["name"] = m["candidates"][0]["name"]
                            result["person_id"] = m["candidates"][0]["person_id"]
                        if ctx.settings.get("show_candidates", True):
                            result["candidates"] = m["candidates"]
                        result["computed_frame"] = frame
                        cache["recognition"] = (frame, result)
                        face["recognition"] = result
                    else:
                        face["recognition"] = {**cached[1], "cached": True}
            else:
                unavailable["recognition"] = "No face recognizer is installed."

        if opts.expression:
            model = self.hub.expression()
            if model is None:
                unavailable["expression"] = "FER+ is not installed or is turned off."
            elif due("expression", opts.expression_every):
                cache["expression"] = (frame, {**timed("expression", lambda: model.predict(image, face["box"])), "note": EXPRESSION_NOTE})
            if "expression" in cache:
                a["expression"] = cache["expression"][1]

        clip = self.hub.clip() if (opts.attributes or opts.age) else None
        if (opts.attributes or opts.age) and clip is not None and due("clip", opts.attributes_every):
            cache["clip"] = (frame, timed("attributes", lambda: clip.predict(image, face["box"])))
        if opts.attributes:
            if clip is None:
                unavailable["attributes"] = "The CLIP attribute model is not installed or is turned off."
            elif "clip" in cache:
                a["attributes"] = {"probabilities": cache["clip"][1]["attributes"], "model": "CLIP ViT-B/32 zero-shot",
                                   "experimental": True}

        if opts.age:
            age: dict[str, Any] = {}
            ga = self.hub.genderage()
            band = float(ctx.settings.get("age_band_years", 8))
            if ga is not None:
                if due("genderage", opts.age_every):
                    r = timed("age", lambda: ga.predict(image, face["box"]))
                    hist = state.setdefault("ages", [])
                    hist.append(r["age"])
                    del hist[:-10]
                    cache["genderage"] = (frame, r)
                r = cache["genderage"][1]
                est = float(np.mean(state.get("ages", [r["age"]])))
                age = {"estimate": round(est, 1), "range": [max(0, round(est - band)), round(est + band)],
                       "source": "InsightFace genderage (research licence)",
                       "note": f"Range is the estimate +/- {band:g} years, a display band, not a calibrated interval."}
                if opts.appearance and ctx.settings.get("allow_appearance", False):
                    probs = r["appearance"]
                    label = max(probs, key=probs.get)
                    a["appearance"] = {"model_label": label, "probability": probs[label], "note": APPEARANCE_NOTE}
            if clip is not None and "clip" in cache:
                c = cache["clip"][1]
                age["clip_bracket"] = {"top": c["age_top"], "probability": c["age_top_probability"],
                                       "distribution": c["age_brackets"], "experimental": True}
                if "range" not in age:
                    lo, _, hi = c["age_top"].partition("-")
                    age["range"] = [int(lo.rstrip("+")), int(hi) if hi else None]
                    age["source"] = "CLIP zero-shot age brackets (experimental)"
            if age:
                a["age"] = age
            else:
                unavailable["age"] = "Install the CLIP attribute model or the InsightFace research pack."
        if opts.appearance and "appearance" not in a:
            unavailable["appearance"] = ("Turned off in Settings." if not ctx.settings.get("allow_appearance", False)
                                         else "Needs the InsightFace research pack.")

        if opts.antispoof:
            model = self.hub.antispoof()
            if model is None:
                unavailable["antispoof"] = "The anti-spoofing models are not installed or are turned off."
            else:
                a["antispoof"] = timed("antispoof", lambda: model.predict(image, face["box"]))

        reasons = []
        if face.get("truncated"):
            reasons.append("face extends past the frame edge")
        if face["score"] < LOW_CONFIDENCE:
            reasons.append("low detection confidence")
        if opts.landmarks and lm is None and self.hub.landmarker() is not None:
            reasons.append("landmarks could not be fitted")
        attrs = a.get("attributes", {}).get("probabilities", {})
        if attrs.get("face_mask", 0) > 0.6:
            reasons.append("face covering likely")
        if attrs.get("sunglasses", 0) > 0.6:
            reasons.append("sunglasses likely")
        a["occlusion"] = {"likely": bool(reasons), "reasons": reasons}
        if unavailable:
            a["unavailable"] = unavailable
        face["analysis"] = a
        return face

    # ------------------------------------------------------------------ whole images
    def analyze_image(self, image: np.ndarray, opts: Options, ctx: Context) -> dict:
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        faces = []
        if opts.detection:
            t = time.perf_counter()
            faces = self.detect(image, opts)
            timings["detection"] = round((time.perf_counter() - t) * 1000, 2)
            for i, f in enumerate(faces):
                f["index"] = i
                self.analyze_face(image, f, opts, ctx, timings=timings)
        return {
            "image": {"width": int(image.shape[1]), "height": int(image.shape[0])},
            "face_count": len(faces),
            "faces": [clean(f) for f in faces],
            "options": asdict(opts),
            "timings_ms": {**timings, "total": round((time.perf_counter() - t0) * 1000, 2)},
        }


class LiveSession:
    """Per-connection state for live video: tracker, per-track caches and FPS measurement."""

    def __init__(self, analyzer: Analyzer):
        self.analyzer = analyzer
        self.tracker = FaceTracker()
        self.frame = 0
        self.t_start = time.time()
        self._times: list[float] = []

    def process(self, image: np.ndarray, opts: Options, ctx: Context, t: float | None = None) -> dict:
        t0 = time.perf_counter()
        now = time.time() if t is None else t
        self.frame += 1
        timings: dict[str, float] = {}
        faces: list[dict] = []
        events: list[dict] = []
        if opts.detection:
            tt = time.perf_counter()
            faces = self.analyzer.detect(image, opts)
            timings["detection"] = round((time.perf_counter() - tt) * 1000, 2)
            if opts.tracking:
                events = self.tracker.update(faces, self.frame, now)
            for i, f in enumerate(faces):
                f["index"] = i
                tr = self.tracker.tracks.get(f.get("track_id")) if opts.tracking else None
                self.analyzer.analyze_face(image, f, opts, ctx, frame=self.frame,
                                           cache=tr.cache if tr else None, state=tr.state if tr else None,
                                           timings=timings)
        elif self.tracker.tracks:
            events = self.tracker.flush()
        total = (time.perf_counter() - t0) * 1000
        self._times.append(time.time())
        self._times = [x for x in self._times if x > time.time() - 2.0]
        fps = (len(self._times) - 1) / (self._times[-1] - self._times[0]) if len(self._times) > 1 else 0.0
        return {
            "frame": self.frame,
            "image": {"width": int(image.shape[1]), "height": int(image.shape[0])},
            "face_count": len(faces),
            "faces": [clean(f) for f in faces],
            "events": events,
            "tracking": {"active_tracks": len(self.tracker.tracks), **self.tracker.stats} if opts.tracking else None,
            "processing_fps": round(fps, 1),
            "latency_ms": round(total, 1),
            "timings_ms": timings,
        }


def clean(face: dict) -> dict:
    return {k: v for k, v in face.items() if not k.startswith("_")}
