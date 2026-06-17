#!/usr/bin/env python3
"""Teste de eficiência CBOR2 + SQLite"""

import os
import sys
import time
import sqlite3
import cbor2
from pathlib import Path

# Add iaglobal to path
sys.path.insert(0, '/home/user/projeto-iaglobal')

from iaglobal._paths import DB_DIR, CBOR2_DIR

def test_cbor2_basic():
    """Teste básico de serialização CBOR2"""
    test_data = {
        "prompt": "crie uma calculadora em php com tema escuro",
        "response": "codigo gerado",
        "metadata": {"type": "code", "language": "php"}
    }
    
    # Teste serialização
    serialized = cbor2.dumps(test_data)
    print(f"✓ Serialização: {len(serialized)} bytes")
    
    # Teste deserialização
    deserialized = cbor2.loads(serialized)
    assert deserialized == test_data
    print(f"✓ Deserialização: OK")
    
    return True

def test_sqlite_cbor2_integration():
    """Teste de integração SQLite + CBOR2"""
    test_db = DB_DIR / "test_cbor2.db"
    
    # Cria tabela de teste
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_table (
            id INTEGER PRIMARY KEY,
            data BLOB
        )
    """)
    conn.commit()
    
    # Insere dados serializados
    test_payload = {"test": "data", "value": 12345}
    encoded = cbor2.dumps(test_payload)
    cursor.execute("INSERT INTO test_table (data) VALUES (?)", (encoded,))
    conn.commit()
    
    # Recupera e deserializa
    cursor.execute("SELECT data FROM test_table ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    retrieved = cbor2.loads(row[0])
    conn.close()
    
    # Limpa
    test_db.unlink(missing_ok=True)
    
    assert retrieved == test_payload
    print(f"✓ Integração SQLite+CBOR2: OK")
    return True

def test_cbor2_dir():
    """Verifica se diretório cbor2 existe e é gravável"""
    CBOR2_DIR.mkdir(parents=True, exist_ok=True)
    test_file = CBOR2_DIR / "test.cbor2"
    
    test_data = {"benchmark": "test", "timestamp": time.time()}
    with open(test_file, "wb") as f:
        cbor2.dump(test_data, f)
    
    with open(test_file, "rb") as f:
        loaded = cbor2.load(f)
    
    test_file.unlink()
    assert loaded == test_data
    print(f"✓ Diretório CBOR2 gravável: OK")
    return True

def benchmark_serialization():
    """Benchmark de performance CBOR2 vs JSON"""
    import json
    large_data = {"items": [{"id": i, "data": f"item_data_{i}"} for i in range(1000)]}
    
    # CBOR2
    start = time.perf_counter()
    for _ in range(100):
        cbor2.dumps(large_data)
    cbor2_time = time.perf_counter() - start
    
    # JSON
    start = time.perf_counter()
    for _ in range(100):
        json.dumps(large_data)
    json_time = time.perf_counter() - start
    
    print(f"⏱ CBOR2: {cbor2_time*10:.2f}ms | JSON: {json_time*10:.2f}ms")
    print(f"✓ CBOR2 é {'mais' if cbor2_time < json_time else 'menos'} eficiente")
    return True

if __name__ == "__main__":
    print("=== TESTE CBOR2 + SQLITE ===")
    print(f"DB_DIR: {DB_DIR}")
    print(f"CBOR2_DIR: {CBOR2_DIR}\n")
    
    tests = [
        ("básico", test_cbor2_basic),
        ("integração", test_sqlite_cbor2_integration),
        ("diretório", test_cbor2_dir),
        ("benchmark", benchmark_serialization),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            test_fn()
            results.append((name, "✓ PASS"))
        except Exception as e:
            print(f"✗ {name}: {e}")
            results.append((name, f"✗ FAIL: {e}"))
    
    print("\n=== RESULTADOS ===")
    for name, result in results:
        print(f"{name}: {result}")