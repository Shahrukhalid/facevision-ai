"""Regression tests for input handling, privacy and concurrency fixes. None of these need model files."""

from __future__ import annotations

import json
import subprocess
import sys
import threading

import numpy as np
import pytest
from fastapi.testclient import TestClient

from facevision.api.app import create_app
from facevision.api.deps import safe_filename
from facevision.jobs import csv_safe, safe_fps, unique_name
from facevision.storage.db import now_iso

PASS = "a long passphrase"


@pytest.fixture
def client(state):
    with TestClient(create_app(state), base_url="http://localhost") as c:
        c.fv = state
        yield c


def test_decompression_bomb_is_rejected():
    # OpenCV reads the pixel limit when cv2 is imported, so this runs in a fresh interpreter that imports facevision first
    code = (
        "import facevision, cv2, numpy as np\n"
        "from facevision.jobs import read_image_bytes\n"
        "data = cv2.imencode('.png', np.zeros((8000, 8000), np.uint8))[1].tobytes()\n"  # 64 MP, ~70 KB
        "try:\n    read_image_bytes(data)\n    print('decoded')\n"
        "except ValueError:\n    print('rejected')\n"
        "print(read_image_bytes(cv2.imencode('.png', np.zeros((100, 100), np.uint8))[1].tobytes()).shape)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["rejected", "(100,", "100,", "3)"]


def test_settings_types_and_ranges(client):
    for bad in ({"detection_threshold": "high"}, {"detection_threshold": 5}, {"keep_job_outputs_days": -1},
                {"keep_job_outputs_days": "7"}, {"show_candidates": "yes"}, {"preset": "turbo"},
                {"recognition_thresholds": {"sface": "x"}}, {"max_faces_live": 0}):
        assert client.put("/api/settings", json=bad).status_code == 400, bad
    ok = client.put("/api/settings", json={"detection_threshold": 0.7, "recognition_thresholds": {"sface": 0.4}})
    assert ok.status_code == 200 and ok.json()["detection_threshold"] == 0.7


def test_bad_saved_retention_does_not_break_startup(state):
    state.db.set_setting("app", {"keep_job_outputs_days": "soon"})
    assert state.cleanup_outputs() == 0


def _person_with_template(state):
    state.vault.setup(PASS)
    p = state.identities.create_person("Ada", True)
    emb = np.random.default_rng(0).standard_normal(128).astype(np.float32)
    state.identities.add_template(p["id"], "sface", emb / np.linalg.norm(emb), 0.9, "test")
    return p


def test_gallery_read_racing_a_change_is_not_cached(state):
    p = _person_with_template(state)
    ids = state.identities
    real_query = ids.db.query

    def query_then_change(sql, params=()):
        rows = real_query(sql, params)
        if "FROM templates WHERE model_id" in sql:
            ids.delete_person(p["id"])  # a deletion lands while the gallery is being decrypted
        return rows

    ids.db.query = query_then_change
    embs, _ = ids.gallery("sface")
    ids.db.query = real_query
    assert len(embs) == 1  # this read saw the old rows...
    assert len(ids.gallery("sface")[0]) == 0  # ...but they were not cached, so the deleted person is gone


def test_deleting_a_person_empties_the_wal(state):
    p = _person_with_template(state)
    state.identities.delete_person(p["id"])
    wal = state.config.db_path.with_name(state.config.db_path.name + "-wal")
    assert not wal.exists() or wal.stat().st_size == 0
    assert state.db.one("PRAGMA secure_delete")["secure_delete"] == 1


def _insert_job(state, jid, identity_access):
    ts = now_iso()
    state.db.execute("INSERT INTO jobs(id, kind, status, progress, options, outputs, created_at, updated_at) "
                     "VALUES(?,?,?,?,?,?,?,?)",
                     (jid, "batch", "done", 1.0, json.dumps({"identity_access": identity_access}),
                      json.dumps({"json": "report.json"}), ts, ts))
    d = state.config.outputs_dir / jid
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.json").write_text('{"recognized_as": "Ada"}')


def test_recognition_jobs_need_sign_in(client):
    st = client.fv
    client.post("/api/auth/setup", json={"passphrase": PASS})
    _insert_job(st, "job-rec", True)
    _insert_job(st, "job-plain", False)
    assert client.get("/api/jobs/job-rec").status_code == 200
    client.cookies.clear()
    assert client.get("/api/jobs/job-rec").status_code == 401
    assert client.get("/api/jobs/job-rec/files/report.json").status_code == 401
    assert client.delete("/api/jobs/job-rec").status_code == 401
    assert client.get("/api/jobs/job-plain").status_code == 200
    assert client.get("/api/jobs/job-plain/files/report.json").status_code == 200


def test_clear_cache_keeps_files_of_running_jobs(state):
    keep_dir = state.config.outputs_dir / "running-job"
    keep_dir.mkdir()
    keep_upload = state.config.uploads_dir / "abc__clip.mp4"
    keep_upload.write_bytes(b"x")
    stale = state.config.uploads_dir / "def__old.mp4"
    stale.write_bytes(b"x")
    state.jobs._cancel["running-job"] = threading.Event()
    state.jobs._active_inputs.add(keep_upload)
    state.clear_cache()
    assert keep_dir.is_dir() and keep_upload.is_file() and not stale.exists()


def test_helpers():
    assert safe_fps(float("nan")) == 25.0 and safe_fps(0) == 25.0 and safe_fps(1000) == 25.0 and safe_fps(29.97) == 29.97
    used: set[str] = set()
    assert [unique_name(n, used) for n in ("a.jpg", "a.jpg", "A.jpg", "b")] == ["a.jpg", "a-2.jpg", "A-3.jpg", "b"]
    assert csv_safe("=cmd()") == "'=cmd()" and csv_safe("-1.5") == "-1.5" and csv_safe(3) == 3
    assert safe_filename("..\\..\\evil.mp4") == "evil.mp4"
    assert safe_filename("../x/clip\x00.mp4") == "clip_.mp4"
    assert safe_filename("") == "upload" and len(safe_filename("a" * 500 + ".jpg")) == 120
