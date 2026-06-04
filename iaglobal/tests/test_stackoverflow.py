# iaglobal/tests/test_stackoverflow.py

# iaglobal/tests/test_stackoverflow.py

import os
import sqlite3
import hashlib
import datetime
import html
import re
import requests

try:
    import cbor2
except ImportError:
    cbor2 = None


def extrair_codigo(html_texto):
    """
    Extrai blocos <pre><code>...</code></pre> do HTML.
    """

    blocos = re.findall(
        r"<pre><code>(.*?)</code></pre>",
        html_texto,
        re.DOTALL
    )

    blocos_limpos = []

    for bloco in blocos:
        codigo = html.unescape(bloco)
        codigo = re.sub(r"<[^>]+>", "", codigo).strip()

        if len(codigo) > 40:
            blocos_limpos.append(codigo)

    return blocos_limpos


def run():
    prompt_cmd = "como criar um script em python para bloco genesis"
    question_id = 11227809

    print(
        f"🌐 Consultando StackOverflow API "
        f"(Question ID: {question_id})..."
    )

    url_resposta = (
        f"https://api.stackexchange.com/2.3/"
        f"questions/{question_id}/answers"
        f"?order=desc"
        f"&sort=votes"
        f"&site=stackoverflow"
        f"&filter=withbody"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(
            url_resposta,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        dados = response.json()

        respostas = dados.get("items", [])

        if not respostas:
            print("❌ Nenhuma resposta encontrada.")
            return

        # Prioriza resposta aceita
        melhor_resposta = next(
            (a for a in respostas if a.get("is_accepted")),
            respostas[0]
        )

        corpo_html = melhor_resposta.get("body", "")

        blocos = extrair_codigo(corpo_html)

        if blocos:
            codigo_puro = (
                "\n\n# --- Próximo Bloco de Código ---\n\n"
            ).join(blocos)
        else:
            codigo_puro = re.sub(
                r"<[^>]+>",
                "",
                html.unescape(corpo_html)
            ).strip()

        texto_final = (
            f"FONTE: StackOverflow "
            f"(Thread {question_id})\n\n"
            f"SCRIPT DE REFERÊNCIA:\n\n"
            f"{codigo_puro}"
        )

        print(
            f"📊 Debug: "
            f"{len(texto_final)} caracteres capturados."
        )

        if len(codigo_puro) <= 30:
            print("❌ Código muito curto.")
            return

        if not cbor2:
            print("⚠️ cbor2 não instalado.")
            print("Execute: pip install cbor2")
            return

        print("📦 Serializando payload em CBOR2...")

        timestamp_utc = (
            datetime.datetime.now(datetime.UTC)
            .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )

        payload = {
            "timestamp": timestamp_utc,
            "task": prompt_cmd,
            "codigo": texto_final
        }

        from iaglobal._paths import CACHE_DB
        db_path = str(CACHE_DB)

        os.makedirs(
            os.path.dirname(db_path),
            exist_ok=True
        )

        print("💾 Gravando registro no cache.db...")

        conn = sqlite3.connect(
            db_path,
            timeout=10.0
        )

        try:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS success_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_hash TEXT UNIQUE,
                    data BLOB
                )
            """)

            task_hash = hashlib.sha256(
                prompt_cmd.encode("utf-8")
            ).hexdigest()

            payload_cbor = cbor2.dumps(payload)

            cursor.execute(
                """
                INSERT OR REPLACE INTO success_registry
                (task_hash, data)
                VALUES (?, ?)
                """,
                (
                    task_hash,
                    sqlite3.Binary(payload_cbor)
                )
            )

            conn.commit()

        finally:
            conn.close()

        print(
            "🎉 [APRENDIZADO CONCLUÍDO] "
            "Dados armazenados com sucesso!"
        )

    except requests.exceptions.RequestException as e:
        print(f"❌ Erro HTTP/API: {e}")

    except sqlite3.Error as e:
        print(f"❌ Erro SQLite: {e}")

    except Exception as e:
        print(f"❌ Erro inesperado: {e}")


if __name__ == "__main__":
    run()
