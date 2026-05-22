# memory_vector.py

import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer
import os

# Configuração
BASE_DIR = os.path.expanduser("~/.ia-global/memory")
os.makedirs(BASE_DIR, exist_ok=True)
DB = os.path.join(BASE_DIR, "core.db")

model = SentenceTransformer("all-MiniLM-L6-v2")

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            content TEXT,
            embedding BLOB,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def store(text, mtype="fact"):
    conn = sqlite3.connect(DB)
    # Converta para float32 explicitamente antes de virar bytes
    vec = model.encode(text).astype(np.float32).tobytes()
    conn.execute("INSERT INTO memory (type, content, embedding) VALUES (?, ?, ?)", 
                 (mtype, text, vec))
    conn.commit()
    conn.close()

def search(query, top_k=5):
    qvec = model.encode(query).astype(np.float32)
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT content, embedding FROM memory").fetchall()
    conn.close()

    results = []
    for content, emb_blob in rows:
        v = np.frombuffer(emb_blob, dtype=np.float32)
        # Produto escalar (já que os vetores do SentenceTransformer são normalizados)
        score = np.dot(qvec, v) 
        results.append((score, content))
    
    return sorted(results, key=lambda x: x[0], reverse=True)[:top_k]

init_db()