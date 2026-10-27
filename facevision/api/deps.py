"""Shared FastAPI dependencies: state access, authentication, rate limits and upload handling."""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile

from .. import MAX_IMAGE_PIXELS
from ..jobs import read_image_bytes
from ..state import AppState

SESSION_COOKIE = "fv_session"


def state(request: Request) -> AppState:
    return request.app.state.fv


def client_id(request: Request) -> str:
    return request.client.host if request.client else "local"


def is_signed_in(request: Request) -> bool:
    st = state(request)
    token = request.cookies.get(SESSION_COOKIE)
    if st.vault.check_session(token):
        return True
    key = request.headers.get("x-api-key")
    auth = request.headers.get("authorization", "")
    if not key and auth.lower().startswith("bearer "):
        key = auth[7:].strip()
    if key:
        try:
            return st.vault.check_api_key(key)
        except Exception:
            return False
    return False


def require_identity(request: Request) -> AppState:
    """Biometric endpoints: a signed-in session or a valid API key."""
    st = state(request)
    if not st.vault.configured:
        raise HTTPException(403, "Set an access passphrase in Settings before using face recognition.")
    if not is_signed_in(request):
        raise HTTPException(401, "Sign in to use face recognition and enrolled faces.")
    return st


def require_admin(request: Request) -> AppState:
    """Configuration changes: allowed freely until a passphrase exists, then only when signed in."""
    st = state(request)
    if st.vault.configured and not is_signed_in(request):
        raise HTTPException(401, "Sign in to change settings.")
    return st


def rate_limit(request: Request, bucket: str, per_min: float, burst: float) -> None:
    if not state(request).limiter.allow(client_id(request), bucket, per_min, burst):
        raise HTTPException(429, "Too many requests. Wait a moment and try again.")


async def read_upload(file: UploadFile, max_mb: int) -> bytes:
    limit = max_mb * 1024 * 1024
    data = bytearray()
    while True:
        chunk = await file.read(1 << 20)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(413, f"{file.filename or 'File'} is larger than the {max_mb} MB limit.")
    if not data:
        raise HTTPException(400, f"{file.filename or 'File'} is empty.")
    return bytes(data)


async def read_image(request: Request, file: UploadFile):
    st = state(request)
    data = await read_upload(file, st.config.max_image_mb)
    try:
        img = read_image_bytes(data)
    except ValueError as e:
        raise HTTPException(415, str(e))
    h, w = img.shape[:2]
    if h * w > MAX_IMAGE_PIXELS:
        raise HTTPException(413, "Images above 50 megapixels are not supported.")
    return img


def safe_filename(filename: str | None, default: str = "upload") -> str:
    """Base name only (either slash style), without control or reserved characters, at most 120 characters."""
    name = re.split(r"[\\/]", filename or "")[-1]
    name = re.sub(r"[^\w.\- ()+,]", "_", name).strip(" .")
    return name[-120:] or default


async def save_upload(request: Request, file: UploadFile, max_mb: int, allowed_ext: set[str]) -> Path:
    st = state(request)
    name = safe_filename(file.filename)
    ext = Path(name).suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(415, f"{name}: unsupported file type. Allowed: {', '.join(sorted(allowed_ext))}")
    dest = st.config.uploads_dir / f"{secrets.token_hex(8)}__{name}"
    limit, size = max_mb * 1024 * 1024, 0
    with open(dest, "wb") as out:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"{name} is larger than the {max_mb} MB limit.")
            out.write(chunk)
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, f"{name} is empty.")
    return dest


def parse_json_field(value: str | None, name: str) -> dict:
    if not value:
        return {}
    try:
        v = json.loads(value)
    except json.JSONDecodeError:
        raise HTTPException(400, f"{name} must be valid JSON.")
    if not isinstance(v, dict):
        raise HTTPException(400, f"{name} must be a JSON object.")
    return v
