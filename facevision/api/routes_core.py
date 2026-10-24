"""Health, system, models, settings and single-image endpoints."""

from __future__ import annotations

import base64
import platform
import sys
import time

import cv2
import numpy as np
import psutil
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .. import __version__
from ..engine import liveness as L
from ..engine import runtime
from ..engine.anonymize import METHODS, anonymize
from ..engine.draw import annotate, encode, thumbnail
from ..engine.pipeline import Options, mesh_topology
from ..engine.quality import assess
from ..engine.recognizer import cosine
from .deps import is_signed_in, parse_json_field, rate_limit, read_image, require_admin, state

router = APIRouter(prefix="/api")
_proc = psutil.Process()
_liveness: dict[str, L.LivenessSession] = {}


def b64_jpeg(img: np.ndarray, quality: int = 88) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(encode(img, "jpg", quality)).decode()


# ------------------------------------------------------------------ status
@router.get("/health")
def health(request: Request):
    st = state(request)
    return {"status": "ok", "version": __version__, "uptime_s": round(time.time() - st.started, 1),
            "detector_ready": st.registry.installed("yunet")}


@router.get("/system")
def system(request: Request):
    st = state(request)
    vm = psutil.virtual_memory()
    try:
        import mediapipe
        mp_version = mediapipe.__version__
    except Exception:  # pragma: no cover
        mp_version = None
    return {
        "version": __version__,
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
                     "python": sys.version.split()[0]},
        "cpu": {"percent": psutil.cpu_percent(interval=None), "count": psutil.cpu_count(logical=True),
                "process_percent": _proc.cpu_percent(interval=None)},
        "memory": {"total": vm.total, "available": vm.available, "percent": vm.percent,
                   "process_rss": _proc.memory_info().rss},
        "hardware": runtime.hardware_summary(),
        "libraries": {"opencv": cv2.__version__, "mediapipe": mp_version, "numpy": np.__version__},
        "models": st.hub.status(),
        "disk": st.disk_usage(),
        "auth": {"configured": st.vault.configured, "signed_in": is_signed_in(request)},
        "binding": {"host": st.config.host, "port": st.config.port},
        "offline_mode": st.config.offline,
    }


@router.get("/mesh/topology")
def topology():
    return mesh_topology()


# ------------------------------------------------------------------ models
class InstallBody(BaseModel):
    accept_license: bool = False


class EnableBody(BaseModel):
    enabled: bool


@router.get("/models")
def models(request: Request):
    return state(request).registry.list()


@router.post("/models/{model_id}/install")
def install_model(model_id: str, body: InstallBody, request: Request):
    st = require_admin(request)
    try:
        st.registry.start_download(model_id, body.accept_license)
    except KeyError:
        raise HTTPException(404, "Unknown model")
    except ValueError as e:
        raise HTTPException(400, str(e))
    if body.accept_license:
        st.db.audit("model.license_accepted", model_id)
    return st.registry.describe(model_id)


@router.post("/models/{model_id}/cancel")
def cancel_model(model_id: str, request: Request):
    st = require_admin(request)
    st.registry.cancel_download(model_id)
    return st.registry.describe(model_id)


@router.post("/models/{model_id}/verify")
def verify_model(model_id: str, request: Request):
    st = state(request)
    if model_id not in st.registry.models:
        raise HTTPException(404, "Unknown model")
    return {"model": model_id, "files": st.registry.verify(model_id)}


@router.post("/models/{model_id}/enable")
def enable_model(model_id: str, body: EnableBody, request: Request):
    st = require_admin(request)
    try:
        st.registry.set_model_enabled(model_id, body.enabled)
    except KeyError:
        raise HTTPException(404, "Unknown model")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return st.registry.describe(model_id)


@router.delete("/models/{model_id}")
def delete_model(model_id: str, request: Request):
    st = require_admin(request)
    try:
        st.registry.delete(model_id)
    except KeyError:
        raise HTTPException(404, "Unknown model")
    except ValueError as e:
        raise HTTPException(400, str(e))
    st.db.audit("model.deleted", model_id)
    return st.registry.describe(model_id)


@router.post("/models/warmup")
def warmup(request: Request):
    return {"timings_ms": state(request).hub.warmup()}


# ------------------------------------------------------------------ settings
@router.get("/settings")
def get_settings(request: Request):
    return state(request).settings()


