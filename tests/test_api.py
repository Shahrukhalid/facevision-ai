"""End-to-end API tests through FastAPI's test client."""

from __future__ import annotations

import json
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from facevision.api.app import create_app
from tests.conftest import att_images, jpeg, need

PASS = "a long passphrase"


@pytest.fixture
def client(state):
    with TestClient(create_app(state), base_url="http://localhost") as c:
        c.fv = state
        yield c


def signed_in(client):
    r = client.post("/api/auth/setup", json={"passphrase": PASS})
    assert r.status_code == 200, r.text
    return r.json()["api_key"]


def test_health_and_docs(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/openapi.json").status_code == 200
    sysinfo = client.get("/api/system").json()
    assert "providers" in sysinfo["hardware"] and sysinfo["auth"]["configured"] is False
    assert client.get("/api/models").status_code == 200


def test_security_headers_and_host_checks(client):
    r = client.get("/api/health")
    assert r.headers["x-frame-options"] == "DENY" and "default-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 403
    r = client.post("/api/auth/login", json={"passphrase": "x"}, headers={"origin": "http://evil.example"})
    assert r.status_code == 403


def test_biometric_endpoints_require_auth(client):
    assert client.get("/api/persons").status_code == 403  # no passphrase yet
    signed_in(client)
    client.cookies.clear()
    assert client.get("/api/persons").status_code == 401
    assert client.post("/api/persons", json={"name": "x", "consent_confirmed": True}).status_code == 401
    assert client.get("/api/data/backup").status_code == 401
    r = client.post("/api/auth/login", json={"passphrase": "wrong passphrase"})
    assert r.status_code == 401
    assert client.post("/api/auth/login", json={"passphrase": PASS}).status_code == 200
    assert client.get("/api/persons").status_code == 200


def test_api_key_auth(client):
    key = signed_in(client)
    client.cookies.clear()
    assert client.get("/api/persons", headers={"X-API-Key": key}).status_code == 200
    assert client.get("/api/persons", headers={"Authorization": f"Bearer {key}"}).status_code == 200
    assert client.get("/api/persons", headers={"X-API-Key": "fv_nope"}).status_code == 401


def test_login_rate_limit(client):
    signed_in(client)
    codes = [client.post("/api/auth/login", json={"passphrase": "wrong passphrase"}).status_code for _ in range(8)]
    assert 429 in codes


def test_invalid_uploads(client):
    r = client.post("/api/detect", files={"file": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 415
    r = client.post("/api/detect", files={"file": ("x.jpg", b"", "image/jpeg")})
    assert r.status_code == 400
    client.fv.config.max_image_mb = 1
    r = client.post("/api/detect", files={"file": ("big.jpg", b"0" * (2 * 1024 * 1024), "image/jpeg")})
    assert r.status_code == 413
    r = client.post("/api/jobs/video", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415


def test_detect_analyze_annotate(client, portrait):
    need(client.fv, "yunet")
    r = client.post("/api/detect", files={"file": ("p.jpg", jpeg(portrait), "image/jpeg")}, data={"crops": "true"})
    assert r.status_code == 200 and r.json()["face_count"] == 1
    assert r.json()["faces"][0]["crop"].startswith("data:image/jpeg;base64,")
    r = client.post("/api/analyze", files={"file": ("p.png", cv2.imencode(".png", portrait)[1].tobytes(), "image/png")},
                    data={"options": json.dumps({"preset": "balanced"}), "annotate_image": "true"})
    body = r.json()
    assert r.status_code == 200 and body["faces"][0]["analysis"]["head_pose"]
    assert body["annotated_image"].startswith("data:image/jpeg")
    webp = cv2.imencode(".webp", portrait)[1].tobytes()
    assert client.post("/api/detect", files={"file": ("p.webp", webp, "image/webp")}).json()["face_count"] == 1


def test_compare(client, portrait):
    need(client.fv, "yunet", "sface")
    same = client.post("/api/compare", files={"file_a": ("a.jpg", jpeg(portrait), "image/jpeg"),
                                              "file_b": ("b.jpg", jpeg(cv2.flip(portrait, 1)), "image/jpeg")}).json()
    assert same["match"] is True and same["similarity"] > 0.6
    assert "not a probability" in same["note"]
    blank = np.zeros((300, 300, 3), np.uint8)
    r = client.post("/api/compare", files={"file_a": ("a.jpg", jpeg(portrait), "image/jpeg"),
                                           "file_b": ("b.jpg", jpeg(blank), "image/jpeg")})
    assert r.status_code == 422


def test_compare_different_people(client):
    need(client.fv, "yunet", "sface")
    a, b = att_images("s1", 1)[0], att_images("s2", 1)[0]
    r = client.post("/api/compare", files={"file_a": ("a.jpg", jpeg(a), "image/jpeg"),
                                           "file_b": ("b.jpg", jpeg(b), "image/jpeg")}).json()
    assert r["match"] is False


def test_anonymize(client, portrait):
    need(client.fv, "yunet")
    r = client.post("/api/anonymize", files={"file": ("p.jpg", jpeg(portrait), "image/jpeg")},
                    data={"method": "pixelate", "strength": "0.8"})
    assert r.status_code == 200 and r.headers["x-faces-anonymized"] == "1"
    out = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    face = (slice(80, 160), slice(190, 260))
    assert np.abs(out[face].astype(int) - portrait[face].astype(int)).mean() > 8
    r = client.post("/api/anonymize", files={"file": ("p.jpg", jpeg(portrait), "image/jpeg")}, data={"faces": "none"})
    assert r.headers["x-faces-anonymized"] == "0"


def test_enrol_recognize_verify_delete(client):
    need(client.fv, "yunet", "sface")
    signed_in(client)
    r = client.post("/api/persons", json={"name": "Volunteer 1", "consent_confirmed": False})
    assert r.status_code == 400
    pid = client.post("/api/persons", json={"name": "Volunteer 1", "consent_confirmed": True,
                                            "consent_note": "test"}).json()["id"]
    imgs = att_images("s1", 10)
    files = [("files", (f"{i}.jpg", jpeg(im), "image/jpeg")) for i, im in enumerate(imgs[:4])]
    enrol = client.post(f"/api/persons/{pid}/templates", files=files, data={"allow_low_quality": "true"}).json()
    assert enrol["added"] >= 3
    # the same person in photos not used for enrolment
    hits = 0
    for im in imgs[5:]:
        rec = client.post("/api/recognize", files={"file": ("q.jpg", jpeg(im), "image/jpeg")}).json()["faces"][0]["recognition"]
        hits += rec["status"] in {"match", "low_quality"} and (rec.get("name") in {None, "Volunteer 1"})
    assert hits >= 4
    # somebody else stays unknown
    other = att_images("s7", 3)
    for im in other:
        rec = client.post("/api/recognize", files={"file": ("q.jpg", jpeg(im), "image/jpeg")}).json()["faces"][0]["recognition"]
        assert rec["status"] == "unknown" and "name" not in rec
    # an impossible threshold rejects everyone
    rec = client.post("/api/recognize", files={"file": ("q.jpg", jpeg(imgs[6]), "image/jpeg")},
                      data={"threshold": "0.999"}).json()["faces"][0]["recognition"]
    assert rec["status"] == "unknown"
    v = client.post("/api/verify", files={"file": ("q.jpg", jpeg(imgs[7]), "image/jpeg")}, data={"person_id": pid}).json()
    assert v["similarity"] > 0.363
    v2 = client.post("/api/verify", files={"file": ("q.jpg", jpeg(other[0]), "image/jpeg")}, data={"person_id": pid}).json()
    assert v2["verified"] is False
    # duplicate warning when enrolling the same face under another name
    pid2 = client.post("/api/persons", json={"name": "Duplicate", "consent_confirmed": True}).json()["id"]
    dup = client.post(f"/api/persons/{pid2}/templates", files=[("files", ("d.jpg", jpeg(imgs[8]), "image/jpeg"))],
                      data={"allow_low_quality": "true"}).json()
    assert any("duplicate" in w.lower() for w in dup["results"][0].get("warnings", []))
    assert client.delete(f"/api/persons/{pid2}").status_code == 200
    # deletion removes the ability to recognise
    assert client.delete(f"/api/persons/{pid}").status_code == 200
    rec = client.post("/api/recognize", files={"file": ("q.jpg", jpeg(imgs[6]), "image/jpeg")}).json()["faces"][0]["recognition"]
    assert rec["status"] == "no_gallery"
    assert client.fv.db.one("SELECT COUNT(*) AS n FROM templates")["n"] == 0
    actions = [a["action"] for a in client.get("/api/audit").json()]
    assert "person.created" in actions and "person.deleted" in actions


def test_enrolment_rejects_multi_face_and_no_face(client, portrait):
    need(client.fv, "yunet", "sface")
    signed_in(client)
    pid = client.post("/api/persons", json={"name": "P", "consent_confirmed": True}).json()["id"]
    two = np.hstack([portrait, portrait])
    r = client.post(f"/api/persons/{pid}/templates", files=[
        ("files", ("two.jpg", jpeg(two), "image/jpeg")),
        ("files", ("none.jpg", jpeg(np.zeros((200, 200, 3), np.uint8)), "image/jpeg"))]).json()
    assert r["added"] == 0 and "2 faces" in r["results"][0]["reason"] and "No face" in r["results"][1]["reason"]


def test_websocket_live(client, portrait):
    need(client.fv, "yunet")
    with client.websocket_connect("/ws/live") as ws:
        ws.send_json({"type": "options", "options": {"preset": "fast"}})
        assert ws.receive_json()["type"] == "options"
        ids = []
        for i in range(4):
            frame = np.zeros((560, 800, 3), np.uint8)
            frame[20:532, 20 + i * 8:532 + i * 8] = portrait
            ws.send_bytes(jpeg(frame))
            r = json.loads(ws.receive_text())
            assert r["type"] == "result" and r["face_count"] == 1
            ids.append(r["faces"][0]["track_id"])
        assert len(set(ids)) == 1 and r["latency_ms"] > 0
        ws.send_bytes(b"garbage")
        assert ws.receive_json()["type"] == "error"


def test_websocket_rejects_cross_origin(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/live", headers={"origin": "http://evil.example"}) as ws:
            ws.receive_json()


def test_liveness_session_api(client, portrait):
    need(client.fv, "yunet", "face_landmarker")
    s = client.post("/api/liveness/sessions").json()
    assert s["state"] == "running" and len(s["steps"]) == 3
    r = client.post(f"/api/liveness/sessions/{s['session_id']}/frame",
                    files={"file": ("f.jpg", jpeg(portrait), "image/jpeg")}).json()
    assert r["frames"] == 1 and len(r["faces"]) == 1
    if "smile" in [x["id"] for x in s["steps"]] and s["steps"][0]["id"] == "smile":
        assert r["steps"][0]["done"]  # the portrait is smiling


def _wait(client, jid, timeout=180):
    t = time.time()
    while time.time() - t < timeout:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in {"done", "failed", "cancelled"}:
            return j
        time.sleep(0.3)
    raise AssertionError("job timed out")


def _make_video(path, portrait, frames=30):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (800, 560))
    for i in range(frames):
        f = np.zeros((560, 800, 3), np.uint8)
        if 5 <= i < 25:  # face enters at frame 5, leaves at frame 25
            f[20:532, 20 + i * 5:532 + i * 5] = portrait
        w.write(f)
    w.release()


def test_video_job_with_events_and_export(client, portrait, tmp_path):
    need(client.fv, "yunet")
    vid = tmp_path / "clip.mp4"
    _make_video(vid, portrait)
    r = client.post("/api/jobs/video", files={"file": ("clip.mp4", vid.read_bytes(), "video/mp4")},
                    data={"options": json.dumps({"analysis": {"preset": "fast"}, "export_video": True})})
    assert r.status_code == 200, r.text
    j = _wait(client, r.json()["id"])
    assert j["status"] == "done", j
    res = j["result"]
    assert res["summary"]["frames"] == 30 and res["summary"]["tracks"] == 1
    types = [e["type"] for e in res["events"]]
    assert types == ["enter", "exit"]
    for name in j["outputs"].values():
        f = client.get(f"/api/jobs/{j['id']}/files/{name}")
        assert f.status_code == 200 and len(f.content) > 0
    assert client.get(f"/api/jobs/{j['id']}/files/..%2Ffacevision.db").status_code == 404


def test_video_anonymize_job(client, portrait, tmp_path):
    need(client.fv, "yunet")
    vid = tmp_path / "clip.mp4"
    _make_video(vid, portrait, frames=12)
    r = client.post("/api/jobs/video", files={"file": ("clip.mp4", vid.read_bytes(), "video/mp4")},
                    data={"options": json.dumps({"anonymize": {"method": "solid"}, "sample_every": 5})})
    j = _wait(client, r.json()["id"])
    assert j["status"] == "done" and j["result"]["summary"]["sample_every"] == 1


def test_batch_job_and_cancel(client, portrait):
    need(client.fv, "yunet")
    files = [("files", (f"{i}.jpg", jpeg(portrait), "image/jpeg")) for i in range(3)]
    files.append(("files", ("broken.jpg", b"garbage", "image/jpeg")))
    r = client.post("/api/jobs/batch", files=files, data={"options": json.dumps({"mode": "anonymize"})})
    j = _wait(client, r.json()["id"])
    assert j["status"] == "done"
    s = j["result"]["summary"]
    assert s["succeeded"] == 3 and s["failed"] == 1 and s["faces"] == 3
    assert client.get(f"/api/jobs/{j['id']}/files/outputs.zip").status_code == 200
    assert client.delete(f"/api/jobs/{j['id']}").status_code == 200


def test_data_management(client):
    signed_in(client)
    assert client.get("/api/data/summary").json()["persons"] == 0
    exp = client.get("/api/data/export")
    assert exp.status_code == 200 and "persons" in exp.json()
    b = client.get("/api/data/backup")
    assert b.status_code == 200 and b.content[:2] == b"PK"
    assert client.post("/api/data/delete-all", json={"confirm": "no"}).status_code == 400
    assert client.post("/api/data/delete-all", json={"confirm": "DELETE EVERYTHING"}).json()["configured"] is False


def test_settings_validation(client):
    assert client.put("/api/settings", json={"bogus": 1}).status_code == 400
    assert client.put("/api/settings", json={"recognizer": "nope"}).status_code == 400
    assert client.put("/api/settings", json={"age_band_years": 5}).json()["age_band_years"] == 5
    signed_in(client)
    client.cookies.clear()
    assert client.put("/api/settings", json={"age_band_years": 6}).status_code == 401
