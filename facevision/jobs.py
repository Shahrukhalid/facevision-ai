"""Background jobs for video analysis and batch image processing, with progress and cancellation."""

from __future__ import annotations

import csv
import io
import json
import logging
import math
import secrets
import threading
import time
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from .engine.anonymize import anonymize
from .engine.draw import annotate, encode
from .engine.pipeline import LiveSession, Options
from .storage.db import now_iso

if TYPE_CHECKING:
    from .state import AppState

log = logging.getLogger(__name__)
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class Cancelled(Exception):
    pass


def open_video_writer(path_base: Path, fps: float, size: tuple[int, int]) -> tuple[cv2.VideoWriter, Path]:
    """WebM/VP8 plays in browsers; fall back to MPEG-4 when VP8 is unavailable."""
    for fourcc, ext in (("VP80", ".webm"), ("mp4v", ".mp4")):
        p = path_base.with_suffix(ext)
        w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*fourcc), max(1.0, fps), size)
        if w.isOpened():
            return w, p
        w.release()
        p.unlink(missing_ok=True)
    raise RuntimeError("No video encoder is available in this OpenCV build.")


class JobManager:
    def __init__(self, state: "AppState"):
        self.state = state
        self.pool = ThreadPoolExecutor(max_workers=state.config.job_workers, thread_name_prefix="job")
        self._cancel: dict[str, threading.Event] = {}
        self._active_inputs: set[Path] = set()  # uploads still needed by queued or running jobs
        # Jobs interrupted by a restart cannot resume
        state.db.execute("UPDATE jobs SET status='failed', error='Interrupted by a server restart' "
                         "WHERE status IN ('queued','running')")

    # ---------- bookkeeping
    def _row(self, jid: str) -> dict:
        r = self.state.db.one("SELECT * FROM jobs WHERE id=?", (jid,))
        if not r:
            raise KeyError(jid)
        for k in ("options", "result", "outputs"):
            r[k] = json.loads(r[k]) if r[k] else None
        return r

    def get(self, jid: str) -> dict:
        return self._row(jid)

    def list(self, limit: int = 50) -> list[dict]:
        rows = self.state.db.query("SELECT id FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
        out = []
        for r in rows:
            j = self._row(r["id"])
            j.pop("result", None)
            out.append(j)
        return out

    def _update(self, jid: str, **kw):
        sets, vals = [], []
        for k, v in kw.items():
            sets.append(f"{k}=?")
            vals.append(json.dumps(v) if k in {"options", "result", "outputs"} and v is not None else v)
        sets.append("updated_at=?")
        vals.append(now_iso())
        self.state.db.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", (*vals, jid))

    def job_dir(self, jid: str) -> Path:
        d = self.state.config.outputs_dir / jid
        d.mkdir(parents=True, exist_ok=True)
        return d

    def submit(self, kind: str, inputs: list[Path], options: dict, identity_access: bool) -> str:
        jid = time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
        ts = now_iso()
        safe_opts = {**options, "inputs": [p.name.split("__", 1)[-1] for p in inputs],
                     "identity_access": bool(identity_access and (options.get("analysis") or {}).get("recognition"))}
        self.state.db.execute(
            "INSERT INTO jobs(id, kind, status, progress, options, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
            (jid, kind, "queued", 0.0, json.dumps(safe_opts), ts, ts))
        self._cancel[jid] = threading.Event()
        self._active_inputs.update(inputs)
        fn = self._run_video if kind == "video" else self._run_batch
        self.pool.submit(self._wrap, fn, jid, inputs, options, identity_access)
        return jid

    def cancel(self, jid: str) -> None:
        self._row(jid)
        ev = self._cancel.get(jid)
        if ev:
            ev.set()

    def delete(self, jid: str) -> None:
        j = self._row(jid)
        if j["status"] in {"queued", "running"}:
            raise ValueError("Cancel the job before deleting it.")
        import shutil
        shutil.rmtree(self.state.config.outputs_dir / jid, ignore_errors=True)
        self.state.db.execute("DELETE FROM jobs WHERE id=?", (jid,))

    def _wrap(self, fn, jid, inputs, options, identity_access):
        self._update(jid, status="running", message="Starting")
        try:
            result, outputs = fn(jid, inputs, options, identity_access)
            self._update(jid, status="done", progress=1.0, message="Finished", result=result, outputs=outputs)
        except Cancelled:
            self._update(jid, status="cancelled", message="Cancelled")
        except Exception as e:
            log.exception("job %s failed", jid)
            self._update(jid, status="failed", error=str(e), message="Failed")
        finally:
            for p in inputs:
                p.unlink(missing_ok=True)
                self._active_inputs.discard(p)
            self._cancel.pop(jid, None)

    def active(self) -> tuple[set[str], set[Path]]:
        """Ids of queued/running jobs and the upload files they still need (clear_cache must keep these)."""
        return set(self._cancel), set(self._active_inputs)

    def _check(self, jid: str):
        ev = self._cancel.get(jid)
        if ev and ev.is_set():
            raise Cancelled()

    # ---------- video
    def _run_video(self, jid: str, inputs: list[Path], options: dict, identity_access: bool):
        src = inputs[0]
        opts = Options.from_dict(options.get("analysis"))
        anon = options.get("anonymize")  # {"method": ..., "strength": ...} or None
        sample_every = max(1, int(options.get("sample_every", 1)))
        if anon:
            sample_every = 1  # every frame must be checked or faces would be missed
        export_video = bool(options.get("export_video", True))
        ctx = self.state.context(identity_access and opts.recognition)
        cap = cv2.VideoCapture(str(src))
        if not cap.isOpened():
            raise ValueError("Could not open the video. Supported: MP4, MOV, AVI, MKV, WebM (codec support depends on OpenCV).")
        fps = safe_fps(cap.get(cv2.CAP_PROP_FPS))
        n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        total = int(n_frames) if math.isfinite(n_frames) and n_frames > 0 else 0
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out_dir = self.job_dir(jid)
        # The writer is opened on the first frame: decoded frames can differ from the container's reported size
        # (rotation metadata), and VideoWriter silently drops frames of the wrong size.
        writer, video_path = None, None
        session = LiveSession(self.state.analyzer)
        session.tracker.max_missed_seconds = max(1.0, 3 * sample_every / fps)
        events, samples = [], []
        tracks: dict[int, dict] = {}
        last = {"faces": []}
        idx = 0
        t_start = time.perf_counter()
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                t_video = idx / fps
                if idx % sample_every == 0:
                    self._check(jid)
                    last = session.process(frame, opts, ctx, t=t_video)
                    for e in last["events"]:
                        events.append({**e, "frame": idx})
                    for f in last["faces"]:
                        tid = f.get("track_id")
                        if tid is None:
                            continue
                        tr = tracks.setdefault(tid, {"track_id": tid, "first_seen_s": round(t_video, 3), "frames": 0,
                                                     "max_score": 0.0, "names": Counter(), "expressions": Counter()})
                        tr["last_seen_s"] = round(t_video, 3)
                        tr["frames"] += 1
                        tr["max_score"] = max(tr["max_score"], f["score"])
                        rec = f.get("recognition") or {}
                        if rec.get("status") == "match":
                            tr["names"][rec["name"]] += 1
                        ex = f.get("analysis", {}).get("expression")
                        if ex:
                            tr["expressions"][ex["label"]] += 1
                    samples.append({"frame": idx, "t": round(t_video, 3), "face_count": last["face_count"],
                                    "faces": [{"track_id": f.get("track_id"), "box": f["box"], "score": f["score"],
                                               "recognition": (f.get("recognition") or {}).get("status")}
                                              for f in last["faces"]]})
                if export_video and writer is None:
                    w, h = frame.shape[1], frame.shape[0]
                    writer, video_path = open_video_writer(out_dir / "annotated", fps, (w, h))
                if writer is not None:
                    if anon:
                        out = anonymize(frame, [f["box"] for f in last["faces"]], anon.get("method", "blur"),
                                        float(anon.get("strength", 0.6)))
                    else:
                        out = annotate(frame, last, draw_landmarks=opts.overlay != "none")
                    writer.write(out)
                idx += 1
                if idx % 10 == 0:
                    self._update(jid, progress=round(idx / total, 4) if total else 0.0,
                                 message=f"Frame {idx}" + (f" of {total}" if total else ""))
        finally:
            cap.release()
            if writer is not None:
                writer.release()
        for e in session.tracker.flush():
            events.append({**e, "frame": idx})
        elapsed = time.perf_counter() - t_start
        track_list = []
        for tr in tracks.values():
            names = tr.pop("names")
            exprs = tr.pop("expressions")
            tr["duration_s"] = round(tr["last_seen_s"] - tr["first_seen_s"], 3)
            if names:
                tr["recognized_as"] = names.most_common(1)[0][0]
            if exprs:
                tr["most_common_expression"] = exprs.most_common(1)[0][0]
            track_list.append(tr)
        summary = {
            "source": src.name.split("__", 1)[-1], "frames": idx, "fps": round(fps, 2), "width": w, "height": h,
            "duration_s": round(idx / fps, 2), "sample_every": sample_every,
            "processed_frames": len(samples), "processing_seconds": round(elapsed, 2),
            "processing_fps": round(len(samples) / elapsed, 2) if elapsed else None,
            "max_faces_in_frame": max((s["face_count"] for s in samples), default=0),
            "tracks": len(track_list), "anonymized": bool(anon), "options": options,
        }
        result = {"summary": summary, "events": events, "tracks": track_list, "samples": samples}
        outputs = self._write_reports(out_dir, result, kind="video")
        if video_path is not None:
            outputs["video"] = video_path.name
        return {"summary": summary, "events": events[:500], "tracks": track_list}, outputs

    # ---------- batch
    def _run_batch(self, jid: str, inputs: list[Path], options: dict, identity_access: bool):
        mode = options.get("mode", "analyze")
        opts = Options.from_dict(options.get("analysis"))
        anon = options.get("anonymize") or {"method": "blur", "strength": 0.6}
        concurrency = max(1, min(4, int(options.get("concurrency", 2))))
        ctx = self.state.context(identity_access and opts.recognition)
        out_dir = self.job_dir(jid)
        zbuf = out_dir / "outputs.zip"
        rows, done = [], 0
        used_names: set[str] = set()
        lock = threading.Lock()
        t0 = time.perf_counter()

        def work(path: Path):
            self._check(jid)
            name = path.name.split("__", 1)[-1]
            img = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if img is None:
                return name, {"file": name, "error": "Not a readable image"}, None
            res = self.state.analyzer.analyze_image(img, opts if mode == "analyze" else Options.from_dict(
                {"preset": "fast", "score_threshold": opts.score_threshold, "max_side": max(opts.max_side, 960)}), ctx)
            if mode == "anonymize":
                out = anonymize(img, [f["box"] for f in res["faces"]], anon.get("method", "blur"), float(anon.get("strength", 0.6)))
            else:
                out = annotate(img, res)
            row = {"file": name, "faces": res["face_count"], "ms": res["timings_ms"]["total"], "result": res}
            return name, row, encode(out, "jpg")

        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z, ThreadPoolExecutor(concurrency) as ex:
            for name, row, data in ex.map(work, inputs):
                with lock:
                    rows.append(row)
                    if data:
                        stem = Path(name).stem
                        z.writestr(unique_name(f"{stem}_{'anonymized' if mode == 'anonymize' else 'annotated'}.jpg",
                                               used_names), data)
                    done += 1
                    self._update(jid, progress=round(done / len(inputs), 4), message=f"{done} of {len(inputs)} files")
        elapsed = time.perf_counter() - t0
        summary = {"files": len(inputs), "succeeded": sum(1 for r in rows if "error" not in r),
                   "failed": sum(1 for r in rows if "error" in r), "faces": sum(r.get("faces", 0) for r in rows),
                   "mode": mode, "processing_seconds": round(elapsed, 2), "concurrency": concurrency}
        result = {"summary": summary, "files": rows}
        outputs = self._write_reports(out_dir, result, kind="batch")
        outputs["zip"] = zbuf.name
        brief = [{k: v for k, v in r.items() if k != "result"} for r in rows]
        return {"summary": summary, "files": brief}, outputs

    # ---------- reports
    def _write_reports(self, out_dir: Path, result: dict, kind: str) -> dict:
        (out_dir / "report.json").write_text(json.dumps(result, indent=1, default=str))
        buf = io.StringIO()
        w = csv.writer(buf)
        if kind == "video":
            w.writerow(["track_id", "first_seen_s", "last_seen_s", "duration_s", "frames", "max_score",
                        "recognized_as", "most_common_expression"])
            for t in result["tracks"]:
                w.writerow([t["track_id"], t["first_seen_s"], t["last_seen_s"], t["duration_s"], t["frames"],
                            round(t["max_score"], 3), csv_safe(t.get("recognized_as", "")),
                            t.get("most_common_expression", "")])
            w.writerow([])
            w.writerow(["event", "track_id", "t_seconds", "frame"])
            for e in result["events"]:
                w.writerow([e["type"], e["track_id"], e["t"], e["frame"]])
        else:
            w.writerow(["file", "faces", "processing_ms", "error"])
            for r in result["files"]:
                w.writerow([csv_safe(r["file"]), r.get("faces", ""), r.get("ms", ""), r.get("error", "")])
        (out_dir / "report.csv").write_text(buf.getvalue())
        s = result["summary"]
        lines = [f"FaceVision AI {kind} report", f"Created: {now_iso()}", ""]
        lines += [f"{k}: {v}" for k, v in s.items() if k != "options"]
        lines += ["", "Estimates (age, expression, attributes) are model outputs with uncertainty, not facts.",
                  "Track IDs are temporary and do not identify anyone."]
        (out_dir / "summary.txt").write_text("\n".join(lines) + "\n")
        return {"json": "report.json", "csv": "report.csv", "summary": "summary.txt"}


def read_image_bytes(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    try:
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except cv2.error:  # e.g. above OPENCV_IO_MAX_IMAGE_PIXELS (see facevision/__init__.py)
        img = None
    if img is None:
        raise ValueError("The file is not a supported image (JPG, PNG, WebP or BMP up to 50 megapixels).")
    return img


def safe_fps(value: float | None, default: float = 25.0) -> float:
    """Containers often report 0, NaN or nonsense (e.g. 1000 for WebM from MediaRecorder) as the frame rate."""
    try:
        v = float(value or 0.0)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) and 0.5 <= v <= 240.0 else default


def unique_name(name: str, used: set[str]) -> str:
    """Return name, or name with a numeric suffix, so that it is not in used; records the result in used."""
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    candidate, n = name, 1
    while candidate.lower() in used:
        n += 1
        candidate = f"{stem}-{n}.{ext}" if dot else f"{stem}-{n}"
    used.add(candidate.lower())
    return candidate


def csv_safe(value):
    """Neutralise spreadsheet formulas in text cells (CSV injection); numbers are left as they are."""
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        try:
            float(value)
        except ValueError:
            return "'" + value
    return value
