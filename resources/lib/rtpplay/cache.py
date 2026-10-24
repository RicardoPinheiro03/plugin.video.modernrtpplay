"""Persistent key-value cache with expiry, so repeat visits cost no requests.

Kodi starts a fresh process for every navigation, so an in-memory cache would
never be hit. This one lives in an SQLite file shared by those processes.
Values are stored as JSON.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


class Cache:
    def __init__(self, path: str = ":memory:", clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        # Another Kodi process may be writing; wait for it rather than fail.
        self._db = sqlite3.connect(path, timeout=5)
        with self._db:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS cache"
                " (key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL NOT NULL)"
            )
            self._db.execute("DELETE FROM cache WHERE expires <= ?", (clock(),))

    def get(self, key: str) -> Optional[Any]:
        """The value stored under ``key``, or None if it is missing or expired."""
        try:
            row = self._db.execute(
                "SELECT value FROM cache WHERE key = ? AND expires > ?", (key, self._clock())
            ).fetchone()
        except sqlite3.Error as error:
            # The cache only saves requests; a broken one must not break the add-on.
            log.warning("Cache read failed: %s", error)
            return None
        if not row:
            return None
        try:
            return json.loads(row[0])
        except ValueError:
            log.warning("Ignoring a corrupt cache entry for %s", key)
            return None

    def set(self, key: str, value: Any, ttl: float) -> None:
        try:
            with self._db:
                self._db.execute(
                    "INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
                    (key, json.dumps(value), self._clock() + ttl),
                )
        except sqlite3.Error as error:
            log.warning("Cache write failed: %s", error)

    def close(self) -> None:
        self._db.close()