@router.put("/settings")
def put_settings(body: dict, request: Request):
    st = require_admin(request)
    if "recognizer" in body and body["recognizer"] not in {"sface", "insightface_buffalo_s"}:
        raise HTTPException(400, "Unknown recognizer")
    if "accelerator" in body and body["accelerator"] not in {"auto", "cpu"}:
        raise HTTPException(400, "accelerator must be 'auto' or 'cpu'")
    try:
        return st.update_settings(body)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ single image
def _opts(request: Request, raw: dict) -> Options:
    st = state(request)
    if "score_threshold" not in raw:
        raw["score_threshold"] = st.settings()["detection_threshold"]
    return Options.from_dict(raw)


def _run(request: Request, img, opts: Options):
    st = state(request)
    try:
        return st.analyzer.analyze_image(img, opts, st.context(is_signed_in(request)))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@router.post("/detect")
async def detect(request: Request, file: UploadFile = File(...), score_threshold: float | None = Form(None),
                 max_side: int = Form(1280), crops: bool = Form(False)):
    rate_limit(request, "infer", 600, 60)
    img = await read_image(request, file)
    raw = {"preset": "fast", "max_side": max_side}
    if score_threshold is not None:
        raw["score_threshold"] = score_threshold
    res = _run(request, img, _opts(request, raw))
    if crops:
        for f in res["faces"]:
            f["crop"] = b64_jpeg(thumbnail(img, f["box"]))
    return res


@router.post("/analyze")
async def analyze(request: Request, file: UploadFile = File(...), options: str | None = Form(None),
                  annotate_image: bool = Form(False), crops: bool = Form(False)):
    rate_limit(request, "infer", 600, 60)
    img = await read_image(request, file)
    opts = _opts(request, parse_json_field(options, "options"))
    res = _run(request, img, opts)
    if annotate_image:
        res["annotated_image"] = b64_jpeg(annotate(img, res, draw_landmarks=opts.overlay != "none"))
    if crops:
        for f in res["faces"]:
            f["crop"] = b64_jpeg(thumbnail(img, f["box"]))
    return res


@router.post("/landmarks")
async def landmarks(request: Request, file: UploadFile = File(...)):
    rate_limit(request, "infer", 600, 60)
    img = await read_image(request, file)
    st = state(request)
    if st.hub.landmarker() is None:
        raise HTTPException(503, "MediaPipe Face Landmarker is not installed. Install it in the Model Manager.")
    opts = _opts(request, {"preset": "balanced", "overlay": "detailed", "expression": False, "recognition": False,
                           "quality": False, "max_side": 1280})
    res = _run(request, img, opts)
    return {"image": res["image"], "faces": [
        {"index": f["index"], "box": f["box"], "landmarks": f.get("landmarks"),
         "head_pose": f["analysis"].get("head_pose"), "unavailable": f["analysis"].get("unavailable")}
        for f in res["faces"]]}


@router.post("/compare")
async def compare(request: Request, file_a: UploadFile = File(...), file_b: UploadFile = File(...),
                  face_a: int = Form(0), face_b: int = Form(0), threshold: float | None = Form(None)):
    rate_limit(request, "infer", 300, 30)
    st = state(request)
    img_a, img_b = await read_image(request, file_a), await read_image(request, file_b)
    rec = st.hub.recognizer(st.settings().get("recognizer", "sface"))
    if rec is None:
        raise HTTPException(503, "No face recognizer is installed. Install SFace in the Model Manager.")
    opts = _opts(request, {"preset": "fast", "max_side": 1280})
    sides = []
    for img, idx, label in ((img_a, face_a, "A"), (img_b, face_b, "B")):
        faces = st.analyzer.detect(img, opts)
        if not faces:
            raise HTTPException(422, f"No face found in image {label}.")
        if not 0 <= idx < len(faces):
            raise HTTPException(400, f"Image {label} has {len(faces)} face(s); choose 0-{len(faces) - 1}.")
        f = faces[idx]
        emb, aligned = rec.embed(img, f)
        q = assess(aligned, f, None)
        sides.append({
            "faces": [{"index": i, "box": g["box"], "score": g["score"], "crop": b64_jpeg(thumbnail(img, g["box"], 96))}
                      for i, g in enumerate(faces)],
            "selected": idx, "aligned": b64_jpeg(cv2.resize(aligned, (160, 160))), "quality": q,
            "embedding": {"dim": int(emb.size), "norm": round(float(np.linalg.norm(emb)), 4),
                          "preview": [round(float(v), 4) for v in emb[:16]]},
            "_emb": emb})
    thr = float(threshold) if threshold is not None else st.analyzer.recognition_threshold(st.context(False), rec.model_id)
    sim = cosine(sides[0].pop("_emb"), sides[1].pop("_emb"))
    warnings = []
    for label, s in zip("AB", sides):
        if not s["quality"]["suitable_for_matching"]:
            warnings.append(f"Image {label} has low quality for matching: {', '.join(s['quality']['failed'])}.")
    return {
        "model": rec.model_id, "similarity": round(sim, 4), "threshold": thr, "match": sim >= thr,
        "decision": "same person likely" if sim >= thr else "different people likely",
        "note": "Cosine similarity between face embeddings. It is not a probability that the two faces are the same person.",
        "warnings": warnings, "a": sides[0], "b": sides[1],
    }


