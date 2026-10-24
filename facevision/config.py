"""Runtime configuration from environment variables (see .env.example)."""

from __future__ import annotations

import ipaddress
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _default_data_dir() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "FaceVision AI"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "FaceVision AI"
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "facevision-ai"


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines); real environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def is_loopback(host: str) -> bool:
    if host in {"localhost"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8600
    data_dir: Path = field(default_factory=_default_data_dir)
    allow_remote: bool = False
    allowed_hosts: list[str] = field(default_factory=list)
    max_image_mb: int = 20
    max_video_mb: int = 1024
    max_batch_files: int = 200
    job_workers: int = 1
    log_level: str = "INFO"
    offline: bool = False

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "facevision.db"

    @property
    def keys_dir(self) -> Path:
        return self.data_dir / "keys"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.models_dir, self.outputs_dir, self.uploads_dir, self.keys_dir):
            d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.keys_dir, 0o700)
        except OSError:
            pass

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Config":
        _load_dotenv(env_file or Path.cwd() / ".env")
        cfg = cls()
        cfg.host = os.environ.get("FV_HOST", cfg.host)
        cfg.port = int(os.environ.get("FV_PORT", cfg.port))
        if os.environ.get("FV_DATA_DIR"):
            cfg.data_dir = Path(os.environ["FV_DATA_DIR"]).expanduser().resolve()
        cfg.allow_remote = _env_bool("FV_ALLOW_REMOTE", False)
        cfg.allowed_hosts = [h.strip() for h in os.environ.get("FV_ALLOWED_HOSTS", "").split(",") if h.strip()]
        cfg.max_image_mb = int(os.environ.get("FV_MAX_IMAGE_MB", cfg.max_image_mb))
        cfg.max_video_mb = int(os.environ.get("FV_MAX_VIDEO_MB", cfg.max_video_mb))
        cfg.max_batch_files = int(os.environ.get("FV_MAX_BATCH_FILES", cfg.max_batch_files))
        cfg.job_workers = max(1, int(os.environ.get("FV_JOB_WORKERS", cfg.job_workers)))
        cfg.log_level = os.environ.get("FV_LOG_LEVEL", cfg.log_level).upper()
        cfg.offline = _env_bool("FV_OFFLINE", False)
        return cfg

    def validate(self) -> None:
        if not is_loopback(self.host) and not self.allow_remote:
            raise SystemExit(
                f"Refusing to listen on {self.host}: FaceVision AI serves biometric data and binds to 127.0.0.1 by "
                "default. Set FV_ALLOW_REMOTE=1 (and FV_ALLOWED_HOSTS) only on a network you trust."
            )


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
