"""Application state: one instance per running server."""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .engine import runtime
from .engine.hub import ModelHub
from .engine.pipeline import Analyzer, Context
from .models.registry import Registry
from .security import RateLimiter, Vault
from .storage.db import Database
from .storage.identities import IdentityStore

log = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "preset": "balanced",
    "detection_threshold": 0.6,
    "recognizer": "sface",
    "recognition_thresholds": {},
    "show_candidates": True,
    "age_band_years": 8,
    "allow_appearance": False,
    "keep_job_outputs_days": 7,
    "accelerator": "auto",
    "max_faces_live": 10,
}


@dataclass
class AppState:
    config: Config
    db: Database = field(init=False)
    vault: Vault = field(init=False)
    registry: Registry = field(init=False)
    hub: ModelHub = field(init=False)
    analyzer: Analyzer = field(init=False)
    identities: IdentityStore = field(init=False)
    limiter: RateLimiter = field(init=False)
    started: float = field(default_factory=time.time)

    def __post_init__(self):
        self.config.ensure_dirs()
        self.db = Database(self.config.db_path)
        self.vault = Vault(self.db)
        self.registry = Registry(
            models_dir=self.config.models_dir,
            get_enabled=lambda: self.db.get_setting("models.enabled", {}),
            set_enabled=lambda v: self.db.set_setting("models.enabled", v),
            offline=self.config.offline,
        )
        self.hub = ModelHub(self.registry)
        self.analyzer = Analyzer(self.hub)
        self.identities = IdentityStore(self.db, self.vault)
        self.limiter = RateLimiter()
        runtime.set_preference(self.settings().get("accelerator", "auto"))
        from .jobs import JobManager
        self.jobs = JobManager(self)
        self.cleanup_outputs()

    # ---- settings
    def settings(self) -> dict:
        s = dict(DEFAULT_SETTINGS)
        s.update(self.db.get_setting("app", {}))
        return s

    def update_settings(self, changes: dict) -> dict:
        current = self.db.get_setting("app", {})
        for k, v in changes.items():
            if k not in DEFAULT_SETTINGS:
                raise ValueError(f"Unknown setting: {k}")
            current[k] = v
        self.db.set_setting("app", current)
        if "accelerator" in changes:
            runtime.set_preference(changes["accelerator"])
            self.hub.unload()
        if "recognizer" in changes:
            self.identities.invalidate()
        self.db.audit("settings.updated", ",".join(sorted(changes)))
        return self.settings()

    def context(self, identity_access: bool) -> Context:
        return Context(identity_access=identity_access and self.vault.unlocked, identities=self.identities,
                       settings=self.settings())

    # ---- retention
    def cleanup_outputs(self) -> int:
        days = float(self.settings().get("keep_job_outputs_days", 7))
        if days <= 0:
            return 0
        cutoff = time.time() - days * 86400
        removed = 0
        for d in self.config.outputs_dir.iterdir() if self.config.outputs_dir.exists() else []:
            try:
                if d.stat().st_mtime < cutoff:
                    shutil.rmtree(d, ignore_errors=True) if d.is_dir() else d.unlink()
                    removed += 1
            except OSError:
                pass
        if removed:
            self.db.execute("DELETE FROM jobs WHERE updated_at < ?",
                            (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(cutoff)),))
        for f in self.config.uploads_dir.glob("*"):
            if f.stat().st_mtime < time.time() - 3600:
                f.unlink(missing_ok=True)
        return removed

    def clear_cache(self) -> dict:
        n_files = 0
        for d in (self.config.outputs_dir, self.config.uploads_dir):
            for p in list(d.iterdir()):
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
                n_files += 1
        self.db.execute("DELETE FROM jobs WHERE status NOT IN ('queued', 'running')")
        self.db.audit("data.cache_cleared", f"items={n_files}")
        return {"removed": n_files}

    def disk_usage(self) -> dict:
        def size(p: Path) -> int:
            if not p.exists():
                return 0
            if p.is_file():
                return p.stat().st_size
            return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

        return {"models": size(self.config.models_dir), "outputs": size(self.config.outputs_dir),
                "database": size(self.config.db_path), "temp": size(self.config.uploads_dir)}
