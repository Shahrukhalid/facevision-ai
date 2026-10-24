"""WebSocket endpoints for live processing.

/ws/live    The browser captures the camera (getUserMedia) and sends JPEG frames; the server replies with JSON results.
            Nothing is stored. The client sends the next frame only after receiving a result (natural backpressure).
/ws/source  Experimental: the server opens a local camera index or an RTSP/HTTP stream itself and streams frames and
            results back. Useful for IP cameras.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from ..engine import liveness as L
from ..engine.pipeline import LiveSession, Options
from .deps import SESSION_COOKIE
from .routes_core import liveness_session

log = logging.getLogger(__name__)
router = APIRouter()
MAX_FRAME_BYTES = 8 * 1024 * 1024


def _ws_signed_in(ws: WebSocket) -> bool:
    st = ws.app.state.fv
    return st.vault.check_session(ws.cookies.get(SESSION_COOKIE))


@router.websocket("/ws/live")
async def live(ws: WebSocket):
    await ws.accept()
    st = ws.app.state.fv
    session = LiveSession(st.analyzer)
    opts = Options.from_dict({"preset": st.settings().get("preset", "balanced")})
    mirrored = False
    liveness_id = None
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("text") is not None:
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "message": "Invalid JSON"})
                    continue
                if data.get("type") == "options":
                    raw = dict(data.get("options") or {})
                    raw.setdefault("score_threshold", st.settings()["detection_threshold"])
                    opts = Options.from_dict(raw)
                    mirrored = bool(data.get("mirrored", False))
                    liveness_id = data.get("liveness_session")
                    if data.get("reset_tracking"):
                        session.tracker.reset()
                    await ws.send_json({"type": "options", "options": opts.__dict__})
                continue
            frame = msg.get("bytes")
            if not frame:
                continue
            if len(frame) > MAX_FRAME_BYTES:
                await ws.send_json({"type": "error", "message": "Frame too large"})
                continue
            img = cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                await ws.send_json({"type": "error", "message": "Could not decode frame"})
                continue
            ctx = st.context(_ws_signed_in(ws))
            local_opts = opts
            ls = liveness_session(liveness_id) if liveness_id else None
            if ls is not None:
                local_opts = Options.from_dict({**opts.__dict__, "landmarks": True, "antispoof": True})
            try:
                result = await run_in_threadpool(session.process, img, local_opts, ctx)
            except RuntimeError as e:
                await ws.send_json({"type": "error", "message": str(e)})
                continue
            if ls is not None:
                L.update(ls, result["faces"], mirrored=mirrored)
                result["liveness"] = ls.public()
            result["type"] = "result"
            await ws.send_text(json.dumps(result, default=float))
    except WebSocketDisconnect:
        pass
    except Exception:  # pragma: no cover
        log.exception("live websocket error")


_SOURCE_RE = re.compile(r"^(\d{1,2}|rtsps?://\S+|https?://\S+)$")


@router.websocket("/ws/source")
async def source(ws: WebSocket):
    await ws.accept()
    st = ws.app.state.fv
    if st.vault.configured and not _ws_signed_in(ws):
        await ws.send_json({"type": "error", "message": "Sign in to open server-side camera or stream sources."})
        await ws.close()
        return
    stop = asyncio.Event()
    opts_box = {"opts": Options.from_dict({"preset": "balanced"})}
    task = None

    async def pump(src: str):
        cap = await run_in_threadpool(cv2.VideoCapture, int(src) if src.isdigit() else src)
        if not cap.isOpened():
            await ws.send_json({"type": "error", "message": f"Could not open source {src}."})
            return
        session = LiveSession(st.analyzer)
        await ws.send_json({"type": "started", "source": src})
        try:
            while not stop.is_set():
                ok, frame = await run_in_threadpool(cap.read)
                if not ok:
                    await ws.send_json({"type": "ended"})
                    break
                h, w = frame.shape[:2]
                if max(h, w) > 1280:
                    k = 1280 / max(h, w)
                    frame = cv2.resize(frame, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
                ctx = st.context(_ws_signed_in(ws))
                result = await run_in_threadpool(session.process, frame, opts_box["opts"], ctx)
                result["type"] = "result"
                ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                await ws.send_text(json.dumps(result, default=float))
                await ws.send_bytes(jpg.tobytes())
                await asyncio.sleep(0)
        finally:
            cap.release()

    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "start":
                src = str(data.get("source", "")).strip()
                if not _SOURCE_RE.match(src):
                    await ws.send_json({"type": "error", "message": "Use a camera number (0-99) or an rtsp:// or http(s):// stream URL."})
                    continue
                if task and not task.done():
                    stop.set()
                    await task
                stop.clear()
                task = asyncio.create_task(pump(src))
            elif data.get("type") == "options":
                opts_box["opts"] = Options.from_dict(data.get("options") or {})
            elif data.get("type") == "stop":
                stop.set()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        stop.set()
        if task:
            try:
                await asyncio.wait_for(task, 5)
            except Exception:
                pass
