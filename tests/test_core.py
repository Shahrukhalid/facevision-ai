"""Tests that need no model files: security, storage, tracking, anonymisation, configuration, manifest."""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from facevision.engine.anonymize import anonymize
from facevision.engine.tracker import FaceTracker, iou
from facevision.security import AuthError, RateLimiter


def test_manifest_is_complete():
    from facevision.models.registry import MANIFEST_PATH
    m = json.loads(MANIFEST_PATH.read_text())
    ids = set()
    for model in m["models"]:
        assert model["id"] not in ids
        ids.add(model["id"])
        for key in ("name", "task", "license", "license_url", "source", "description", "files"):
            assert model.get(key), (model["id"], key)
        for f in model["files"]:
            assert re.fullmatch(r"[0-9a-f]{64}", f["sha256"]), (model["id"], f["name"])
            assert f["size"] > 0
            urls = [u.replace("{pack}", m["pack_base_url"]) for u in (f.get("urls") or f["archive"]["urls"])]
            assert all(u.startswith("https://") for u in urls)
        if model["research_only"]:
            assert not model["commercial_use"] and not model["default"]
    assert {"yunet", "sface", "face_landmarker"} <= ids


def test_vault_setup_login_and_encryption(state):
    v = state.vault
    assert not v.configured
    with pytest.raises(AuthError):
        v.setup("short")
    api_key = v.setup("a long passphrase")
    assert api_key.startswith("fv_")
    nonce, ct = v.encrypt(b"\x01\x02template", b"1:sface")
    assert v.decrypt(nonce, ct, b"1:sface") == b"\x01\x02template"
    from cryptography.exceptions import InvalidTag
    with pytest.raises(InvalidTag):
        v.decrypt(nonce, ct, b"2:sface")  # bound to the person and model
    # a fresh process holds no key until someone signs in
    from facevision.security import Vault
    v2 = Vault(state.db)
    assert v2.configured and not v2.unlocked
    with pytest.raises(AuthError):
        v2.login("wrong passphrase!!")
    token = v2.login("a long passphrase")
    assert v2.check_session(token) and not v2.check_session("bogus")
    assert v2.decrypt(nonce, ct, b"1:sface") == b"\x01\x02template"
    v3 = Vault(state.db)
    assert v3.check_api_key(api_key) and v3.unlocked
    assert not Vault(state.db).check_api_key("fv_wrong")
    # passphrase hashes, not passphrases, are stored
    raw = state.config.db_path.read_bytes()
    assert b"a long passphrase" not in raw


def test_templates_are_encrypted_at_rest(state):
    state.vault.setup("a long passphrase")
    p = state.identities.create_person("Test Person", consent_confirmed=True)
    emb = np.random.default_rng(0).normal(size=128).astype(np.float32)
    emb /= np.linalg.norm(emb)
    state.identities.add_template(p["id"], "sface", emb, 1.0, "test")
    row = state.db.one("SELECT ciphertext FROM templates")
    assert emb.tobytes() not in bytes(row["ciphertext"])
    m = state.identities.match("sface", emb, 0.363)
    assert m["status"] == "match" and m["candidates"][0]["name"] == "Test Person"
    other = np.random.default_rng(1).normal(size=128).astype(np.float32)
    assert state.identities.match("sface", other / np.linalg.norm(other), 0.363)["status"] == "unknown"
    state.identities.delete_person(p["id"])
    assert state.db.one("SELECT COUNT(*) AS n FROM templates")["n"] == 0
    assert state.identities.match("sface", emb, 0.363)["status"] == "no_gallery"


def test_enrolment_requires_consent(state):
    state.vault.setup("a long passphrase")
    with pytest.raises(ValueError):
        state.identities.create_person("No Consent", consent_confirmed=False)


def test_ambiguous_match(state):
    state.vault.setup("a long passphrase")
    rng = np.random.default_rng(3)
    base = rng.normal(size=128).astype(np.float32)
    base /= np.linalg.norm(base)
    for name in ("Twin A", "Twin B"):
        p = state.identities.create_person(name, consent_confirmed=True)
        state.identities.add_template(p["id"], "sface", base, 1.0, "test")
    assert state.identities.match("sface", base, 0.363)["status"] == "ambiguous"


def test_rate_limiter():
    rl = RateLimiter()
    assert all(rl.allow("c", "b", 60, 3) for _ in range(3))
    assert not rl.allow("c", "b", 60, 3)
    assert rl.allow("other", "b", 60, 3)


def test_tracker_ids_and_events():
    tr = FaceTracker(max_missed_seconds=0.5, min_hits=2)
    t = 0.0
    events = []
    for i in range(5):  # one face moving right
        faces = [{"box": [100 + i * 5, 100, 80, 80]}]
        events += tr.update(faces, i, t)
        assert faces[0]["track_id"] == 1
        t += 0.1
    assert [e["type"] for e in events] == ["enter"]
    faces = [{"box": [120, 100, 80, 80]}, {"box": [400, 300, 60, 60]}]
    tr.update(faces, 5, t)
    assert faces[0]["track_id"] == 1 and faces[1]["track_id"] == 2
    for i in range(6, 15):  # both disappear
        t += 0.1
        events = tr.update([], i, t)
        if events:
            break
    assert {e["type"] for e in events} == {"exit"}
    assert iou([0, 0, 10, 10], [5, 0, 10, 10]) == pytest.approx(1 / 3)


def test_anonymize_only_changes_face_regions():
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, (200, 300, 3), dtype=np.uint8)
    for method in ("blur", "pixelate", "solid"):
        out = anonymize(img, [[100, 50, 60, 60]], method, 0.8)
        assert out.shape == img.shape
        inside = (slice(70, 100), slice(115, 145))
        assert np.abs(out[inside].astype(int) - img[inside].astype(int)).mean() > 10, method
        assert np.array_equal(out[:, :60], img[:, :60]), method
    with pytest.raises(ValueError):
        anonymize(img, [], "swirl")


def test_config_refuses_public_binding(monkeypatch):
    from facevision.config import Config
    cfg = Config()
    cfg.host = "0.0.0.0"
    with pytest.raises(SystemExit):
        cfg.validate()
    cfg.allow_remote = True
    cfg.validate()


def test_registry_rejects_bad_checksum(state, tmp_path):
    (tmp_path / "face_detection_yunet_2023mar.onnx").write_bytes(b"not a model")
    with pytest.raises(ValueError):
        state.registry.install_local("yunet", tmp_path)


def test_research_model_needs_licence_acceptance(state):
    state.config.offline = False
    with pytest.raises(ValueError, match="non-commercial"):
        state.registry.start_download("insightface_buffalo_s")


def test_offline_mode_blocks_downloads(state):
    state.registry.offline = True
    with pytest.raises(ValueError, match="Offline"):
        state.registry.start_download("yunet")
