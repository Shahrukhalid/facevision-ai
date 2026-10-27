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


def test_legacy_jobs_without_flag_are_protected(client):
    st = client.fv
    client.post("/api/auth/setup", json={"passphrase": PASS})
    ts = now_iso()
    for jid, opts in (("legacy-default", {}), ("legacy-balanced-null", {"analysis": {"recognition": None}}),
                      ("legacy-explicit", {"analysis": {"recognition": True}}),
                      ("legacy-fast", {"analysis": {"preset": "fast"}})):
        st.db.execute("INSERT INTO jobs(id, kind, status, progress, options, outputs, created_at, updated_at) "
                      "VALUES(?,?,?,?,?,?,?,?)",
                      (jid, "batch", "done", 1.0, json.dumps(opts), json.dumps({"json": "report.json"}), ts, ts))
    client.cookies.clear()
    assert client.get("/api/jobs/legacy-default").status_code == 401  # balanced preset recognises by default
    assert client.get("/api/jobs/legacy-balanced-null").status_code == 401
    assert client.get("/api/jobs/legacy-explicit").status_code == 401
    assert client.get("/api/jobs/legacy-fast").status_code == 200  # recognition cannot have been on


def test_submit_derives_identity_access_from_resolved_options(state, tmp_path, monkeypatch):
    monkeypatch.setattr(state.jobs.pool, "submit", lambda *a, **k: None)
    f = tmp_path / "a__x.jpg"
    f.write_bytes(b"x")
    flags = {}
    for label, analysis in (("omitted", None), ("null", {"recognition": None}), ("fast", {"preset": "fast"}),
                            ("fast-on", {"preset": "fast", "recognition": True})):
        jid = state.jobs.submit("batch", [f], {"analysis": analysis} if analysis is not None else {}, True)
        flags[label] = state.jobs.get(jid)["options"]["identity_access"]
    assert flags == {"omitted": True, "null": True, "fast": False, "fast-on": True}
    jid = state.jobs.submit("batch", [f], {}, False)
    assert state.jobs.get(jid)["options"]["identity_access"] is False


def test_batch_records_decoder_errors_per_file(state, tmp_path, monkeypatch):
    import cv2

    from facevision import jobs as jobs_mod

    def boom(*a, **k):
        raise cv2.error("image too large")

    monkeypatch.setattr(jobs_mod.cv2, "imread", boom)
    f = tmp_path / "a__huge.png"
    f.write_bytes(b"x")
    result, _ = state.jobs._run_batch("j-huge", [f], {}, False)
    assert result["summary"]["failed"] == 1 and result["summary"]["succeeded"] == 0
    assert result["files"][0]["error"] == "Not a readable image"


def test_clear_cache_waits_for_upload_registration(state):
    started, finished = threading.Event(), threading.Event()

    def clear():
        started.set()
        state.clear_cache()
        finished.set()

    upload = state.config.uploads_dir / "new__clip.mp4"
    with state.jobs.lock:  # a submission is in the middle of registering
        t = threading.Thread(target=clear)
        t.start()
        started.wait(5)
        assert not finished.wait(0.3)  # pruning cannot take its snapshot yet
        state.jobs.reserve_upload(upload)
        upload.write_bytes(b"x")
    t.join(10)
    assert finished.is_set() and upload.is_file()


def test_factory_reset_stops_workers_before_deleting_files(client):
    st = client.fv
    client.post("/api/auth/setup", json={"passphrase": PASS})
    started = threading.Event()
    out = st.config.outputs_dir / "busy-job"

    def slow_run(jid, inputs, options, identity_access):
        out.mkdir(parents=True, exist_ok=True)
        started.set()
        while True:
            st.jobs._check(jid)
            threading.Event().wait(0.01)
            (out / "late.json").write_text("{}")

    st.jobs._run_batch = slow_run
    f = st.config.uploads_dir / "z__a.jpg"
    f.write_bytes(b"x")
    st.jobs.submit("batch", [f], {}, True)
    assert started.wait(5)
    r = client.post("/api/data/delete-all", json={"confirm": "DELETE EVERYTHING"})
    assert r.status_code == 200, r.text
    assert not out.exists() and not f.exists()
    assert st.jobs.active() == (set(), set())
    assert st.db.one("SELECT COUNT(*) AS n FROM jobs")["n"] == 0
