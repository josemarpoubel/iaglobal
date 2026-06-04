import os
import sqlite3
import hashlib
import datetime
import wikipediaapi

try:
    import cbor2
except ImportError:
    cbor2 = None

def run():
    # 📝 PROMPT EVOLUÍDO E ALINHADO PARA GERAÇÃO DE CÓDIGO
    prompt_cmd = "como criar um script em python para bloco genesis"
    termo_busca = "Blockchain"
    
    print(f"🌐 Conectando à base técnica para a tarefa de código: '{prompt_cmd}'...")
    
    try:
        wiki = wikipediaapi.Wikipedia(
            user_agent="IA-Global-Learning-Bot/1.0 (user@debian-node01.local)",
            language="pt"
        )
        
        page = wiki.page(termo_busca)
        
        if page.exists():
            # Estrutura uma especificação técnica focada em desenvolvimento de software
            texto_estruturado = (
                f"ESPECIFICAÇÃO TÉCNICA PARA O SCRIPT PYTHON\n"
                f"Contexto: {page.title}\n\n"
                f"DIRETRIZES DE ENGENHARIA DO BLOCO GENESIS:\n"
                f"1. O bloco genesis deve possuir index = 0.\n"
                f"2. O campo 'previous_hash' deve conter uma string de inicialização (ex: '0'*64).\n"
                f"3. Deve conter cálculo de assinatura SHA-256 combinando indice, timestamp e dados.\n\n"
                f"REFERÊNCIA CONCEITUAL RECUPERADA:\n{page.summary}"
            )
            
            print(f"📊 Debug: Tamanho do payload de engenharia: {len(texto_estruturado)} caracteres.")

            if cbor2:
                print("📦 Serializando payload de desenvolvimento em CBOR2...")
                timestamp_utc = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                
                payload_dados = {
                    "timestamp": timestamp_utc,
                    "task": prompt_cmd, # Vincula ao prompt exato de escrita de script
                    "codigo": texto_estruturado
                }
                cbor_binary = cbor2.dumps(payload_dados)
                task_hash = hashlib.sha256(prompt_cmd.encode('utf-8')).hexdigest()
                
                base_dir = os.path.expanduser("~/projeto-iaglobal")
                from iaglobal._paths import CACHE_DB
                caminho_db = str(CACHE_DB)
                
                print(f"💾 Gravando novo registro de código no cache.db...")
                conn = sqlite3.connect(caminho_db, timeout=10.0)
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS success_registry (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_hash TEXT UNIQUE,
                        data BLOB
                    )
                """)
                cursor.execute(
                    "INSERT OR REPLACE INTO success_registry (task_hash, data) VALUES (?, ?)",
                    (task_hash, sqlite3.Binary(cbor_binary))
                )
                conn.commit()
                conn.close()
                print("🎉 [APRENDIZADO CONCLUÍDO]: Contexto de script injetado com sucesso na memória!")
        else:
            print("❌ Falha ao recuperar dados de referência.")

    except Exception as e:
        print(f"❌ Erro crítico: {e}")

if __name__ == "__main__":
    run()

