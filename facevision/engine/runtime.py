"""ONNX Runtime session creation with hardware-acceleration preference and CPU fallback."""

from __future__ import annotations

import logging
import platform
import threading

import onnxruntime as ort

log = logging.getLogger(__name__)

# Execution providers we know how to use, in preference order for "auto".
ACCELERATED = ["CoreMLExecutionProvider", "DmlExecutionProvider", "CUDAExecutionProvider"]
_state = {"preference": "auto"}
_lock = threading.Lock()


def available_providers() -> list[str]:
    return list(ort.get_available_providers())


def set_preference(pref: str) -> None:
    """'auto' (try accelerators, fall back to CPU) or 'cpu'."""
    _state["preference"] = pref if pref in {"auto", "cpu"} else "auto"


def get_preference() -> str:
    return _state["preference"]


def make_session(path: str, threads: int = 0, allow_accel: bool = True) -> tuple[ort.InferenceSession, str]:
    """Create a session and return it with the provider actually used."""
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    if threads:
        opts.intra_op_num_threads = threads
    opts.log_severity_level = 3
    avail = available_providers()
    candidates: list[list[str]] = []
    if allow_accel and _state["preference"] == "auto":
        for p in ACCELERATED:
            if p in avail:
                candidates.append([p, "CPUExecutionProvider"])
    candidates.append(["CPUExecutionProvider"])
    last_err: Exception | None = None
    for providers in candidates:
        try:
            with _lock:
                sess = ort.InferenceSession(path, sess_options=opts, providers=providers)
            used = sess.get_providers()[0]
            return sess, used
        except Exception as e:  # accelerator not usable for this model; fall back
            last_err = e
            log.warning("provider %s failed for %s: %s", providers[0], path, e)
    raise RuntimeError(f"could not load {path}: {last_err}")


def hardware_summary() -> dict:
    avail = available_providers()
    return {
        "machine": platform.machine(),
        "system": platform.system(),
        "onnxruntime": ort.__version__,
        "providers": avail,
        "accelerators": {
            "coreml": "CoreMLExecutionProvider" in avail,
            "directml": "DmlExecutionProvider" in avail,
            "cuda": "CUDAExecutionProvider" in avail,
        },
        "preference": _state["preference"],
    }
