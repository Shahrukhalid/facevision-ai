"""Video and batch jobs."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from ..jobs import IMAGE_EXTS, VIDEO_EXTS, job_identity_access
from .deps import is_signed_in, parse_json_field, rate_limit, save_upload, state

router = APIRouter(prefix="/api/jobs")
MEDIA = {".json": "application/json", ".csv": "text/csv", ".txt": "text/plain", ".zip": "application/zip",
         ".webm": "video/webm", ".mp4": "video/mp4"}


def _job(request: Request, jid: str) -> dict:
    """Look up a job. Jobs that recognised enrolled people contain names, so they need a signed-in session or
    API key, like the other biometric endpoints."""
    st = state(request)
    try:
        job = st.jobs.get(jid)
    except KeyError:
        raise HTTPException(404, "Job not found")
    if job_identity_access(job.get("options")) and not is_signed_in(request):
        raise HTTPException(401, "This job recognised enrolled faces. Sign in to see it.")
    return job


@router.get("")
def list_jobs(request: Request):
    return state(request).jobs.list()


@router.post("/video")
async def video_job(request: Request, file: UploadFile = File(...), options: str | None = Form(None)):
    rate_limit(request, "jobs", 30, 10)
    st = state(request)
    opts = parse_json_field(options, "options")
    if (opts.get("analysis") or {}).get("recognition") and not is_signed_in(request):
        raise HTTPException(401, "Sign in to recognise enrolled faces in videos.")
    path = await save_upload(request, file, st.config.max_video_mb, VIDEO_EXTS)
    try:
        jid = st.jobs.submit("video", [path], opts, is_signed_in(request))
    except BaseException:
        path.unlink(missing_ok=True)
        st.jobs.release_upload(path)
        raise
    return st.jobs.get(jid)


@router.post("/batch")
async def batch_job(request: Request, files: list[UploadFile] = File(...), options: str | None = Form(None)):
    rate_limit(request, "jobs", 30, 10)
    st = state(request)
    if len(files) > st.config.max_batch_files:
        raise HTTPException(400, f"Upload at most {st.config.max_batch_files} files per batch.")
    opts = parse_json_field(options, "options")
    if (opts.get("analysis") or {}).get("recognition") and not is_signed_in(request):
        raise HTTPException(401, "Sign in to recognise enrolled faces.")
    paths = []
    total_mb = 0.0
    try:
        for f in files:
            p = await save_upload(request, f, st.config.max_image_mb, IMAGE_EXTS)
            paths.append(p)
            total_mb += p.stat().st_size / 1e6
            if total_mb > st.config.max_image_mb * 25:
                raise HTTPException(413, f"A batch can hold at most {st.config.max_image_mb * 25} MB.")
        jid = st.jobs.submit("batch", paths, opts, is_signed_in(request))
    except BaseException:
        for p in paths:
            p.unlink(missing_ok=True)
            st.jobs.release_upload(p)
        raise
    return st.jobs.get(jid)


@router.get("/{jid}")
def get_job(jid: str, request: Request):
    return _job(request, jid)


@router.post("/{jid}/cancel")
def cancel_job(jid: str, request: Request):
    st = state(request)
    _job(request, jid)
    try:
        st.jobs.cancel(jid)
    except KeyError:
        raise HTTPException(404, "Job not found")
    return st.jobs.get(jid)


@router.delete("/{jid}")
def delete_job(jid: str, request: Request):
    _job(request, jid)
    try:
        state(request).jobs.delete(jid)
    except KeyError:
        raise HTTPException(404, "Job not found")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"deleted": jid}


@router.get("/{jid}/files/{name}")
def job_file(jid: str, name: str, request: Request, download: bool = False):
    st = state(request)
    job = _job(request, jid)
    allowed = set((job.get("outputs") or {}).values())
    if name not in allowed:
        raise HTTPException(404, "File not found")
    path = (st.config.outputs_dir / jid / name).resolve()
    if st.config.outputs_dir.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type=MEDIA.get(Path(name).suffix, "application/octet-stream"),
                        filename=f"{jid}-{name}" if download else None)