@router.post("/anonymize")
async def anonymize_image(request: Request, file: UploadFile = File(...), method: str = Form("blur"),
                          strength: float = Form(0.6), faces: str = Form("all"), score_threshold: float | None = Form(None),
                          output_format: str = Form("jpg")):
    rate_limit(request, "infer", 600, 60)
    if method not in METHODS:
        raise HTTPException(400, f"method must be one of {', '.join(METHODS)}")
    img = await read_image(request, file)
    raw = {"preset": "fast", "max_side": 1600}
    if score_threshold is not None:
        raw["score_threshold"] = score_threshold
    st = state(request)
    detected = st.analyzer.detect(img, _opts(request, raw))
    if faces.strip().lower() == "all":
        chosen = list(range(len(detected)))
    elif faces.strip().lower() == "none":
        chosen = []
    else:
        try:
            chosen = sorted({int(x) for x in faces.split(",") if x.strip()})
        except ValueError:
            raise HTTPException(400, "faces must be 'all' or a comma-separated list of face numbers.")
    boxes = [detected[i]["box"] for i in chosen if 0 <= i < len(detected)]
    out = anonymize(img, boxes, method, strength)
    fmt = output_format if output_format in {"jpg", "png", "webp"} else "jpg"
    media = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[fmt]
    return Response(encode(out, fmt), media_type=media, headers={
        "X-Faces-Detected": str(len(detected)), "X-Faces-Anonymized": str(len(boxes)),
        "Cache-Control": "no-store"})


# ------------------------------------------------------------------ liveness
@router.post("/liveness/sessions")
def new_liveness(request: Request):
    for sid in [k for k, s in _liveness.items() if time.time() - s.created > 120]:
        _liveness.pop(sid, None)
    s = L.new_session()
    _liveness[s.id] = s
    return s.public()


@router.get("/liveness/sessions/{sid}")
def get_liveness(sid: str):
    s = _liveness.get(sid)
    if not s:
        raise HTTPException(404, "Unknown or expired liveness session")
    return s.public()


def liveness_session(sid: str) -> L.LivenessSession | None:
    return _liveness.get(sid)


@router.post("/liveness/sessions/{sid}/frame")
async def liveness_frame(sid: str, request: Request, file: UploadFile = File(...), mirrored: bool = Form(False)):
    rate_limit(request, "liveness", 1200, 60)
    s = _liveness.get(sid)
    if not s:
        raise HTTPException(404, "Unknown or expired liveness session")
    img = await read_image(request, file)
    opts = Options.from_dict({"preset": "balanced", "expression": False, "quality": False, "antispoof": True,
                              "overlay": "none"})
    res = _run(request, img, opts)
    L.update(s, res["faces"], mirrored=mirrored)
    return {**s.public(), "faces": [{"box": f["box"], "head_pose": f["analysis"].get("head_pose"),
                                     "eyes": f["analysis"].get("eyes"), "smile": f["analysis"].get("smile"),
                                     "antispoof": f["analysis"].get("antispoof")} for f in res["faces"]]}


@router.post("/liveness/passive")
async def passive_liveness(request: Request, file: UploadFile = File(...)):
    rate_limit(request, "infer", 600, 60)
    img = await read_image(request, file)
    res = _run(request, img, Options.from_dict({"preset": "fast", "antispoof": True}))
    if state(request).hub.antispoof() is None:
        raise HTTPException(503, "The anti-spoofing models are not installed. Install them in the Model Manager.")
    return {"faces": [{"index": f["index"], "box": f["box"], **f["analysis"]["antispoof"]} for f in res["faces"]],
            "note": "A single-image check can be fooled. Use it as one signal alongside the active challenge."}
