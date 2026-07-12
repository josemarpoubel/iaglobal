# check_db.py

import sqlite3
import cbor2
from datetime import datetime

from iaglobal._paths import CACHE_DB

if __name__ == "__main__":
    conn = sqlite3.connect(CACHE_DB)
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, task_hash, data FROM success_registry ORDER BY id DESC")
        registros = cursor.fetchall()
        
        print(f"📊 Encontrados {len(registros)} registros no cache.\n")
        
        for reg in registros:
            id_reg, t_hash, blob = reg
            dados = cbor2.loads(blob)
            
            print(f"--- [ID: {id_reg}] ---")
            print(f"Tarefa: {dados.get('task')}")
            print(f"Modelo: {dados.get('modelo')}")
            print(f"Agente: {dados.get('agente')}")
            print(f"Iterações: {dados.get('iteracoes')}")
            print(f"Código: {dados.get('codigo', '')[:50]}...")
            print("-" * 30 + "\n")
            
    except Exception as e:
        print(f"Erro ao ler o banco: {e}")
    finally:
        conn.close()
