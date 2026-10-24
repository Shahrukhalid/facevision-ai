"""Access control, consented enrolment, recognition, verification and data management."""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from ..engine.draw import thumbnail
from ..engine.pipeline import Options
from ..engine.quality import assess
from ..security import SESSION_IDLE_SECONDS, AuthError
from ..storage.db import now_iso
from .deps import SESSION_COOKIE, client_id, is_signed_in, rate_limit, read_image, require_identity, state
from .routes_core import b64_jpeg

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------ auth
class PassBody(BaseModel):
    passphrase: str


class ChangePassBody(BaseModel):
    old_passphrase: str
    new_passphrase: str


class ConfirmBody(BaseModel):
    confirm: str


def _set_cookie(resp: Response, token: str, request: Request):
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict", max_age=SESSION_IDLE_SECONDS,
                    secure=request.url.scheme == "https", path="/")


@router.get("/auth/status")
def auth_status(request: Request):
    st = state(request)
    return {"configured": st.vault.configured, "signed_in": is_signed_in(request)}


@router.post("/auth/setup")
def auth_setup(body: PassBody, request: Request):
    rate_limit(request, "auth", 10, 5)
    st = state(request)
    try:
        api_key = st.vault.setup(body.passphrase)
        token = st.vault.login(body.passphrase)
    except AuthError as e:
        raise HTTPException(400, str(e))
    resp = JSONResponse({"configured": True, "signed_in": True, "api_key": api_key,
                         "note": "Store the API key somewhere safe. It is shown only once."})
    _set_cookie(resp, token, request)
    return resp


@router.post("/auth/login")
def auth_login(body: PassBody, request: Request):
    rate_limit(request, "auth", 10, 5)
    st = state(request)
    try:
        token = st.vault.login(body.passphrase)
    except AuthError as e:
        st.db.audit("auth.login_failed", client_id(request))
        raise HTTPException(401, str(e))
    st.db.audit("auth.login", client_id(request))
    resp = JSONResponse({"configured": True, "signed_in": True})
    _set_cookie(resp, token, request)
    return resp


@router.post("/auth/logout")
def auth_logout(request: Request):
    state(request).vault.logout(request.cookies.get(SESSION_COOKIE))
    resp = JSONResponse({"signed_in": False})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.post("/auth/change-passphrase")
def change_passphrase(body: ChangePassBody, request: Request):
    rate_limit(request, "auth", 10, 5)
    st = require_identity(request)
    try:
        st.vault.change_passphrase(body.old_passphrase, body.new_passphrase)
    except AuthError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.post("/auth/api-key/rotate")
def rotate_key(request: Request):
    st = require_identity(request)
    return {"api_key": st.vault.rotate_api_key(), "note": "The previous key no longer works."}


@router.post("/auth/reset")
def auth_reset(body: ConfirmBody, request: Request):
    """Forgotten passphrase: permanently deletes every enrolled person and template, then the credentials."""
    rate_limit(request, "auth", 10, 5)
    if body.confirm != "DELETE ALL ENROLLED FACES":
        raise HTTPException(400, "Type DELETE ALL ENROLLED FACES to confirm.")
    st = state(request)
    n = st.identities.delete_all()
    st.vault.reset()
    return {"deleted_people": n, "configured": False}


# ------------------------------------------------------------------ people
class PersonBody(BaseModel):
    name: str
    consent_confirmed: bool
    consent_note: str = ""
    external_id: str = ""
    notes: str = ""


class PersonPatch(BaseModel):
    name: str | None = None
    external_id: str | None = None
    notes: str | None = None
    consent_note: str | None = None


@router.get("/persons")
def list_persons(request: Request):
    st = require_identity(request)
    return st.identities.list_persons()


@router.post("/persons")
def create_person(body: PersonBody, request: Request):
    st = require_identity(request)
    try:
        return st.identities.create_person(body.name, body.consent_confirmed, body.consent_note, body.external_id,
                                           body.notes)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/persons/{pid}")
def get_person(pid: int, request: Request):
    st = require_identity(request)
    try:
        return st.identities.get_person(pid)
    except KeyError:
        raise HTTPException(404, "Person not found")


@router.patch("/persons/{pid}")
def patch_person(pid: int, body: PersonPatch, request: Request):
    st = require_identity(request)
    try:
        return st.identities.update_person(pid, **body.model_dump())
    except KeyError:
        raise HTTPException(404, "Person not found")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/persons/{pid}")
def delete_person(pid: int, request: Request):
    st = require_identity(request)
    try:
        st.identities.delete_person(pid)
    except KeyError:
        raise HTTPException(404, "Person not found")
    return {"deleted": pid, "note": "The person and all of their face templates were permanently deleted."}


