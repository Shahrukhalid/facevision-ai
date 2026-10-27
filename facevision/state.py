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


NUMERIC_RANGES = {
    "detection_threshold": (0.05, 0.99),
    "age_band_years": (0, 50),
    "keep_job_outputs_days": (0, 3650),
    "max_faces_live": (1, 100),
}


def validate_setting(key: str, value):
    """Check type and range of one setting, so a bad value cannot break analysis or start-up later."""
    if key not in DEFAULT_SETTINGS:
        raise ValueError(f"Unknown setting: {key}")
    default = DEFAULT_SETTINGS[key]
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")
        return value
    if isinstance(default, (int, float)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a number")
        lo, hi = NUMERIC_RANGES[key]
        if not lo <= value <= hi:
            raise ValueError(f"{key} must be between {lo} and {hi}")
        return int(value) if isinstance(default, int) and float(value).is_integer() else value
    if isinstance(default, dict):
        if not isinstance(value, dict) or not all(
                isinstance(k, str) and isinstance(v, (int, float)) and not isinstance(v, bool) and -1.0 <= v <= 1.0
                for k, v in value.items()):
            raise ValueError(f"{key} must map model ids to numbers between -1 and 1")
        return value
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    if key == "preset" and value not in {"fast", "balanced", "detailed"}:
        raise ValueError("preset must be fast, balanced or detailed")
    return value


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
            current[k] = validate_setting(k, v)
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
        try:
            days = float(self.settings().get("keep_job_outputs_days", 7))
        except (TypeError, ValueError):  # a bad value saved by an older version must not stop start-up
            days = float(DEFAULT_SETTINGS["keep_job_outputs_days"])
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
            try:
                if f.stat().st_mtime < time.time() - 3600:
                    f.unlink(missing_ok=True)
            except OSError:
                pass
        return removed

    def clear_cache(self, everything: bool = False) -> dict:
        """Delete job outputs and temporary uploads, except those of jobs that are still queued or running.

        everything=True (factory reset) first stops all jobs and waits for their workers, then deletes it all."""
        if everything:
            self.jobs.stop_all()
        n_files = 0
        # Registration of uploads and jobs takes the same lock, so nothing can be registered between the snapshot
        # of active work and the directory listing.
        with self.jobs.lock:
            active_jobs, active_inputs = (set(), set()) if everything else self.jobs.active()
            for d in (self.config.outputs_dir, self.config.uploads_dir):
                for p in list(d.iterdir()):
                    if p.name in active_jobs or p in active_inputs:
                        continue
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
