# iaglobal/tests/read_cache.py

import sqlite3
import cbor2

from iaglobal._paths import CACHE_DB
DB_PATH = str(CACHE_DB)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
SELECT task_hash, data
FROM success_registry
LIMIT 1
""")

row = cursor.fetchone()

if row:
    task_hash, blob = row

    payload = cbor2.loads(blob)

    print("\n=== TASK HASH ===")
    print(task_hash)

    print("\n=== PAYLOAD ===")
    print(payload)

else:
    print("Nenhum registro encontrado.")

conn.close()