async def _enroll_images(request: Request, pid: int, files: list[UploadFile], allow_low_quality: bool) -> dict:
    st = state(request)
    rec = st.hub.recognizer(st.settings().get("recognizer", "sface"))
    if rec is None:
        raise HTTPException(503, "No face recognizer is installed. Install SFace in the Model Manager.")
    thr = st.analyzer.recognition_threshold(st.context(True), rec.model_id)
    existing_embs, existing_pids = st.identities.gallery(rec.model_id)
    own = existing_embs[existing_pids == pid] if len(existing_pids) else np.zeros((0, rec.dim), np.float32)
    results, added = [], 0
    for file in files:
        name = Path(file.filename or "image").name
        try:
            img = await read_image(request, file)
        except HTTPException as e:
            results.append({"file": name, "added": False, "reason": e.detail})
            continue
        faces = st.analyzer.detect(img, Options.from_dict({"preset": "fast", "max_side": 1280,
                                                           "score_threshold": st.settings()["detection_threshold"]}))
        if len(faces) != 1:
            results.append({"file": name, "added": False,
                            "reason": "No face found." if not faces else f"{len(faces)} faces found; use photos with exactly one face."})
            continue
        f = faces[0]
        emb, aligned = rec.embed(img, f)
        q = assess(aligned, f, None)
        entry = {"file": name, "quality": q, "crop": b64_jpeg(thumbnail(img, f["box"], 112))}
        if not q["suitable_for_matching"] and not allow_low_quality:
            results.append({**entry, "added": False, "reason": "Low quality: " + ", ".join(q["failed"])})
            continue
        warnings = []
        m = st.identities.match(rec.model_id, emb, thr, exclude_person=pid)
        if m["candidates"] and m["candidates"][0]["similarity"] >= thr:
            c = m["candidates"][0]
            warnings.append(f"Possible duplicate: this face matches {c['name']} (similarity {c['similarity']:.2f}).")
        if len(own):
            consistency = float(np.max(own @ emb))
            entry["similarity_to_existing"] = round(consistency, 4)
            if consistency < thr:
                warnings.append("This photo does not match this person's other photos. Check it is the same person.")
        tid = st.identities.add_template(pid, rec.model_id, emb, q["score"], "upload")
        own = np.vstack([own, emb[None]]) if len(own) else emb[None]
        added += 1
        results.append({**entry, "added": True, "template_id": tid, "warnings": warnings})
    return {"person": st.identities.get_person(pid), "added": added, "results": results, "model": rec.model_id}


@router.post("/persons/{pid}/templates")
async def add_templates(pid: int, request: Request, files: list[UploadFile] = File(...),
                        allow_low_quality: bool = Form(False)):
    st = require_identity(request)
    rate_limit(request, "enroll", 120, 30)
    try:
        st.identities.get_person(pid)
    except KeyError:
        raise HTTPException(404, "Person not found")
    if len(files) > 20:
        raise HTTPException(400, "Upload at most 20 photos at a time.")
    return await _enroll_images(request, pid, files, allow_low_quality)


@router.delete("/persons/{pid}/templates/{tid}")
def delete_template(pid: int, tid: int, request: Request):
    st = require_identity(request)
    try:
        st.identities.delete_template(pid, tid)
    except KeyError:
        raise HTTPException(404, "Template not found")
    return {"deleted": tid}


