# iaglobal/memory/core.py

import sqlite3
import hashlib
import cbor2

from .._paths import CACHE_DB


DB_PATH = CACHE_DB


class MemoryCore:
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash TEXT UNIQUE,
            payload BLOB
        )
        """)

        conn.commit()
        conn.close()

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def save(self, prompt: str, response: str, **kwargs):

        payload = {"prompt": prompt, "response": response}
        if kwargs:
            payload["metadata"] = kwargs.get("metadata")

        encoded = cbor2.dumps(payload)
        h = self._hash(prompt)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
        INSERT OR REPLACE INTO memory_cache (hash, payload)
        VALUES (?, ?)
        """,
            (h, encoded),
        )

        conn.commit()
        conn.close()

    def load(self, prompt: str):

        h = self._hash(prompt)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
        SELECT payload FROM memory_cache
        WHERE hash = ?
        """,
            (h,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return cbor2.loads(row[0])


memory = MemoryCore()
