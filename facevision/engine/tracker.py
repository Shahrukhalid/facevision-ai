"""Multi-face tracker: greedy IoU association with box smoothing and track expiry.

Track IDs are temporary numbers for faces moving through a video. They are not identities: a person who leaves and
comes back gets a new track ID, and two people can swap IDs if they cross paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def iou(a: list[float], b: list[float]) -> float:
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ix = max(0.0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0))
    iy = max(0.0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    id: int
    box: list[float]
    smooth_box: list[float]
    first_seen: float
    last_seen: float
    last_frame: int
    hits: int = 1
    misses: int = 0
    confirmed: bool = False
    cache: dict = field(default_factory=dict)       # analysis results with the frame they were computed on
    state: dict = field(default_factory=dict)       # temporal state (blinks etc.)


class FaceTracker:
    def __init__(self, iou_threshold: float = 0.25, max_missed_seconds: float = 1.0, min_hits: int = 2,
                 smoothing: float = 0.55):
        self.iou_threshold = iou_threshold
        self.max_missed_seconds = max_missed_seconds
        self.min_hits = min_hits
        self.smoothing = smoothing
        self.tracks: dict[int, Track] = {}
        self._next_id = 1
        self.stats = {"created": 0, "expired": 0, "frames": 0}

    def reset(self):
        self.tracks.clear()

    def update(self, faces: list[dict], frame_idx: int, t: float) -> list[dict]:
        """Assign 'track_id' to each face in place. Returns enter/exit events."""
        self.stats["frames"] += 1
        events: list[dict] = []
        ids = list(self.tracks)
        pairs = []
        for di, f in enumerate(faces):
            for tid in ids:
                tr = self.tracks[tid]
                s = iou(f["box"], tr.box)
                if s < self.iou_threshold:
                    # allow fast motion: centre within half a box of the previous position and similar size
                    fx, fy = f["box"][0] + f["box"][2] / 2, f["box"][1] + f["box"][3] / 2
                    tx, ty = tr.box[0] + tr.box[2] / 2, tr.box[1] + tr.box[3] / 2
                    size_ratio = (f["box"][2] * f["box"][3]) / max(1.0, tr.box[2] * tr.box[3])
                    if np.hypot(fx - tx, fy - ty) < 0.5 * max(tr.box[2], tr.box[3]) and 0.5 < size_ratio < 2.0:
                        s = self.iou_threshold * 0.99
                    else:
                        continue
                pairs.append((s, di, tid))
        pairs.sort(reverse=True)
        used_d, used_t = set(), set()
        for _s, di, tid in pairs:
            if di in used_d or tid in used_t:
                continue
            used_d.add(di)
            used_t.add(tid)
            tr = self.tracks[tid]
            box = faces[di]["box"]
            a = self.smoothing
            tr.smooth_box = [a * n + (1 - a) * o for n, o in zip(box, tr.smooth_box)]
            tr.box = box
            tr.last_seen, tr.last_frame = t, frame_idx
            tr.hits += 1
            tr.misses = 0
            faces[di]["track_id"] = tid
            if not tr.confirmed and tr.hits >= self.min_hits:
                tr.confirmed = True
                events.append({"type": "enter", "track_id": tid, "t": round(tr.first_seen, 3)})
        for di, f in enumerate(faces):
            if di in used_d:
                continue
            tid = self._next_id
            self._next_id += 1
            self.stats["created"] += 1
            self.tracks[tid] = Track(id=tid, box=f["box"], smooth_box=list(f["box"]), first_seen=t, last_seen=t,
                                     last_frame=frame_idx, confirmed=self.min_hits <= 1)
            if self.min_hits <= 1:
                events.append({"type": "enter", "track_id": tid, "t": round(t, 3)})
            f["track_id"] = tid
        for tid in list(self.tracks):
            tr = self.tracks[tid]
            if tid in used_t or tr.last_frame == frame_idx:
                continue
            tr.misses += 1
            if t - tr.last_seen > self.max_missed_seconds:
                if tr.confirmed:
                    events.append({"type": "exit", "track_id": tid, "t": round(tr.last_seen, 3),
                                   "duration": round(tr.last_seen - tr.first_seen, 3)})
                self.stats["expired"] += 1
                del self.tracks[tid]
        for f in faces:
            tr = self.tracks.get(f.get("track_id"))
            if tr:
                f["smooth_box"] = [round(v, 1) for v in tr.smooth_box]
                f["track_confirmed"] = tr.confirmed
        return events

    def flush(self) -> list[dict]:
        events = [{"type": "exit", "track_id": tid, "t": round(tr.last_seen, 3),
                   "duration": round(tr.last_seen - tr.first_seen, 3)}
                  for tid, tr in self.tracks.items() if tr.confirmed]
        self.tracks.clear()
        return events
