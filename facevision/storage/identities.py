"""Enrolled people and their encrypted face templates."""

from __future__ import annotations

import threading

import numpy as np

from ..security import Vault
from .db import Database, now_iso


class IdentityStore:
    def __init__(self, db: Database, vault: Vault):
        self.db = db
        self.vault = vault
        self._cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}  # model_id -> (embeddings, person_ids)
        self._lock = threading.Lock()
        self._generation = 0  # bumped on every change, so a gallery read that raced with a change is not cached

    def invalidate(self):
        with self._lock:
            self._generation += 1
            self._cache.clear()

    # ---------- people
    def create_person(self, name: str, consent_confirmed: bool, consent_note: str = "", external_id: str = "",
                      notes: str = "") -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError("Enter a name or identifier.")
        if not consent_confirmed:
            raise ValueError("Enrolment needs the person's informed consent. Confirm it to continue.")
        ts = now_iso()
        cur = self.db.execute(
            "INSERT INTO persons(name, external_id, notes, consent_confirmed, consent_note, consent_at, created_at, "
            "updated_at) VALUES(?,?,?,?,?,?,?,?)", (name[:200], external_id[:200], notes[:2000], 1, consent_note[:2000], ts, ts, ts))
        self.db.audit("person.created", f"id={cur.lastrowid}")
        return self.get_person(cur.lastrowid)

    def update_person(self, pid: int, **fields) -> dict:
        allowed = {k: v for k, v in fields.items() if k in {"name", "external_id", "notes", "consent_note"} and v is not None}
        if "name" in allowed and not str(allowed["name"]).strip():
            raise ValueError("Name cannot be empty.")
        if allowed:
            sets = ", ".join(f"{k}=?" for k in allowed)
            self.db.execute(f"UPDATE persons SET {sets}, updated_at=? WHERE id=?", (*allowed.values(), now_iso(), pid))
            self.db.audit("person.updated", f"id={pid}")
        return self.get_person(pid)

    def get_person(self, pid: int) -> dict:
        p = self.db.one("SELECT * FROM persons WHERE id=?", (pid,))
        if not p:
            raise KeyError(pid)
        p["templates"] = self.db.query(
            "SELECT id, model_id, quality, source, created_at FROM templates WHERE person_id=? ORDER BY id", (pid,))
        return p

    def list_persons(self) -> list[dict]:
        rows = self.db.query(
            "SELECT p.*, (SELECT COUNT(*) FROM templates t WHERE t.person_id=p.id) AS template_count, "
            "(SELECT GROUP_CONCAT(DISTINCT t.model_id) FROM templates t WHERE t.person_id=p.id) AS models "
            "FROM persons p ORDER BY p.name COLLATE NOCASE")
        for r in rows:
            r["models"] = (r["models"] or "").split(",") if r["models"] else []
        return rows

    def delete_person(self, pid: int) -> None:
        with self.db.transaction() as c:
            c.execute("DELETE FROM templates WHERE person_id=?", (pid,))
            n = c.execute("DELETE FROM persons WHERE id=?", (pid,)).rowcount
        if not n:
            raise KeyError(pid)
        self.db.audit("person.deleted", f"id={pid}")
        self.invalidate()
        self.db.vacuum()  # remove deleted template bytes from the database file

    def delete_all(self) -> int:
        n = self.db.one("SELECT COUNT(*) AS n FROM persons")["n"]
        with self.db.transaction() as c:
            c.execute("DELETE FROM templates")
            c.execute("DELETE FROM persons")
        self.db.audit("person.deleted_all", f"count={n}")
        self.invalidate()
        self.db.vacuum()
        return n

    # ---------- templates
    def add_template(self, pid: int, model_id: str, embedding: np.ndarray, quality: float | None, source: str) -> int:
        self.get_person(pid)
        emb = np.asarray(embedding, np.float32).ravel()
        nonce, ct = self.vault.encrypt(emb.tobytes(), f"{pid}:{model_id}".encode())
        cur = self.db.execute(
            "INSERT INTO templates(person_id, model_id, dim, nonce, ciphertext, quality, source, created_at) "
            "VALUES(?,?,?,?,?,?,?,?)", (pid, model_id, emb.size, nonce, ct, quality, source[:200], now_iso()))
        self.db.execute("UPDATE persons SET updated_at=? WHERE id=?", (now_iso(), pid))
        self.db.audit("template.added", f"person={pid} model={model_id}")
        self.invalidate()
        return cur.lastrowid

    def delete_template(self, pid: int, tid: int) -> None:
        n = self.db.execute("DELETE FROM templates WHERE id=? AND person_id=?", (tid, pid)).rowcount
        if not n:
            raise KeyError(tid)
        self.db.audit("template.deleted", f"person={pid} template={tid}")
        self.invalidate()
        self.db.vacuum()

    def gallery(self, model_id: str) -> tuple[np.ndarray, np.ndarray]:
        with self._lock:
            if model_id in self._cache:
                return self._cache[model_id]
            generation = self._generation
        rows = self.db.query("SELECT person_id, dim, nonce, ciphertext FROM templates WHERE model_id=?", (model_id,))
        embs, pids = [], []
        for r in rows:
            raw = self.vault.decrypt(bytes(r["nonce"]), bytes(r["ciphertext"]), f"{r['person_id']}:{model_id}".encode())
            embs.append(np.frombuffer(raw, np.float32))
            pids.append(r["person_id"])
        result = (np.stack(embs) if embs else np.zeros((0, 1), np.float32), np.array(pids, np.int64))
        with self._lock:
            if self._generation == generation:
                self._cache[model_id] = result
        return result

    def names(self) -> dict[int, str]:
        return {r["id"]: r["name"] for r in self.db.query("SELECT id, name FROM persons")}

    # ---------- matching
    def match(self, model_id: str, embedding: np.ndarray, threshold: float, margin: float = 0.05,
              exclude_person: int | None = None, top_k: int = 3) -> dict:
        embs, pids = self.gallery(model_id)
        if len(pids) == 0:
            return {"status": "no_gallery", "candidates": []}
        scores = embs @ np.asarray(embedding, np.float32)
        best: dict[int, float] = {}
        for pid, s in zip(pids.tolist(), scores.tolist()):
            if pid == exclude_person:
                continue
            if s > best.get(pid, -2.0):
                best[pid] = s
        if not best:
            return {"status": "no_gallery", "candidates": []}
        names = self.names()
        ranked = sorted(best.items(), key=lambda kv: -kv[1])[:top_k]
        cands = [{"person_id": pid, "name": names.get(pid, "?"), "similarity": round(float(s), 4)} for pid, s in ranked]
        top = cands[0]["similarity"]
        second = cands[1]["similarity"] if len(cands) > 1 else -1.0
        if top < threshold:
            status = "unknown"
        elif second >= threshold and top - second < margin:
            status = "ambiguous"
        else:
            status = "match"
        return {"status": status, "candidates": cands, "threshold": threshold, "margin": margin}
