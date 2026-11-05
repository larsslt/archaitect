"""Small persistent TTL cache (SQLite, zlib-compressed bodies) shared by all source adapters.

Why: parcel/land-use data change on the scale of weeks, the services are public and unmetered but not instant, and the
same parcel is clicked repeatedly. A hit makes a click essentially free; ``get_stale`` lets a source outage degrade to
the last good answer instead of a false "unknown".
"""
from __future__ import annotations
import hashlib
import os
import sqlite3
import threading
import time
import zlib
from pathlib import Path


def make_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode('utf-8'))
        h.update(b'\x00')
    return h.hexdigest()


class TtlCache:
    def __init__(self, path: str | os.PathLike | None = None, max_rows: int = 4000):
        self.path = str(path) if path else None
        self.max_rows = max_rows
        self._lock = threading.Lock()
        self._mem: dict[str, tuple[float, bytes]] = {}
        self._db: sqlite3.Connection | None = None
        if self.path:
            try:
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
                self._db = sqlite3.connect(self.path, check_same_thread=False, timeout=5)
                self._db.execute('CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, ts REAL NOT NULL, v BLOB NOT NULL)')
                self._db.commit()
            except sqlite3.Error:
                self._db = None  # cache is an optimisation, never a dependency

    def get(self, key: str, ttl: float, allow_stale: bool = False) -> bytes | None:
        now = time.time()
        with self._lock:
            row = self._mem.get(key)
            if row is None and self._db is not None:
                try:
                    r = self._db.execute('SELECT ts, v FROM c WHERE k=?', (key,)).fetchone()
                    if r:
                        row = (r[0], zlib.decompress(r[1]))
                        self._mem[key] = row
                except (sqlite3.Error, zlib.error):
                    row = None
        if row is None:
            return None
        ts, body = row
        if allow_stale or now - ts <= ttl:
            return body
        return None

    def put(self, key: str, body: bytes) -> None:
        now = time.time()
        with self._lock:
            self._mem[key] = (now, body)
            if len(self._mem) > 256:  # keep RAM small; SQLite holds the rest
                for k in sorted(self._mem, key=lambda x: self._mem[x][0])[:64]:
                    self._mem.pop(k, None)
            if self._db is not None:
                try:
                    self._db.execute('INSERT OR REPLACE INTO c (k, ts, v) VALUES (?,?,?)', (key, now, zlib.compress(body, 3)))
                    n = self._db.execute('SELECT COUNT(*) FROM c').fetchone()[0]
                    if n > self.max_rows:
                        self._db.execute('DELETE FROM c WHERE k IN (SELECT k FROM c ORDER BY ts LIMIT ?)', (n - self.max_rows,))
                    self._db.commit()
                except sqlite3.Error:
                    pass