@router.post("/enroll")
async def enroll(request: Request, name: str = Form(...), consent_confirmed: bool = Form(False),
                 consent_note: str = Form(""), files: list[UploadFile] = File(...),
                 allow_low_quality: bool = Form(False)):
    """Create a person and add photos in one call (API convenience)."""
    st = require_identity(request)
    rate_limit(request, "enroll", 120, 30)
    try:
        person = st.identities.create_person(name, consent_confirmed, consent_note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    result = await _enroll_images(request, person["id"], files, allow_low_quality)
    if result["added"] == 0:
        st.identities.delete_person(person["id"])
        result["person"] = None
        result["note"] = "No usable photo was found, so the person was not created."
    return result


# ------------------------------------------------------------------ recognition
@router.post("/recognize")
async def recognize(request: Request, file: UploadFile = File(...), threshold: float | None = Form(None)):
    st = require_identity(request)
    rate_limit(request, "infer", 600, 60)
    img = await read_image(request, file)
    ctx = st.context(True)
    if threshold is not None:
        rid = st.settings().get("recognizer", "sface")
        ctx.settings = {**ctx.settings, "recognition_thresholds": {**ctx.settings.get("recognition_thresholds", {}), rid: threshold}}
    res = st.analyzer.analyze_image(img, Options.from_dict({"preset": "fast", "recognition": True, "quality": True,
                                                            "max_side": 1280}), ctx)
    return {"face_count": res["face_count"], "faces": [
        {"index": f["index"], "box": f["box"], "score": f["score"], "recognition": f.get("recognition"),
         "quality": f["analysis"].get("quality")} for f in res["faces"]], "timings_ms": res["timings_ms"]}


@router.post("/verify")
async def verify(request: Request, file: UploadFile = File(...), person_id: int = Form(...),
                 threshold: float | None = Form(None)):
    """One-to-one: does the largest face in the photo match this enrolled person?"""
    st = require_identity(request)
    rate_limit(request, "infer", 600, 60)
    try:
        person = st.identities.get_person(person_id)
    except KeyError:
        raise HTTPException(404, "Person not found")
    rec = st.hub.recognizer(st.settings().get("recognizer", "sface"))
    if rec is None:
        raise HTTPException(503, "No face recognizer is installed.")
    img = await read_image(request, file)
    faces = st.analyzer.detect(img, Options.from_dict({"preset": "fast", "max_side": 1280}))
    if not faces:
        raise HTTPException(422, "No face found in the photo.")
    f = faces[0]
    emb, aligned = rec.embed(img, f)
    embs, pids = st.identities.gallery(rec.model_id)
    own = embs[pids == person_id] if len(pids) else np.zeros((0, rec.dim))
    if not len(own):
        raise HTTPException(409, f"{person['name']} has no templates for the active recognizer ({rec.model_id}).")
    thr = float(threshold) if threshold is not None else st.analyzer.recognition_threshold(st.context(True), rec.model_id)
    sim = float(np.max(own @ emb))
    q = assess(aligned, f, None)
    return {"person_id": person_id, "name": person["name"], "similarity": round(sim, 4), "threshold": thr,
            "verified": sim >= thr and q["suitable_for_matching"], "quality": q, "model": rec.model_id,
            "note": "Similarity is not a probability. Low-quality photos are never verified."}


# ------------------------------------------------------------------ data management
@router.get("/data/summary")
def data_summary(request: Request):
    st = state(request)
    counts = st.db.one("SELECT (SELECT COUNT(*) FROM persons) AS persons, (SELECT COUNT(*) FROM templates) AS templates, "
                       "(SELECT COUNT(*) FROM jobs) AS jobs, (SELECT COUNT(*) FROM audit) AS audit_entries")
    return {**counts, "disk": st.disk_usage(), "data_dir": str(st.config.data_dir),
            "retention_days": st.settings().get("keep_job_outputs_days")}


@router.post("/data/clear-cache")
def clear_cache(request: Request):
    st = state(request)
    if st.vault.configured and not is_signed_in(request):
        raise HTTPException(401, "Sign in to clear processing files.")
    return st.clear_cache()


@router.get("/data/export")
def export_metadata(request: Request):
    """Everything except face templates and images, as JSON."""
    st = require_identity(request)
    persons = st.identities.list_persons()
    st.db.audit("data.exported", "metadata")
    payload = {"exported_at": now_iso(), "settings": st.settings(), "persons": persons,
               "jobs": st.db.query("SELECT id, kind, status, created_at, updated_at FROM jobs"),
               "audit": st.db.query("SELECT at, action, detail FROM audit ORDER BY id"),
               "note": "Face templates are not included. Use Backup for a restorable copy."}
    return Response(json.dumps(payload, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="facevision-export.json"'})


@router.get("/data/backup")
def backup(request: Request):
    """A consistent copy of the database. Templates stay encrypted; restoring needs the same passphrase."""
    st = require_identity(request)
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "facevision.db"
        src = sqlite3.connect(str(st.config.db_path))
        dst = sqlite3.connect(str(snap))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "facevision.db")
            z.writestr("README.txt", "FaceVision AI backup\n\nTo restore: stop FaceVision AI and replace facevision.db "
                       "in your data folder with this file.\nFace templates in it are encrypted and can only be "
                       "used after signing in with the passphrase that was active when the backup was made.\n")
    st.db.audit("data.backup")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="facevision-backup.zip"'})


@router.post("/data/delete-biometrics")
def delete_biometrics(body: ConfirmBody, request: Request):
    st = require_identity(request)
    if body.confirm != "DELETE":
        raise HTTPException(400, "Type DELETE to confirm.")
    return {"deleted_people": st.identities.delete_all()}


@router.post("/data/delete-all")
def delete_all(body: ConfirmBody, request: Request):
    """Factory reset: people, templates, jobs, outputs, settings and credentials. Installed models are kept."""
    st = require_identity(request)
    if body.confirm != "DELETE EVERYTHING":
        raise HTTPException(400, "Type DELETE EVERYTHING to confirm.")
    n = st.identities.delete_all()
    st.clear_cache()
    st.db.execute("DELETE FROM jobs")
    st.db.execute("DELETE FROM settings WHERE key='app'")
    st.db.execute("DELETE FROM audit")
    st.vault.reset()
    st.db.vacuum()
    resp = JSONResponse({"deleted_people": n, "configured": False})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.get("/audit")
def audit(request: Request, limit: int = 200):
    st = require_identity(request)
    return st.db.query("SELECT at, action, detail FROM audit ORDER BY id DESC LIMIT ?", (min(1000, max(1, limit)),))
