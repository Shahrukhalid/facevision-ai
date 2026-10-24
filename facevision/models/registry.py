"""Model manifest, installation (download + SHA-256 verification) and activation."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
USER_AGENT = "FaceVision-AI-model-manager"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class DownloadState:
    status: str = "idle"  # idle | downloading | verifying | done | error
    bytes_done: int = 0
    bytes_total: int = 0
    message: str = ""
    started: float = 0.0
    cancel: bool = False


@dataclass
class Registry:
    models_dir: Path
    get_enabled: Callable[[], dict[str, bool]]
    set_enabled: Callable[[dict[str, bool]], None]
    offline: bool = False
    manifest: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        base = self.manifest["pack_base_url"]
        self.models: dict[str, dict] = {}
        for m in self.manifest["models"]:
            for f in m["files"]:
                f["urls"] = [u.replace("{pack}", base) for u in f.get("urls", [])]
                if "archive" in f:
                    f["archive"]["urls"] = [u.replace("{pack}", base) for u in f["archive"]["urls"]]
            self.models[m["id"]] = m
        self.downloads: dict[str, DownloadState] = {}
        self._lock = threading.Lock()
        self.on_change: list[Callable[[str], None]] = []

    # ---------- paths and status
    def model_dir(self, model_id: str) -> Path:
        return self.models_dir / model_id

    def file_path(self, model_id: str, key: str) -> Path:
        m = self.models[model_id]
        f = next(f for f in m["files"] if f["key"] == key)
        return self.model_dir(model_id) / f["name"]

    def installed(self, model_id: str) -> bool:
        m = self.models[model_id]
        for f in m["files"]:
            p = self.model_dir(model_id) / f["name"]
            if not p.is_file():
                return False
            if f.get("size") and p.stat().st_size != f["size"]:
                return False
        return True

    def enabled(self, model_id: str) -> bool:
        if not self.installed(model_id):
            return False
        flags = self.get_enabled()
        if model_id in flags:
            return bool(flags[model_id])
        m = self.models[model_id]
        return bool(m.get("default")) and not m.get("research_only")

    def license_accepted(self, model_id: str) -> bool:
        return bool(self.get_enabled().get(f"license:{model_id}"))

    def set_model_enabled(self, model_id: str, on: bool) -> None:
        if model_id not in self.models:
            raise KeyError(model_id)
        m = self.models[model_id]
        if on and not self.installed(model_id):
            raise ValueError("Install the model first.")
        if not on and m.get("required"):
            raise ValueError("This model is required and cannot be turned off.")
        flags = dict(self.get_enabled())
        flags[model_id] = on
        self.set_enabled(flags)
        self._changed(model_id)

    def describe(self, model_id: str) -> dict:
        m = self.models[model_id]
        d = self.downloads.get(model_id, DownloadState())
        size = sum((f.get("archive", {}).get("size") if f.get("archive") else f.get("size")) or 0 for f in m["files"])
        if any(f.get("archive") for f in m["files"]):
            size = max(f["archive"]["size"] for f in m["files"] if f.get("archive"))
        return {
            **{k: v for k, v in m.items() if k not in {"files"}},
            "installed": self.installed(model_id),
            "enabled": self.enabled(model_id),
            "license_accepted": self.license_accepted(model_id),
            "download_size": size,
            "files": [{"name": f["name"], "sha256": f["sha256"], "size": f.get("size"),
                       "urls": f.get("urls") or f["archive"]["urls"]} for f in m["files"]],
            "download": {"status": d.status, "bytes_done": d.bytes_done, "bytes_total": d.bytes_total,
                         "message": d.message},
        }

    def list(self) -> list[dict]:
        return [self.describe(mid) for mid in self.models]

    # ---------- install / verify / delete
    def verify(self, model_id: str) -> dict:
        m = self.models[model_id]
        results = {}
        for f in m["files"]:
            p = self.model_dir(model_id) / f["name"]
            if not p.is_file():
                results[f["name"]] = "missing"
            else:
                results[f["name"]] = "ok" if sha256_file(p) == f["sha256"] else "checksum mismatch"
        return results

    def delete(self, model_id: str) -> None:
        if self.models[model_id].get("required"):
            raise ValueError("This model is required. Reinstall it instead of deleting it.")
        shutil.rmtree(self.model_dir(model_id), ignore_errors=True)
        self._changed(model_id)

    def start_download(self, model_id: str, accept_license: bool = False) -> None:
        if model_id not in self.models:
            raise KeyError(model_id)
        m = self.models[model_id]
        if self.offline:
            raise ValueError("Offline mode is on (FV_OFFLINE=1). Turn it off to download models.")
        if m.get("research_only"):
            if not (accept_license or self.license_accepted(model_id)):
                raise ValueError("This model is licensed for non-commercial research only. Accept its licence to download it.")
            flags = dict(self.get_enabled())
            flags[f"license:{model_id}"] = True
            self.set_enabled(flags)
        if any(f["sha256"] == "PACK" for f in m["files"]):
            raise ValueError("This build has no checksum for the model pack yet.")
        with self._lock:
            state = self.downloads.get(model_id)
            if state and state.status in {"downloading", "verifying"}:
                return
            self.downloads[model_id] = DownloadState(status="downloading", started=time.time())
        threading.Thread(target=self._download, args=(model_id,), daemon=True, name=f"download-{model_id}").start()

    def cancel_download(self, model_id: str) -> None:
        state = self.downloads.get(model_id)
        if state:
            state.cancel = True

    def install_blocking(self, model_id: str, accept_license: bool = False) -> None:
        self.start_download(model_id, accept_license)
        while self.downloads[model_id].status in {"downloading", "verifying"}:
            time.sleep(0.2)
        if self.downloads[model_id].status != "done":
            raise RuntimeError(self.downloads[model_id].message)

    def _fetch(self, urls: list[str], dest: Path, expected_sha: str, size: int, state: DownloadState) -> None:
        errors = []
        for url in urls:
            try:
                tmp = dest.with_suffix(dest.suffix + ".part")
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                h = hashlib.sha256()
                with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as out:
                    total = int(r.headers.get("Content-Length") or size or 0)
                    state.bytes_total = total
                    state.bytes_done = 0
                    while True:
                        if state.cancel:
                            raise InterruptedError("Download cancelled.")
                        chunk = r.read(1 << 16)
                        if not chunk:
                            break
                        out.write(chunk)
                        h.update(chunk)
                        state.bytes_done += len(chunk)
                state.status = "verifying"
                if h.hexdigest() != expected_sha:
                    tmp.unlink(missing_ok=True)
                    raise ValueError(f"checksum mismatch for {url}")
                tmp.replace(dest)
                state.status = "downloading"
                return
            except InterruptedError:
                raise
            except Exception as e:  # try the next mirror
                log.warning("download failed from %s: %s", url, e)
                errors.append(f"{url}: {e}")
        raise RuntimeError("; ".join(errors) or "no download URL")

    def _download(self, model_id: str) -> None:
        state = self.downloads[model_id]
        m = self.models[model_id]
        target = self.model_dir(model_id)
        staging = self.models_dir / f".{model_id}.staging"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        try:
            archives: dict[str, Path] = {}
            for f in m["files"]:
                if "archive" in f:
                    a = f["archive"]
                    if a["sha256"] not in archives:
                        state.message = f"Downloading {Path(a['urls'][0]).name}"
                        ap = staging / Path(a["urls"][0]).name
                        self._fetch(a["urls"], ap, a["sha256"], a["size"], state)
                        archives[a["sha256"]] = ap
                    with zipfile.ZipFile(archives[a["sha256"]]) as z:
                        member = next(n for n in z.namelist() if n.split("/")[-1] == a["member"])
                        (staging / f["name"]).write_bytes(z.read(member))
                    if sha256_file(staging / f["name"]) != f["sha256"]:
                        raise ValueError(f"checksum mismatch for {f['name']}")
                else:
                    state.message = f"Downloading {f['name']}"
                    self._fetch(f["urls"], staging / f["name"], f["sha256"], f.get("size", 0), state)
            for ap in archives.values():
                ap.unlink(missing_ok=True)
            shutil.rmtree(target, ignore_errors=True)
            staging.rename(target)
            state.status, state.message = "done", "Installed and verified"
            log.info("installed model %s", model_id)
            self._changed(model_id)
        except Exception as e:
            shutil.rmtree(staging, ignore_errors=True)
            state.status, state.message = "error", str(e)
            log.error("model %s install failed: %s", model_id, e)

    def install_local(self, model_id: str, source_dir: Path) -> None:
        """Install from files already on disk (offline installs, CI caches). Checksums are still verified."""
        m = self.models[model_id]
        target = self.model_dir(model_id)
        target.mkdir(parents=True, exist_ok=True)
        for f in m["files"]:
            src = source_dir / f["name"]
            if sha256_file(src) != f["sha256"]:
                raise ValueError(f"checksum mismatch for {src}")
            shutil.copyfile(src, target / f["name"])
        self._changed(model_id)

    def _changed(self, model_id: str) -> None:
        for cb in self.on_change:
            try:
                cb(model_id)
            except Exception:  # pragma: no cover
                log.exception("model change callback failed")
