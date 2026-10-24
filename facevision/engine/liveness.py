"""Active liveness checks: a random sequence of challenges (blink, turn, smile) answered on camera.

What it does: it confirms that a single face responded to randomly chosen prompts in real time, which defeats a
still photograph and simple pre-recorded videos. What it does not do: it cannot reliably stop a skilled attacker
with a mask, a deepfake driven in real time, or a replay that happens to follow the prompts. See docs/LIVENESS.md.
"""

from __future__ import annotations

import random
import secrets
import time
from dataclasses import dataclass, field

CHALLENGES = {
    "blink": "Blink both eyes",
    "turn_left": "Turn your head to your left",
    "turn_right": "Turn your head to your right",
    "smile": "Smile",
}
TIMEOUT_SECONDS = 25.0


@dataclass
class LivenessSession:
    id: str
    steps: list[str]
    created: float = field(default_factory=time.time)
    index: int = 0
    state: str = "running"  # running | passed | failed
    reason: str = ""
    step_state: dict = field(default_factory=dict)
    passive_scores: list[float] = field(default_factory=list)
    frames: int = 0
    last_box: list[float] | None = None

    def public(self) -> dict:
        current = self.steps[self.index] if self.state == "running" and self.index < len(self.steps) else None
        passive = round(sum(self.passive_scores) / len(self.passive_scores), 3) if self.passive_scores else None
        return {
            "session_id": self.id,
            "state": self.state,
            "reason": self.reason,
            "steps": [{"id": s, "prompt": CHALLENGES[s], "done": i < self.index or self.state == "passed"}
                      for i, s in enumerate(self.steps)],
            "current": {"id": current, "prompt": CHALLENGES[current]} if current else None,
            "seconds_left": max(0.0, round(TIMEOUT_SECONDS - (time.time() - self.created), 1)),
            "passive_real_score": passive,
            "frames": self.frames,
        }


def new_session(n_steps: int = 3) -> LivenessSession:
    steps = random.sample(list(CHALLENGES), k=min(n_steps, len(CHALLENGES)))
    return LivenessSession(id=secrets.token_urlsafe(12), steps=steps)


def _iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    u = aw * ah + bw * bh - ix * iy
    return ix * iy / u if u else 0


def update(session: LivenessSession, faces: list[dict], mirrored: bool = False) -> LivenessSession:
    """Advance the session with one analysed frame. `faces` come from the analysis pipeline."""
    if session.state != "running":
        return session
    session.frames += 1
    if time.time() - session.created > TIMEOUT_SECONDS:
        session.state, session.reason = "failed", "Timed out. Start a new check."
        return session
    if len(faces) != 1:
        if len(faces) > 1:
            session.state, session.reason = "failed", "More than one face was visible."
        return session
    f = faces[0]
    if session.last_box is not None and _iou(session.last_box, f["box"]) < 0.05:
        session.state, session.reason = "failed", "The face jumped between frames. Keep one face in view."
        return session
    session.last_box = f["box"]
    a = f.get("analysis", {})
    if a.get("antispoof"):
        session.passive_scores.append(a["antispoof"]["real_score"])
    step = session.steps[session.index]
    st = session.step_state.setdefault(step, {})
    pose = a.get("head_pose") or {}
    eyes = a.get("eyes") or {}
    smile = a.get("smile") or {}
    # A user turning to their own left moves the nose towards the right of an unmirrored camera image.
    yaw = -pose.get("yaw", 0.0) if mirrored else pose.get("yaw", 0.0)
    done = False
    if step == "blink":
        closed = eyes.get("both_closed")
        if closed is None:
            return session
        if closed:
            st["closed"] = True
        elif st.get("closed"):
            done = True
    elif step == "turn_left":
        done = yaw > 20
    elif step == "turn_right":
        done = yaw < -20
    elif step == "smile":
        done = bool(smile.get("smiling"))
    if done:
        session.index += 1
        if session.index >= len(session.steps):
            session.state = "passed"
            passive = session.public()["passive_real_score"]
            if passive is not None and passive < 0.5:
                session.state = "failed"
                session.reason = "Challenges completed, but the passive check suggests a photo or screen."
    return session
