"""Local access control and biometric template encryption.

* The app owner sets a passphrase on first use. It is stored only as a scrypt hash.
* Face templates are encrypted with AES-256-GCM under a random data key. The data key is stored only in wrapped
  (encrypted) form: once under a key derived from the passphrase and once under a key derived from the API key.
  Templates can therefore only be read after someone signs in (or presents the API key); a copy of the database
  on its own is not enough to recover them.
* Sessions are random tokens held in memory and sent as an HttpOnly, SameSite=Strict cookie.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .storage.db import Database

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**15, 8, 1
MIN_PASSPHRASE = 10
SESSION_IDLE_SECONDS = 12 * 3600


class AuthError(Exception):
    pass


def _scrypt(secret: str, salt: bytes) -> bytes:
    return hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                          maxmem=128 * 1024 * 1024, dklen=32)


def _hkdf(secret: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=SHA256(), length=32, salt=None, info=info).derive(secret)


def _wrap(kek: bytes, dek: bytes, label: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(kek).encrypt(nonce, dek, label)


def _unwrap(kek: bytes, blob: bytes, label: bytes) -> bytes:
    return AESGCM(kek).decrypt(blob[:12], blob[12:], label)


@dataclass
class Session:
    token: str
    created: float
    last_seen: float


class Vault:
    """Owns the passphrase, API key, sessions and the in-memory template data key."""

    def __init__(self, db: Database):
        self.db = db
        self._dek: bytes | None = None
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    # ---- state
    @property
    def configured(self) -> bool:
        return self.db.get_auth("pass_hash") is not None

    @property
    def unlocked(self) -> bool:
        return self._dek is not None

    # ---- setup / passphrase
    def setup(self, passphrase: str) -> str:
        """First-run setup. Returns the API key (shown once)."""
        if self.configured:
            raise AuthError("A passphrase is already set.")
        self._check_strength(passphrase)
        dek = AESGCM.generate_key(bit_length=256)
        api_key = self._store_credentials(passphrase, dek, new_api_key=True)
        self._dek = dek
        self.db.audit("auth.setup")
        return api_key

    def change_passphrase(self, old: str, new: str) -> None:
        dek = self._unlock_with_passphrase(old)
        self._check_strength(new)
        self._store_credentials(new, dek, new_api_key=False)
        self.db.audit("auth.passphrase_changed")

    def rotate_api_key(self) -> str:
        if self._dek is None:
            raise AuthError("Sign in first.")
        api_key = "fv_" + secrets.token_urlsafe(32)
        self.db.set_auth("api_key_hash", hashlib.sha256(api_key.encode()).digest())
        self.db.set_auth("dek_by_api_key", _wrap(_hkdf(api_key.encode(), b"fv-api-kek"), self._dek, b"dek"))
        self.db.audit("auth.api_key_rotated")
        return api_key

    def reset(self) -> None:
        """Forget all credentials. Callers must delete encrypted templates first, as they become unreadable."""
        for key in ("pass_salt", "pass_hash", "kek_salt", "dek_by_pass", "api_key_hash", "dek_by_api_key"):
            self.db.delete_auth(key)
        self._dek = None
        with self._lock:
            self._sessions.clear()
        self.db.audit("auth.reset")

    def _check_strength(self, passphrase: str) -> None:
        if len(passphrase or "") < MIN_PASSPHRASE:
            raise AuthError(f"Use at least {MIN_PASSPHRASE} characters.")

    def _store_credentials(self, passphrase: str, dek: bytes, new_api_key: bool) -> str:
        pass_salt, kek_salt = os.urandom(16), os.urandom(16)
        self.db.set_auth("pass_salt", pass_salt)
        self.db.set_auth("pass_hash", _scrypt(passphrase, pass_salt))
        self.db.set_auth("kek_salt", kek_salt)
        self.db.set_auth("dek_by_pass", _wrap(_scrypt(passphrase, kek_salt), dek, b"dek"))
        if new_api_key:
            self._dek = dek
            return self.rotate_api_key()
        return ""

    def _unlock_with_passphrase(self, passphrase: str) -> bytes:
        salt, stored = self.db.get_auth("pass_salt"), self.db.get_auth("pass_hash")
        if not salt or not stored:
            raise AuthError("No passphrase has been set yet.")
        if not hmac.compare_digest(_scrypt(passphrase or "", salt), stored):
            raise AuthError("Incorrect passphrase.")
        kek = _scrypt(passphrase, self.db.get_auth("kek_salt"))
        return _unwrap(kek, self.db.get_auth("dek_by_pass"), b"dek")

    # ---- sign in
    def login(self, passphrase: str) -> str:
        self._dek = self._unlock_with_passphrase(passphrase)
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._sessions[token] = Session(token, now, now)
        return token

    def logout(self, token: str | None) -> None:
        if token:
            with self._lock:
                self._sessions.pop(token, None)

    def check_session(self, token: str | None) -> bool:
        if not token:
            return False
        now = time.time()
        with self._lock:
            s = self._sessions.get(token)
            if not s:
                return False
            if now - s.last_seen > SESSION_IDLE_SECONDS:
                self._sessions.pop(token, None)
                return False
            s.last_seen = now
        return self._dek is not None

    def check_api_key(self, key: str | None) -> bool:
        stored = self.db.get_auth("api_key_hash")
        if not key or not stored:
            return False
        if not hmac.compare_digest(hashlib.sha256(key.encode()).digest(), stored):
            return False
        if self._dek is None:
            self._dek = _unwrap(_hkdf(key.encode(), b"fv-api-kek"), self.db.get_auth("dek_by_api_key"), b"dek")
        return True

    # ---- template encryption
    def encrypt(self, data: bytes, aad: bytes) -> tuple[bytes, bytes]:
        if self._dek is None:
            raise AuthError("Sign in to unlock biometric data.")
        nonce = os.urandom(12)
        return nonce, AESGCM(self._dek).encrypt(nonce, data, aad)

    def decrypt(self, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
        if self._dek is None:
            raise AuthError("Sign in to unlock biometric data.")
        return AESGCM(self._dek).decrypt(nonce, ciphertext, aad)


class RateLimiter:
    """Token bucket per (client, bucket name)."""

    def __init__(self):
        self._state: dict[tuple[str, str], tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, client: str, bucket: str, rate_per_min: float, burst: float) -> bool:
        now = time.monotonic()
        key = (client, bucket)
        with self._lock:
            tokens, last = self._state.get(key, (burst, now))
            tokens = min(burst, tokens + (now - last) * rate_per_min / 60.0)
            if tokens < 1:
                self._state[key] = (tokens, now)
                return False
            self._state[key] = (tokens - 1, now)
            return True
