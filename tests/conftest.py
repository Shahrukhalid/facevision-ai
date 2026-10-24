"""Test fixtures.

Model-dependent tests need the model files. Point FV_TEST_MODELS at a folder containing them (CI downloads them
with `python -m facevision models install`), otherwise those tests are skipped. Test images are generated or come
from scikit-image's public-domain NASA portrait (skimage.data.astronaut). Recognition tests that need several
people use the AT&T "Database of Faces" (40 consenting volunteers photographed at the Olivetti Research Laboratory)
when FV_TEST_ATT points at it; nothing from either source is committed to this repository.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

MODEL_IDS = ["yunet", "sface", "face_landmarker", "ferplus", "antispoof", "clip_attributes", "insightface_buffalo_s"]


def models_source() -> Path | None:
    p = os.environ.get("FV_TEST_MODELS")
    return Path(p) if p and Path(p).is_dir() else None


def att_dir() -> Path | None:
    p = os.environ.get("FV_TEST_ATT")
    return Path(p) if p and Path(p).is_dir() else None


@pytest.fixture
def config(tmp_path):
    from facevision.config import Config
    cfg = Config()
    cfg.data_dir = tmp_path / "data"
    return cfg


def _install_available(state):
    src = models_source()
    installed = []
    if src is None:
        return installed
    for mid in MODEL_IDS:
        files = state.registry.models[mid]["files"]
        if all((src / f["name"]).is_file() for f in files):
            target = state.registry.model_dir(mid)
            target.mkdir(parents=True, exist_ok=True)
            for f in files:  # link instead of copying large files; checksums were verified when downloaded
                dest = target / f["name"]
                try:
                    os.link(src / f["name"], dest)
                except OSError:
                    shutil.copyfile(src / f["name"], dest)
            installed.append(mid)
    for mid in ("clip_attributes", "insightface_buffalo_s"):
        if mid in installed:
            state.registry.set_model_enabled(mid, True)
    return installed


@pytest.fixture
def state(config):
    from facevision.state import AppState
    st = AppState(config)
    st.installed = _install_available(st)
    yield st
    st.hub.unload()
    st.db.close()


def need(state, *ids):
    missing = [m for m in ids if m not in state.installed]
    if missing:
        pytest.skip(f"models not available: {missing} (set FV_TEST_MODELS)")


@pytest.fixture(scope="session")
def portrait() -> np.ndarray:
    skimage_data = pytest.importorskip("skimage.data")
    return cv2.cvtColor(skimage_data.astronaut(), cv2.COLOR_RGB2BGR)


def jpeg(img: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes()


def att_images(person: str, n: int = 10, scale: float = 3.0) -> list[np.ndarray]:
    root = att_dir()
    if root is None:
        pytest.skip("AT&T faces not available (set FV_TEST_ATT)")
    files = sorted((root / person).glob("*.pgm"), key=lambda p: int(p.stem))[:n]
    return [cv2.resize(cv2.imread(str(f)), None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) for f in files]
