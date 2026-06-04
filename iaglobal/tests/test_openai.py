import asyncio
import json
import sqlite3
import hashlib
import datetime
import cbor2

from playwright.async_api import async_playwright

# Tenta importar o cbor2 para persistência estruturada nativa
try:
    import cbor2
except ImportError:
    print("⚠️ Módulo 'cbor2' não encontrado no venv. Instale com: pip install cbor2")
    cbor2 = None

async def run():
    async with async_playwright() as p:
        print("🚀 Iniciando navegador oculto (Chromium)...")
        browser = await p.chromium.launch(headless=True)
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo"
        )
        page = await context.new_page()

        print("🌐 Acessando a página do ChatGPT...")
        await page.goto("https://chatgpt.com", wait_until="networkidle", timeout=60000)
        await asyncio.sleep(5)

        try:
            # Inicializa a variável no escopo correto para evitar o erro de UnboundLocalError
            texto_anterior = ""

            print("🔍 Executando clique cego no centro da tela...")
            await page.mouse.click(720, 450)
            await asyncio.sleep(1)

            print("⚡ Forçando foco no container de prompt editável...")
            await page.locator('#prompt-textarea').first.focus(timeout=10000)
            
            print("⌨️ Digitando o prompt de forma simulada...")
            prompt_cmd = "Explique detalhadamente o conceito de Polimorfismo na Programação Orientada a Objetos"
            await page.keyboard.type(prompt_cmd, delay=45)
            
            print("🚀 Disparando o comando pelo teclado...")
            await page.keyboard.press("Enter")
            
            print("⏳ Aguardando a OpenAI inicializar a resposta...")
            # Seletor universal robusto que combina blocos de texto e nós de conversação da OpenAI
            seletor_resposta = '[data-testid^="conversation-turn"], div.markdown, article, .prose'
            
            try:
                await page.wait_for_selector(seletor_resposta, timeout=30000)
            except Exception:
                print("⚠️ Aviso: Tempo limite do seletor atingido. Tentando varredura profunda...")

            # Streaming Guard: Espera o streaming de texto terminar na interface
            print("✍️ Capturando o streaming de texto puro em tempo real...")
            estavel_count = 0
            
            for _ in range(30):  # Limite máximo de 60 segundos de monitoramento de escrita (30 x 2s)
                await asyncio.sleep(2)
                try:
                    elementos = page.locator(seletor_resposta)
                    count = await elementos.count()
                    
                    if count > 0:
                        texto_atual = await elementos.last.inner_text()
                    else:
                        # Fallback agressivo: captura o corpo inteiro se os seletores falharem
                        texto_atual = await page.evaluate("() => document.body.innerText")
                    
                    # Se o tamanho do texto parar de mudar por 2 iterações, a IA terminou de falar
                    if texto_atual == texto_anterior and len(texto_atual) > 0:
                        estavel_count += 1
                        if estavel_count >= 2:
                            break
                    else:
                        estavel_count = 0
                        texto_anterior = texto_atual
                except Exception:
                    continue

            # Exibe o log de Debug na posição correta (após o encerramento da captura do texto)
            print(f"📊 Debug: Tamanho do texto capturado: {len(texto_anterior)} caracteres.")

            print("\n✅ [TEXTO PURO CAPTURADO COM SUCESSO]:")
            print("="*60)
            print(texto_anterior.strip())
            print("="*60 + "\n")

            # 💾 SISTEMA DE APRENDIZADO EM TEMPO REAL: GERAÇÃO DE PAYLOAD E PERSISTÊNCIA EM CACHE
            if cbor2 and len(texto_anterior) > 10:
                print("📦 Convertendo payload bruto para o formato estruturado CBOR2...")
                
                # Monta a árvore de dicionário idêntica à consumida pela memória do iaglobal
                payload_dados = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "task": prompt_cmd,
                    "codigo": texto_anterior.strip()
                }
                
                # Serializa o dicionário em bytes binários compactados
                cbor_binary = cbor2.dumps(payload_dados)
                
                # Gera o hash SHA256 do prompt para indexação única (task_hash)
                task_hash = hashlib.sha256(prompt_cmd.encode('utf-8')).hexdigest()
                
                print("💾 Gravando dados serializados na tabela success_registry do cache.db...")
                from iaglobal._paths import CACHE_DB
                caminho_db = str(CACHE_DB)
                
                try:
                    conn = sqlite3.connect(caminho_db, timeout=10.0)
                    cursor = conn.cursor()
                    
                    # Garante que a tabela exista se rodar isoladamente
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS success_registry (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            task_hash TEXT UNIQUE,
                            data BLOB
                        )
                    """)
                    
                    # Insere os dados compactados substituindo duplicatas para atualizar o aprendizado
                    cursor.execute(
                        "INSERT OR REPLACE INTO success_registry (task_hash, data) VALUES (?, ?)",
                        (task_hash, sqlite3.Binary(cbor_binary))
                    )
                    conn.commit()
                    conn.close()
                    print("🎉 [APRENDIZADO CONCLUÍDO]: Resposta salva com sucesso no cérebro de curto prazo!")
                except Exception as db_err:
                    print(f"⚠️ Erro ao acessar o arquivo sqlite (.db): {db_err}")
            else:
                print("❌ Ignorando persistência: Texto muito curto ou biblioteca cbor2 ausente.")

        except Exception as e:
            print(f"❌ Ocorreu uma falha no procedimento: {e}")

if __name__ == "__main__":
    asyncio.run(run())
