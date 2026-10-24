"""FaceVision AI must not contact the network while analysing faces.

The check runs the engine in a child process whose HTTP(S) proxy points at a local socket that records every
connection attempt. Libraries that phone home (for example ONNX Runtime's telemetry client) go through the proxy
and are caught here.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from tests.conftest import models_source

ROOT = Path(__file__).resolve().parents[1]


def _proxy():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(20)
    seen: list[str] = []

    def loop():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            try:
                seen.append(c.recv(2048).decode(errors="replace").split("\r\n")[0])
                c.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            finally:
                c.close()

    threading.Thread(target=loop, daemon=True).start()
    return srv, seen


def test_no_outbound_connections_during_analysis(tmp_path):
    src = models_source()
    if src is None:
        pytest.skip("models not available (set FV_TEST_MODELS)")
    srv, seen = _proxy()
    port = srv.getsockname()[1]
    script = textwrap.dedent(f"""
        import time, numpy as np, cv2
        from facevision.config import Config
        from facevision.state import AppState
        from facevision.engine.pipeline import Options
        from pathlib import Path
        cfg = Config(); cfg.data_dir = Path({str(tmp_path)!r}); s = AppState(cfg)
        for mid in ["yunet", "sface", "face_landmarker", "ferplus", "antispoof"]:
            s.registry.install_local(mid, Path({str(src)!r}))
        img = np.zeros((480, 640, 3), np.uint8)
        cv2.circle(img, (320, 240), 90, (200, 180, 160), -1)
        s.hub.warmup()
        s.analyzer.analyze_image(img, Options.from_dict({{"preset": "detailed", "antispoof": True}}), s.context(False))
        time.sleep(20)  # ONNX Runtime's telemetry client sends after a delay
        print("done")
    """)
    env = {k: v for k, v in os.environ.items() if k.upper() not in {"ORT_DISABLE_TELEMETRY", "NO_PROXY"}}
    proxy = f"http://127.0.0.1:{port}"
    env.update(HTTP_PROXY=proxy, HTTPS_PROXY=proxy, http_proxy=proxy, https_proxy=proxy, PYTHONPATH=str(ROOT))
    out = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=240)
    srv.close()
    assert "done" in out.stdout, out.stderr[-2000:]
    assert seen == [], f"unexpected outbound connections: {seen}"
